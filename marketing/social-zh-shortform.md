# 中文社交平台 — 短版文案集

适用：X (中文圈)、微博、即刻、小红书短帖、知乎想法、V2EX、Telegram 频道。
长版博客在 `blog-zh-os-memory-for-agents.md`，这里只放 1-3 条卡片。

---

## A. 极简单条版（适合 X / 即刻 / V2EX 标题）

> AI agent 的"记忆"，主流方案都在做向量库。
>
> openMnemos 换个思路：把 Linux 内核的内存子系统搬过来。
> Demand paging、kswapd 淘汰、mlock 钉死、CRIU 快照。
>
> 一个 SQLite 文件，多 agent 共享，MCP 原生。MIT。
>
> https://github.com/soolaugust/openMnemos

---

## B. 钩子版（适合微博/小红书前置 hook 抓眼球）

> 跟你打赌一件事：2026 年 agent memory 会成为基础设施层，就像 90 年代的数据库。
>
> 而做对它的团队，会从操作系统偷思路，不是从搜索引擎。
>
> Demand paging > top-K 相似。Pin > TTL。水位线 > 无限增长。
>
> 我把这套思路写成了 openMnemos：
> https://github.com/soolaugust/openMnemos

---

## C. 痛点版（适合知乎想法 / 即刻 / 微信群）

> 你有没有发现：每次跟 AI 重开一个 session，它就像失忆一样？
>
> 上次告诉它的约束、踩过的坑、定下的口径——全部归零。
> 再开一个 agent 一起干活？两边互不知道对方学了啥。
>
> 这不是模型的问题，是缺了一层基础设施。
>
> 我搬了一套 OS 内存管理的范式做了 openMnemos。
> 单文件 SQLite、MCP 原生、多 agent 共享。
>
> /install-plugin github:soolaugust/openMnemos
>
> 仓库：https://github.com/soolaugust/openMnemos

---

## D. 技术细节版（适合 V2EX / 知乎正文 / Telegram 技术频道）

> openMnemos —— 给 LLM agent 用的 OS 风格持久记忆层
>
> 设计映射：
>   • 上下文窗口 ↔ RAM
>   • 知识库     ↔ 磁盘
>   • 按需检索   ↔ Demand paging
>   • 容量淘汰   ↔ kswapd 水位线
>   • 钉死约束   ↔ mlock（hard/soft 两档）
>   • Session 快照 ↔ CRIU
>   • 后台抽取   ↔ kworker pool
>   • 多 agent 共享 ↔ 同一份 SQLite，零同步协议
>
> v0.1.0 刚发，1051+ 内部迭代，3500+ 测试。MIT 协议。
>
> https://github.com/soolaugust/openMnemos

---

## E. 即刻 / 小红书 — 第一人称叙事版

> 做了个开源项目分享一下。
>
> 起因是我用 Claude Code 多 session 干活，每次新开都要重新解释一遍上下文，多个 agent 之间也没法共享笔记。市面上的 LLM 记忆库（mem0、Letta、Zep）大都是向量库套壳，解决"找相似"，但解决不了"硬约束不能丢"和"多 agent 共享"。
>
> 后来想通了：这就是操作系统四十年前解过的问题。RAM 和磁盘、按需分页、kswapd 淘汰、mlock 锁页、CRIU 快照——直接照搬。
>
> 项目叫 openMnemos，单文件 SQLite，MCP 原生，多 agent 共享。
>
> 一行装：`/install-plugin github:soolaugust/openMnemos`
>
> 仓库：https://github.com/soolaugust/openMnemos

---

## 投放节奏建议

| 平台 | 用哪条 | 时间 |
|------|--------|------|
| 微博 | B (钩子版) | 工作日 12:00 / 21:00 |
| 即刻 | E (叙事版) | 工作日 21:00-23:00（即刻活跃高峰）|
| 知乎想法 | C (痛点版) | 工作日 09:00-10:00 |
| V2EX | D (技术细节版) | 周二/三 09:00 |
| 小红书 | E (叙事版改成"个人副业项目"口吻) | 周末 20:00 |
| Telegram 中文技术频道 | A 或 D | 任意 |

---

## 标签

- 微博：#开源# #AI Agent# #LLM#
- 知乎话题：人工智能 / 大语言模型 / 开源软件
- 即刻：圈子 → AI 探索站 / 独立开发者俱乐部
- V2EX：节点 → `share` 或 `programmer`
- 小红书：标签 #AI #开源 #程序员日常 #副业项目

避免：#AI 大爆炸 / #ChatGPT（噪声大、流量不精准）。
