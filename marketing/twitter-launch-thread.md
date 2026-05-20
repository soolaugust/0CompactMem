# Twitter/X launch package

Two artifacts:
1. **Single-tweet version** — for one-shot posting / quote-retweet bait
2. **Thread version (6 tweets)** — for max engagement when you're online

Each tweet ≤ 280 characters, hand-counted.

---

## Single-tweet version

> Most "LLM memory" libraries are vector stores in disguise.
>
> openMnemos takes a different angle: borrow the OS memory subsystem.
> Demand paging. kswapd eviction. mlock pinning. CRIU snapshots.
>
> Single SQLite file. MCP-native. Multi-agent shared. MIT.
>
> https://github.com/soolaugust/openMnemos

---

## Thread version (6 tweets)

### 1/6 — the hook

> Every new conversation with an AI agent starts from zero.
>
> Decisions, hard-won constraints, lessons learned — gone.
>
> Multi-agent setups have no shared state.
>
> This isn't a model limitation. It's a missing infrastructure layer.

### 2/6 — the wrong frame

> Most LLM "memory" libraries (mem0, Letta, Zep) treat memory as a *store*.
>
> Vector DB, sometimes a graph or temporal index. Optimize for "find similar."
>
> But cognition needs more: back-pressure under capacity, hard-pin a constraint,
> coherent multi-agent sharing.

### 3/6 — the right frame

> Operating systems solved this 40 years ago.
>
> RAM ↔ context window
> Disk ↔ knowledge base
> Demand paging ↔ on-demand retrieval
> kswapd ↔ capacity-aware eviction
> mlock ↔ pin a constraint, never evict
> CRIU ↔ session checkpoint
>
> Same problem. Same solutions transfer.

### 4/6 — what I built

> openMnemos: an OS-style memory layer for LLM agents.
>
> 🧠 demand-paging retrieval
> 🌊 kswapd watermarks + DAMON access tracking
> 📌 hard / soft pin (mlock semantics)
> 🤝 single SQLite file = multi-agent shared
> 🔌 MCP-native (Claude Code / Cursor / your agents)
> 🧪 3,500+ tests

### 5/6 — try it

> One-line install in Claude Code:
>
>     /install-plugin github:soolaugust/openMnemos
>
> Or:
>
>     git clone https://github.com/soolaugust/openMnemos
>     pip install -e .
>     python init/bootstrap.py
>
> v0.1.0 just shipped. MIT.

### 6/6 — the bet

> Agent memory becomes infrastructure in 2026, the way databases were in the 90s.
>
> The teams who get this right will steal from operating systems, not from
> search engines.
>
> Demand paging > top-K similar. Pinning > TTL. Watermarks > unbounded growth.
>
> https://github.com/soolaugust/openMnemos

---

## Posting tactics

- **Pin the thread** to your X profile after posting.
- **Post Tuesday 09:00-11:00 ET** (peak dev-Twitter window).
- **Reply to your own tweet 30 min later** with the v0.1.0 release link
  (https://github.com/soolaugust/openMnemos/releases/tag/v0.1.0) for a small
  algorithmic bump.
- **DM the thread to 3-5 people** in the LLM/agent space who might QT.
- **Cross-post to LinkedIn** in long-form (paste tweets 1+3+4 stitched
  together; LinkedIn dev audience eats this format).
- After Show HN goes up, **quote-tweet** your own thread with "now on HN: <link>"
  to bridge audiences.

## Hashtags (use sparingly — max 2)

Best signal-to-noise:
- `#LLM` — broad reach
- `#AIAgents` — niche but precise
- `#buildinpublic` — gets you community boosts

Avoid: `#AI` (too noisy), `#OpenSource` (too generic).

---

## Single-tweet alternates (for A/B'ing or reposting)

> Hot take: agent memory is an OS problem, not a search problem.
>
> openMnemos brings demand paging, kswapd eviction, and mlock pinning
> to LLM agents. Single SQLite file. MCP-native.
>
> https://github.com/soolaugust/openMnemos

> What if agent "memory" was modeled on the Linux memory subsystem?
>
> openMnemos: demand paging, watermark eviction, mlock pinning,
> multi-agent shared. v0.1.0 shipped today.
>
> https://github.com/soolaugust/openMnemos

> Stop building agent memory like a vector DB. Start building it like
> a kernel memory subsystem.
>
> openMnemos — MIT, MCP-native, single-file SQLite deploy.
>
> https://github.com/soolaugust/openMnemos
