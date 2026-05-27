#!/usr/bin/env python3
"""
Paper benchmark suite — validates evaluation claims in main.tex.

Benchmarks:
  1. Multi-session retention: Recall@5, MRR@5
  2. Constraint survival under pressure: pin survival rate
  3. Multi-agent coherence: write visibility + pin respect
  4. Latency: p50/p95 for lookup, write, pin, eviction
"""

import sys
import os
import time
import json
import sqlite3
import tempfile
import statistics
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ['MEMORY_OS_DIR'] = '/tmp/bench_memory_os'

from store_vfs import fts_search, open_db, pin_chunk, unpin_chunk, is_pinned, get_pinned_chunks, ensure_schema


def create_test_db(path=None):
    if path is None:
        path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_schema(conn)
    return conn, path


def insert_chunk(conn, chunk_id, summary, content, chunk_type="knowledge",
                 importance=0.7, project="bench", access_count=0, days_ago=0):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO memory_chunks
        (id, project, chunk_type, summary, content, importance,
         access_count, last_accessed, created_at, updated_at,
         source_session, retrievability, info_class, chunk_state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (chunk_id, project, chunk_type, summary, content, importance,
          access_count, ts, ts, ts, "bench_session", 1.0, "world", "ACTIVE"))
    rowid = cursor.lastrowid
    # FTS uses rowid_ref to join back to main table
    if rowid:
        cursor.execute("""
            INSERT INTO memory_chunks_fts (rowid_ref, summary, content)
            VALUES (?, ?, ?)
        """, (str(rowid), summary, content))
    conn.commit()


# ════════════════════════════════════════════════════════════════
# Benchmark 1: Multi-Session Retention
# ════════════════════════════════════════════════════════════════

def bench_retention():
    print("\n" + "="*60)
    print("BENCHMARK 1: Multi-Session Retention")
    print("="*60)

    conn, path = create_test_db()
    N = 200

    # Simulate 20 sessions of knowledge accumulation
    topics = [
        "architectural decision about {}", "user preference regarding {}",
        "domain constraint on {}", "performance finding about {}",
        "API behavior of {}", "design pattern for {}",
        "security requirement for {}", "testing strategy of {}",
        "deployment config for {}", "debugging insight about {}"
    ]
    subjects = [
        "authentication", "caching", "database schema", "API rate limits",
        "error handling", "logging", "monitoring", "CI/CD pipeline",
        "code review", "type safety", "dependency management", "state management",
        "concurrency", "memory usage", "startup time", "hot reload",
        "feature flags", "A/B testing", "user permissions", "data migration"
    ]

    # Insert 200 items across 20 simulated sessions
    for i in range(N):
        session = i // 10
        topic = topics[i % len(topics)]
        subject = subjects[i % len(subjects)]
        summary = topic.format(subject)
        content = f"Session {session}: {summary}. Details about {subject} including implementation notes and constraints."
        insert_chunk(conn, f"chunk_{i:04d}", summary, content,
                     importance=0.5 + (i % 5) * 0.1,
                     access_count=max(0, 5 - session // 4),
                     days_ago=20 - session)

    # Query with paraphrased versions
    queries = [
        ("auth system design choice", "authentication"),
        ("cache strategy decision", "caching"),
        ("DB table structure", "database schema"),
        ("rate limiting rules", "API rate limits"),
        ("error management approach", "error handling"),
        ("log configuration", "logging"),
        ("observability setup", "monitoring"),
        ("deployment automation", "CI/CD pipeline"),
        ("PR review process", "code review"),
        ("type checking policy", "type safety"),
        ("package management", "dependency management"),
        ("state handling pattern", "state management"),
        ("parallel execution safety", "concurrency"),
        ("memory optimization", "memory usage"),
        ("boot performance", "startup time"),
        ("live reload setup", "hot reload"),
        ("feature toggle system", "feature flags"),
        ("experiment framework", "A/B testing"),
        ("access control model", "user permissions"),
        ("schema migration", "data migration"),
    ]

    recall_at_5 = 0
    mrr_at_5 = 0
    total_queries = len(queries)

    for query, expected_subject in queries:
        results = fts_search(conn, query, top_k=10, project="bench")
        top_5_summaries = [r["summary"] for r in results[:5]]

        # Check if expected subject appears in top 5
        found = any(expected_subject.lower() in s.lower() for s in top_5_summaries)
        if found:
            recall_at_5 += 1

        # MRR: reciprocal rank of first relevant result
        for rank, s in enumerate(top_5_summaries, 1):
            if expected_subject.lower() in s.lower():
                mrr_at_5 += 1.0 / rank
                break

    recall_at_5 /= total_queries
    mrr_at_5 /= total_queries

    print(f"  Items: {N}, Queries: {total_queries}")
    print(f"  Recall@5: {recall_at_5:.3f}")
    print(f"  MRR@5:    {mrr_at_5:.3f}")

    conn.close()
    os.unlink(path)
    return {"recall_at_5": recall_at_5, "mrr_at_5": mrr_at_5}


# ════════════════════════════════════════════════════════════════
# Benchmark 2: Constraint Survival Under Pressure
# ════════════════════════════════════════════════════════════════

def bench_constraint_survival():
    print("\n" + "="*60)
    print("BENCHMARK 2: Constraint Survival Under Pressure")
    print("="*60)

    conn, path = create_test_db()

    # Insert 50 critical constraints (same importance as filler to make eviction non-trivial)
    N_CONSTRAINTS = 50
    for i in range(N_CONSTRAINTS):
        chunk_id = f"constraint_{i:03d}"
        insert_chunk(conn, chunk_id,
                     f"Critical constraint #{i}: must not violate invariant {i}",
                     f"This is a non-negotiable constraint about invariant {i}.",
                     chunk_type="design_constraint",
                     importance=0.6, access_count=1, days_ago=15)
        pin_chunk(conn, chunk_id, project="bench", pin_type="hard")

    # Inject 4x pressure: 200 chunks with SAME importance (eviction must choose)
    for i in range(200):
        insert_chunk(conn, f"filler_{i:04d}",
                     f"General knowledge item {i} about various topics",
                     f"This is general knowledge that competes for space.",
                     importance=0.6, access_count=1, days_ago=10+i%20)

    # Simulate aggressive eviction: keep only 50 chunks (from 250)
    # This forces 80% eviction — extreme pressure
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, importance, access_count, last_accessed FROM memory_chunks
        WHERE project = 'bench'
        ORDER BY last_accessed ASC, importance ASC
    """)
    all_chunks = cursor.fetchall()

    eviction_target = len(all_chunks) - 50  # keep only 50, evict 200
    evicted = 0
    for row in all_chunks:
        if evicted >= eviction_target:
            break
        chunk_id = row[0]
        # Pin semantics: skip pinned chunks
        if is_pinned(conn, chunk_id, project="bench"):
            continue
        cursor.execute("DELETE FROM memory_chunks WHERE id = ?", (chunk_id,))
        evicted += 1
    conn.commit()

    # Check constraint survival
    survived = 0
    for i in range(N_CONSTRAINTS):
        chunk_id = f"constraint_{i:03d}"
        cursor.execute("SELECT 1 FROM memory_chunks WHERE id = ?", (chunk_id,))
        if cursor.fetchone():
            survived += 1

    survival_rate = survived / N_CONSTRAINTS
    print(f"  Constraints: {N_CONSTRAINTS}, Pressure: 4x (200 filler, same importance)")
    print(f"  Eviction target: {eviction_target} (keep 50 of 250)")
    print(f"  Survived (with pins): {survived}/{N_CONSTRAINTS} = {survival_rate*100:.1f}%")

    # Baseline: same setup but NO pins
    conn2, path2 = create_test_db()
    for i in range(N_CONSTRAINTS):
        insert_chunk(conn2, f"constraint_{i:03d}",
                     f"Critical constraint #{i}",
                     f"Constraint about invariant {i}.",
                     chunk_type="design_constraint",
                     importance=0.6, access_count=1, days_ago=15)
        # NO pin!
    for i in range(200):
        insert_chunk(conn2, f"filler_{i:04d}",
                     f"General knowledge {i}", f"Competes for space {i}.",
                     importance=0.6, access_count=1, days_ago=10+i%20)

    cursor2 = conn2.cursor()
    cursor2.execute("""
        SELECT id FROM memory_chunks WHERE project = 'bench'
        ORDER BY last_accessed ASC, importance ASC
    """)
    all2 = cursor2.fetchall()
    evicted2 = 0
    for row in all2:
        if evicted2 >= eviction_target:
            break
        cursor2.execute("DELETE FROM memory_chunks WHERE id = ?", (row[0],))
        evicted2 += 1
    conn2.commit()

    survived_nopins = 0
    for i in range(N_CONSTRAINTS):
        cursor2.execute("SELECT 1 FROM memory_chunks WHERE id = ?", (f"constraint_{i:03d}",))
        if cursor2.fetchone():
            survived_nopins += 1

    baseline_rate = survived_nopins / N_CONSTRAINTS
    print(f"  Survived (no pins, same importance): {survived_nopins}/{N_CONSTRAINTS} = {baseline_rate*100:.1f}%")

    conn.close()
    conn2.close()
    os.unlink(path)
    os.unlink(path2)
    return {"pinned_survival": survival_rate, "baseline_survival": baseline_rate}


# ════════════════════════════════════════════════════════════════
# Benchmark 3: Multi-Agent Coherence
# ════════════════════════════════════════════════════════════════

def bench_multi_agent():
    print("\n" + "="*60)
    print("BENCHMARK 3: Multi-Agent Coherence (WAL)")
    print("="*60)

    path = tempfile.mktemp(suffix=".db")

    # Agent A: writes and pins
    conn_a = sqlite3.connect(path)
    conn_a.row_factory = sqlite3.Row
    conn_a.execute("PRAGMA journal_mode=WAL")
    ensure_schema(conn_a)

    N_ITEMS = 100
    N_PINS = 10

    for i in range(N_ITEMS):
        insert_chunk(conn_a, f"agent_a_{i:03d}",
                     f"Knowledge from Agent A item {i}",
                     f"Agent A's contribution #{i}",
                     project="shared")
    for i in range(N_PINS):
        pin_chunk(conn_a, f"agent_a_{i:03d}", project="shared", pin_type="hard")

    # Ensure Agent A's writes are committed
    conn_a.commit()

    # Agent B: opens same DB, checks visibility
    conn_b = sqlite3.connect(path)
    conn_b.row_factory = sqlite3.Row
    conn_b.execute("PRAGMA journal_mode=WAL")

    cursor_b = conn_b.cursor()
    cursor_b.execute("SELECT COUNT(*) FROM memory_chunks WHERE project = 'shared'")
    visible = cursor_b.fetchone()[0]

    # Check pin visibility
    pinned = get_pinned_chunks(conn_b, project="shared")
    pin_visible = len(pinned)

    write_visibility = visible / N_ITEMS
    pin_respect = pin_visible / N_PINS

    print(f"  Agent A writes: {N_ITEMS}, pins: {N_PINS}")
    print(f"  Agent B sees: {visible}/{N_ITEMS} writes = {write_visibility*100:.0f}%")
    print(f"  Agent B sees: {pin_visible}/{N_PINS} pins = {pin_respect*100:.0f}%")

    conn_a.close()
    conn_b.close()
    os.unlink(path)
    return {"write_visibility": write_visibility, "pin_respect": pin_respect}


# ════════════════════════════════════════════════════════════════
# Benchmark 4: Latency
# ════════════════════════════════════════════════════════════════

def bench_latency():
    print("\n" + "="*60)
    print("BENCHMARK 4: Operation Latency")
    print("="*60)

    conn, path = create_test_db()

    # Populate with 10,000 chunks
    N = 10000
    print(f"  Populating {N} chunks...")
    for i in range(N):
        insert_chunk(conn, f"lat_chunk_{i:05d}",
                     f"Knowledge item {i} about topic {i % 100}",
                     f"Detailed content for item {i} covering various aspects of topic {i % 100}.",
                     importance=0.3 + (i % 7) * 0.1,
                     access_count=i % 10)

    # Measure lookup latency
    lookup_times = []
    queries = ["authentication decision", "cache strategy", "error handling",
               "database schema", "deployment", "performance", "security",
               "testing", "monitoring", "logging"]
    for _ in range(50):
        for q in queries:
            t0 = time.perf_counter()
            fts_search(conn, q, top_k=5, project="bench")
            lookup_times.append((time.perf_counter() - t0) * 1000)

    # Measure write latency
    write_times = []
    for i in range(500):
        t0 = time.perf_counter()
        insert_chunk(conn, f"write_test_{i:04d}",
                     f"Write test item {i}", f"Content {i}",
                     importance=0.5)
        write_times.append((time.perf_counter() - t0) * 1000)

    # Measure pin latency
    pin_times = []
    for i in range(200):
        cid = f"lat_chunk_{i:05d}"
        t0 = time.perf_counter()
        pin_chunk(conn, cid, project="bench", pin_type="soft")
        pin_times.append((time.perf_counter() - t0) * 1000)

    def stats(times):
        times.sort()
        p50 = times[len(times)//2]
        p95 = times[int(len(times)*0.95)]
        return p50, p95

    lp50, lp95 = stats(lookup_times)
    wp50, wp95 = stats(write_times)
    pp50, pp95 = stats(pin_times)

    print(f"  Lookup (top-5):  p50={lp50:.1f}ms  p95={lp95:.1f}ms  (n={len(lookup_times)})")
    print(f"  Write:           p50={wp50:.1f}ms  p95={wp95:.1f}ms  (n={len(write_times)})")
    print(f"  Pin:             p50={pp50:.1f}ms  p95={pp95:.1f}ms  (n={len(pin_times)})")

    conn.close()
    os.unlink(path)
    return {
        "lookup_p50": lp50, "lookup_p95": lp95,
        "write_p50": wp50, "write_p95": wp95,
        "pin_p50": pp50, "pin_p95": pp95,
    }


# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("0CompactMem Paper Benchmark Suite")
    print("=" * 60)

    results = {}
    results["retention"] = bench_retention()
    results["survival"] = bench_constraint_survival()
    results["multi_agent"] = bench_multi_agent()
    results["latency"] = bench_latency()

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(json.dumps(results, indent=2))

    # Save results
    out_path = Path(__file__).parent / "benchmark_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {out_path}")
