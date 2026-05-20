# Product Hunt launch package

Submission link: https://www.producthunt.com/posts/new

## Tagline (60 chars max)

Primary:

> Kernel-grade persistent memory for LLM agents

Backups:

> Memory for AI agents, modeled on the Linux kernel
> Persistent, shared memory layer for Claude Code & friends

## Topics (pick up to 4)

- Artificial Intelligence
- Developer Tools
- Open Source
- GitHub

## Description (260 chars max)

> openMnemos is a memory infrastructure layer for LLM agents. It applies
> operating-system memory management (demand paging, kswapd-style eviction,
> mlock pinning) to AI cognition. SQLite single-file deploy, MCP-native,
> multi-agent shared. MIT.

## First comment (Maker comment — post at launch)

> Hi PH 👋 — maker here.
>
> **Why I built this**: every new conversation with an AI assistant starts from
> zero. Decisions, pitfalls, hard-won constraints — gone. And if you run more
> than one agent (Claude Code + Cursor + your own scripts), they have *no way*
> to share what they've learned.
>
> Most "LLM memory" libraries are vector stores in disguise. They optimize for
> "find similar things." But cognition needs more: it needs back-pressure when
> capacity is full, a way to **pin a constraint** so it never gets evicted, and
> a coherent multi-agent sharing model.
>
> The OS world solved exactly these problems decades ago — demand paging,
> kswapd, mlock, kworker, CRIU. openMnemos borrows those primitives directly:
>
> - 🧠 **Demand paging** — `memory_lookup` is the explicit page-fault primitive
> - 🌊 **kswapd-style eviction** — watermarks, not arbitrary TTLs
> - 📌 **mlock pinning** — hard pins are *guaranteed* to survive every reclaim path
> - 🤝 **Multi-agent native** — open the SQLite file, you're in the same memory
> - 🔌 **MCP server** — works with Claude Code, Cursor, custom agents out of the box
> - 🧪 **3,500+ tests, 1,050+ tuning iterations** — eviction logic is the kind
>   of code that only fails in production, so test coverage isn't optional
>
> One-line install in Claude Code:
>
>     /install-plugin github:soolaugust/openMnemos
>
> Or pip install + bootstrap (README has the steps).
>
> **What it isn't**: a managed cloud service, a full agent runtime, or a
> planet-scale vector DB. It's the memory *layer*; pair it with whatever
> runtime you like.
>
> Repo: https://github.com/soolaugust/openMnemos
> Long-form blog post: [link to dev.to once published]
>
> Happy to dig into the OS analogy, eviction policy, SQLite-vs-vector-DB
> trade-offs, or the multi-agent coherence model. Roast away 🔥

## Hunter

If possible, find a hunter active in AI/dev-tools (more launches usually =
better front-page placement). If self-hunting, that's fine in 2026 too.

## Visuals checklist

- [ ] **Logo** — 240×240 PNG
- [ ] **Gallery image 1** — hero shot, the social-preview SVG converted to PNG
- [ ] **Gallery image 2** — animated GIF / static screenshot of `memory_lookup`
      in Claude Code returning results
- [ ] **Gallery image 3** — diagram: OS concept → openMnemos primitive
- [ ] **Optional video** — 30-60s screen recording of pinning a constraint and
      seeing it survive across sessions

## Launch-day timing

- **Post at 00:01 PT** (PH resets daily at 00:00 PT). Posts that go up first
  in the day have more time to accumulate upvotes.
- **Avoid Mondays and Fridays.** Tuesday/Wednesday are best.
- **Avoid major tech-news days** (Apple keynote, OpenAI launch, etc.) — your
  story gets buried.

## Engagement plan (first 24h)

- Reply to *every* comment within 30 minutes — PH ranks engagement.
- Don't ask friends to "vote." Do tell them you launched and link the post;
  they'll naturally upvote and that counts.
- Post a Twitter/X thread (3-4 tweets) with the PH link **2 hours after**
  launch — gives the post initial traction before Twitter amplifies.
- Cross-post to:
  - r/LocalLLaMA (after it's been on PH for a few hours)
  - r/ClaudeAI
  - Twitter/X (#buildinpublic, #LLM, #AIAgents)
- Update the README with a "Featured on Product Hunt" badge after launch.

## Post-launch artifacts

- A "Day 1 retro" tweet/blog with numbers (votes, signups, GH stars).
- Pin the PH link on the GH repo for a week.
- Add a `# Press` section to README listing the launch and any coverage.
