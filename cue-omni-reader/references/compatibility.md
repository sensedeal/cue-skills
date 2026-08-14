# Cue Omni Reader compatibility

- Skill version: `0.1.1`
- Bridge version: `1.2.1`
- Evidence date: 2026-08-11 (Bridge 1.2.0 pin: 2026-08-14)

## Tool-surface boundary

The local Bridge exposes a source-only `parse(source)` schema and automatically returns a recoverable operation after its foreground budget. Other official Omni surfaces may expose `wait`; the agent must inspect the active schema and use `wait: false` for timeout-prone work only when that field exists.

Bridge 1.2.0 preserves the authoritative strict `structuredContent` contract and the 1.1.3 traditional-text channel for clients that hide it. Completed inline parses return exact Markdown. Processing, artifact, cleanup, cancellation, expiration, failure, `read_result`, and `discard_result` return compact JSON in `content[].text`; artifact consumers append only each `result.text` and follow every `next_cursor`. This behavior is covered by the local [content-only compatibility report](../docs/verification-reports/2026-08-11-content-only-compat.md). 1.2.1 keeps that contract and adds the free-credits README section and the Hub api-key URL; it is published and `latest` on npm.

Long-video handling is a duration and recoverability rule, not a hostname rule. A Bilibili or other public-video URL may be used as a release fixture, but resolved site incidents do not become permanent routing instructions.

## Client evidence

| Client | Skill loading evidence | URL orchestration | Local Bridge bootstrap | Evidence level |
|---|---|---|---|---|
| Claude Code | exact text passed instruction contexts; native ephemeral project discovery plus model-selected `Skill` activation simulated verified | simulated verified | simulated verified | [report](../docs/verification-reports/2026-08-08-claude-code.md); live unverified |
| Codex CLI | exact text passed instruction contexts; JSONL recorded a read of the exact `.agents/skills/cue-omni-reader/SKILL.md` file before answering, without establishing discovery, loading, selection, activation, or how the file was reached | simulated verified | root-expansion only; install/doctor bootstrap unverified | [report](../docs/verification-reports/2026-08-08-codex-cli.md); live unverified |
| Gemini CLI | exact text passed four instruction-text contexts; native project discovery plus model-selected `activate_skill` simulated verified in an ephemeral workspace | simulated verified | simulated verified | [report](../docs/verification-reports/2026-08-08-gemini-cli.md); live unverified |
| Hermes | exact text passed four instruction-text contexts; native explicit preload through `hermes chat` with `--skills` simulated verified in an ephemeral profile | simulated verified | simulated verified | [report](../docs/verification-reports/2026-08-08-hermes.md); live unverified |
| WorkBuddy | historical source-artifact provenance only; exact official text not injected | prior authorized async behavior observed; not release acceptance | unverified | [report](../docs/verification-reports/2026-08-08-workbuddy.md); official v0.1.0 loading remains unverified, so its client-specific release claim remains blocked |

Claude Code native project discovery and model-selected `Skill` activation are simulated verified only in an ephemeral project copy.

Codex CLI evidence is limited to JSONL recording a read of the exact `.agents/skills/cue-omni-reader/SKILL.md` project file before answering; it does not establish a client activation event.

Gemini native project discovery plus `activate_skill` is simulated verified only in an ephemeral project copy. Hermes native user-selected explicit preload is simulated verified only through the `chat` subcommand. WorkBuddy official v0.1.0 native loading remains unverified. Persistent installation, unprompted automatic triggering, and live Omni behavior remain unverified on every client.

The installed Hermes Agent v0.20.0 build 2026.8.3, source commit [`01a1037d1e6d7b6eb96a786ef282c3aea4818194`](https://github.com/NousResearch/hermes-agent/commit/01a1037d1e6d7b6eb96a786ef282c3aea4818194), has a version-specific implementation defect: the [top-level one-shot dispatcher](https://github.com/NousResearch/hermes-agent/blob/01a1037d1e6d7b6eb96a786ef282c3aea4818194/hermes_cli/main.py#L12541-L12550) omits the skills argument, while the [`chat` path](https://github.com/NousResearch/hermes-agent/blob/01a1037d1e6d7b6eb96a786ef282c3aea4818194/cli.py#L18101-L18146) applies explicit preload. Thus top-level `hermes -z --skills` bypasses preload in that build. This is not a general Hermes CLI contract; use `hermes chat --skills <name> -q <prompt>` for explicit preload verification.

Bridge setup flags, native-adapter source, and trusted rollback semantics are [package-source verified](../docs/verification-reports/2026-08-08-bridge-cli-audit.md); no live client configuration write has been verified for this skill release.

`simulated` means an agent was pressure-tested with described tool states or responses but no production parse occurred. `live` means the named client drove the real service and the report records billing, result, and cleanup outcomes. Never promote one level to the other.

## Known compatibility boundary

A client-side synchronous timeout does not prove backend failure. If no operation is recoverable, a replacement submission may duplicate work or billing and requires confirmation. The source-only Bridge avoids unsupported `wait` arguments; tool surfaces that publish `wait` may select the asynchronous path explicitly.

## Updating this file

For every client run, link a scrubbed report under `docs/verification-reports/`, record the exact skill and Bridge versions, and mark whether each path was simulated or live. Leave unsupported or unavailable clients unverified rather than inferring compatibility.
