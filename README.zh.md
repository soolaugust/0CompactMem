<div align="center">

# openMnemos

**为 LLM agent 设计的 OS 风格持久化记忆层。**

*Demand paging。kswapd 风格淘汰。mlock 级别钉死。多 agent 共享。*

[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/storage-SQLite%20WAL-lightgrey?logo=sqlite)](https://sqlite.org/)
[![Tests](https://img.shields.io/badge/tests-3500%2B%20passing-brightgreen)](#测试)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Discussions](https://img.shields.io/badge/讨论-GitHub-blue?logo=github)](https://github.com/soolaugust/openMnemos/discussions)

[English](./README.md) · [中文](./README.zh.md)

</div>

> **Claude Code 一行装：**
> ```
> /install-plugin github:soolaugust/openMnemos
> ```

---

## 问题

每次启动与 AI 助手的新对话，它都从零开始。所有决策、踩过的坑、架构约束——全部消失。你重新解释背景，模型重新犯同样的错。如果同时跑多个 agent，它们之间也无法共享彼此学到的任何东西。

这不是模型限制，而是**缺失的基础设施层**。

---

## 解决方案

openMnemos 把**操作系统内存管理哲学**搬给 AI 认知资源用。让 Linux 用有限 RAM 处理数百万进程的同一套原语，现在赋予 LLM agent 持久化、可检索、多 agent 共享的记忆。

| OS 概念 | openMnemos 对应 |
|---|---|
| RAM（工作区） | Context window — AI 当前能看到的内容 |
| 磁盘（持久存储） | 知识库 — 跨 session 存活的事实 |
| Demand paging（按需分页） | 按需检索 — 在合适的时刻取相关记忆 |
| `mlock` | Hard / soft pinning — 钉死一条不可被淘汰的约束 |
| kswapd 水位线 | 容量感知淘汰 — 压力下的可预测回收 |
| CRIU 检查点 / 恢复 | Session 快照 — 暂停与无缝恢复 |
| 进程调度 | 多 agent 协调 — 多个 agent 共享同一个知识库 |
| kworker 线程池 | 异步提取 — I/O 从关键路径卸载 |

---

## 与 mem0 / Letta / Zep 的差异

LLM agent 记忆层已经有不少方案。openMnemos 走的是一条根本不同的路线：**复用成熟的操作系统原语，而不是从零发明一套新机制。**

|                  | **openMnemos**           | mem0           | Letta (MemGPT) | Zep            |
|------------------|--------------------------|----------------|----------------|----------------|
| 设计隐喻         | OS 内存子系统            | 向量库         | Agent 运行时   | 时序知识图     |
| 多 agent 共享    | ✅ 原生单一存储          | ⚠️ 通过 API    | ✅             | ✅             |
| MCP 原生支持     | ✅ first-class           | ❌             | ❌             | ❌             |
| 单文件部署       | ✅ SQLite，无需服务      | ❌ 需服务      | ❌ 需服务      | ❌ 需服务      |
| 显式按需分页检索 | ✅                       | 隐式           | 隐式           | 隐式           |
| 淘汰策略         | ✅ kswapd 风格 + DAMON   | 仅 TTL         | 近因           | 近因 + 衰减    |
| Pin / mlock 语义 | ✅                       | ❌             | ❌             | ❌             |

> **一句话总结。** 如果你想要一个能 `pip install`、在笔记本上以 sidecar 运行、被多个 Claude Code / Cursor / 自定义 agent 共享、能用操作系统心智模型推理的记忆层，openMnemos 就是为此而生的。如果你需要托管云服务或完整 agent 运行时，请考虑上面的替代方案。

---

## 工作原理

```
用户输入
  → 系统检索相关记忆 → 注入上下文
  → AI 基于完整上下文响应
  → Session 结束 → 决策与洞察自动提取 → 持久化到 store.db
  → 下次 Session 启动 → 工作集自动恢复
```

整个流水线运行在 Claude Code hooks 内，零手动记忆管理。

---

## 快速开始

**一行装（推荐）。**

```
/install-plugin github:soolaugust/openMnemos
```

**手动安装。**

```bash
git clone https://github.com/soolaugust/openMnemos
cd openMnemos
pip install -e .
mkdir -p ~/.claude/memory-os
```

完整的 Claude Code hook 配置、守护进程管理、故障排查见 [`docs/SETUP.md`](./docs/SETUP.md)。

---

## 性能一瞥

| 指标 | 数值 |
|---|---|
| 检索延迟（P50，热路径） | **~0.1 ms**（比 54 ms 子进程基线快 540×）|
| Recall@3 提升 vs 基线 | **+147%** |
| 跨 session 召回率 | **94.2%** |
| 每次调用 token 成本 | 注入 ~44 tokens，**净 ROI +256 tokens**（节省的复述）|
| 测试套件 | 3500+ 用例覆盖检索/淘汰/MCP/隐私过滤 |

数据来自标准基准；复现脚本在 `benchmarks/` 下。

---

## 架构

三层：

1. **Hooks** — 位于 Claude Code 系统调用边界（`SessionStart` / `UserPromptSubmit` / `Stop` / `PostToolUse`），调用 store。
2. **Store** — 单个 SQLite 文件（WAL 模式）+ FTS5 全文索引，藏在统一 VFS 接口（`store.py` / `store_vfs.py` / `store_criu.py`）后。
3. **Daemons & IPC** — 常驻 retriever daemon（Unix socket）、异步 extractor pool（kworker 风格）、跨 agent 通知总线。

完整分层图、磁盘 schema、各子系统设计动因见 [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)。完整的 OS 与认知科学原语映射见 [`docs/DESIGN_PHILOSOPHY.md`](./docs/DESIGN_PHILOSOPHY.md)。

---

## 路线图

- **分布式 openMnemos** — cgroup 风格多 agent 配额、网络复制存储
- **自适应水位线** — 跟随 agent 行为观测自动调参的淘汰
- **arXiv preprint** — 与 mem0 / Letta / Zep 的正式对比评估
- **Per-chunk embedding 路由** — 代码与文本用不同的 embedding 模型

已经做完的（1051+ 次调参迭代，八轮主要能力升级）见 [`CHANGELOG.md`](./CHANGELOG.md)。沿途解决的具体痛点见 [`docs/PROBLEMS_SOLVED.md`](./docs/PROBLEMS_SOLVED.md)。

---

## 测试

```bash
# 稳定测试子集
python3 -m pytest tests/test_agent_team.py tests/test_chaos.py -q
```

覆盖：per-session 数据库隔离、并发写安全、跨 agent IPC 投递、extractor pool 队列语义、CRIU 检查点校验、goals progress 幂等性。

---

## 依赖

无 GPU。无外部 API。完全本地运行。

| 依赖 | 用途 |
|---|---|
| Python 3.12+ | 核心运行时 |
| SQLite（内置） | 存储 + FTS5 全文索引 |
| `nc`, `flock` | Daemon socket + 单实例启动 |

---

## 贡献

每个子系统都藏在干净的 VFS 接口背后，组件可独立测试。欢迎提 Issue、设计建议、PR——设计类问题去 [Discussions](https://github.com/soolaugust/openMnemos/discussions)，提 PR 前请先跑一下上面的稳定测试子集。

---

<div align="center">

*操作系统几十年前就解过的问题。同样的方案直接迁移。*

**[English](./README.md) · [中文](./README.zh.md)**

</div>
