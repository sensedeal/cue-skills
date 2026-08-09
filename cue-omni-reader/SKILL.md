---
name: cue-omni-reader
description: "Use when the user wants an external AI agent to parse or understand an HTTP(S) URL or an authorized local document, audio, or video source through Cue Omni Reader."
license: MIT
metadata:
  version: "0.1.0"
  requires:
    bins: ["node"]
  envOptional: ["CUE_API_KEY"]
---

# Cue Omni Reader

Use the official Omni MCP surface to turn a URL or authorized local file into content, then complete the user's requested summary, extraction, comparison, or question-answering task. The MCP package and active tool schemas are authoritative; this skill never implements a parser, upload client, or MCP driver.

## Core flow

1. **Preserve the source.** Only HTTP(S) strings are URLs. Pass the user's source string directly to `parse`. Do not pre-read, attach, base64-encode, or paste local source content into the conversation. Do not fall back to `file://`, localhost, or a public temporary upload service.
2. **Use an available official Omni tool first.** A URL does not require local Bridge installation when a suitable remote Omni tool is already connected. A local source requires the official Bridge and an allowed root.
3. **Bootstrap only with consent.** Before installing the Bridge or expanding an allowed root, obtain user confirmation and add only the minimum required directory. Read [`references/setup.md`](references/setup.md), use the exact audited version, run `doctor`, follow its reload or restart instruction, and verify the five public tools are visible. Never ask the user to paste an API key into chat. If the requested file is already inside an allowed root, the explicit request to parse it is authorization; do not ask for another confirmation.
4. **Call the schema you actually have.** Obey the active `parse` schema and never invent arguments. Use its synchronous/default path for an ordinary short page or document. For long media, long audio, a large document, or a short client timeout: if the schema exposes `wait`, use `wait: false`; with the source-only Bridge, call `parse(source)` and accept its recoverable processing operation after the foreground budget.
5. **Preserve one operation.** On `processing`, save the `operation_id` and use `get_parse_status` with the returned poll timing or supported `wait_ms`. Recover the existing operation before resubmitting after interruption. Do not race synchronous and asynchronous submissions. After an ambiguous timeout with no recoverable operation, explain possible duplicate work or billing and obtain confirmation before creating a replacement.
6. **Consume the complete result.** Inline content can be used directly. For `result.kind=artifact`, retain the result ID, call `read_result`, append chunks in order, and follow every `next_cursor` until absent. A preview or first chunk is not the complete result.
7. **Finish and clean up.** Continue the user's original task after parsing. Keep an artifact until that task is complete, then call `discard_result` unless the user asked to retain it. Claim deletion only after discard or cleanup is confirmed.

## Operation states

| State | Action |
|---|---|
| `processing` | Continue the same operation and report authoritative progress. |
| `completed` | Consume the inline or artifact result. |
| `cleanup_pending` | Use any available result, continue the original task, and track cleanup separately; do not claim deletion or resubmit. |
| `failed` | Surface the structured error; retry only when `retryable=true` and the state permits. |
| `canceled` | Report confirmed cancellation, billing, and cleanup facts. |
| `expired` | Explain expiration and obtain confirmation before starting new work. |

For any state not recognized here, preserve the existing operation and follow the active schema and structured response. Do not resubmit or claim completion, cancellation, billing, or cleanup.

If the user asks to stop an active operation, call `cancel_parse` with the saved ID. Do not discard a result as a substitute for cancellation, and you cannot promise that cancellation avoided charges.

## Truthful error handling

A tool-level error is not an MCP disconnection. Preserve structured authentication, billing, constraint, parser, retryability, and cleanup facts. Report the billing facts returned for this operation; do not auto-retry a billing denial. Do not claim a source is unsupported merely because one fetch or parser attempt failed.

## Public tools

Use the semantic tool names exposed by the client, without hardcoded client namespaces:

- `parse`
- `get_parse_status`
- `cancel_parse`
- `read_result`
- `discard_result`

Mutable client and service evidence belongs in [`references/compatibility.md`](references/compatibility.md), not in permanent routing rules.
