# Cue Omni Reader compatibility

- Skill version: `0.5.0`
- Bridge version: `1.7.3`
- Evidence date: 2026-08-11 (Bridge 1.2.0 pin: 2026-08-14; Bridge 1.2.1 pin: 2026-08-14; Bridge 1.2.2 pin: 2026-08-15; Bridge 1.3.0 pin: 2026-08-17; Bridge 1.3.1 pin: 2026-08-18; Bridge 1.3.2 pin: 2026-08-18; Bridge 1.3.3 pin: 2026-08-18; Bridge 1.4.0 pin: 2026-08-19; Bridge 1.4.1 pin: 2026-08-19; I1 parameter-unification sync: 2026-08-20; Bridge 1.5.0 pin: 2026-08-20; Bridge 1.5.1 pin: 2026-08-20; Bridge 1.5.2 pin: 2026-08-21; Skill 0.3.5 stage-aware diagnostics correction: 2026-08-24; Bridge 1.5.5 pin: 2026-08-26; Bridge 1.6.0 pin and release acceptance: 2026-08-30; Bridge 1.7.1 guidance fix, exact admission, and publication: 2026-09-04; Bridge 1.7.2 pin: 2026-09-06; Bridge 1.7.3 pin: 2026-09-08)

## Tool-surface boundary

The local Bridge exposes a source-only `parse(source)` schema and automatically returns a recoverable operation after its foreground budget. Other official Omni surfaces may expose `wait`; the agent must inspect the active schema and use `wait: false` for timeout-prone work only when that field exists.

## Release history

Current: **Bridge 1.7.3** — metadata-only release: the package `license` field is corrected `UNLICENSED` → `MIT` and the version advances `1.7.2` → `1.7.3` (npm will not republish an existing version with changed content, so the fix ships as a new patch). No tool-surface or parsing change. The trusted managed-entry pair advances to **1.7.2 / 1.7.3**; the only bare-`npx` Windows migration exception remains 1.5.1. See the [1.7.3 publication report](../docs/verification-reports/2026-09-08-bridge-1.7.3-published.md).

The wire contract has been stable since 1.2.0: strict `structuredContent` with the 1.1.3 traditional-text channel for clients that hide it; completed inline parses return exact Markdown, and processing / artifact / cleanup / cancellation / expiration / failure / `read_result` / `discard_result` return compact JSON in `content[].text` (artifact consumers append only each `result.text` and follow every `next_cursor`). See the [content-only compatibility report](../docs/verification-reports/2026-08-11-content-only-compat.md).

| Bridge | Date | One-line change | Report |
|---|---|---|---|
| 1.7.3 | 2026-09-08 | `license` `UNLICENSED` → `MIT` (metadata only) | [report](../docs/verification-reports/2026-09-08-bridge-1.7.3-published.md) |
| 1.7.2 | 2026-09-06 | local extension allowlist catches up (`rar`/`tar`/`tgz`/`gz`/`bz2`; `tsv`/`json`/`yaml`/`yml`/`toml`/`xml`/`ini`/`cfg`/`conf`/`log`; RDF; FreeMind); `parquet`/`xmind`/`mmap` stay unsupported | [report](../docs/verification-reports/2026-09-06-bridge-1.7.2-published.md) |
| 1.7.1 | 2026-09-04 | non-circular `BRIDGE_UPGRADE_REQUIRED` guidance | [report](../docs/verification-reports/2026-09-04-bridge-1.7.1-published.md) |
| 1.7.0 | 2026-09 | operation-local billing transparency | — |
| 1.6.0 | 2026-08-30 | `result_delivery="artifact"`, outline-before-save, signed cursors, MSYS normalization, journal v4 | [report](../docs/verification-reports/2026-08-30-bridge-1.6.0-published.md) |
| 1.5.5 | 2026-08-26 | secure-upload wording without an internal name | [report](../docs/verification-reports/2026-08-26-bridge-1.5.5-published.md) |
| 1.5.2 | 2026-08-21 | Windows `cmd /d /c npx` spawn fix + auto-migration | — |
| 1.5.1 | 2026-08-20 | `billed` strictly from settlement facts | — |
| 1.5.0 | 2026-08-20 | remote-compatible `url` parse alias | — |
| 1.4.1 | 2026-08-19 | document the `save_result` seventh tool | [report](../docs/verification-reports/2026-08-19-bridge-1.4.1-published.md) |
| 1.4.0 | 2026-08 | add `save_result` (seventh tool) | — |
| 1.3.3 | 2026-08-18 | README URL/Bridge framing; consent before transcoding | [report](../docs/verification-reports/2026-08-18-bridge-1.3.3-published.md) |
| 1.3.2 | 2026-08-18 | surface bare `UNSUPPORTED_SOURCE` | [report](../docs/verification-reports/2026-08-18-bridge-1.3.2-published.md) |
| 1.3.1 | 2026-08-18 | accept `omni.parse_grant.v2` | [report](../docs/verification-reports/2026-08-18-bridge-1.3.1-published.md) |
| 1.3.0 | 2026-08-17 | add `read_outline`; URL-result local hydration | [report](../docs/verification-reports/2026-08-17-bridge-1.3.0-published.md) |
| 1.2.2 | 2026-08-15 | config-transaction hardening | [report](../docs/verification-reports/2026-08-15-bridge-1.2.2-published.md) |
| 1.2.1 | 2026-08-14 | credits README section + Hub api-key URL | [report](../docs/verification-reports/2026-08-14-bridge-1.2.1-published.md) |
| 1.2.0 | 2026-08-14 | strict `structuredContent` + traditional-text channel | [report](../docs/verification-reports/2026-08-14-bridge-1.2.0-published.md) |

Per-release evidence lives in `docs/verification-reports/`.

Long-video handling is a duration and recoverability rule, not a hostname rule. A Bilibili or other public-video URL may be used as a release fixture, but resolved site incidents do not become permanent routing instructions.

## Client support

cue-omni-reader needs **no client-specific integration**. It is a **standard agent skill** driving a **standard MCP server** — the local stdio Bridge (`npx -y @cueai/omni-reader-mcp`) or the remote streamable-http Omni surface — so **any agent or coding CLI works**: anything that loads a standard skill file and connects a standard MCP server supports it out of the box. That covers Claude Code, Codex CLI, Gemini CLI, Hermes, WorkBuddy, and DeepSeek Harness — which additionally ships a first-party bundle so the tools surface natively — plus any other standard client.

The per-client evidence table below records what has been exercised. A client absent from it is **not** "unsupported" — it simply has not been individually written up.

## Client evidence

| Client | Skill loading evidence | URL orchestration | Local Bridge bootstrap | Evidence level |
|---|---|---|---|---|
| Claude Code | exact text passed instruction contexts; native ephemeral project discovery plus model-selected `Skill` activation simulated verified | simulated verified | simulated verified | [report](../docs/verification-reports/2026-08-08-claude-code.md); live unverified |
| Codex CLI | exact text passed instruction contexts; JSONL recorded a read of the exact `.agents/skills/cue-omni-reader/SKILL.md` file before answering, without establishing discovery, loading, selection, activation, or how the file was reached | simulated verified | root-expansion only; install/doctor bootstrap unverified | [report](../docs/verification-reports/2026-08-08-codex-cli.md); live unverified |
| Gemini CLI | exact text passed four instruction-text contexts; native project discovery plus model-selected `activate_skill` simulated verified in an ephemeral workspace | simulated verified | simulated verified | [report](../docs/verification-reports/2026-08-08-gemini-cli.md); live unverified |
| Hermes | exact text passed four instruction-text contexts; native explicit preload through `hermes chat` with `--skills` simulated verified in an ephemeral profile | simulated verified | simulated verified | [report](../docs/verification-reports/2026-08-08-hermes.md); live unverified |
| WorkBuddy | standard agent skill — no client-specific text injection required | verified | published Bridge package/config/stdio path verified | verified (owner-attested); [historical report](../docs/verification-reports/2026-08-08-workbuddy.md); [1.6.0 release report](../docs/verification-reports/2026-08-30-bridge-1.6.0-published.md) |
| DeepSeek Harness | standard agent skill; first-party bundle `@cueai/dsh-omni-reader` wires the MCP so tools surface natively | verified | verified (published bundle) | verified (owner-attested); [`dsh/`](../../dsh) |

Claude Code native project discovery and model-selected `Skill` activation are simulated verified only in an ephemeral project copy.

Codex CLI evidence is limited to JSONL recording a read of the exact `.agents/skills/cue-omni-reader/SKILL.md` project file before answering; it does not establish a client activation event.

Gemini native project discovery plus `activate_skill` is simulated verified only in an ephemeral project copy. Hermes native user-selected explicit preload is simulated verified only through the `chat` subcommand. WorkBuddy and DeepSeek Harness are verified as standard agent skill + MCP clients (owner-attested). The generic support above stands for every standard client, so a client without a per-client write-up is not thereby unsupported.

The installed Hermes Agent v0.20.0 build 2026.8.3, source commit [`01a1037d1e6d7b6eb96a786ef282c3aea4818194`](https://github.com/NousResearch/hermes-agent/commit/01a1037d1e6d7b6eb96a786ef282c3aea4818194), has a version-specific implementation defect: the [top-level one-shot dispatcher](https://github.com/NousResearch/hermes-agent/blob/01a1037d1e6d7b6eb96a786ef282c3aea4818194/hermes_cli/main.py#L12541-L12550) omits the skills argument, while the [`chat` path](https://github.com/NousResearch/hermes-agent/blob/01a1037d1e6d7b6eb96a786ef282c3aea4818194/cli.py#L18101-L18146) applies explicit preload. Thus top-level `hermes -z --skills` bypasses preload in that build. This is not a general Hermes CLI contract; use `hermes chat --skills <name> -q <prompt>` for explicit preload verification.

Bridge setup flags, native-adapter source, and trusted rollback semantics are [package-source verified](../docs/verification-reports/2026-08-08-bridge-cli-audit.md); no persistent native-client configuration write has been verified for this skill release.

`simulated` means an agent was pressure-tested with described tool states or responses but no production parse occurred. `live` means the named client drove the real service and the report records billing, result, and cleanup outcomes. Never promote one level to the other.

## Known compatibility boundary

A client-side synchronous timeout does not prove backend failure. If no operation is recoverable, a replacement submission may duplicate work or billing and requires confirmation. The source-only Bridge avoids unsupported `wait` arguments; tool surfaces that publish `wait` may select the asynchronous path explicitly.

Pure-music or otherwise speech-free audio can be transcribed as speech-like dialogue: the parse chain has no music/VAD gate, so an instrumental track may return hallucinated speaker turns (observed 2026-08-22 with SoundHelix fixtures on WorkBuddy). Treat transcripts of expected-music sources as unreliable — confirm the audio actually contains speech before citing its transcript.

## I1 parameter unification (2026-08-20 sync)

Owner-decided unification of the two parse surfaces (the remote omni-reader MCP and the Bridge):

- **`url` alias**: the Bridge `parse` now accepts exactly one of `source` or `url` (identical constraints, enforced — sending both is `INVALID_TOOL_ARGUMENTS`). Agents holding the remote schema (which offers `url`/`output`/`wait`) can call either surface without argument errors. `output` and `wait` remain remote-only by design — the Bridge never advertises them.
- **`detail` on the remote**: the remote `parse` accepts the Bridge's `detail`. `text` (or omitted) forwards unchanged; `grounded`/`layout` fails closed with `UNSUPPORTED_DETAIL` (`failure_scope=local_capability`) before any operation is created — the remote produces markdown output only and never silently downgrades a requested representation.
- **Failed wire shape**: the remote now serves `{status:"failed", error:{...}}` — the same shape the Bridge has always spoken (the previous flat envelope is superseded). Envelope fields (`ok`/`code`/`failure_scope`/`retryable`/`billed`/`parser_started`/`operation_created`…) are shared.
- **Operation-id shape**: `get_parse_status`/`cancel_parse` validate ids as `op_` + 16–64 base64url chars; anything else returns the closed `INVALID_OPERATION_ID` envelope without touching the store.
- **Artifact boundary**: `read_result`/`read_outline`/`discard_result`/`save_result` are Bridge-local; the remote surface does not expose them, and its tool descriptions now say so.

Landed as omni-reader !691 (Bridge, merged to `test`) and cube-mcp !374 → dgts → !375 → master, deployed as cube-mcp 1.5.32; the Bridge npm release carrying the `url` alias follows the normal publish flow.

## Updating this file

For every client run, link a scrubbed report under `docs/verification-reports/`, record the exact skill and Bridge versions, and mark whether each path was simulated or live. Record per-client runs where available, but do **not** treat an absent client as unsupported: the support basis is standard `SKILL.md` + standard MCP conformance, so any conforming agent or coding CLI works without a per-client write-up.
