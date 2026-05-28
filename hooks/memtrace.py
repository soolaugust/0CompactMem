"""
memtrace.py — Memory operation tracing and failure attribution

Inspired by "MemTrace: Tracing and Attributing Errors in LLM Memory Systems"
(Deng et al., 2026, arXiv:2605.28732). Transforms memory operations into a
traceable execution graph for root-cause analysis of retrieval failures.

OS analogy: ftrace / perf — kernel tracing infrastructure that records syscall
paths, enabling post-hoc diagnosis of latency spikes or missed wakeups.

Usage:
    tracer = MemTracer(conn, project)
    tracer.trace_write(chunk_id, text, importance)
    tracer.trace_retrieve(query, results)
    tracer.trace_evict(chunk_id, reason)

    # When retrieval fails:
    diagnosis = tracer.diagnose_miss(query, expected_id)
    # Returns: {"root_cause": "evicted", "evicted_at": ..., "reason": ...}
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum


class TraceOp(str, Enum):
    WRITE = "write"
    RETRIEVE = "retrieve"
    EVICT = "evict"
    PIN = "pin"
    UNPIN = "unpin"


@dataclass
class TraceEntry:
    timestamp: str
    op: str
    chunk_id: str = ""
    query: str = ""
    details: dict = None

    def to_dict(self):
        d = asdict(self)
        if d["details"] is None:
            d["details"] = {}
        return d


class MemTracer:
    """Lightweight memory operation tracer with failure attribution."""

    def __init__(self, db_path: str = None, max_entries: int = 10000):
        if db_path is None:
            base = os.environ.get("MEMORY_OS_DIR", os.path.expanduser("~/.claude/memory-os"))
            db_path = os.path.join(base, "memtrace.db")

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.max_entries = max_entries
        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trace_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                op TEXT NOT NULL,
                chunk_id TEXT DEFAULT '',
                query TEXT DEFAULT '',
                details TEXT DEFAULT '{}'
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trace_chunk ON trace_log(chunk_id)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trace_op ON trace_log(op)
        """)
        self.conn.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log(self, op: TraceOp, chunk_id: str = "", query: str = "", details: dict = None):
        self.conn.execute(
            "INSERT INTO trace_log (timestamp, op, chunk_id, query, details) VALUES (?,?,?,?,?)",
            (self._now(), op.value, chunk_id, query, json.dumps(details or {}))
        )
        self.conn.commit()
        self._gc()

    def _gc(self):
        """Keep trace log bounded."""
        count = self.conn.execute("SELECT COUNT(*) FROM trace_log").fetchone()[0]
        if count > self.max_entries:
            self.conn.execute(
                f"DELETE FROM trace_log WHERE id IN (SELECT id FROM trace_log ORDER BY id LIMIT {count - self.max_entries})"
            )
            self.conn.commit()

    # ── Trace operations ──────────────────────────────────────────

    def trace_write(self, chunk_id: str, summary: str, importance: float = 0.5):
        self._log(TraceOp.WRITE, chunk_id=chunk_id, details={
            "summary": summary[:200], "importance": importance
        })

    def trace_retrieve(self, query: str, result_ids: list, scores: list = None):
        self._log(TraceOp.RETRIEVE, query=query, details={
            "result_ids": result_ids[:10],
            "scores": (scores or [])[:10],
            "result_count": len(result_ids)
        })

    def trace_evict(self, chunk_id: str, reason: str = "watermark"):
        self._log(TraceOp.EVICT, chunk_id=chunk_id, details={"reason": reason})

    def trace_pin(self, chunk_id: str, pin_type: str = "hard"):
        self._log(TraceOp.PIN, chunk_id=chunk_id, details={"pin_type": pin_type})

    def trace_unpin(self, chunk_id: str):
        self._log(TraceOp.UNPIN, chunk_id=chunk_id)

    # ── Diagnosis / Attribution ───────────────────────────────────

    def diagnose_miss(self, query: str, expected_chunk_id: str) -> dict:
        """
        Diagnose why a retrieval missed the expected chunk.

        Returns attribution with root cause:
          - "never_written": chunk was never stored
          - "evicted": chunk was evicted (shows when and why)
          - "query_mismatch": chunk exists but wasn't in results (BM25 didn't match)
          - "pinned_but_missed": chunk is pinned and exists but retrieval missed it
        """
        # Check if chunk was ever written
        write_entry = self.conn.execute(
            "SELECT * FROM trace_log WHERE op='write' AND chunk_id=? ORDER BY id DESC LIMIT 1",
            (expected_chunk_id,)
        ).fetchone()

        if not write_entry:
            return {
                "root_cause": "never_written",
                "chunk_id": expected_chunk_id,
                "query": query,
                "explanation": "Chunk was never written to the store."
            }

        # Check if chunk was evicted after write
        evict_entry = self.conn.execute(
            "SELECT * FROM trace_log WHERE op='evict' AND chunk_id=? AND id > ? ORDER BY id DESC LIMIT 1",
            (expected_chunk_id, write_entry["id"])
        ).fetchone()

        if evict_entry:
            details = json.loads(evict_entry["details"])
            return {
                "root_cause": "evicted",
                "chunk_id": expected_chunk_id,
                "query": query,
                "written_at": write_entry["timestamp"],
                "evicted_at": evict_entry["timestamp"],
                "eviction_reason": details.get("reason", "unknown"),
                "explanation": f"Chunk was evicted due to: {details.get('reason', 'unknown')}. "
                              f"Written at {write_entry['timestamp']}, evicted at {evict_entry['timestamp']}."
            }

        # Check if chunk was pinned
        pin_entry = self.conn.execute(
            "SELECT * FROM trace_log WHERE op='pin' AND chunk_id=? ORDER BY id DESC LIMIT 1",
            (expected_chunk_id,)
        ).fetchone()

        # Check recent retrieval attempts for this query
        recent_retrieve = self.conn.execute(
            "SELECT * FROM trace_log WHERE op='retrieve' AND query=? ORDER BY id DESC LIMIT 1",
            (query,)
        ).fetchone()

        if recent_retrieve:
            details = json.loads(recent_retrieve["details"])
            result_ids = details.get("result_ids", [])
            if expected_chunk_id in result_ids:
                return {
                    "root_cause": "found_in_results",
                    "chunk_id": expected_chunk_id,
                    "query": query,
                    "rank": result_ids.index(expected_chunk_id) + 1,
                    "explanation": "Chunk WAS in results — diagnosis unnecessary."
                }

        # Chunk exists, not evicted, but not retrieved → query mismatch
        write_details = json.loads(write_entry["details"])
        return {
            "root_cause": "query_mismatch",
            "chunk_id": expected_chunk_id,
            "query": query,
            "stored_summary": write_details.get("summary", ""),
            "is_pinned": pin_entry is not None,
            "explanation": f"Chunk exists in store (written at {write_entry['timestamp']}) "
                          f"but BM25/retrieval did not match query '{query}' to "
                          f"stored text '{write_details.get('summary', '')[:80]}'. "
                          f"This is a lexical mismatch — the query terms don't overlap with stored terms."
        }

    def get_chunk_history(self, chunk_id: str) -> list[dict]:
        """Get full lifecycle of a chunk: write → retrieve → pin → evict."""
        rows = self.conn.execute(
            "SELECT * FROM trace_log WHERE chunk_id=? ORDER BY id",
            (chunk_id,)
        ).fetchall()
        return [{"timestamp": r["timestamp"], "op": r["op"],
                 "details": json.loads(r["details"])} for r in rows]

    def get_retrieval_history(self, query: str = None, limit: int = 20) -> list[dict]:
        """Get recent retrieval attempts, optionally filtered by query."""
        if query:
            rows = self.conn.execute(
                "SELECT * FROM trace_log WHERE op='retrieve' AND query LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM trace_log WHERE op='retrieve' ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [{"timestamp": r["timestamp"], "query": r["query"],
                 "details": json.loads(r["details"])} for r in rows]

    def close(self):
        self.conn.close()
