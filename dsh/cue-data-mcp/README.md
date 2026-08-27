# @cueai/dsh-cue-data-mcp

**[English](https://github.com/sensedeal/cue-skills/blob/main/dsh/cue-data-mcp/README.md)** · [中文](https://github.com/sensedeal/cue-skills/blob/main/dsh/cue-data-mcp/README.zh-CN.md)

A [DeepSeek Harness](https://github.com/deepseek-harness) **bundle** that exposes
Cue's public **data** MCP services as native `mcp__cue_<domain>__*` tools in any
Harness profile. Each live data domain is wired as one
[`@deepseek-ai/dsh-mcp-client`](https://github.com/deepseek-harness) instance
(`transport: streamable-http`) against Cue's own endpoints — no SSRF guard needed,
the URLs are fixed Cue endpoints and the tool set is the data surface.

15 live domains / **~104 tools** (as of 2026-08-24): regulatory (OFAC/EU/BIS, 11),
China regulatory (16), macro (15), US disclosures SEC EDGAR (5), CN disclosures (5),
statute full text (3), institutional (2), entity data (2), academic (3), fact index (4),
IPO (9), ESOP (10), buyback (2), footnote (14), margin (3).
`omni-reader` is excluded — it has its own dedicated `cue-omni-reader` skill.

## Install

```sh
dsh plugin --profile web add @cueai/dsh-cue-data-mcp
# or one-off
dsh web --patch ./dsh/cue-data-mcp/cordis.patch.yml
```

## Configure

Only one credential is needed — env-driven:

```sh
# $DSH_HOME/.env (or export before launching dsh)
CUE_API_KEY=sk-...     # from https://cuecue.cn/hub/api-key
```

Each server sends `Authorization: Bearer $CUE_API_KEY` and the streamable-http
`Accept` header.

## Usage

After a restart the model sees `mcp__cue_<domain>__*` per domain (e.g.
`mcp__cue_regulatory__*`, `mcp__cue_macro__*`, `mcp__cue_ipo__*`). Discover the
live tool names with `tools/list` per endpoint; call them with `tools/call`.

## Verify

```sh
dsh --profile web --dump-config     # should list 15 `mcp-cue_*` rows
# then in a session confirm the mcp__cue_* tools and a small data call succeed.
```

## Security & scope

- Requires `CUE_API_KEY`; the model can query Cue's data tool set but the endpoints
  are Cue-owned and fixed, so there is no arbitrary egress/SSRF surface.
- Never put the key in chat, command arguments, this file, logs, or generated JSON.
- The data endpoints are `streamable-http`; DSH bridges them with
  `@deepseek-ai/dsh-mcp-client` (peer dependency, `^0.1.1-rc.2`).

## Versioning / Rollback

- `@deepseek-ai/dsh-mcp-client` is a **peer** dependency (Harness profile provides it).
- Roll back: `dsh plugin --profile web remove @cueai/dsh-cue-data-mcp`.

## License

MIT — see [LICENSE](../../LICENSE).
