# cue-buddy

**[English](README.md) · [中文](README.zh-CN.md)**

> An AI-agent skill that lets business experts author, validate, test, and pin-as-frequent [Cue](https://cuecue.cn) "buddy" templates — without writing code.

> **Sibling skill:** [`cue-research`](../cue-research) — for *using* buddies (ask → match → confirm → run → optionally save as a buddy) from inside your AI agent. cue-buddy is the *author* tool; cue-research is the *use* tool.

## What is Cue / What is a buddy

[Cue](https://cuecue.cn) is a **Deep Research Agent + Intelligence Sentinel** platform built for high-precision finance and business workflows. Cue picks the right tools from **300+ professional data sources** — A-share / HK / US equity disclosures, fund AMAC registries, business registries, court records, regulatory feeds, sell-side research, capital flow data — cross-validates findings across sources, and produces structured, **source-cited** reports in minutes instead of hours. Every conclusion links back to its origin; nothing is fabricated.

A **"buddy" (搭子)** is your personal research companion in Cue. You define a scenario once — corporate-credit pre-diligence, public-record compliance snapshot, quarterly earnings review, wealth-management peer comparison, private-fund manager due diligence, etc. — and Cue **solidifies the research playbook** (what to fetch, how to cross-validate, what report shape to produce) into a reusable template. From then on you just supply the subject (entity name, focus topic) and the buddy runs the playbook end-to-end. Cue's product premise is *"turn satisfying research experiences into your AI companions"* (把满意经历沉淀成你身边的 AI 伙伴) — buddy templates are how that solidification happens.

## What this skill is

`cue-buddy` is a [skill](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills) that plugs into any AI agent (Claude Code, Codex CLI, Gemini CLI, OpenClaw, etc.) and turns natural conversation into Cue template authoring. Business experts (no Python, no API knowledge) talk to their agent in domain language; the agent drafts, validates, creates, tests, tunes, and pins the template as "frequent" (设为常用) via the Cue production API.

A buddy template is just **4 LLM-consumed fields**:
- **`input_form_spec`** — what inputs the user supplies (with a default fallback)
- **`goal`** — a concise, value-first one-paragraph intro (the buddy's card copy): what problem it solves / what value it delivers — no role-play preamble, no implementation detail, no hardcoded subject
- **`search_plan`** — research strategy clustered by data source
- **`report_format`** — the report skeleton (sections + per-section execution blueprints)

Once created, the buddy lives in the user's cuecue.cn template library and can run real research tasks (typically 3–8 积分 / credits per run; exact cost shown in the workbench). Mark it as "常用" (frequent) to pin it to the workbench home for quick access.

This skill makes the authoring loop self-serve for business users:

```
User: "我想做一个针对城商行客户经理的对公授信预尽调搭子"
Agent: [reads SKILL.md → triggers +author flow]
       → asks 4 groups of business questions
       → calls GET /api/tools/capabilities to inventory current Cue
         researcher surface (~391 tools / ~56 categories / 10 presets)
       → drafts the 4 fields via LLM, aligned to supported capability
         domains (category = supervisor routing label)
       → cross-checks each search_plan dimension against capabilities
         API; warns user if any declared evidence source has no
         backing category (some niche public-source dimensions may
         fall back to web_search)
       → runs +validate against 7 hard rules
       → on confirmation, POSTs to user's template library
       → optionally runs +test on a real case
       → on confirmation, +frequent to pin to workbench home
```

## Status

**v0.2.0** — cross-agent verified. The detailed write-up ([`docs/verification-reports/2026-05-20-gemini-cli.md`](./docs/verification-reports/2026-05-20-gemini-cli.md)) is the v0.1.0 Gemini CLI run that drove the `+test` long-stream replay-fallback hardening; Claude Code + Codex CLI were verified alongside it. **v0.2.0 itself has live cross-agent runs** (real tasks against the production API) on **Hermes, OpenClaw, and Kimi**, among others — see the report's **v0.2.0 status update** section.

## Who this is for

- **Domain experts**: finance / banking credit / asset management / private fund DD / regulatory compliance / corporate-strategy research / industry analyst
- Knows their scenario deeply but does not write Python and does not read API specs
- Has a Cue account (sign up at [cuecue.cn](https://cuecue.cn))
- Has an API key (create one at [cuecue.cn/api-key](https://cuecue.cn/api-key))

If you are a developer integrating Cue into a custom application, use the [Cue API docs](https://cuecue.cn) directly. This skill is opinionated for non-technical authoring.

## Quickstart

### 1. Install the skill in your agent

Clone this repo (or download the directory) and tell your agent to load it.

- **Claude Code**: place the directory under a configured skills path, or invoke `/skill cue-buddy` if your CLI version supports it
- **Codex CLI**: load the SKILL.md manually with `cat <path>/SKILL.md` and ask the agent to apply
- **Gemini CLI**: use `activate_skill` with the SKILL.md path
- **OpenClaw / others**: follow the agent's skill loading convention

### 2. Configure your API key (one-time)

Create a key at [https://cuecue.cn/api-key](https://cuecue.cn/api-key), then set it as an environment variable:

```bash
export CUE_API_KEY=sk...
```

Or write to `~/.cue/config.json`:

```json
{ "api_key": "sk...", "base": "https://cuecue.cn/api" }
```

Verify it works:

```bash
python3 scripts/cue_api.py whoami
```

### 3. Try it out

In your agent, just say what you want:

```
"我想做一个高风险主体公开合规快照搭子"
"design a buddy for earnings-call quick reviews"
"基于这份样例报告 ./report.pdf 做一个尽调搭子"
"测一下我刚才那个搭子，主体用万科"
```

The agent reads SKILL.md and dispatches the right verb (`+author`, `+test`, `+tune`, `+frequent`, etc.).

## What you can do

| Verb | Description | Costs credits? |
|---|---|---|
| `+author` | Guided Q&A drafting the 4 fields; calls `+capabilities` to align with Cue's actual tool surface and warns on uncovered evidence sources | No |
| `+capabilities` | List Cue researcher surface (~391 tools / ~56 categories / 10 presets); supports `q=<term>` / `category=<label>` probes; ETag-cached | No |
| `+validate` | Lint a template JSON against 7 hard rules, offline | No |
| `+create` | POST a validated template to your library | No |
| `+list` | List your templates | No |
| `+get` | Fetch one full template | No |
| `+update` | Modify an existing template | No |
| `+test` | Run a real research conversation, capture report, run 8 checks. A single deep-research run **typically takes 3–15 min** (longer for complex subjects); the server hard-times-out at **60 min**, so the client waits up to `--timeout` (default 3600s) and falls back to DB replay if the stream drops | **Yes** (~3–8 积分) |
| `+tune` | Let LLM revise the template based on your issue notes; diff preview + auto-backup before PUT | **Yes** (~1–3 积分) |
| `+frequent` | Mark template as "frequent" — pins it to your workbench home (`is_frequent=true`). This is *not* cross-user publishing; Cue has no such primitive. | No |
| `+unfrequent` | Unmark "frequent" — unpins from workbench home | No |

## Privacy

Reference materials you provide (sample reports, internal SOPs, monitor pages) **stay on your machine**. The skill extracts structure (chapter outline, source clusters, tone) for drafting but never uploads your originals to Cue.

See [`references/materials-intake.md`](references/materials-intake.md) for the detailed rules the agent follows when consuming your local files.

## Repo layout

```
cue-buddy/
├── SKILL.md                   # Skill spec read by the calling agent
├── scripts/
│   ├── cue_api.py             # Stdlib-only HTTP client (no deps)
│   ├── validate_template.py   # Offline 7-rule validator
│   ├── test_template.py       # Run real conversation + 8 parametric checks
│   └── tune_template.py       # Generate-revise + diff + confirm + backup + PUT
└── references/
    ├── template-fields-spec.md     # 4-field detailed format guide
    ├── hard-rules.md               # Validator rules R1-R8 with rationale
    ├── materials-intake.md         # How agent consumes user-provided local files
    └── examples/
        └── corporate-credit.md     # Full sample template (verified working)
```

## Dependencies

- Python 3.10+ (stdlib only — no `pip install` needed)
- An AI agent that supports skills

## License

[MIT](../LICENSE)

## Contributing

Issues and PRs welcome. Especially valuable:
- New `references/examples/<scenario>.md` covering domain templates not yet shipped (private-fund DD, public-record compliance snapshot, gov-procurement lead scan, policy-watch, sector-tracking, etc. — `corporate-credit.md` and `earnings-review.md` are already in the repo) — scope should align with Cue's actual tool surface (finance / 工商 / 司法 / 监管 / 资金流 / 行业研报 / 政府采购),avoid scenarios requiring private data (e.g. real AML on bank-internal transactions, medical diagnosis)
- Cross-agent verification reports (Codex / Gemini / OpenClaw)
- Hard-rule additions backed by failure-mode evidence
