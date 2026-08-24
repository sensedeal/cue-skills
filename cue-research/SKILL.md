---
name: cue-research
description: "Use when the user asks a research question they want Cue to run — against a saved 搭子(buddy) template or as free-form deep research. Triggers: 帮我查/调研/研究 + 主体或话题; ask Cue about X; 用 Cue 跑一下 Y; 看看哪个搭子能查 X; 把刚才那次调研存成搭子. Public-data scope only — refuse for private-data scenarios (real AML / medical / internal accounting)."
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

# cue-research — let Cue do the work inside your agent

Lets you hand a research question to Cue **in natural language from inside your own AI agent**: it auto-matches ≤2 candidates from your buddy library (or falls back to **free-form deep research through the backend `/api/rewrite`** when nothing fits), runs after you confirm the credits, and can optionally solidify a satisfying run into a buddy. This skill is the **sibling of [`cue-buddy`](../cue-buddy)** — cue-buddy is for **authoring** buddies, cue-research is for **using** them.

## Scope boundary (before invoking)

Cue's tool surface covers **public data sources only** (business registry / courts / regulators / filings / capital flows / procurement …). Scenarios needing **private data** (real AML on bank flows, medical diagnosis, internal accounting) are **refused** by the agent, which suggests rewriting the scenario in public-data terms or using the cuecue.cn web side.

## Setup

**Dependency**: this skill has a single thin runtime script `scripts/research_run.py` (run + fetch report + save to disk); it and all other calls import shared primitives from the sibling `../cue-buddy/scripts` (see "Import convention" below). Therefore **`cue-buddy` must be installed as a sibling directory of this skill** (e.g. both under `~/.claude/skills/`) — installing only cue-research fails at import time.

It shares the cue-buddy API-key configuration (`CUE_API_KEY` env or `~/.cue/config.json`). See the "Setup" section of [`../cue-buddy/SKILL.md`](../cue-buddy/SKILL.md).

## Invocation convention (verbs)

| Verb | What it does | Costs credits? |
|---|---|---|
| `+ask <question>` | Main entry: parse → match ≤2 buddies → user picks 1/2/0/n → run → deliver → optionally solidify. **Also accepts implicit natural-language triggers** | Explicit confirmation before running; nothing charged if you don't run |
| `+match <question>` | Only match candidate buddies, don't run | No |
| `+rewrite <question>` | Only call /api/rewrite to see `user_confirmation` + `rewritten_mandate`, don't run | No |
| `+save <conversation_id>` | Solidify a successful free-form run into a buddy (handoff to cue-buddy's `+author`/`+create`) | No (template generation itself is free; only test runs consume) |
| `+upgrade` | Check and (after confirmation) upgrade the skill itself to the latest GitHub `main`. git-clone installs use `git pull --ff-only`; copy installs get manual instructions. On session start the agent should silently run `update_skill.py --silent-check --skill cue-research` (24h cooldown; prints one stderr line when behind, no dialog) | No |

## Decision tree

```
User says (Chinese/English/casual)                               → route
─────────────────────────────────────────────────────────────────────────
"帮我查/调研/研究 <subject or topic>"                              → +ask
"ask Cue about X" / "用 Cue 跑一下 Y"                               → +ask
"看看哪个搭子能查 X" (match only, don't run)                       → +match
"先帮我把这个问题改写成结构化的(不跑)"                               → +rewrite
"把刚才那次调研存成搭子" / "save this run as a buddy"               → +save
"更新一下 skill" / "check for updates" / "升级搭子工具本身"          → +upgrade
─────────────────────────────────────────────────────────────────────────
```

## Main flow `+ask` (most used)

### Stage 1: parse + light clarification

Extract from the user's question:
- **Core entity** (company / person / product / industry)
- **Time window** (if not stated, ask one question to confirm)
- **Angle** (investment / compliance / competitor / sentiment; ask one question if clearly ambiguous)

Ask **≤1 clarification question**. **Do not rewrite the deep-research logic yourself** — that is the backend `rewrite_prompt`'s job, left for Stage 4.

### Stage 2: match candidate buddies (single-stage — read the full catalog, pick directly)

The agent **pulls all visible templates at once** (user-created + system public buddies), groups them mentally by `secondary_category`, and **picks top ≤2 directly from its own semantic understanding — no backend keyword search**. Backend search only matches title + primary/secondary category literally; Chinese isn't tokenized, so 「投资价值」「业绩超预期」「兆易创新」all come back 0 hits (verified in practice); agent LLM semantic understanding is far stronger than such literal matching.

**Implementation:**

```python
from cue_api import search_templates
# pull the full set: keyword=" " + include_system=True, page until done (backend page_size cap 100)
pool, page = [], 1
while True:
    batch = search_templates(keyword=" ", include_system=True, page=page, page_size=100)
    if not batch: break
    pool.extend(batch)
    if len(batch) < 100: break
    page += 1
```

Each template carries `template_id / title / primary_category / secondary_category / goal`. **`template_id` is a string `template_<base62-suffix>` (e.g. `template_fnig0i`) — Stage 4 running uses this field's value, never the numeric `id` field (templates have both a numeric DB `id` and the string `template_id`, easy to confuse) or a list index; a bare number like `142` is not a valid id.** The agent groups by **`secondary_category`** and scans (`深度核查` / `投资研究` / `信贷尽调` / `市值管理` / `财富投顾` / `私募尽调` / `融资融券` / `法律与行研` / `资本运作` / `行业研究` / `商机挖掘` / `保险营销` … top-12 secondary cats cover ~80% of templates), semantically matching the query against each candidate's `goal`, and picks the most relevant **≤2** candidates.

**Key principle — entity vs intent separation:**

| Info type | Examples | How to use |
|---|---|---|
| **Entity** | 兆易创新 / 万科 / 比亚迪 / a regulatory document name | Left for **Stage 4** to fill `task_input` — **never enters any template-matching step** |
| **Intent** | investment value / compliance risk / earnings review / competitor benchmarking | Agent semantic understanding matches the template's goal/title/category |

**Why separation is mandatory**: templates are **generic research frameworks**; title/category/goal **never** contain specific entity names. Matching 「兆易创新」 as a query against templates is like asking the agent to find a specific subject inside generic frameworks — it can't. The agent must first peel the entity out for `task_input` and match with intent only. See Hard Rule 6.

**Worked examples (6 real queries verified, 4 beat backend keyword search, 1 tied, 1 honestly admitted no match → weak-match):**

| User query | Entity (→ task_input) | Hit secondary_cat → candidates |
|---|---|---|
| 「兆易创新为什么值得投资」 | 兆易创新 | 投资研究 → `个股估值与股价分析` + `个股基本面与风险体检` |
| 「万科最近合规风险」 | 万科 | 法律与行研 + 深度核查 → `企业合规风险体检` + `监管处罚与问询全景` |
| 「调研一下宁德时代财报」 | 宁德时代 | 投资研究 + 财报点评 → `财报分析` + `财务质量与供应链核查` |
| 「这家公司毛利在变」 | (no explicit entity) | 投资研究 + 财报点评 → `财务质量与供应链核查` + `个股基本面与风险体检` |
| 「比亚迪 vs 长城混动竞争」 | 比亚迪、长城 | no perfect match → weak-match nudge |

**Context cost**: ~106 templates today ≈ 2.8K tokens, fully manageable.

**Future extension (labeled follow-up, not done today)**: when the library grows past **200+ templates** and the context cost crosses ~6K tokens, switch to **two-stage**: Stage A shows only `secondary_category` + per-cat template counts (~500 tokens) for the agent to pick 1–3 cats; Stage B shows only the templates inside those cats (~1–2K tokens) for the fine pick. Single-stage is simplest today.

**Low-confidence fallback to keep**: after picking top ≤2, if the agent judges the match weak (query angle diverges from the chosen buddies'), follow the Stage 3 **weak-match nudge** below to suggest "maybe make a new buddy?".

### Stage 3: present + user confirmation

Present, e.g.:

```
Found these possibly-suitable buddies (keyword match, for reference only):
  1. <Buddy A title> — <one-line value>
  2. <Buddy B title> — <one-line value>
  0. None fit → free-form deep research (goes through /api/rewrite for privacy masking + public-source constraints first)
  n. Cancel

The exact credits are only known after the run (the backend offers no pre-run estimate; the first few runs calibrate it — cross-check in the cuecue.cn workbench).

**Duration**: a single deep-research run **usually takes 3–15 minutes**, longer for complex subjects; **the server hard-timeouts at 60 minutes**. The client/agent wait must be set accordingly (don't cut it off at the usual tens-of-seconds API timeout) — stay patient while it runs, don't judge "failed" just because it's slow.
Please enter:
```

**Weak-match fallback:** if the agent judges the listed candidates as only **tangential keyword overlap** with the user's question (titles/categories brush against it but the angle doesn't line up), append one extra line after the list:

> Matching is weak — maybe make a new buddy?

- User answers "做"/"好"/"建"/"+author" or any positive reply → **route to the [`cue-buddy`](../cue-buddy) `+author` flow** (note: **never mention the verb name `+author` to the user in external copy** — internal routing only; to the user just say "make a new buddy").
- User answers "不用"/"直跑"/or picks 0 → go to Stage 4b free-form deep research.

**This nudge only appears on weak match** — on strong/medium match, show the normal 1/2/0/n list and **don't bother the user**.

### Stage 4a: user picks 1/2 — run the buddy (background run + save, fetch when done)

**User question vs internal execution layering (applies to every run path):** `--query` carries the user's original wording or a business-language clarification — only supplementing subject, scope, time, deliverable, source preference, and "say so honestly when something can't be confirmed". The agent **must not inject** internal node/tool names, call counts, or execution order (e.g. "first Researcher then Reporter", "call file_retrieval N times"); those execution constraints stay in the template, runtime policy, monitoring, and post-hoc acceptance. If a technical term is itself the research subject, keep the original meaning — this rule bans extra orchestration language, not mechanical editing of user input. With materials, natural phrasing like "please answer based on my uploaded materials and cite the sources" suffices.

**Don't hold the live stream for an hour inside an agent turn.** A deep-research run takes 3–15 minutes (server hard-timeout 60 min); blocking synchronously wastes turns and is fragile (the live stream often drops before the reporter section arrives). Use **fire-and-retrieve** instead: `research_run.py` runs the full flow **in the background** (start chat_stream → fetch report live → fall back to replay when empty → save to disk); the agent yields its turn immediately; when the background task completes the agent is recalled (**recall is platform-dependent and not always reliable — don't just wait, see "Proactively check completion" below**) and reads the `--output` file to deliver. **Never tell the user "I'll notify you when it's done"** — proactively check completion, don't bet on recall.

**⚠️ stdout is an agent-internal signal, not for the user:** the `[cue-research] …` lines from `research_run.py` (`STARTED conv_id=` / `▶ agent=…` / `🔧 tool=…` / `✓ report finalized` / `RESULT`) are for the **agent's internal judgment** of start/progress/completion — **never paste them to the user verbatim**. Talk to the user in plain language (start confirmation / progress translation / final delivery); the user should not see conv_id / agent= / tool= technical lines.

**Launch (Bash, `run_in_background: true`):**

`--template-id` takes the Stage 2 candidate's `template_id` field value (shape `template_fnig0i`). **Don't pass the numeric `id` or a list index** — the runner fail-fasts on pure-numeric suffixes (e.g. `142`→`template_142`) without burning credits, because Cue id suffixes are never pure-numeric.

```bash
python3 <skill>/scripts/research_run.py \
  --template-id <chosen template_id> \
  --query "<original or clarified question>"
# --output/--log left empty -> runner uses default unique log/report paths; after launch the log= line prints the log path, the RESULT line prints the report path (both absolute-path literals, see "Completion detection" below)
```

**⚠️ Path writability:** `cue_api.py root` already probes a writable root and creates `reports/` `logs/` (auto-falls back to the agent cwd or temp when `~/.cue` is unwritable — no cross-platform `/tmp` dependency). **Don't `mkdir` or `touch .wtest` yourself** — the runner re-probes via `cue_root()` at launch and fails fast (before burning credits) if unwritable. When `--output` points elsewhere the runner probes that directory too.

**Confirm launch after starting (don't wait for the result, only for the start signal):** wait until the background stdout shows `[cue-research] STARTED conv_id=…` (usually within 2–5 seconds — the first SSE event arriving means the backend accepted it) before yielding the turn. If `[cue-research] chat_stream failed` appears (start failure, parameter/auth issue), handle per diagnostics immediately — don't tell the user "it's running".

**What to say to the user before yielding (plain language):** "Successfully started (about 3–15 minutes) — when it's done I'll paste the report and save it under your cue directory (full path when done)." **Don't forward the `STARTED conv_id=` / `▶ agent=` stdout lines to the user** (see ⚠️ above).

**You must consume research_run.py's streaming stdout (progress AND completion both come from it):** research_run.py's stdout is **streamed in real time** (`flush=True`): `STARTED` → `▶ agent=… task=…` (research steps) → `✓ report finalized` → `RESULT ok|empty`. This stream is your **only source of progress + completion** — consume it; don't yield and sleep waiting for a recall (recall is unreliable; .workbuddy-style platform notifications often never arrive).

**Completion detection (mandatory):** the runner has a built-in `--log` (default `<root>/logs/cue-run-<conv_id>.log`, **unique per run**) and **tees** progress to that file and stdout at the same time — **no shell `>` redirect needed** (the old `./cue-run.log` approach's pitfall: two Bash calls had to share one hard-coded path, which broke when the sandbox/Windows changed). **A unique log name kills two race classes**: stale RESULT (a new file has no old content, `tail -F` won't match a previous result) + missed RESULT (`tail -F` reads content already in the new file even if RESULT was written before the watcher attached; `tail -n 0` would miss a second-scale failure's RESULT and the watcher would wait 61 min).

⚠️ **Shell variables don't carry across Bash calls**: launching (Bash1) and waiting for RESULT (Bash2) are two separate Bash invocations; `$root`/`$log` don't carry over. **Don't use variables — use literal absolute paths** — the runner prints `[cue-research] log=<absolute path>` as its first line; the agent reads Bash1's stdout anyway to confirm `STARTED`, so note the path literal from that line for Bash2:

```bash
# Bash1 launch (run_in_background; --output/--log both empty, runner uses default unique log, RESULT line prints the full output path):
python3 <skill>/scripts/research_run.py --template-id … --query …
# -> first line [cue-research] log=<root>/logs/cue-run-<conv_id>.log  <- note this absolute path
# -> STARTED conv_id=… ; progress lines ; last line RESULT ok|empty output=<absolute report path>
# Bash2 second background Bash (tail -F reads the new file's content, never misses RESULT; use the literal log path Bash1 printed):
timeout 3660 tail -F "<absolute log path from Bash1>" | grep -m1 "RESULT"
# grep -m1 exits on RESULT; timeout 3660 guards against runner crash (OOM/SIGKILL/uncaught exception) never writing RESULT (61 min > 60 min hard timeout)
# Bash completes -> read the RESULT line: ok -> read its output=<path> report and deliver; empty/timeout -> diagnose / tell the user it failed
```

**Progress display:** translate the stdout progress lines (`▶ agent=… task=…`) into research steps for the user:
- Claude Code: `Monitor` tool (`tail -F <absolute log path from Bash1> | grep "▶\|✓\|RESULT"`), each line notifies → translate and report to the user.
- Agents without Monitor (.workbuddy etc.): **when the user asks about progress**, read the latest lines of `<absolute log path from Bash1>` and translate (not periodic polling — you don't wake up after yielding, so periodic reads are infeasible; the background-Bash completion notification is the only proactive trigger).
- Translation: `▶ agent=researcher task=查…` → "research step: 查…"; `✓ report finalized` → "report generated, fetching now"; `RESULT` → deliver. **Never paste raw `▶ agent=` lines** (see ⚠️ above).

**Never tell the user "I'll be notified automatically when it's done"** — you consume the streaming stdout to detect progress + completion proactively, not bet on recall.

Translation details: present the **task_requirement** of `▶ agent=… task=<requirement>` as a **research step**, don't show the agent name (coordinator/supervisor/researcher are internal roles the user doesn't care about):
- `▶ agent=researcher task=查半导体细分景气度` → "research step: 查半导体细分景气度"
- `▶ agent=reporter task=撰写半导体景气度报告` → "research step: 撰写半导体景气度报告"
- Collect multiple tasks into a **step list** (1. 2. 3. …), mark done ✅ / in-progress 🔄 / pending ⏳
- `▶ agent=coordinator/supervisor` (no task_requirement): **skip**, don't report (internal coordination)
- `✓ report finalized` → "report generated, fetching now"; `RESULT ok` → read the `--output` report and deliver
- **Never paste raw `▶ agent=` lines** (see ⚠️ above). The whole progress stream from `STARTED` to `RESULT` lives in one stdout file.

**⚠️ Don't poll the stdout file at high frequency:** progress is **event-driven** — either use `Monitor` to receive pushes passively (each progress line notifies you proactively), or start a background Bash `tail -F <absolute log path from Bash1> | grep -m1 "RESULT"` and let the completion notification trigger you. Long gaps without output are **normal** (one deep-research step can run minutes without a progress line) — **don't repeatedly Read the same stdout file waiting for events** (wastes turns and risks context overflow).

**Remember the conv_id:** take it from the `STARTED conv_id=…` line after launch (or pass `--conversation-id <custom>` at launch); all later checks/replays use it. **Never double-launch**: when a conv_id is already running/done and the user asks for progress, check that conv_id (stdout/replay) — **don't re-run `research_run.py`** (burns new credits + loses context); only a new subject/buddy warrants a fresh launch.

**Proactively check completion (poll on a timer, don't wait for recall/don't wait for the user to ask/don't wait 5 minutes):** recall is unreliable — you're not passively waiting for notification, you're **polling the stdout tail continuously (every 1–2 minutes, until `RESULT` appears)** (the same periodic mechanism as "proactively track right after launch"; not a single check). On `RESULT ok` → deliver; no RESULT → replay(conv_id) to fetch the report:
1. Read the background stdout tail. `RESULT ok` → read `--output` and deliver; `RESULT empty` → next steps per diagnostics.
2. No `RESULT` in stdout (task running long / recall never came) → **actively replay by conv_id to fetch the report** (no credits; if the backend finished, the report must exist):
   ```python
   import sys; sys.path.insert(0, "<repo>/cue-buddy/scripts")
   from cue_api import replay
   from sse_report import extract_reporter_content
   events = list(replay("<conv_id>", max_seconds=60))
   report = extract_reporter_content(events)
   # report non-empty -> backend finished, save and deliver; empty -> still running, check again in a bit
   ```
3. replay has a report → save to `--output` and deliver (same save format as research_run); replay empty → backend not done yet, check again in 1–2 minutes (don't replay immediately in a loop).

**After the completion recall (or proactive check sees RESULT):** read the stdout tail line `[cue-research] RESULT ok conv_id=… chars=… output=…` (failure is `RESULT empty …`); on `ok` read the `--output` file → Stage 5 delivery; on `empty` give next steps per the diagnostics in the file/stdout (usually: check the conversation on the cuecue.cn web side).

**Why this design is right (background — don't rewrite it):** `research_run.py` is a **thin orchestration** over the `cue_api` + `sse_report` shared primitives (no copying, no drift); internally it treats **replay as the primary report-fetch path**: long live client streams usually disconnect before the reporter section arrives (the server still runs to completion and writes the DB), so `extract_reporter_content(live_events)` returning empty is **normal, not a bug** — `chat_stream` and `replay` SSE parsing are byte-for-byte the same and share one extract, and replay reads the complete `workflow_events` from the DB so it almost always succeeds. This L1 diagnostics (`diagnose_empty_report`'s three `kind`s) + L2 replay hardening shares its origin with `cue-buddy/scripts/test_template.py` and has passed ≥9 subjects. Note `stream_cut_before_reporter` is a **`kind` string returned by `diagnose_empty_report`, not an importable function**. For foreground debugging (`--foreground` semantics) just drop `run_in_background`, but the default is background.

### Stage 4b: user picks 0 — free-form deep research (through /api/rewrite)

1. First call `rewrite(input=<user question>)` (already unwraps the DataResponse wrapper), get the dict — top level is `thinking / user_confirmation / task_node / rewritten_mandate / safety_flag`.
2. Show `user_confirmation` (it explains: from what angle to research, what privacy was masked) + the `safety_flag.pii_masked` list, and ask:
   > Research it this way?
   > 1. Run as shown
   > 2. I want to change the query and re-rewrite
   > 3. Cancel
3. User picks 1 → feed `rewritten_mandate` as `--query` to the same `research_run.py`, **without `--template-id`** (free-form goes through deepresearch_team; pick 2 returns to Stage 1 for a new query and re-runs; pick 3 exits):

```bash
python3 <skill>/scripts/research_run.py \
  --query "<rewrite_result['rewritten_mandate']>"
# No --template-id = free-form deep research. Same run_in_background:true (after launch wait for the STARTED signal to confirm start + you can read stdout for progress mid-run, see Stage 4a), then read --output after the completion recall.
```

**rewrite stays agent-side in the foreground; the runner never touches it** (Hard Rules 3/4: don't re-implement the backend rewrite logic in the runner; and the user must confirm `user_confirmation` + `pii_masked` first). **Why rewrite first?** `chat_stream` itself does not invoke `rewrite_prompt` (only the /api/rewrite endpoint does); skipping it loses privacy masking + public-source constraints + intent augmentation. The runner only does "run + fetch report + save".

**Optional — mimic style (free-form only).** Free-form runs can make the report **imitate a reference's writing style/structure**. Before the Stage 4b confirmation, ask one optional line (skip if the user has no need — don't bother them):

> Want the report to imitate some style/structure? Give a **link** or a **sample document** (optional — otherwise just run).

- Link → add `--mimic-url "<URL>"`; document → add `--mimic-file "<local path>"` (the runner uploads it first and swaps in a `file_hash`; supported types per the server's `/api/file_server/accept_type`).
- **Free-form only**: `--mimic-*` **cannot** combine with `--template-id` (a buddy already has a report_format; the backend lets template_id override mimic → silent no-op, the runner refuses outright). The two mimic args are mutually exclusive too.
- **Run to completion, no mid-run confirmation** (`need_confirm=False`): the backend auto-generates a style template from the sample and runs straight through, **without** stopping to wait for "review the template" input — this preserves the one-shot background run. Trade-off: you don't get to see the auto-generated template before credits are spent; if the style comes out wrong, give a new sample and re-run. (Interactive template review is Phase 2, not built yet.)

**Optional — document grounding (materials, works for both buddy and free-form).** When the user wants the research **grounded in their own documents** (contracts / annual reports / PDFs / meeting notes …) rather than public sources only, pass the documents in as **materials**: the backend does semantic retrieval over the full text (real RAG, not just previewing the first page). Orthogonal to `mimic` (style) and compatible with `--template-id`.

- Add `--material "<local path>"`, **repeatable** for multiple files: `--material a.pdf --material b.docx`. The runner uploads each file first (waits for the SSE flow to reach `…→completed` to get the `file_id`), then binds them into this run via `conversation_file_ids`.
- **Get user confirmation before uploading** (see safety rules: local materials are never uploaded by default). Ask: "Should I upload this document as research material? It will be used for retrieval and counts toward this run's credits."
- Types/sizes (all **server-side** constraints; the runner doesn't pre-check size locally): supported types and exact limits per `/api/file_server/accept_type`, **single file max 256 MiB** (over-limit / unsupported types are rejected with an error by the server); file_id is **single-use bound** (backend behavior: one file_id serves one conversation; re-runs/new conversations need a re-upload). Per the backend: upload only checks balance, **no separate charge**; running the chat is what spends credits.
- Write the query in normal business language with explicit material boundaries, e.g.: "Please answer based on my uploaded materials, citing sources item by item; explicitly state anything the materials can't confirm." **Don't** put internal nodes, tool names, call counts, or execution order into the query. Whether the full text was actually read is verified by run logs/replay evidence, not by piling orchestration jargon into the user's question.

```bash
python3 <skill>/scripts/research_run.py \
  --query "<question; explicitly ask to base research on uploaded materials>" \
  --material "~/Downloads/某公司年报.pdf"
# Free-form with materials as above (rewrite first still); buddy with materials adds --template-id <id>. Same run_in_background:true.
```

### Stage 5: deliver + satisfaction

Present the report (reporter content). Ask:
> Happy with this report?
> 1. Yes
> 2. No

- User picks **1 (yes)** → if this was a 4b free-form run, go to Stage 6; if 4a buddy run, end here.
- User picks **2 (no)** → offer follow-ups, keep the 1/2/3 style:
  > 1. Re-run with another candidate buddy (if Stage 3 had unused candidates)
  > 2. Re-run with added clarification (back to Stage 1: change query / subject / time window)
  > 3. Re-run via the other path (was buddy → free-form; was free-form → buddy, back to Stage 2 to re-match)

### Stage 6: solidify into a buddy (optional handoff to cue-buddy)

When Stage 5 was satisfied and the run was 4b free-form, ask the user (**verb names never appear in external copy**):
> This research was useful — save it as a new buddy? Next time you'll have a ready one for the same class of question.
> 1. Save
> 2. No

On **1**, the agent routes **internally** (the following is for the agent, never shown in the user conversation):
- Hand the successful run's `conversation_id` + original question + reporter report to cue-buddy's `+author` flow (the backend fetches this run's history by `conversation_id` to generate the template).
- Go through cue-buddy's `+validate` → user confirm → `+create` to persist.
- This is **explicit and user-confirmed**, never automatic. **Say only "存"/"帮你存"/"做成搭子" to the user — never "+author"/"+validate"/"+create"**.

## Community invite (Cue user community)

At **high-intent moments**, invite the user to the「Cue 用户社群」(Q&A + newest buddy-template sharing), presenting the group QR per the trigger + cooldown rules in [`../community-invite.md`](../community-invite.md) — **restrained, one extra line, not every session**:

- **① First use**: a quiet line in the first `+ask` presentation (one-time).
- **② After a run completes**: one line **after the report + satisfaction/next-step questions are all delivered** (**never inserted mid-delivery**): "Like it? Join the group for the latest templates" (14-day cooldown).
- **③ Stuck/error**: no buddy matched / permission errors / user confusion → **first help the user / give next steps**, then offer the group as a **gentle fallback** — not dumping the user into the group on every error (14-day cooldown).
- **④ User explicitly asks**: "how do I join the group / community / feedback / any new templates" → **show the QR image** (**no cooldown**).

**Passive triggers (①②③) get one line of text pointing to the QR image `../assets/community-group-qr.png` — no large image rendering; the large image is only shown on ④ (user-initiated).** The only join entry is the QR code (which encodes the group link) — **never print a plaintext group link**. Cooldown `${CUE_HOME:-$HOME/.cue}/last-community-invite.json` (same dir as config; moves with CUE_HOME) (passive triggers at most once per session, skipped if <14 days since last; read/write failure → no more invites this session). **External groups: Feishu users (incl. other tenants) can scan to join; only pure non-Feishu users cannot** — full rules and boundaries in [`../community-invite.md`](../community-invite.md).

## Hard rules (ironclad)

1. **Never auto-pick a buddy.** Always let the user choose from ≤2 candidates + "0 run directly" + "n cancel".
2. **Explicitly confirm credits before every real run.** Even when the user chose "0 run directly" as a fallback, confirm once more ("free-form deep research can cost more than a templated run — confirm we proceed?").
3. **The free-form path (Stage 4b) must call /api/rewrite first.** Don't shove the user's raw question straight into chat_stream.
4. **Don't re-implement the backend's rewrite logic agent-side.** Need a rewrite → call /api/rewrite; clarify with ≤1 question.
5. **Don't implement `+delete`** (prevents accidental deletion; delete buddies on the web workbench).
6. **Entity names (specific company/person/product/event names) go only into `task_input` — never into any template-matching step.** Templates are generic research frameworks; title/category/goal never contain specific entity names — mixing them in makes the agent force-match what shouldn't be matched (or leaves it at a loss). Matching relies on the agent's semantic understanding of the query's **intent** dimension (investment/compliance/earnings/competitor…); entity names are left for Stage 4 to fill `task_input`. This rule is independent of the matching mechanism — it holds whether today's single-pass pick or a future two-stage split. See Stage 2.
7. **User question vs internal execution must stay layered.** What goes into `--query` keeps the user's original wording/business language; the agent must not add Researcher/Reporter/coordinator, tool names, call counts, or node order. Internal constraints live in the template/runtime/monitoring/acceptance; material phrasing just says "based on uploaded materials and cite sources".

## Safety rules

Same source as cue-buddy: the API key never appears in output/logs/commits; a key pasted by the user → remind them to rotate it immediately at cuecue.cn/api-key. **Local materials are never uploaded by default**; only when the user **explicitly asks for document grounding** (`--material`) and confirms, upload their specified material files (used for `file_retrieval` retrieval) — never touch the user's local files otherwise.

## Script-to-verb mapping

| Verb | Path | Script/function used |
|---|---|---|
| `+ask` (main entry) | Stage 1-5 orchestration | Stage 2-3 matching: `cue_api.search_templates`; Stage 4 run + fetch: **`scripts/research_run.py`** (background run, saves to disk); Stage 4b first `cue_api.rewrite` |
| `+match` | Only Stage 2-3 | `cue_api.search_templates` |
| `+rewrite` | Only /api/rewrite | `cue_api.rewrite` |
| `+save` | Stage 6 handoff | handoff to cue-buddy's `generate_template` + `validate_template` + `cue_api.create_template` |
| `+upgrade` | Upgrade the skill itself | `python3 ../cue-buddy/scripts/update_skill.py --skill cue-research` (interactive) / add `--silent-check` (session-start lightweight) |

This skill's only runtime script is **`scripts/research_run.py`** — a **thin orchestration** over the `../cue-buddy/scripts/` shared primitives (`cue_api` + `sse_report`), doing exactly "start chat_stream → fetch report live → fall back to replay when empty → save to disk", **copying no primitives** (avoids version drift with cue-buddy). `scripts/test_skill_regression.py` only does structure/import self-checks. **Don't hand-write a chat_stream event loop in prose** — that was exactly the root cause of early reporter-content misses being misdiagnosed as "the parser is broken"; always go through `research_run.py`.

### Import convention (runtime bootstrap)

**Running/fetching always goes through `research_run.py`** (it already handles sys.path + chat_stream + replay + save internally); the agent does **not** hand-write chat_stream/replay loops. The only things the agent imports **directly** are Stage 2-3 matching + Stage 4b rewrite (read-only, fast, foreground). `cue_api` / `sse_report` aren't on the default import path (they live in sibling `cue-buddy/scripts/`); those two call classes start with:

```python
import sys
from pathlib import Path
# cue-research/<...>  →  cue-skills/cue-buddy/scripts
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cue-buddy" / "scripts"))

from cue_api import search_templates, rewrite     # Stage 2-3 matching / Stage 4b pre-rewrite
```

When the agent runs via Bash `python3 -c "..."`, use the absolute path instead: `sys.path.insert(0, "<repo>/cue-buddy/scripts")`. Avoidance point: never copy-paste `cue_api.py` under cue-research/ — it would drift from cue-buddy's version.

## Compatibility

| Platform | Status |
|---|---|
| Claude Code | Same as cue-buddy (SKILL.md auto-loaded) |
| Gemini CLI / Codex CLI | Same loading convention as cue-buddy |
| Hermes / OpenClaw / Kimi | ✅ v0.2.0 cross-agent verified (real tasks against the live API; same loading convention as cue-buddy + shared scripts) |

> **Honest verification status of the v0.3.0 surface**: the background runner (`research_run.py`), the replay-primary path, and mimic (URL + document) are all **run through against the real live API on Claude Code** (2026-06-08: replay dual-path comparison, mimic PDF end-to-end); but these v0.3.0 new surfaces have **not been re-run cross-agent on Hermes/OpenClaw/Kimi** — the cross-agent conclusion in the line above covers the v0.2.0 surface. New-surface cross-agent is "expected to work (shared scripts + same loading convention)", not yet demonstrated.
