---
name: cue-omni-reader
description: "Use when the user wants an external AI agent to parse or understand an HTTP(S) URL or an authorized local document, audio, or video source through Cue Omni Reader."
license: MIT
metadata:
  version: "0.2.1"
  requires:
    bins: ["node"]
  envOptional: ["CUE_API_KEY"]
---

# Cue Omni Reader

Use the official Omni MCP surface to turn a URL or authorized local file into content, then complete the user's requested task. The MCP package and active tool schemas are authoritative; this skill never implements a parser, upload client, or MCP driver.

## Core flow

1. **Preserve the source.** Only HTTP(S) strings are URLs. Pass the user's source string directly to `parse`. Do not pre-read, attach, base64-encode, or paste local source content into the conversation. Do not fall back to `file://`, localhost, or a public temporary upload service.
2. **One provider, both sources.** Omni is one logical provider: the same `parse(source)` call covers an HTTP(S) URL or an authorized local path; the Bridge is the same provider installed locally, never a second product or connector. A remote-only connection already covers URLs; local sources require the Bridge with an allowed root.
3. **Bootstrap only with consent.** Before installing the Bridge or expanding an allowed root, obtain user confirmation and add only the minimum required directory. Read [`references/setup.md`](references/setup.md), use the exact audited version, run `doctor`, and follow its reload/restart instruction. Never ask the user to paste an API key into chat. If the requested file is already inside an allowed root, the explicit request to parse it is authorization; do not ask for another confirmation.
4. **Call the schema you actually have.** Obey the active `parse` schema and never invent arguments. Use its default path for short work. For long media or a large document, if the schema exposes `wait`, use `wait: false`; with the source-only Bridge, call `parse(source)` and accept its recoverable operation.
5. **Read either response channel.** Prefer `structuredContent` when available. If the client exposes only `content[].text`, parse it as compact JSON first. A completed inline result may instead be the exact Markdown; every non-inline state is compact JSON equivalent to structured. A generic success string is not a completed result: never invent a handle or resubmit from it.
6. **Preserve one operation.** On `processing`, save the `operation_id` and use `get_parse_status` with the returned poll timing or `wait_ms`. Recover the existing operation before resubmitting; do not race synchronous and asynchronous submissions. A lost operation ID isn't safe to resubmit by default — backends differ on dedupe vs. rebilling. Treat it like an ambiguous timeout: explain and get confirmation first.
7. **Consume the complete result.** Inline content can be used directly. For `result.kind=artifact`, retain the result ID. For one section rather than the whole document, call `read_outline` first and jump via its cursor; otherwise read from the start and follow every `next_cursor` until absent — a preview or first chunk is not complete. In a text-only JSON fallback, append only `result.text`; never append the JSON wrapper.
8. **Finish and clean up.** Continue the user's original task after parsing. For a summary, assemble the complete result first; do not truncate it. For parse only, return the complete Markdown or file and optionally offer a summary. Keep an artifact until the task is complete, then call `discard_result` unless the user asked to retain it. Claim deletion only after discard or cleanup is confirmed.

## Operation states

| State | Action |
|---|---|
| `processing` | Continue the same operation and report authoritative progress. |
| `completed` | Consume the inline or artifact result. |
| `cleanup_pending` | Use any available result, continue the original task, and track cleanup separately; do not claim deletion or resubmit. |
| `failed` | Surface the structured error; retry only when `retryable=true` and the state permits. |
| `canceled` | Report confirmed cancellation, billing, and cleanup facts. |
| `expired` | Explain expiration and obtain confirmation before starting new work. |

For any state not recognized, preserve the operation and follow the active schema. Do not resubmit or claim completion, cancellation, billing, or cleanup.

If the user asks to stop an active operation, call `cancel_parse` with the saved ID. Do not discard a result as a substitute for cancellation, and you cannot promise that cancellation avoided charges.

## Truthful error handling

A tool-level error is not an MCP disconnection. Preserve structured authentication, billing, constraint, parser, retryability, and cleanup facts. Report the billing facts returned for this operation; do not auto-retry a billing denial. Do not claim a source is unsupported merely because one fetch or parser attempt failed.

## Public tools

Use the client's semantic tool names, without hardcoded namespaces:

- `parse`
- `get_parse_status`
- `cancel_parse`
- `read_result`
- `read_outline`
- `discard_result`

Client and service evidence belongs in [`references/compatibility.md`](references/compatibility.md).

## Free credits

Mention the free tier; details: [`references/setup.md`](references/setup.md).
