<div align="center">

# openMnemos

**OS-inspired persistent memory for LLM agents.**

*Demand paging. kswapd-style eviction. mlock-grade pinning. Multi-agent shared.*

[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/storage-SQLite%20WAL-lightgrey?logo=sqlite)](https://sqlite.org/)
[![Tests](https://img.shields.io/badge/tests-3500%2B%20passing-brightgreen)](#testing)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Discussions](https://img.shields.io/badge/discuss-on%20GitHub-blue?logo=github)](https://github.com/soolaugust/openMnemos/discussions)

[English](./README.md) · [中文](./README.zh.md)

</div>

> **One-line install via Claude Code:**
> ```
> /install-plugin github:soolaugust/openMnemos
> ```

---

## The problem

Every new conversation with an AI assistant starts from zero. Decisions, hard-won constraints, and architectural lessons all evaporate. You re-explain context. The model re-learns the same mistakes. And if you run several agents in parallel, they have no way to share what any of them have learned.

This isn't a model limitation. It's a missing infrastructure layer.

---

## The solution

openMnemos applies **operating-system memory-management philosophy** to AI cognitive resources. The same primitives that let Linux handle millions of processes with limited RAM now give LLM agents persistent, retrievable, multi-agent-shared memory.

| OS concept | openMnemos equivalent |
|---|---|
| RAM (working space) | Context window — what the AI sees right now |
| Disk (persistent storage) | Knowledge base — facts that survive across sessions |
| Demand paging | On-demand retrieval — fetch relevant memories at the right moment |
| `mlock` | Hard / soft pinning — guarantee a constraint is never evicted |
| kswapd watermarks | Capacity-aware eviction under pressure |
| CRIU checkpoint / restore | Session snapshots — pause and resume seamlessly |
| Process scheduling | Multi-agent coordination — many agents, one knowledge base |
| kworker thread pool | Async extraction — I/O off the critical path |

---

## How is this different from mem0 / Letta / Zep?

There are several memory layers for LLM agents already. openMnemos takes a fundamentally different angle: **it borrows mature operating-system primitives instead of inventing new ones from scratch.**

|                          | **openMnemos**           | mem0           | Letta (MemGPT) | Zep            |
|--------------------------|--------------------------|----------------|----------------|----------------|
| Design metaphor          | OS memory subsystem      | Vector store   | Agent runtime  | Temporal graph |
| Multi-agent shared       | ✅ native, single store  | ⚠️ via API     | ✅             | ✅             |
| MCP-native               | ✅ first-class           | ❌             | ❌             | ❌             |
| Single-file deploy       | ✅ SQLite, no service    | ❌ needs server| ❌ needs server| ❌ needs server|
| Demand-paging retrieval  | ✅ explicit              | implicit       | implicit       | implicit       |
| Eviction policy          | ✅ kswapd + DAMON        | TTL only       | recency        | recency + decay|
| Pin / mlock semantics    | ✅                       | ❌             | ❌             | ❌             |

> **TL;DR.** If you want a memory layer you can `pip install`, run as a sidecar on a laptop, share between several Claude Code / Cursor / custom agents, and reason about with operating-system mental models — openMnemos is built for that. If you want a managed cloud service or a full agent runtime, look at the alternatives above.

---

## How it works

```
You speak
  → System retrieves relevant memories → injects into context
  → AI responds with full context
  → Session ends → decisions and insights auto-extracted → persisted to store.db
  → Next session starts → working set restored automatically
```

The whole pipeline runs inside Claude Code hooks. There is no manual memory management.

---

## Quick start

**One-line install (recommended).**

```
/install-plugin github:soolaugust/openMnemos
```

**Manual install.**

```bash
git clone https://github.com/soolaugust/openMnemos
cd openMnemos
pip install -e .
mkdir -p ~/.claude/memory-os
```

Detailed Claude Code hook configuration, daemon management, and troubleshooting live in [`docs/SETUP.md`](./docs/SETUP.md).

---

## Performance at a glance

| Metric | Value |
|---|---|
| Retrieval latency (P50, hot path) | **~0.1 ms** (540× faster than the 54 ms subprocess baseline) |
| Recall@3 vs baseline | **+147%** |
| Cross-session recall | **94.2%** |
| Token cost per call | ~44 tokens injected, **+256 tokens net ROI** (avoided re-explanation) |
| Test suite | 3,500+ tests across retrieval, eviction, MCP, privacy filter |

Numbers were measured on the canonical benchmark; reproducibility scripts are in `benchmarks/`.

---

## Architecture

Three layers:

1. **Hooks** — sit at the Claude Code syscall boundary (`SessionStart`, `UserPromptSubmit`, `Stop`, `PostToolUse`) and call into the store.
2. **Store** — single SQLite file (WAL mode) with FTS5 full-text index, behind a unified VFS interface (`store.py` / `store_vfs.py` / `store_criu.py`).
3. **Daemons & IPC** — persistent retriever daemon (Unix socket), async extractor pool (kworker-style), cross-agent notify bus.

For the full layered diagram, on-disk schema, and the rationale behind each subsystem, see [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md). For the comprehensive OS-and-cognitive-science primitive mapping, see [`docs/DESIGN_PHILOSOPHY.md`](./docs/DESIGN_PHILOSOPHY.md).

---

## Roadmap

- **Distributed openMnemos** — cgroup-style multi-agent quotas, network-replicated stores
- **Adaptive watermarks** — eviction tuning that follows observed agent behavior
- **arXiv preprint** — formal evaluation against mem0 / Letta / Zep
- **Per-chunk embedding routing** — different models for code vs prose

What landed already (1,051+ tuning iterations, eight major capability rounds) is summarized in [`CHANGELOG.md`](./CHANGELOG.md). Pain points it has resolved along the way are in [`docs/PROBLEMS_SOLVED.md`](./docs/PROBLEMS_SOLVED.md).

---

## Testing

```bash
# stable test subset
python3 -m pytest tests/test_agent_team.py tests/test_chaos.py -q
```

Coverage: per-session DB isolation, concurrent-write safety, cross-agent IPC delivery, extractor-pool queue semantics, CRIU checkpoint validation, goals-progress idempotency.

---

## Dependencies

No GPU. No external API. Everything runs locally.

| Dependency | Purpose |
|---|---|
| Python 3.12+ | Core runtime |
| SQLite (built-in) | Store + FTS5 full-text index |
| `nc`, `flock` | Daemon socket + single-instance startup |

---

## Contributing

Each subsystem hides behind a clean VFS interface, so components are testable in isolation. Issues, design proposals, and pull requests are welcome — see the [Discussions tab](https://github.com/soolaugust/openMnemos/discussions) for design questions, and please run the test subset above before submitting a PR.

---

<div align="center">

*Same problem the OS solved decades ago. Same solutions transfer.*

**[English](./README.md) · [中文](./README.zh.md)**

</div>
