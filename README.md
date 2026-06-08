# cue-skills

**[English](README.md) · [中文](README.zh-CN.md)**

Open-source agent skills published by [Cue](https://cuecue.cn) (sensedeal).

A **skill** is a portable instruction bundle that any AI agent ([Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills), Codex CLI, Gemini CLI, …) can load to gain a new capability — without modifying the agent itself. This repo collects the skills Cue maintains for public use.

## Skills in this repo

| Skill | Purpose | Status |
|---|---|---|
| [`cue-buddy/`](./cue-buddy) — **cue-buddy** | Lets business experts author, validate, test, tune, and pin-as-frequent [Cue](https://cuecue.cn) "buddy" research templates via natural conversation. No Python / API knowledge needed; the agent talks to the Cue production API on the user's behalf. | v0.2.0 |
| [`cue-research/`](./cue-research) — **cue-research** | Sibling to cue-buddy for *using* Cue from inside your AI agent: ask a question → skill matches ≤2 candidate buddies (or routes to free-form deep research via `/api/rewrite`) → you confirm credits → it runs in the background and retrieves the report via replay → on satisfaction you can distill a free-form run into a saved buddy via cue-buddy. Supports 仿写/mimic (imitate a reference URL or sample document's writing style). | v0.3.0 |

More skills will be added here as Cue's surface grows.

## What is Cue / What is a buddy

[Cue](https://cuecue.cn) is a **Deep Research Agent + Intelligence Sentinel** platform for high-precision finance and business workflows. It picks tools from 300+ professional data sources (A-share / HK / US equity disclosures, fund AMAC registries, business registries, court records, regulatory feeds, sell-side research, capital flow data), cross-validates findings across sources, and produces structured, source-cited reports in minutes instead of hours.

A **"buddy" (搭子)** is a research playbook for a specific scenario — corporate-credit pre-diligence, public-record compliance snapshot, quarterly earnings review, private-fund manager DD, etc. — defined once and reused by supplying the subject. The `cue-buddy` skill in this repo is what business experts use to author these playbooks conversationally.

> **Scope boundary**: Cue's tool surface covers public data sources only (equity disclosures / business registries / court records / regulatory filings / capital flows / etc.). Scenarios requiring private data (real AML on bank-internal transactions, medical diagnosis, internal accounting) are **not appropriate** as Cue buddies — the supervisor cannot route them and falls back to generic web search. `cue-buddy +author` flow calls `+capabilities` to cross-check each declared evidence source against the actual catalog before persisting a template.

See [`cue-buddy/README.md`](./cue-buddy/README.md) for the full skill walkthrough.

## Using a skill

`cue-buddy` is self-contained: an entrypoint `SKILL.md`, supporting `references/`, and stdlib-only `scripts/`. `cue-research` ships **no runtime scripts of its own** — it reuses cue-buddy's (`cue_api` / `sse_report`), so it must be installed **alongside `cue-buddy` as a sibling folder**.

**Claude Code**: copy the skill folder into `~/.claude/skills/` or reference it via `/use-skill <path>`. See per-skill README for exact installation. **For `cue-research`, install `cue-buddy` next to it** (same parent dir) so its shared scripts resolve.

**Other agents**: load `<skill>/SKILL.md` as a system instruction. The skill's scripts are stdlib-only Python where possible.

## Contributing

Bug reports and skill suggestions: [open an issue](https://github.com/sensedeal/cue-skills/issues).

Pull requests welcome. Each skill has its own hard-rules / validator; see the skill's README for contribution guidelines.

## License

MIT — see [LICENSE](./LICENSE). Skill content is free to use, modify, and redistribute.
