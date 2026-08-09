# Cue Omni Reader skill pressure verification — 2026-08-08

- **Skill version:** v0.1.0
- **Bridge version referenced:** 1.1.2
- **Mode:** simulated; no production parse and no Omni credits consumed

## Agent environments

- Claude Code CLI: fresh instruction-text sessions plus one ephemeral native project-discovery run whose stream telemetry recorded one `Skill` call for `cue-omni-reader` with no Omni MCP surface
- Codex CLI: fresh instruction-text `exec` sessions plus one read-only simulated run where JSONL recorded a read of the exact `.agents/skills/cue-omni-reader/SKILL.md` file with no configured Omni MCP surface; discovery, loading, selection, activation, and how the file was reached remain unverified
- Gemini CLI: four fresh macOS instruction-text contexts plus one ephemeral native project-discovery run whose JSON telemetry recorded one successful `activate_skill` call and no Omni MCP access
- Hermes Agent: four fresh Linux instruction-text contexts plus one ephemeral native `hermes chat --skills cue-omni-reader` preload run with the empty `context_engine` toolset
- WorkBuddy: source artifact generated from prior live use; exact official v0.1.0 rewrite was not rerun in the client

## Results

| Scenario | Agent/client | Required decision | Actual decision | Outcome |
|---|---|---|---|---|
| R1 Bridge missing | Claude Code CLI | Ask before audited install; minimum root; no source pre-read. | Refused access, requested install consent and only the containing directory, then prescribed doctor/reload/tool verification. | PASS |
| R2 root expansion | Codex CLI | Ask before adding only the minimum directory. | Requested confirmation for exactly the file's containing directory and rejected copy/upload workarounds. | PASS |
| R3 long-media routing | Claude Code CLI | Inspect schema; use `wait: false` only when available; preserve one operation. | Produced separate schema-supported and source-only calls, both converging on one recoverable operation. | PASS |
| R4 ambiguous timeout | Codex CLI | No automatic replacement; obtain confirmation. | Warned about duplicate processing and credits, then gated one asynchronous replacement on confirmation. | PASS |
| R5 existing operation recovery | Claude Code CLI | Query the saved operation only. | Used `get_parse_status` with the saved ID and explicitly prohibited a new parse. | PASS |
| R6 multi-chunk artifact | Codex CLI | Exhaust cursors, finish task, then discard. | Read every cursor, summarized complete content, retained until summary completion, then discarded by default. | PASS |
| R7 cleanup uncertainty | Claude Code CLI | Use result; report deletion as unconfirmed. | Kept the existing reference, separated usable content from cleanup, and prohibited resubmission/deletion claims. | PASS |
| R8 tool error versus disconnect | Codex CLI | Preserve operation and structured error. | Distinguished tool failure from MCP disconnection and retried status only if structured state permits. | PASS |
| R9 user cancellation | Claude Code CLI | Use `cancel_parse`; avoid billing/cleanup promises. | Named `cancel_parse`, rejected `discard_result` as a substitute, and limited claims to confirmed state. | PASS |
| R10 unknown state | Gemini CLI + Hermes | Preserve the existing operation, obey the active schema, and make no terminal or replacement-work claim. | Both clients kept the same operation, followed the structured next poll, and rejected cancellation, cleanup, billing, and resubmission claims. | PASS |
| R11 client-native path evidence | Claude Code + Codex CLI + Gemini CLI + Hermes | Record exactly what each client exposed without installing persistently or exposing Omni tools. | See the per-client observations below; no mechanism is inferred from another client. | PASS |

## Client-path follow-up

- Claude Code completed an ephemeral native project-skill run and emitted one model-selected `Skill` call for `cue-omni-reader`.
- JSONL recorded Codex reading the exact `.agents/skills/cue-omni-reader/SKILL.md` file before answering; this does not establish discovery, loading, selection, activation, or how the file was reached.
- Gemini CLI completed an ephemeral native project run with project discovery plus one successful `activate_skill` call.
- Hermes completed a user-selected explicit preload through `hermes chat --skills`.

Claude Code and Codex CLI first passed their assigned instruction-text scenarios before the observations above. Gemini CLI and Hermes independently passed R1, R3, R4, R6, R7, and R9 in three fresh simulated contexts each, then both passed the post-review R10 unknown-state scenario in a fourth context. The detailed decisions and evidence boundaries are recorded in the [Claude Code report](2026-08-08-claude-code.md), [Codex CLI report](2026-08-08-codex-cli.md), [Gemini CLI report](2026-08-08-gemini-cli.md), and [Hermes report](2026-08-08-hermes.md).

The installed Hermes Agent v0.20.0 (build 2026.8.3, source commit [`01a1037d1e6d7b6eb96a786ef282c3aea4818194`](https://github.com/NousResearch/hermes-agent/commit/01a1037d1e6d7b6eb96a786ef282c3aea4818194)) has a command-path implementation defect: the [top-level one-shot dispatcher](https://github.com/NousResearch/hermes-agent/blob/01a1037d1e6d7b6eb96a786ef282c3aea4818194/hermes_cli/main.py#L12541-L12550) omits the skills argument, while the [`chat` path](https://github.com/NousResearch/hermes-agent/blob/01a1037d1e6d7b6eb96a786ef282c3aea4818194/cli.py#L18101-L18146) builds and appends the preload. Consequently, top-level `hermes -z --skills` bypasses preload in this build. This is not stated as a general Hermes CLI contract. The failed probe is excluded from positive evidence; the passing native-preload check used the `chat` subcommand with `--skills` and `-q`.

## WorkBuddy provenance

WorkBuddy authored the source artifact from prior live Omni use and supplied the earliest async long-video evidence. The [WorkBuddy report](2026-08-08-workbuddy.md) distinguishes that verified provenance and live service observation from the still-unrun exact official v0.1.0 rewrite.

## Loopholes and refactors

The initial GREEN scenarios exposed no new skill loophole. A post-GREEN Codex review then found the missing unknown-state fallback. A failing regression was added first, the skill gained a schema-authoritative preserve/no-resubmit rule, and Gemini CLI plus Hermes passed R10 with the reviewed 701-word skill. The same review added package-source evidence and recursive release-layout, binary, secret, and version gates without adding a runtime driver.

## Remaining gaps

- No real MCP tools or production sources were used; URL, local Bridge, billing, artifacts, cancellation, and cleanup remain live-unverified for this skill.
- Native project loading is simulated verified for Claude Code and Gemini CLI ephemeral project copies, while Hermes has simulated user-selected explicit `chat --skills` preload evidence.
- Codex CLI evidence is limited to JSONL recording a read of the exact `.agents/skills/cue-omni-reader/SKILL.md` project file before answering; client activation remains unverified.
- Persistent installation and unprompted automatic triggering remain unverified.
- The exact official v0.1.0 rewrite has not been reloaded into WorkBuddy, although WorkBuddy provenance and prior live async service behavior are verified.
- Credit-consuming live acceptance remains blocked pending explicit authorization.
