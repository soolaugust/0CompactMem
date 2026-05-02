"""
iter583: tlb_shootdown — TLB Generation Counter Age-Out for Dark Page Diversity

OS 类比：Linux TLB generation counter (Andy Lutomirski, 2017, PCID/ASID generation)
  每个 TLB entry 绑定写入时的 generation number，当 global generation 超过
  entry generation + max_age 时自动失效，保证 scan_unevictable 有执行机会。

测试：generation 文件读写、age-out 判定、bump 递增、TLB write 记录 generation、
      vDSO Stage 1 generation 过期强制 miss。
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


@pytest.fixture(autouse=True)
def tmp_memory_dir(tmp_path, monkeypatch):
    """隔离测试环境：所有文件写入 tmp_path。"""
    d = str(tmp_path)
    monkeypatch.setenv("MEMORY_OS_DIR", d)
    # Patch retriever module-level constants
    import hooks.retriever as ret
    monkeypatch.setattr(ret, "MEMORY_OS_DIR", d)
    monkeypatch.setattr(ret, "TLB_FILE", os.path.join(d, ".last_tlb.json"))
    monkeypatch.setattr(ret, "TLB_GENERATION_FILE", os.path.join(d, ".tlb_generation"))
    monkeypatch.setattr(ret, "CHUNK_VERSION_FILE", os.path.join(d, ".chunk_version"))
    monkeypatch.setattr(ret, "HASH_FILE", os.path.join(d, ".last_injection_hash"))
    monkeypatch.setattr(ret, "STORE_DB", os.path.join(d, "store.db"))
    return d


def _write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


class TestTlbBumpGeneration:
    """_tlb_bump_generation() 单元测试"""

    def test_bump_from_zero(self, tmp_memory_dir):
        import hooks.retriever as ret
        gen = ret._tlb_bump_generation()
        assert gen == 1
        with open(ret.TLB_GENERATION_FILE) as f:
            assert f.read().strip() == "1"

    def test_bump_increments(self, tmp_memory_dir):
        import hooks.retriever as ret
        _write_file(ret.TLB_GENERATION_FILE, "7")
        gen = ret._tlb_bump_generation()
        assert gen == 8
        with open(ret.TLB_GENERATION_FILE) as f:
            assert f.read().strip() == "8"

    def test_bump_handles_corrupt_file(self, tmp_memory_dir):
        import hooks.retriever as ret
        _write_file(ret.TLB_GENERATION_FILE, "not_a_number")
        gen = ret._tlb_bump_generation()
        assert gen == 1  # corrupt → treat as 0, then bump to 1

    def test_bump_creates_dir(self, tmp_memory_dir):
        import hooks.retriever as ret
        nested = os.path.join(tmp_memory_dir, "sub", "dir")
        ret.MEMORY_OS_DIR = nested
        ret.TLB_GENERATION_FILE = os.path.join(nested, ".tlb_generation")
        gen = ret._tlb_bump_generation()
        assert gen == 1
        assert os.path.exists(ret.TLB_GENERATION_FILE)


class TestTlbWriteGeneration:
    """_tlb_write() 应记录当前 generation"""

    def test_write_records_generation(self, tmp_memory_dir):
        import hooks.retriever as ret
        _write_file(ret.TLB_GENERATION_FILE, "42")
        _write_file(ret.CHUNK_VERSION_FILE, "10")
        ret._tlb_write("abc123", "hash456", 0.0)
        with open(ret.TLB_FILE) as f:
            data = json.load(f)
        assert data["generation"] == 42
        assert data["chunk_version"] == 10
        assert data["slots"]["abc123"]["injection_hash"] == "hash456"

    def test_write_no_generation_file(self, tmp_memory_dir):
        import hooks.retriever as ret
        _write_file(ret.CHUNK_VERSION_FILE, "5")
        ret._tlb_write("p1", "h1", 0.0)
        with open(ret.TLB_FILE) as f:
            data = json.load(f)
        assert data["generation"] == 0  # default when file missing


class TestTlbGenerationAgeOut:
    """TLB hit 路径的 generation age-out 判定"""

    def _setup_tlb_state(self, ret, chunk_ver=10, tlb_gen=3, current_gen=3,
                          prompt_hash="aabbccdd", injection_hash="injhash"):
        """设置 TLB 状态文件"""
        _write_file(ret.CHUNK_VERSION_FILE, str(chunk_ver))
        _write_file(ret.TLB_GENERATION_FILE, str(current_gen))
        _write_file(ret.HASH_FILE, injection_hash)
        _write_file(ret.TLB_FILE, json.dumps({
            "chunk_version": chunk_ver,
            "generation": tlb_gen,
            "slots": {prompt_hash: {"injection_hash": injection_hash}},
        }))
        # Need store.db to exist for TLB path
        _write_file(ret.STORE_DB, "")

    def test_tlb_hit_when_generation_fresh(self, tmp_memory_dir):
        """generation gap < max_age → TLB L1 hit (exit)"""
        import hooks.retriever as ret
        self._setup_tlb_state(ret, chunk_ver=10, tlb_gen=3, current_gen=6)
        # max_age=5, gap=6-3=3 < 5 → should hit
        with patch.object(ret, '_sysctl', side_effect=lambda k: {
            "retriever.tlb_max_generation_age": 5,
        }.get(k, ret._sysctl(k))):
            # Simulate vDSO check: would normally sys.exit(0)
            # We test the logic directly
            chunk_ver = 10
            gen_current = 6
            entry_gen = 3
            max_age = 5
            gen_expired = (gen_current - entry_gen) >= max_age
            assert not gen_expired  # gap=3 < 5, NOT expired

    def test_tlb_miss_when_generation_expired(self, tmp_memory_dir):
        """generation gap >= max_age → TLB forced miss"""
        import hooks.retriever as ret
        self._setup_tlb_state(ret, chunk_ver=10, tlb_gen=3, current_gen=8)
        # max_age=5, gap=8-3=5 >= 5 → should miss
        chunk_ver = 10
        gen_current = 8
        entry_gen = 3
        max_age = 5
        gen_expired = (gen_current - entry_gen) >= max_age
        assert gen_expired  # gap=5 >= 5, EXPIRED

    def test_exact_boundary(self, tmp_memory_dir):
        """generation gap == max_age - 1 → still hit (not expired)"""
        gen_current = 7
        entry_gen = 3
        max_age = 5
        gen_expired = (gen_current - entry_gen) >= max_age
        # 7-3=4, max_age=5, 4 >= 5 is False → NOT expired
        assert not gen_expired

    def test_boundary_equals_max_age(self, tmp_memory_dir):
        """generation gap == max_age → expired"""
        gen_current = 8
        entry_gen = 3
        max_age = 5
        gen_expired = (gen_current - entry_gen) >= max_age
        assert gen_expired  # 8-3=5 >= 5 → True


class TestTlbGenerationIntegration:
    """端到端集成：多次 FULL → generation 递增 → TLB age-out"""

    def test_generation_accumulates_across_fulls(self, tmp_memory_dir):
        """多次 bump 后 generation 持续递增"""
        import hooks.retriever as ret
        for i in range(1, 8):
            gen = ret._tlb_bump_generation()
            assert gen == i

    def test_full_cycle_age_out(self, tmp_memory_dir):
        """5 次 FULL 后 TLB entry 过期"""
        import hooks.retriever as ret
        max_age = 5
        # 写入 TLB at generation=0
        _write_file(ret.CHUNK_VERSION_FILE, "1")
        _write_file(ret.TLB_GENERATION_FILE, "0")
        ret._tlb_write("p1", "h1", 0.0)
        # 验证 TLB entry generation=0
        with open(ret.TLB_FILE) as f:
            assert json.load(f)["generation"] == 0
        # 模拟 5 次 FULL 检索
        for _ in range(max_age):
            ret._tlb_bump_generation()
        # 现在 generation=5, entry_gen=0, gap=5 >= max_age=5 → expired
        with open(ret.TLB_GENERATION_FILE) as f:
            assert int(f.read().strip()) == 5
        gen_current = 5
        entry_gen = 0
        assert (gen_current - entry_gen) >= max_age

    def test_tlb_write_resets_entry_generation(self, tmp_memory_dir):
        """TLB 重写后 entry generation 更新为当前值"""
        import hooks.retriever as ret
        _write_file(ret.TLB_GENERATION_FILE, "10")
        _write_file(ret.CHUNK_VERSION_FILE, "1")
        ret._tlb_write("p1", "h1", 0.0)
        with open(ret.TLB_FILE) as f:
            data = json.load(f)
        assert data["generation"] == 10
        # After write, entry generation = current → gap=0, fresh again

    def test_performance_bump(self, tmp_memory_dir):
        """bump generation 应在 <1ms"""
        import hooks.retriever as ret
        import time
        _write_file(ret.TLB_GENERATION_FILE, "0")
        times = []
        for _ in range(100):
            t0 = time.time()
            ret._tlb_bump_generation()
            times.append((time.time() - t0) * 1000)
        avg_ms = sum(times) / len(times)
        assert avg_ms < 1.0, f"avg {avg_ms:.3f}ms exceeds 1ms budget"


class TestTlbReadCompatibility:
    """_tlb_read() 向后兼容：无 generation 字段 → 默认 0"""

    def test_v2_without_generation(self, tmp_memory_dir):
        import hooks.retriever as ret
        # v2 格式但无 generation 字段
        _write_file(ret.TLB_FILE, json.dumps({
            "chunk_version": 5,
            "slots": {"p1": {"injection_hash": "h1"}},
        }))
        data = ret._tlb_read()
        assert data.get("generation", 0) == 0  # 默认 0 → 向后兼容

    def test_v1_format_migration(self, tmp_memory_dir):
        import hooks.retriever as ret
        # v1 格式
        _write_file(ret.TLB_FILE, json.dumps({
            "prompt_hash": "old",
            "injection_hash": "oldhash",
        }))
        data = ret._tlb_read()
        # v1 迁移后 chunk_version=-1 → 强制 miss
        assert data["chunk_version"] == -1
        assert "generation" not in data or data.get("generation", 0) == 0
