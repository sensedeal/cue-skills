---
name: cue-omni-reader
description: "Use when the user wants an external AI agent to parse or understand an HTTP(S) URL or an authorized local document, audio, or video source through Cue Omni Reader."
license: MIT
metadata:
  version: "0.4.0"
  requires:
    bins: ["node"]
  envOptional: ["CUE_API_KEY"]
---

# Cue Omni Reader

> 中文版见 [`SKILL.zh-CN.md`](SKILL.zh-CN.md) — complete Chinese translation.

Use official Omni MCP tools to parse a URL or authorized local file, then complete the user's task. The MCP package and active tool schemas are authoritative; this skill implements no parser, upload client, or MCP driver.

## Core flow

1. **Preserve the source.** Only HTTP(S) strings are URLs. Pass the user's source string directly to `parse`. Do not pre-read, attach, base64-encode, or paste local content. Do not use `file://`, localhost, or a public temporary upload service.
2. **One provider, both sources.** `parse(source)` covers HTTP(S) URLs and authorized local paths. The Bridge is the same Omni provider, not a second connector; remote-only handles URLs, not local files.
3. **Bootstrap only with consent.** Before installing the Bridge or expanding an allowed root, obtain user confirmation and add only the minimum required directory. Follow [`references/setup.md`](references/setup.md): use its exact audited pin, run `doctor`, then reload/restart. Never ask for an API key in chat. When a file is already inside an allowed root, do not ask for another confirmation.
4. **Call the active schema.** Obey the active `parse` schema and never invent arguments. If the schema exposes `wait`, use `wait: false` for long media or a large document; the source-only Bridge instead returns a recoverable operation. Send exactly one of `source` or `url`. `grounded`/`layout` are Bridge-local; remote `UNSUPPORTED_DETAIL` is final. Do not race synchronous and asynchronous submissions.
5. **Read either response channel.** Prefer `structuredContent` when available. If only `content[].text` exists, parse compact JSON first. Completed inline content may be exact Markdown; non-inline states are compact JSON. A generic success is not a completed result. Append only `result.text`; never append the JSON wrapper.
6. **Preserve one operation.** On `processing`, save the `operation_id` and poll `get_parse_status` at the returned timing/`wait_ms`. Recover the existing operation before resubmitting. A lost ID is an ambiguous timeout: explain duplicate-work/billing risk and get confirmation before replacement.
7. **Choose result delivery deliberately.** Use this decision table:

   ```text
   Answer directly → inline when present; otherwise `read_result`
   Find one section → `read_outline` → `read_result(cursor)`
   Read all content → `read_result` until no `next_cursor`
   Deliver a file → `save_result`
   ```

   Use `result_delivery="artifact"` for saving, section navigation, multiple documents, or strict context control; `auto` keeps bounded text inline when possible. For `result.kind=artifact`, the preview is not complete; read until `next_cursor` is absent. `read_outline` does not require `save_result`. For multiple sources, use bounded concurrent independent `parse` calls and keep handles separate.
8. **Finish and clean up.** Continue the user's original task after parsing. For a summary, assemble the complete result first; do not truncate. For parse only, return complete Markdown or a file and optionally offer a summary. Keep artifacts until task completion, then `discard_result` unless retained. Claim deletion only after discard or cleanup is confirmed.

## Operation states

| State | Action |
|---|---|
| `processing` | Continue the same operation and report authoritative progress. |
| `completed` | Consume the inline or artifact result. |
| `cleanup_pending` | Use an available result; do not claim deletion or resubmit. |
| `failed` | Surface the structured error; retry only when `retryable=true` and state permits. |
| `canceled` | Report confirmed cancellation, billing, and cleanup facts. |
| `expired` | Explain expiration; get confirmation before new work. |

For any state not recognized, preserve the operation; do not resubmit or claim completion, cancellation, billing, or cleanup.

Same-source retries reuse only recoverable or retained-completed records; failed, canceled, expired, or out-of-window retries may create and bill a new operation. On a reusable record, `auto`→`artifact` strengthens delivery without a second operation. If the user asks to stop an active operation, call `cancel_parse` with the saved ID. Do not use discard as cancellation; you cannot promise cancellation avoided charges.

## Unknown client capabilities

Classify Tasks, Roots, host timeout, and cwd/workspace behavior only from direct client evidence; never infer them from a successful parse.

- **Tasks unknown** → use ordinary `parse` plus bounded `get_parse_status` polling.
- **Roots unknown** → use process cwd and explicit roots only.
- **Host timeout unknown** → preserve Bridge's bounded 20-second status wait.
- **Cwd/workspace unknown** → do not widen authorization or guess the active workspace.

## Truthful error and billing handling

A tool-level error is not an MCP disconnection. Preserve authentication, billing, parser, retryability, operation, and cleanup facts. Report only billing facts returned for this operation; retry only when `retryable=true`. Never estimate charges or copy page/media rate conversions.

Run `npx -y @cueai/omni-reader-mcp@1.6.0 doctor --json` first. `CUBE_UNAVAILABLE` is a control-plane failure before upload; a post-grant failure is in the secure upload stage; `CUBE_PROTOCOL_ERROR` is a response-contract mismatch. Use only reported endpoint facts—never guess or publish internal hosts or ports.

## Public tools

Use semantic names:

- `parse`
- `get_parse_status`
- `cancel_parse`
- `read_result` — Bridge-local artifact tool
- `read_outline` — Bridge-local artifact tool
- `discard_result` — Bridge-local artifact tool
- `save_result` — Bridge-local artifact tool

The four artifact tools exist only on the local Bridge; the remote surface never exposes them. Client and service evidence belongs in [`references/compatibility.md`](references/compatibility.md).

## Free credits

New users can try Omni; current policy comes from the live server and `doctor`. Details: [`references/setup.md`](references/setup.md).
