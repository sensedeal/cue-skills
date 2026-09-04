---
name: cue-omni-reader
description: "Use when the user wants an external AI agent to parse or understand an HTTP(S) URL or an authorized local document, audio, or video source through Cue Omni Reader."
license: MIT
metadata:
  version: "0.5.0"
  requires:
    bins: ["node"]
  envOptional: ["CUE_API_KEY"]
---

# Cue Omni Reader

> 中文版见 [`SKILL.zh-CN.md`](SKILL.zh-CN.md) — complete Chinese translation.

Use official Omni MCP tools to parse the source, then complete the user's task. The MCP package and active tool schemas are authoritative; this skill has no parser or protocol driver.

## Core flow

1. **Preserve the source.** Only HTTP(S) strings are URLs. Pass the user's source string directly to `parse`. Do not pre-read or base64-encode local content; never use `file://`, localhost, or a public temporary upload service.
2. **One provider, one first call.** Use `parse` as the only first call for both HTTP(S) URLs and local paths; do not ask the user to choose a local, remote, upload, or URL mode. Bridge is the same provider; remote-only cannot read local files.
3. **Bootstrap only with consent.** Before installing the Bridge or expanding an allowed root, obtain user confirmation and add only the minimum required directory. Follow [`references/setup.md`](references/setup.md)'s exact pin, run `doctor`, then reload/restart. Never ask for an API key in chat. If already inside an allowed root, do not ask for another confirmation.
4. **Call the active schema.** Obey the active `parse` schema. If the schema exposes `wait`, use `wait: false` for long media or a large document; the source-only Bridge returns a recoverable operation. Send one of `source`/`url`. `grounded`/`layout` are Bridge-local; remote `UNSUPPORTED_DETAIL` is final. Do not race synchronous and asynchronous submissions.
5. **Read either response channel.** Prefer `structuredContent` when available; if only `content[].text` exists, parse compact JSON. Completed inline content may be exact Markdown; non-inline states are compact JSON. A generic success is not a completed result. Append only `result.text`; never append the JSON wrapper.
6. **Preserve one operation.** On `processing`, save the `operation_id` and poll `get_parse_status` at the returned timing/`wait_ms`. Recover the existing operation before resubmitting. A lost ID is an ambiguous timeout; explain duplicate-work/billing risk and get confirmation.
7. **Choose continuation and delivery automatically.** Choose continuation tools from the structured result; never present the tool list as a menu for the user. Use this decision table:

   ```text
   Answer directly → inline when present; otherwise `read_result`
   Find one section → `read_outline` → `read_result(cursor)`
   Read all content → `read_result` until no `next_cursor`
   Deliver a file → `save_result`
   ```

   Use `result_delivery="artifact"` for saving, section navigation, multiple documents, or strict context control. For `result.kind=artifact`, the preview is not complete; read until `next_cursor` is absent. `read_outline` does not require `save_result`. Text output is Markdown and may retain headings, lists, GFM tables, or raw HTML tables; it lacks grounding/layout sidecars, not all structure. An empty outline means no recognized headings, not that the text has no structure. For multiple sources, use bounded concurrent independent `parse` calls and keep handles separate.
8. **Finish and clean up.** Continue the user's original task after parsing. For a summary, assemble the complete result first; do not truncate. For parse only, return complete Markdown or a file and optionally offer a summary. Keep artifacts through the task, then `discard_result` unless retained. Claim deletion only after discard or cleanup is confirmed.

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

Same-source retries reuse only recoverable or retained-completed records; failed, canceled, expired, or out-of-window retries may create and bill a new operation. On a reusable record, `auto`→`artifact` strengthens delivery without a second operation. If the user asks to stop an active operation, call `cancel_parse` with the saved ID. Discard is not cancellation; you cannot promise cancellation avoided charges.

## Unknown client capabilities

Classify Tasks, Roots, host timeout, and cwd/workspace only from direct client evidence, never from a successful parse.

- **Tasks unknown** → use ordinary `parse` plus bounded `get_parse_status` polling.
- **Roots unknown** → use process cwd and explicit roots only.
- **Host timeout unknown** → preserve Bridge's bounded 20-second status wait.
- **Cwd/workspace unknown** → do not widen authorization or guess the active workspace.

## Truthful error and billing handling

A tool-level error is not an MCP disconnection. Preserve authentication, billing, parser, retryability, operation, and cleanup facts. Report billing facts returned for this operation; retry only when `retryable=true`. Never estimate charges or rates.

Run `npx -y @cueai/omni-reader-mcp@1.7.1 doctor --json` first. `CUBE_UNAVAILABLE` is pre-upload control-plane failure; post-grant failure is secure upload stage; `CUBE_PROTOCOL_ERROR` is contract mismatch. Use reported facts only; never publish internal hosts or ports.

- `OMNI_NOT_ENTITLED` / HTTP 403 is the account-entitlement signal.
- `DIRECT_UPLOAD_DISABLED` (legacy) or `DIRECT_UPLOAD_UNAVAILABLE` means the direct-upload route/capability is unavailable, not that the account is disabled or text-only.
- `DETAIL_CAPABILITIES_UNAVAILABLE` means grounded/layout is not advertised; text remains Markdown and may retain headings, lists, and tables.
- `UNSUPPORTED_DETAIL` means the requested representation/profile is unavailable; do not retry unchanged or describe the account as text-only.
- `BRIDGE_UPGRADE_REQUIRED`: install the latest published `@cueai/omni-reader-mcp` release and retry once. If already running the latest published release, do not reinstall or retry; run `doctor --json` and ask the service operator to verify Bridge admission.

## Protocol boundary

Remote-only exposes exactly `parse`, `get_parse_status`, and `cancel_parse`. Bridge exposes the same three plus `read_result`, `read_outline`, `discard_result`, and `save_result`. Only `parse` is a first call; the other six are continuation and lifecycle primitives, not user modes. Artifact tools stay Bridge-local. Evidence: [`references/compatibility.md`](references/compatibility.md).

## Granted credits

New users can try Omni; current policy comes from the live server and `doctor`. Details: [`references/setup.md`](references/setup.md).
