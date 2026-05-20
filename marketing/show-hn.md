# Show HN package

Submission link: https://news.ycombinator.com/submit

## Title (80 chars max — HN auto-rejects longer)

Primary:

> Show HN: openMnemos – kernel-grade persistent memory for LLM agents

Backup (more catchy, less technical):

> Show HN: Memory for AI agents, modeled on the Linux memory subsystem

> Show HN: We built LLM memory by stealing kswapd, mlock, and demand paging

## URL

https://github.com/soolaugust/openMnemos

## First comment (post immediately after submitting; HN expects this)

> Hi HN — author here.
>
> openMnemos is a memory layer for LLM agents. The bet is that the right mental
> model for agent memory is the operating-system memory subsystem (RAM ↔ context,
> disk ↔ knowledge base, demand paging, kswapd-style eviction, mlock pinning,
> CRIU-style session checkpoints), not "another vector database."
>
> Concretely it ships as:
>
>   - A single SQLite file (WAL mode). No service to run.
>   - An MCP server, so Claude Code / Cursor / custom agents pick up
>     `memory_lookup`, `pin_memory`, `unpin_memory`, `memory_stats` as tools.
>   - Multi-agent: any process opening the file joins the same memory.
>   - Hard / soft pinning: hard pins survive every reclaim path.
>   - kswapd-style watermarks + DAMON-inspired access tracking for eviction.
>   - 3,500+ tests; ~1,050 internal tuning iterations.
>
> Why I built it: every new conversation with an AI assistant starts from zero,
> and multi-agent setups have no shared state. That's not a model limitation,
> it's a missing infrastructure layer. Treating "memory" like a search index
> only solves the easy half of the problem; the hard half is reclaiming under
> pressure and guaranteeing certain knowledge is never evicted. OS engineers
> solved that 30 years ago, and the algorithms transfer cleanly.
>
> Honest caveats:
>
>   - Single-laptop / single-server scale. Not a planet-scale vector DB.
>   - Not a managed cloud service. If you want SaaS, mem0/Zep cloud are good.
>   - Public release is v0.1.0; APIs may shift before v1.0.
>
> Happy to dig into eviction policy, SQLite-vs-vector-DB choices, multi-agent
> coherence, or the OS analogy itself. Roast away.

## Posting checklist

- [ ] Post Tuesday-Thursday, 09:00-11:00 ET (HN front page traffic peak)
- [ ] Verify GitHub repo is public, README is up-to-date, llms.txt is in
- [ ] Pre-warm: have 2-3 friends ready to upvote in the first 30 minutes
      (don't fake — this is just timing, not vote manipulation)
- [ ] Be online for 4 hours after posting to reply to every comment
- [ ] First comment posted within 60 seconds of submission
- [ ] Don't @mention anyone, don't link other social media in the post
- [ ] Set up a Twitter / X thread *before* posting; share the HN link there
      after the post settles for ~30 min
