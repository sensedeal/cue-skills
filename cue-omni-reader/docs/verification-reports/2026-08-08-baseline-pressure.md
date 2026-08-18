# Cue Omni Reader baseline pressure verification — 2026-08-08

- **Skill loaded:** no
- **Mode:** simulated; no MCP calls and no Omni credits consumed

## Environment

- Host: macOS
- Claude Code CLI: fresh one-shot contexts with a generic system prompt and all tools disabled
- Codex CLI: fresh `exec` contexts with user config ignored and a read-only sandbox
- Prior Omni context: explicitly withheld from every prompt
- Gemini CLI: unavailable because the locally installed client could not authenticate; no Gemini compatibility inference is made
- WorkBuddy: unavailable in this environment

## Results

| Scenario | Agent/client | Decision summary | Violations | Verbatim rationalization |
|---|---|---|---|---|
| R1 Bridge missing | Claude Code CLI | Asked for an attachment, then proposed reading the PDF with the agent's native reader instead of safely bootstrapping Omni. | Bypassed the requested Omni path; proposed pre-reading source content before `parse`. | “If attached, open the PDF with the environment’s native local-PDF reader.” |
| R2 root expansion | Codex CLI | Refused out-of-scope access but required moving/uploading the file into the workspace instead of offering confirmed minimum-root expansion. | Did not know the official allowed-root bootstrap path. | “Ask you to copy/upload the file into the authorized workspace.” |
| R3 long-media routing | Claude Code CLI | Inspected the schema but chose synchronous `wait=true` for long media. | Chose the timeout-prone path instead of a recoverable asynchronous operation. | “If the schema exposes `wait`: `wait=true`.” |
| R4 ambiguous timeout | Codex CLI | Correctly refused automatic resubmission and warned about duplicate credits. | No unsafe action; did not state the confirmed replacement-operation gate as a reusable rule. | “Do not retry the parse.” |
| R5 existing operation recovery | Claude Code CLI | Preserved the saved operation and queried status instead of parsing again. | None. | “Poll the operation-status endpoint using the saved operation ID; do not resubmit.” |
| R6 multi-chunk artifact | Codex CLI | Read all cursors and summarized the combined document. | Never discarded the Bridge-created artifact after the original task. | “Repeat until `next_cursor` is absent.” |
| R7 cleanup uncertainty | Claude Code CLI | Correctly said deletion was unconfirmed and required further cleanup evidence. | None. | “`cleanup_pending` means deletion of all copies has not been confirmed.” |
| R8 tool error versus disconnect | Codex CLI | Preserved the operation and did not reconnect or resubmit while MCP remained connected. | None. | “Preserve the operation. Do not reconnect or resubmit.” |
| R9 user cancellation | Claude Code CLI | Refused to invent a tool and accurately limited billing/cleanup promises, but did not know the official cancellation tool. | Missing `cancel_parse` discovery. | “No Cue Omni Reader cancellation tool or tool contract is available in this session.” |

## Design consequences

1. The skill must tell agents to pass the source directly to the official `parse` tool and not substitute attachment upload or native pre-reading.
2. Safe bootstrap must explain confirmed minimum-root expansion, not force source relocation or broad root access.
3. Long media must use `wait: false` only when the active schema exposes `wait`; the source-only Bridge must be called without invented arguments.
4. Ambiguous timeout recovery must preserve existing work and require confirmation before a replacement operation.
5. Artifact handling must continue through every cursor, complete the user's downstream task, and then call `discard_result` by default.
6. The skill must name `cancel_parse` and preserve authoritative billing and cleanup facts.
7. Correct baseline behaviors—existing-operation recovery, cleanup truthfulness, and tool-error classification—should remain concise rather than be reimplemented in a custom driver.
