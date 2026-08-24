---
name: cue-buddy
description: "Use when the user wants to author / validate / debug / test / tune / pin-as-frequent a Cue 搭子(buddy) research template for a recurring scenario (corporate-credit pre-diligence, compliance snapshot, earnings review, private-fund DD, etc.) via natural conversation. Triggers: 创建搭子 / 做一个 X 搭子 / 调试模板 / 测试我的搭子 / 提交模板 / 设为常用 / design a buddy for X / mark template as frequent. Public-data tool surface only — refuse for private-data scenarios (real AML / medical diagnosis / internal accounting)."
license: MIT
metadata:
  version: "0.3.6"
  requires:
    bins: ["python3"]
    envOptional: ["CUE_API_KEY", "CUE_API_BASE"]
  endpoints:
    base: "https://cuecue.cn/api"
    apiKeyPage: "https://cuecue.cn/api-key"
---

# cue-buddy — the buddy-template authoring tool

Lets business users **draft, validate, create, and debug** buddy templates inside their own AI agent, and submit them to their cuecue.cn template library. No code required — everything goes through the Cue production API.

> 中文版见 [`SKILL.zh-CN.md`](SKILL.zh-CN.md) — complete Chinese translation.

## What is Cue / What is a buddy

[Cue](https://cuecue.cn) is a **Deep Research Agent + Intelligence Sentinel** platform for complex finance and business workflows — the backend picks tools from **300+ professional data sources** (A-share / HK / US equity, funds, business registries, courts, regulatory feeds, sell-side research, capital flow …), cross-validates across sources, and attaches a **source link to every conclusion** — compressing "juggling ten websites for half a day" into minutes.

A **"buddy" (搭子)** is your reusable research companion in Cue: you solidify a *satisfying research path* into a template and **reuse it for the same class of scenario** (corporate-credit pre-diligence / public-record compliance snapshot / quarterly earnings review / wealth-management peer comparison / private-fund DD / sector-activity tracking / gov-procurement lead scan …). From then on you just supply the subject name or focus; the buddy gathers evidence per Cue's actual tool surface (A-share/HK/US equity / fund AMAC / business registry / courts / regulatory / capital flow / sell-side reports / procurement — all public data) and produces a structured report per the **report skeleton** you defined. Cue's product premise is *"turn satisfying research experiences into your AI companions"* — buddy templates are how that solidification happens.

> **Key mental model:** Cue's public buddy library already has **100+ ready-made buddies for common scenarios**, callable by any account — **a one-off, non-recurring research task does not need a buddy to be authored first** (just say "research X" on the [cuecue.cn](https://cuecue.cn) web side or via the sibling skill [`cue-research`](../cue-research)). **This skill (`cue-buddy`) is for "you have a class of scenario you do repeatedly and want to solidify into your own buddy"** — author once, reuse for a long time.

> **On first contact with a user, the agent must assume the user's library is NOT empty** (100+ system public buddies work for any account) — **never imply "+create is required before research can run"**; when unsure, call `search_templates(keyword="", include_system=True)` to see the real state.

> **Scope boundary (avoid stumbles when authoring a buddy):** Cue's tool surface covers **public data sources only**. Scenarios needing **private data** (real AML on bank-internal transaction flows / medical diagnosis on EHRs / tax diligence on internal ledgers) **are not suitable as Cue buddies** — the supervisor finds no matching tool in the catalog and falls back to web_search, losing Cue's research-companion value.
>
> **`+author`'s two-tier protection:**
> 1. **Hard refusal** — when the user explicitly names a **private-data** scenario ("AML", "medical diagnosis", "internal-ledger diligence"), the agent **refuses to draft** and suggests "Cue's public-data surface doesn't support this scenario; consider rewriting it as X (public regulatory + court + penalty data)" — the author either reshapes the scenario or backs off.
> 2. **Soft warn** — when a single `search_plan` dimension has no category backing (e.g. "industry-association public data" has no tool in the current catalog), the `+author` flow warns the user that dimension will fall back to web_search; creation may continue.

The product of this skill is the **4 fields** that define the research companion:

| Field | What it decides | ⚠️ Common misunderstanding |
|---|---|---|
| `title` | The buddy's **name on its card** | Concise and value-bearing (~≤8–10 chars); cut filler words (公开/全量/细项/与分析/简报/深度) but **don't over-simplify away distinguishing value** (keep 信披属实/需求匹配/海外执法 type qualifiers) |
| `input_form_spec` | **User input form spec** (required/optional variables + defaults) | One line: `需提供: [属性_主体_类型]，可提供: [属性_主体_类型] (默认: ...)`; the frontend renders `[...]` as input boxes. **Not** free-text prose |
| `goal` | The buddy intro = card copy: what problem it solves / what value it delivers | Concise, one paragraph (~40–80 chars, value-first); no "how it works", no implementation leaks, no hardcoded subjects, no disclaimers, no numbered lists |
| `search_plan` | Which data sources you gather evidence from, and the strategy | Cluster by **data source**, not by report-section order |
| `report_format` | What report you deliver (sections/blueprints) | Main heading must contain three-part variables; every section carries a `[执行蓝图]` block |

The backend consumes these 4 fields in order: collect input per `input_form_spec` → research/evidence per `search_plan` → produce the report per `report_format`; the whole output's tone is set by `goal`.

Free-form copy like "buddy description/intro" is only displayed as a one-liner on the frontend workbench category card — that is **auto-derived from `goal` by the backend**, so the author never writes it separately.

## Who you are, what you do

- **Target users**: non-technical people who know a business scenario deeply (finance / banking credit / asset management / private-fund DD / compliance research / industry consulting — any domain researchable via public data)
- **What you can do**: describe a scenario in natural language, **or feed the agent sample reports / industry SOPs / regulatory documents / related links from your work**, and this skill guides you into a spec-compliant 4-field template, submits it to your library, and runs a real task to verify it
- **What you don't need**: Python / API / BuddyContract and other technical concepts. This skill hides them; you only ever see business language
- **Privacy boundary**: your local materials stay in your agent's context and are **never uploaded to the Cue server** (see [`references/materials-intake.md`](references/materials-intake.md))

## Onboarding (instructions for the agent — what the first screen says)

**Forbidden**: do **not** show the full verb menu on the first screen (`+author / +list / +capabilities / +test / +tune ...`), and **do not** push `+capabilities` on its own — it is an internal developer verb a business user will never need.

**The first screen should say**:

1. **One warm greeting line** (recognize where they are).
2. **Intent split (2 choices, natural language, brief)**:
   > What would you like to do today?
   > 1. **You have a class of research scenario you do repeatedly** and want your own buddy (a few minutes; afterwards every such question runs through it) → I'll guide you
   > 2. **You just want to research a company/topic right now** (one-off) → use the sibling skill [`cue-research`](../cue-research) (enable it per your agent's loading convention), or go straight to the [cuecue.cn](https://cuecue.cn) web side; **no need to author a buddy first** — the 100+ system public buddies run for any account
3. **One quiet reminder line**: real tasks cost credits (roughly 3–8 积分 to start; always a confirmation before running); public data only (private-data scenarios like bank flows / medical records / internal ledgers are refused).
4. **Stop.** Wait for the user to answer. Do not stuff `+author` / `+ask` / the full verb list / detailed steps into the first screen.

**Optional shortcuts** (only when the user types them, don't advertise): if the user directly types `+author` or `+ask`, treat it as an explicit trigger and run the corresponding flow. **Natural-language routing is the default** (the decision tree below is your internal reference, not a user-facing menu).

**First-screen data safety**: the agent must not call any API that **consumes credits or writes** on the first screen. If the user's library state is needed (user asks "what buddies do I have"), call `search_templates(keyword="", include_system=True)` for the real state (free, read-only) — never assume an empty or non-empty library.

## Community invite (Cue user community)

At **high-intent moments**, invite the user to the「Cue 用户社群」(Q&A + newest buddy-template sharing), presenting the group QR per the trigger + cooldown rules in [`../community-invite.md`](../community-invite.md) — **restrained, one extra line, not every session**:

- **① First use**: one quiet line on the onboarding screen (one-time).
- **② After `+create` succeeds**: "Like it? Join the group for the latest templates" (14-day cooldown).
- **③ Stuck/error**: when `+validate` fails / permission errors / user confusion, **first help the user / give next steps**, then offer the group as a **gentle fallback** ("if you're still stuck, the group can help too") — not dumping the user into the group on every error (14-day cooldown).
- **④ User explicitly asks**: "how do I join the group / community / feedback / any new templates" → **show the QR image** (**no cooldown**).

**Passive triggers (①②③) get one line of text pointing to the QR image `../assets/community-group-qr.png` — no large image rendering; the large image is only shown on ④ (user-initiated).** The only join entry is the QR code (which encodes the group link) — **never print a plaintext group link**. Cooldown `${CUE_HOME:-$HOME/.cue}/last-community-invite.json` (passive triggers at most once per session, skipped if <14 days since last; read/write failure → no more invites this session). **External groups: Feishu users (incl. other tenants) can scan to join; only pure non-Feishu users cannot** — full rules and boundaries in [`../community-invite.md`](../community-invite.md).

## A "buddy" is 4 plain answers

| Question | Field name | Example |
|---|---|---|
| What input does the user give you? | `input_form_spec` | "需提供：[目标_授信_企业]，可提供：[关注_风险_主题] (默认：通用授信审查)" |
| Who are you, what pain do you solve? | `goal` | "作为银行客户经理的预尽调助手，从公开监管披露和司法记录穿透 [目标_授信_企业] 的偿债与合规风险..." |
| How do you research? (grouped by data source) | `search_plan` | 4 clusters — 主体核验 / 财务实证 / 行业景气 / 经营动态 — each with data routing + actions + validation strategy |
| What report shape do you deliver? | `report_format` | `> **关键配置**` header + 13 sections, each with a `> **[执行蓝图]**` block (research goal / logic chain / info needs / output form) |

Detailed field spec: [`references/template-fields-spec.md`](references/template-fields-spec.md). Rule hard-codes: [`references/hard-rules.md`](references/hard-rules.md).

## Setup: one-time API key

1. Open `https://cuecue.cn/api-key` (logged into your Cue account)
2. Create an API key (format `sk...`), copy it
3. Set it as an environment variable in your shell (once):

```bash
export CUE_API_KEY=sk...
```

Or write `~/.cue/config.json`:

```json
{ "api_key": "sk...", "base": "https://cuecue.cn/api" }
```

Optional: `export CUE_API_BASE=https://cuecue.cn/api` (overrides the default).

Before any verb call, the skill auto-checks the key's validity (requests `/api/templates`, a 200 passes).

## Invocation convention (verbs)

All operations are triggered via `+<verb>`. The skill executes through Python scripts in `scripts/` (stdlib only, no dependencies).

| Verb | What it does | Costs credits? | Backend endpoint |
|---|---|---|---|
| `+author` | Guided drafting of a new template: a few business questions → call `+capabilities` for the current Cue tool surface → agent LLM drafts the 4 fields against supported categories → cross-check every search_plan dimension against `+capabilities` for category backing (warn if none) → auto-run `+validate` | No (capabilities is read-only metadata, unbilled) | (local + `GET /api/tools/capabilities`) |
| `+capabilities` | Fetch the current Cue researcher surface (~391 tools / ~56 categories / 10 presets); supports `q=<term>` / `category=<label>` probes; ETag cache + 304 short-circuit; summary when no args | No | `GET /api/tools/capabilities` |
| `+validate <file>` | Offline-lint any template JSON file for compliance | No | (local) |
| `+create` | POST a validated template to your template library | No | `POST /api/templates` |
| `+list` | List all your templates | No | `GET /api/templates` |
| `+get <template_id>` | Fetch one full template | No | `GET /api/templates/<id>` |
| `+update <template_id>` | Modify an existing template | No | `PUT /api/templates/<id>` |
| `+test <template_id> <entity>` | Run one real conversation (e.g. test subject "万科"), capture the SSE stream, run 8 parametric checks. **A single deep-research run typically takes 3–15 min (longer for complex subjects); the server hard-times-out at 60 min** — the client should wait accordingly (`--timeout` default 3600s). On long runs the live SSE stream often drops before the reporter section reaches the client (timeout or network cut); the script then automatically falls back to DB replay to fetch the full report — **no double charge; this is normal, not an error** | **Yes** (roughly **3–8 积分** to start; exact cost in the workbench) | `POST /api/chat/stream` |
| `+tune <template_id> --issues <path>` | Let the LLM optimize the template from current content + an issue list (seed: bypass path), with diff preview and human confirmation | **Yes** (roughly **1–3 积分** to start) | `POST /api/generate_template` + `PUT /api/templates/<id>` |
| `+frequent <template_id>` | Mark the template "frequent" — pins it to the cuecue.cn workbench home "常用" area | No | `POST /api/templates/frequent` |
| `+unfrequent <template_id>` | Unmark "frequent" — removes it from the workbench home "常用" area | No | `POST /api/templates/frequent` (`is_frequent=false`) |
| `+upgrade` | Check and (after confirmation) upgrade the skill itself to the latest GitHub `main`. git-clone installs use `git pull --ff-only`; copy installs get manual instructions; abort without force-overwrite if there are local uncommitted changes. **Note: semantically completely different from `+update <template_id>` (editing a template)** | No | (GitHub raw + `git pull`, **local operation**) |

**All shipped verbs**: `+author / +capabilities / +validate / +create / +list / +get / +update / +test / +tune / +frequent / +unfrequent / +upgrade`.

**`+upgrade` and the session-start silent check**: when the agent loads this SKILL.md, **it should** silently run `python3 cue-buddy/scripts/update_skill.py --silent-check` before any verb. This is a lightweight version comparison with a 24h cooldown — when behind, it prints a single line to stderr `ℹ️ cue-skills/cue-buddy 有新版可用 vX → vY,运行 +upgrade 升级`, no dialog, no blocking, no auto-pull. Network failures are skipped silently (retried later). The cooldown timestamp lives in `~/.cue/last-update-check.json`.

**Why `+frequent` is not called `+publish`**: Cue currently has no "cross-user publishing" primitive; `+frequent` pins the template to the caller's own workbench home "常用" area (`is_frequent=true`) for high-frequency access. Early docs used `+publish`, which misled users into thinking it was public publishing — it has been renamed to `+frequent`. "Share externally" must go through the share/copy flow on the cuecue.cn web side.

## Decision tree (how the agent responds to the user)

Recognizes both Chinese and English; the examples below are typical phrasings — match semantics, not literal strings.

```
用户说什么（中/英文/口语）                                       → 调哪个 verb
──────────────────────────────────────────────────────────────────────────
"创建一个搭子" / "做一个 X 场景的搭子" / "我想做一个 X 助手"      → +author
"design a buddy for X" / "make me a buddy" / "I want to build"   → +author
"启动 X 场景搭子设计"                                            → +author

"我有个模板想检查格式" + 文件路径 / "lint this template"          → +validate
"建到我的模板库" / "保存"(after +author) / "save this" / "提交"   → +create
"看看我有哪些模板" / "list my buddies" / "我的模板"               → +list
"看下 tpl_xxx 的内容" / "show me tpl_xxx" / "fetch X"             → +get <id>
"改 tpl_xxx 的 input_form_spec" / "update <id>" / "改一下 X 字段"    → +update <id>

"跑一下 tpl_xxx 测试" / "测一下 X 主体" / "test with 万科" /
 "run a test on X" / "用 X 验证"                                  → +test
"自动优化 tpl_xxx" / "根据问题改一下" / "tune this" / "调优"      → +tune
"设为常用 tpl_xxx" / "钉到首页" / "mark frequent" / "pin to home"  → +frequent
"取消常用 tpl_xxx" / "从首页摘掉" / "unpin" / "unfrequent"         → +unfrequent

"升级 skill" / "更新 cue-skills" / "更新 cue-buddy" / "check for skill updates" / "拉一下最新版" → +upgrade
(注意:"改 tpl_xxx" / "更新模板 X" 等带 template_id 的语义走 `+update <id>`,**不是** `+upgrade`)
──────────────────────────────────────────────────────────────────────────
```

### Reference-doc routing (mechanical)

Different flow stages must read different references docs — never draft from memory:

| When | Must-read doc |
|---|---|
| `+author` Stage 0 — user provides materials | [`references/materials-intake.md`](references/materials-intake.md) |
| `+author` Stage 1-4 — drafting the 4 fields | [`references/template-fields-spec.md`](references/template-fields-spec.md) |
| `+validate` returns errors / user asks "why does it error" | [`references/hard-rules.md`](references/hard-rules.md) |
| `+author` first launch needs an example | [`references/examples/corporate-credit.md`](references/examples/corporate-credit.md) |

## `+author` flow (most used)

The agent guides the user through 4 groups of questions mapping to the 4 fields. Each question is asked in business language first, then the agent LLM drafts the field and immediately runs `+validate` for feedback.

### Stage 0: reference-material intake (strongly recommended)

Before the field questions, the agent asks the user:

> "Do you have any reference materials for this scenario? Options: a sample report (PDF/Word/Markdown/plain text), an industry SOP / internal spec / regulatory document, a similar competitor buddy description, or relevant links (company site / industry report / regulatory page).
>
> 1. I have a file, here's the path
> 2. I have a link, I'll paste it
> 3. I'll paste text directly
> 4. No, draft directly (from the scenario description)"

(1/2/3 can combine — e.g. paste a link, then add text.)

The agent reads with `Read` / `WebFetch` and uses the materials **only in the local agent context** — never uploaded to the Cue API, never written into any `+create / +update` payload, never committed to git.

Extract from the materials:
- Section structure → reverse into the `report_format` ~13-section skeleton
- Field definitions / industry terms → calibrate wording of `goal` and `search_plan`
- Data-source naming → calibrate `search_plan`'s data-routing clusters
- Report tone (restrained vs strong opinion / long vs short) → write into `关键配置 · 基调设定`

Specific extraction rules: [`references/materials-intake.md`](references/materials-intake.md).

### Stage 1-4: guided drafting of the 4 fields

1. **Scenario and role**
   - Who is your target user? (e.g. banking credit desk, sell-side research, private-fund DD, public-record compliance snapshot, gov-procurement lead analysis)
   - What specific pain does this buddy solve for them?
   - Which starting point?
     > 1. Reference an existing example (`references/examples/corporate-credit.md` is finance pre-diligence — copy-trim it for corporate-credit)
     > 2. From scratch (I describe the scenario, you draft)
     > 3. I describe the scenario first; you recommend the best-matching example from `references/examples/`
   → Draft `goal` + `title` + category

2. **Input definition**
   - What is required from the user? (e.g. company name / case number / industry keyword)
   - What is optional? (e.g. time window / focus)
   - Name the required variable in three parts: `[属性_主体_类型]` (the skill names it for you)
   → Draft `input_form_spec`

3. **Research strategy**
   - Which **public data sources** does your buddy gather evidence from? (public disclosures / court databases / industry reports / news sentiment …)
   - Cluster the sources into 2–5 research dimensions by "one pull serving multiple info types"
   - ⚠️ **Local materials** (the user's sample reports / internal specs / regulatory documents) are reference only for the template's **structure** — they are **not data sources Cue can fetch at runtime**, so never write them into `search_plan`'s "data routing"
   - Per dimension: which report sections it feeds / how to execute / how to validate multi-source conflicts
   → Draft `search_plan`

4. **Output shape**
   - How many sections does the report have? What problem does each solve?
   - What decision basis should the reader have after each section?
   - What order? (conclusion-first / timeline / risk level …)
   → Draft `report_format`, each section with a `[执行蓝图]` block

After each drafting step, run `+validate` immediately; fix any rule violation on the spot.

## Hard rules (violations are rejected by `+validate`)

Full version: [`references/hard-rules.md`](references/hard-rules.md). The 5 most important:

1. **`input_form_spec` must use three-part variables** — `需提供: [属性_主体_类型]，可提供: [属性_主体_类型] (默认: ...)` in one line
2. **`goal` must be concise, forceful, value-first** (it IS the card copy) — one ~40–80-char paragraph about the problem it solves / the value it delivers; no "how it works" (that goes in search_plan), no implementation leaks, no hardcoded subjects, no disclaimers, no numbered lists (see hard-rules R2)
3. **`search_plan` must cluster by "data source"** — not linear by section order
4. **`report_format` main heading must contain variables** — `# [目标_<场景>_主体] <场景>底稿`, never a hardcoded string
5. **No tool names in any field** (`get_*` / `list_*` / `find_*` prefixes etc.), and no decision phrasing like "建议进入/谨慎进入/暂缓进入" — a buddy is an evidence collector, not a decision maker

## Example templates

- [`references/examples/corporate-credit.md`](references/examples/corporate-credit.md) — corporate-credit pre-diligence (finance/banking scenario)
- [`references/examples/earnings-review.md`](references/examples/earnings-review.md) — quarterly earnings review (secondary-market research scenario)
- Coming next: public-record compliance snapshot, market-movement flash, gov-procurement leads, etc.

## Security rules

- The API key must never appear in text output / committed code / logs
- **If the user accidentally pastes an `sk...` key into chat**: immediately tell them (1) don't send it again, (2) rotate the key at cuecue.cn/api-key right away (the previous one must be revoked). The agent must never repeat or print that string in later conversation
- **User-provided local materials stay in the agent context only** — never uploaded to the Cue API, never written into `create / update` payloads, never committed to git
  - "Materials" is defined in [`references/materials-intake.md`](references/materials-intake.md) → "材料 的明确定义" section
  - If materials contain sensitive fields (client names / internal amounts / internal-control rules), after extracting the structure explicitly tell the user "used for template drafting; the original was not uploaded"

### Preflight checklist before `+create` / `+update`

The agent **must self-check these 4 items** before calling `+create` / `+update`; any anomaly → ask the user for confirmation immediately:

1. The `goal / input_form_spec` in the payload contains **no real client names, case numbers, amounts, or internal-spec excerpts** — those are materials and must be replaced with three-part variables or generic terms
2. The `search_plan` in the payload does **not copy-paste verbatim passages of any user-provided sample report** — extract structure (sources/actions/validation), not the original text
3. The `report_format` in the payload carries **no client-specific jargon** — the main heading contains the three-part variables and no hardcoded client name was missed
4. `source_conversation_id` is a `seed:<slug>:v1` or a conv id from the `+author` flow — **never a real business conversation id**

Only then POST.

- Before **write operations** (`+create` / `+update` / `+frequent` / `+unfrequent`), the user must explicitly confirm. Use the uniform 1/2 style so the user can reply with a number:
  > 1. Confirm and execute
  > 2. Cancel
- Before **credit-consuming operations** (`+test` / `+tune`), state "this will cost about N credits" first, then use the same 1/2 confirmation.
- The delete operation (`+delete`) is not implemented yet, to avoid accidental deletion.

## Compatibility

| Platform | Status | How to load |
|---|---|---|
| Claude Code | ✅ Verified | Add the directory to your skills path; the `Skill` tool loads SKILL.md automatically |
| Gemini CLI | ✅ Verified (2026-05-20, see [verification report](docs/verification-reports/2026-05-20-gemini-cli.md)) | `activate_skill` loads SKILL.md |
| Codex CLI | ✅ Verified (2026-05-21) | Manually `cat SKILL.md` inject, or load per the codex skill convention |
| Hermes / OpenClaw / Kimi | ✅ Verified (v0.2.0, real tasks against the live API) | Load SKILL.md + scripts/ per each agent's skill spec |
| Other agents | ⚠️ Not independently verified | Load SKILL.md + scripts/ per each agent's skill spec |

scripts/ uses Python 3.10+ stdlib with no third-party dependencies — any environment that can run Python works. If you get it running on an agent outside the ✅ list, please open an issue on the GitHub repo to report compatibility.

## About API stability

Cue's public API docs currently cover 4 endpoints: `POST /api/chat/stream`, `GET /api/templates`, `POST /api/templates/search`, `GET /api/templates/conversation/<id>`.

This skill **additionally uses** several internal endpoints: `POST /api/templates` (create), `PUT /api/templates/<id>` (update), `GET /api/templates/<id>` (get one), `POST /api/generate_template` (+tune backend), `POST /api/templates/frequent` (+frequent). These share the same auth middleware as the frontend workbench and accept API keys, but are **not listed in the public API docs** — their paths/payloads may change in the future.

If you hit 4xx errors on +create / +update / +tune / +frequent, first check whether the [Cue official docs](https://sensedeal.feishu.cn/wiki/NS0ywPa4jiN4dgkA8V7cQvpxndf) have updated the corresponding spec.

## Script-to-verb mapping

The agent does not need to "hardcode" how a verb executes — call the scripts directly:

| Verb | Script | Equivalent command |
|---|---|---|
| `+validate <path>` | `validate_template.py` | `python3 scripts/validate_template.py path.json` |
| `+list` | `cue_api.py` | `python3 scripts/cue_api.py list` |
| `+get <id>` | `cue_api.py` | `python3 scripts/cue_api.py get <id>` |
| `+create` | `cue_api.py` | `python3 scripts/cue_api.py create payload.json` |
| `+update <id>` | `cue_api.py` | `python3 scripts/cue_api.py update <id> payload.json` |
| `+test <id> <entity>` | `test_template.py` | `python3 scripts/test_template.py <id> <entity> --save run.md` |
| `+tune <id> --issues f` | `tune_template.py` | `python3 scripts/tune_template.py <id> --issues issues.txt` |
| `+frequent <id>` | `cue_api.py` | `python3 scripts/cue_api.py frequent <id>` |
| `+unfrequent <id>` | `cue_api.py` | `python3 scripts/cue_api.py unfrequent <id>` |
| `+upgrade` | `update_skill.py` | `python3 scripts/update_skill.py --skill cue-buddy`(interactive); `--silent-check` for the session-start lightweight version |

`+author` has no dedicated script — it is the agent running SKILL.md's guided Q&A + `validate_template.py` feedback + `cue_api.create_template` persistence as a flow.

**Runtime file location (single root):** all runtime artifacts land in one writable root `<root>` = `python3 scripts/cue_api.py root` (default `~/.cue`; sandboxes that lock home fall back to cwd/temp automatically — no cross-platform `/tmp` dependency). The agent only needs write authorization for this one directory. Script defaults: `+test` run logs -> `<root>/runs/buddy-run-<id>-<ts>.md`; `+tune` proposals (when errors) -> `<root>/proposals/`, pre-update backups -> `<root>/backups/`. `+create`/`+update` temp `payload.json` files go to `$(mktemp)` or `<root>/tmp/` — don't pollute cwd. Config (`config.json`) + cooldowns (`last-update-check.json` / `last-community-invite.json`) stay in `~/.cue/` (moved with `CUE_HOME` if set) — they travel with the config, not with the writable-root fallback.
