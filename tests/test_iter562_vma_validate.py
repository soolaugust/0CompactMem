"""
iter562: vma_validate — 写入时最终准入校验测试。

OS 类比：Linux insert_vm_struct() (kernel/mm/mmap.c) — mmap 写路径最终关卡。
测试 _vma_validate() 对各类漏网碎片的拦截能力，以及对合法知识的放行。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from extractor import _vma_validate


class TestLineNumberPrefix:
    """V1: 行号前缀碎片（Read 工具输出泄漏）"""

    def test_basic_line_number(self):
        assert _vma_validate("1260:- 性能：sched_autogroup <0.3ms/call") is False

    def test_line_number_with_space(self):
        assert _vma_validate("547:  if text[0] in ('_', '|')") is False

    def test_line_number_chinese_colon(self):
        assert _vma_validate("42： 这是代码注释") is False

    def test_short_line_number(self):
        assert _vma_validate("3: import json") is False

    def test_not_line_number_starts_with_digit(self):
        # 合法：以数字开头但不是行号格式
        assert _vma_validate("3 个子系统合计 135ms 超预算，需要组级控制") is True

    def test_not_line_number_version(self):
        # 合法：版本号不是行号
        assert _vma_validate("v2.6.23 引入 CFS 调度器替代 O(1) scheduler") is True


class TestStatusReportPrefix:
    """V2: 状态/健康报告碎片（健康检查输出）"""

    def test_degraded_status(self):
        assert _vma_validate("⚠️ DEGRADED: 9/10 passed, 1 warning") is False

    def test_pass_status(self):
        assert _vma_validate("✅ PASS: all checks healthy") is False

    def test_fail_status(self):
        assert _vma_validate("❌ FAIL: FTS5 inconsistency detected") is False

    def test_warning_status(self):
        assert _vma_validate("⚠️ WARNING: zero access rate 39.8%") is False

    def test_emoji_in_design_constraint(self):
        # 合法：⚠️ 后面不是 status keyword
        assert _vma_validate("⚠️ 注意：Android RT 线程分析需要过滤 binder") is True


class TestMarkdownTableRow:
    """V3: Markdown 表格行碎片"""

    def test_basic_table_row(self):
        assert _vma_validate("| 测试 | 22/22 通过，0.69s |") is False

    def test_problem_table_row(self):
        assert _vma_validate("| 问题 | 单 chunk 垄断 53.6% 召回 |") is False

    def test_verification_table_row(self):
        assert _vma_validate("| 验证 | 13/13 新测试 + 95/95 回归全绿 |") is False

    def test_two_pipes(self):
        # 2 个 pipe 也应拦截（比之前 >=3 的阈值更严格）
        assert _vma_validate("| header | content") is False

    def test_pipe_in_content_is_ok(self):
        # 合法：内容中含单个 pipe 的不是表格行
        assert _vma_validate("cwnd 从 conservative|full 切换为 bypass 模式") is True


class TestLineReference:
    """V4: 行号引用前缀"""

    def test_line_reference(self):
        assert _vma_validate("line 547: 这里有一个 bug") is False

    def test_line_reference_uppercase(self):
        assert _vma_validate("Line 120: config 初始化") is False

    def test_l_prefix(self):
        assert _vma_validate("L1260: 性能瓶颈在这里") is False

    def test_chinese_line_ref(self):
        assert _vma_validate("第42行：这个变量未初始化") is False


class TestLegitimateContent:
    """合法内容应通过验证"""

    def test_decision(self):
        assert _vma_validate("选择 SQLite FTS5 替代 BM25 Python 实现，O(N)→O(log N)") is True

    def test_reasoning(self):
        assert _vma_validate("根因：writer(async) 持写锁导致 retriever 被阻塞 100-400ms") is True

    def test_quantitative(self):
        assert _vma_validate("PSI 从 FULL→SOME，stall_pct 从 90%→35%") is True

    def test_design_constraint(self):
        assert _vma_validate("Android RT 线程 L1 Sleep 分析约束：Binder IPC 等待需要过滤") is True

    def test_procedure(self):
        assert _vma_validate("飞书文档访问必须用 feishu CLI，禁止 mcp__fetch") is True

    def test_causal_chain(self):
        assert _vma_validate("冷启动保护机制：活跃 chunk 少于 5 个时跳过 place_entity") is True

    def test_too_short(self):
        assert _vma_validate("短文本") is False

    def test_empty(self):
        assert _vma_validate("") is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
