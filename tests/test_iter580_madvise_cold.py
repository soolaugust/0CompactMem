"""
iter580: madvise_cold — Cross-Session Injection Futility Detection
测试 chunk_recall_counts 统计范围从 injected=1 扩展到所有 trace。

验证项：
1. chunk_recall_counts 统计所有 trace 中的 chunk 出现次数（含 skipped_same_hash）
2. chunk_recall_counts_memcg 同样统计所有 trace
3. chunk_session_recall_counts 同样统计所有 trace
4. skipped_same_hash trace 中的 chunk 被正确计入 recall_count
5. top_k_json=NULL 的 trace 被正确跳过
6. bandwidth_throttle 和 cfs_bandwidth_throttle 对修正后的 recall_count 正确触发
7. 多 chunk top_k 中每个 chunk 被独立计数
8. 跨 session 统计正确累加
9. 回归：injected=1 的 trace 仍被正确统计
10. 空数据库返回空 dict
"""
import sqlite3
import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store_criu import (
    chunk_recall_counts,
    chunk_recall_counts_memcg,
    chunk_session_recall_counts,
)
from scorer import bandwidth_throttle, cfs_bandwidth_throttle


def _create_test_db():
    """创建内存测试 DB，含 recall_traces schema。"""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE recall_traces (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            session_id TEXT NOT NULL,
            project TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            candidates_count INTEGER,
            top_k_json TEXT,
            injected INTEGER DEFAULT 0,
            reason TEXT,
            duration_ms REAL DEFAULT 0,
            ftrace_json TEXT,
            user_feedback TEXT,
            feedback_ts TEXT,
            agent_id TEXT DEFAULT ''
        )
    """)
    return conn


def _insert_trace(conn, project="proj_a", session_id="sess_1",
                  top_k_json=None, injected=1, reason="hash_changed|full",
                  prompt_hash="abc123"):
    """插入一条 recall_trace。"""
    conn.execute(
        "INSERT INTO recall_traces (id, timestamp, session_id, project, "
        "prompt_hash, candidates_count, top_k_json, injected, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            datetime.now(timezone.utc).isoformat(),
            session_id,
            project,
            prompt_hash,
            10,
            json.dumps(top_k_json) if top_k_json is not None else None,
            injected,
            reason,
        )
    )
    conn.commit()


# ── Test 1: skipped_same_hash 的 trace 被正确计入 ──────────────────────────────
def test_skipped_same_hash_counted():
    """skipped_same_hash trace 中的 chunk 应被统计到 recall_count。"""
    conn = _create_test_db()
    chunk_a = "chunk-aaaa-1111"

    # 5 条 injected=1 trace
    for _ in range(5):
        _insert_trace(conn, top_k_json=[{"id": chunk_a, "score": 0.99}],
                      injected=1, reason="hash_changed|full")
    # 10 条 skipped_same_hash trace（injected=0）
    for _ in range(10):
        _insert_trace(conn, top_k_json=[{"id": chunk_a, "score": 0.99}],
                      injected=0, reason="skipped_same_hash")

    counts = chunk_recall_counts(conn, "proj_a", window=30)
    # 应统计全部 15 条（不只是 5 条 injected=1）
    assert counts.get(chunk_a) == 15, f"expected 15, got {counts.get(chunk_a)}"


# ── Test 2: top_k_json=NULL 的 trace 被跳过 ─────────────────────────────────────
def test_null_top_k_json_skipped():
    """top_k_json 为 NULL 的 trace 不应影响统计。"""
    conn = _create_test_db()
    chunk_a = "chunk-aaaa-2222"

    # 3 条有 top_k_json
    for _ in range(3):
        _insert_trace(conn, top_k_json=[{"id": chunk_a, "score": 0.5}], injected=1)
    # 5 条 top_k_json=NULL（早期 trace 格式或异常）
    for _ in range(5):
        _insert_trace(conn, top_k_json=None, injected=0, reason="error")

    counts = chunk_recall_counts(conn, "proj_a", window=30)
    assert counts.get(chunk_a) == 3


# ── Test 3: 多 chunk top_k 独立计数 ──────────────────────────────────────────────
def test_multi_chunk_independent_counting():
    """top_k 中的每个 chunk 独立计入各自的 recall_count。"""
    conn = _create_test_db()
    chunk_a = "chunk-aaaa"
    chunk_b = "chunk-bbbb"
    chunk_c = "chunk-cccc"

    # trace 1: A, B, C 都在
    _insert_trace(conn, top_k_json=[
        {"id": chunk_a, "score": 0.99},
        {"id": chunk_b, "score": 0.5},
        {"id": chunk_c, "score": 0.3},
    ], injected=1)
    # trace 2: 只有 A（skipped）
    _insert_trace(conn, top_k_json=[{"id": chunk_a, "score": 0.99}],
                  injected=0, reason="skipped_same_hash")
    # trace 3: A 和 B
    _insert_trace(conn, top_k_json=[
        {"id": chunk_a, "score": 0.99},
        {"id": chunk_b, "score": 0.4},
    ], injected=1)

    counts = chunk_recall_counts(conn, "proj_a", window=30)
    assert counts[chunk_a] == 3
    assert counts[chunk_b] == 2
    assert counts[chunk_c] == 1


# ── Test 4: bandwidth_throttle 对修正后的 count 正确触发 ──────────────────────────
def test_bandwidth_throttle_triggers_with_corrected_count():
    """修正后的 recall_count 超过 bw_max_pct 时 throttle 应触发。"""
    conn = _create_test_db()
    chunk_a = "chunk-monopoly"

    # 21/30 trace 包含该 chunk（70% > 30% threshold）
    for i in range(21):
        _insert_trace(conn, top_k_json=[{"id": chunk_a, "score": 0.99}],
                      injected=1 if i % 3 == 0 else 0,
                      reason="hash_changed|full" if i % 3 == 0 else "skipped_same_hash")
    # 9 条不含该 chunk
    for _ in range(9):
        _insert_trace(conn, top_k_json=[{"id": "other-chunk", "score": 0.5}],
                      injected=1)

    counts = chunk_recall_counts(conn, "proj_a", window=30)
    rc = counts.get(chunk_a, 0)
    assert rc == 21, f"expected 21, got {rc}"

    # bandwidth_throttle: 21/30=70% > 30% → 应触发
    bw = bandwidth_throttle(rc)
    assert bw < 1.0, f"bandwidth_throttle should trigger, got {bw}"

    # cfs_bandwidth_throttle: 21 > quota=8 → 应触发
    cbw = cfs_bandwidth_throttle(rc)
    assert cbw < 1.0, f"cfs_bandwidth should trigger, got {cbw}"


# ── Test 5: session_recall_counts 也统计 skipped trace ────────────────────────────
def test_session_recall_counts_includes_skipped():
    """chunk_session_recall_counts 应统计 session 内所有 trace。"""
    conn = _create_test_db()
    chunk_a = "chunk-session-test"
    sess = "session-xyz"

    # 3 条 injected + 4 条 skipped
    for _ in range(3):
        _insert_trace(conn, session_id=sess,
                      top_k_json=[{"id": chunk_a, "score": 0.8}],
                      injected=1)
    for _ in range(4):
        _insert_trace(conn, session_id=sess,
                      top_k_json=[{"id": chunk_a, "score": 0.8}],
                      injected=0, reason="skipped_same_hash")

    counts = chunk_session_recall_counts(conn, "proj_a", sess, window=100)
    assert counts.get(chunk_a) == 7, f"expected 7, got {counts.get(chunk_a)}"


# ── Test 6: memcg 跨项目统计也含 skipped ─────────────────────────────────────────
def test_memcg_includes_skipped():
    """chunk_recall_counts_memcg 应统计跨项目的所有 trace。"""
    conn = _create_test_db()
    global_chunk = "chunk-global"

    # proj_b 的 traces（对 proj_a 来说是跨项目）
    for _ in range(3):
        _insert_trace(conn, project="proj_b",
                      top_k_json=[{"id": global_chunk, "score": 0.9}],
                      injected=1)
    for _ in range(5):
        _insert_trace(conn, project="proj_b",
                      top_k_json=[{"id": global_chunk, "score": 0.9}],
                      injected=0, reason="skipped_same_hash")

    counts = chunk_recall_counts_memcg(conn, "proj_a", window=60)
    assert counts.get(global_chunk) == 8, f"expected 8, got {counts.get(global_chunk)}"


# ── Test 7: window 限制正确 ──────────────────────────────────────────────────────
def test_window_limit():
    """recall_count 应只统计最近 window 条 trace。"""
    conn = _create_test_db()
    chunk_a = "chunk-window"

    # 插入 50 条 trace（都含 chunk_a）
    for _ in range(50):
        _insert_trace(conn, top_k_json=[{"id": chunk_a, "score": 0.9}],
                      injected=0, reason="skipped_same_hash")

    # window=30 → 只统计最近 30 条
    counts = chunk_recall_counts(conn, "proj_a", window=30)
    assert counts[chunk_a] == 30, f"expected 30, got {counts[chunk_a]}"

    # window=10 → 只统计最近 10 条
    counts = chunk_recall_counts(conn, "proj_a", window=10)
    assert counts[chunk_a] == 10


# ── Test 8: 空数据库返回空 dict ──────────────────────────────────────────────────
def test_empty_db():
    """空数据库应返回空 dict。"""
    conn = _create_test_db()
    counts = chunk_recall_counts(conn, "proj_a", window=30)
    assert counts == {}


# ── Test 9: 回归 — injected=1 的 trace 仍被正确统计 ──────────────────────────────
def test_regression_injected_still_counted():
    """确保 injected=1 的 trace 没有被意外排除。"""
    conn = _create_test_db()
    chunk_a = "chunk-regression"

    for _ in range(5):
        _insert_trace(conn, top_k_json=[{"id": chunk_a, "score": 0.7}],
                      injected=1, reason="hash_changed|full")

    counts = chunk_recall_counts(conn, "proj_a", window=30)
    assert counts[chunk_a] == 5


# ── Test 10: 项目隔离 ──────────────────────────────────────────────────────────
def test_project_isolation():
    """chunk_recall_counts 应只统计指定项目的 trace。"""
    conn = _create_test_db()
    chunk_a = "chunk-isolation"

    # proj_a: 3 条
    for _ in range(3):
        _insert_trace(conn, project="proj_a",
                      top_k_json=[{"id": chunk_a, "score": 0.9}], injected=1)
    # proj_b: 7 条（不应被 proj_a 统计）
    for _ in range(7):
        _insert_trace(conn, project="proj_b",
                      top_k_json=[{"id": chunk_a, "score": 0.9}], injected=0,
                      reason="skipped_same_hash")

    counts_a = chunk_recall_counts(conn, "proj_a", window=30)
    counts_b = chunk_recall_counts(conn, "proj_b", window=30)
    assert counts_a[chunk_a] == 3
    assert counts_b[chunk_a] == 7


# ── Test 11: cfs_bandwidth 渐进衰减验证 ──────────────────────────────────────────
def test_cfs_bandwidth_progressive_decay():
    """随着 recall_count 增加，cfs_bandwidth_throttle 应渐进递减。"""
    # quota=8, factor=0.50, decay=0.85
    vals = [cfs_bandwidth_throttle(rc) for rc in [8, 9, 12, 15, 21]]
    assert vals[0] == 1.0  # 不超 quota
    assert vals[1] < 1.0   # 超 1
    assert vals[2] < vals[1]  # 递减
    assert vals[3] < vals[2]
    assert vals[4] < vals[3]
    assert all(v > 0 for v in vals)  # 永远 > 0


# ── Test 12: 生产场景模拟 — 固定模板 prompt 的垄断 chunk ───────────────────────────
def test_production_scenario_template_prompt_monopoly():
    """
    模拟生产环境：固定模板 prompt 导致同一 chunk 在 21/26 trace 中出现。
    修复前：只统计 injected=1 的 8 条 → recall_count=8 → 不 throttle
    修复后：统计全部 21 条 → recall_count=21 → 强力 throttle
    """
    conn = _create_test_db()
    monopoly_chunk = "chunk-feishu-constraint"

    # 模拟：8 条 injected=1，13 条 skipped_same_hash（都含该 chunk）
    for _ in range(8):
        _insert_trace(conn, top_k_json=[{"id": monopoly_chunk, "score": 0.99}],
                      injected=1, reason="hash_changed|full")
    for _ in range(13):
        _insert_trace(conn, top_k_json=[{"id": monopoly_chunk, "score": 0.99}],
                      injected=0, reason="skipped_same_hash")
    # 5 条不含该 chunk（其他 prompt_hash 的 trace）
    for _ in range(5):
        _insert_trace(conn, top_k_json=[{"id": "other-useful-chunk", "score": 0.5}],
                      injected=1, reason="hash_changed|full",
                      prompt_hash="other_hash")

    counts = chunk_recall_counts(conn, "proj_a", window=30)
    rc = counts[monopoly_chunk]

    # 验证统计正确
    assert rc == 21, f"expected 21, got {rc}"

    # 验证 throttle 生效
    bw = bandwidth_throttle(rc)
    cbw = cfs_bandwidth_throttle(rc)
    effective = min(bw, cbw)

    # 有效乘数应 < 0.10（强力削减）
    assert effective < 0.10, f"expected < 0.10, got {effective}"

    # 原始 score=0.99 被削减后 < 0.10
    original_score = 0.99
    throttled_score = original_score * effective
    assert throttled_score < 0.10, f"throttled score {throttled_score} too high"


# ── Test 13: session_id 为空时返回空 dict ────────────────────────────────────────
def test_session_recall_empty_session():
    """session_id 为空时 chunk_session_recall_counts 应返回空 dict。"""
    conn = _create_test_db()
    counts = chunk_session_recall_counts(conn, "proj_a", "", window=100)
    assert counts == {}


# ── Test 14: malformed JSON in top_k_json ────────────────────────────────────────
def test_malformed_json_handled():
    """top_k_json 包含非法 JSON 时不应崩溃。"""
    conn = _create_test_db()
    chunk_a = "chunk-valid"

    # 正常 trace
    _insert_trace(conn, top_k_json=[{"id": chunk_a, "score": 0.5}], injected=1)
    # 手动插入 malformed JSON
    conn.execute(
        "INSERT INTO recall_traces (id, timestamp, session_id, project, "
        "prompt_hash, top_k_json, injected) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(),
         "sess", "proj_a", "hash", "{invalid json", 1)
    )
    conn.commit()

    counts = chunk_recall_counts(conn, "proj_a", window=30)
    assert counts.get(chunk_a) == 1  # 只统计有效的那条


if __name__ == "__main__":
    import time
    tests = [
        test_skipped_same_hash_counted,
        test_null_top_k_json_skipped,
        test_multi_chunk_independent_counting,
        test_bandwidth_throttle_triggers_with_corrected_count,
        test_session_recall_counts_includes_skipped,
        test_memcg_includes_skipped,
        test_window_limit,
        test_empty_db,
        test_regression_injected_still_counted,
        test_project_isolation,
        test_cfs_bandwidth_progressive_decay,
        test_production_scenario_template_prompt_monopoly,
        test_session_recall_empty_session,
        test_malformed_json_handled,
    ]

    t0 = time.time()
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL {test.__name__}: {e}")

    elapsed = time.time() - t0
    print(f"\n{passed}/{passed+failed} passed ({elapsed:.2f}s)")
    if failed:
        sys.exit(1)
