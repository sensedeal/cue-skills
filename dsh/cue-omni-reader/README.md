# @cueai/dsh-omni-reader

**[English](https://github.com/sensedeal/cue-skills/blob/main/dsh/cue-omni-reader/README.md)** · [中文](https://github.com/sensedeal/cue-skills/blob/main/dsh/cue-omni-reader/README.zh-CN.md)

A [DeepSeek Harness](https://github.com/deepseek-harness) **bundle** that registers the
audited **Cue Omni Reader** MCP server so its tools surface as native `mcp__omni__*`
tools in any Harness profile. It is a thin composition layer — DSH exposes the tools
through `@deepseek-ai/dsh-mcp-client`; this bundle only wires the server row and its
configuration, and ships no custom parser or MCP driver.

What the tools do: `parse` / `get_parse_status` / `cancel_parse` / `read_result` /
`read_outline` / `discard_result` / `save_result` — turn an HTTP(S) URL or an
authorized local document, audio, or video source into content.

> The skill-facing guidance (same capability, agent-loadable instructions) ships
> separately in this repo as [`cue-omni-reader/`](../../cue-omni-reader). Install
> both to get the tools **and** the guided flow.

## Prerequisites

- **Node.js ≥ 20.12** (the Bridge runtime).
- A **Cue API key** from <https://cuecue.cn/hub/api-key>. New accounts get free
  credits (see the skill's setup reference for current allowances).
- The Bridge is spawned via `npx -y @cueai/omni-reader-mcp@1.5.5`, so the npm registry
  must be reachable, or pin an install whose binary is on `PATH`.

## Install

Install the bundle into a profile (pnpm-managed; it auto-joins the profile's
bundle stack because it declares `dsh.bundle`):

```sh
dsh plugin --profile web add @cueai/dsh-omni-reader
# or from a local checkout / git spec:
dsh plugin --profile web add ./dsh/cue-omni-reader
```

Alternative one-off apply (no package):

```sh
dsh web --patch ./dsh/cue-omni-reader/cordis.patch.yml
```

## Configure

The server row's env is env-driven (no secrets or absolute paths in this file):

| Env var | Meaning | Default |
|---|---|---|
| `CUE_API_KEY` | Cue Omni credential | required — set in `$DSH_HOME/.env` or export before launching dsh |
| `OMNI_ALLOWED_ROOTS` | `:`-separated absolute dirs the Bridge may read | `process.cwd()` (the dsh working dir) |

Set the key and (optionally) a root, then restart dsh so the layered `.env`/config
takes effect:

```sh
# ~/.dsh/.env
CUE_API_KEY=sk-...
OMNI_ALLOWED_ROOTS=/home/you/workspace
```

## Usage

After a restart the model sees:

```
mcp__omni__parse mcp__omni__get_parse_status mcp__omni__cancel_parse
mcp__omni__read_result mcp__omni__read_outline mcp__omni__discard_result
mcp__omni__save_result
```

Call `mcp__omni__parse` with a `source` (URL or an allowed-root path), poll
`mcp__omni__get_parse_status`, and consume the result.

## Verify

```sh
dsh --profile web --dump-config      # the tree should include an `mcp-omni` row
# then, in a session, confirm the tools appear and a small parse succeeds.
```

## Security & scope

- Omni can parse **any URL** — that is an arbitrary network / egress surface.
  Keep `OMNI_ALLOWED_ROOTS` to the minimum directories the agent actually needs,
  and give consent before exposing URL parsing to an unattended agent.
- Local file reads are bounded by `OMNI_ALLOWED_ROOTS`; the Bridge scrubs ambient
  credential-ish env before launching the child.
- Do not put the API key in chat, command arguments, this file, logs, or generated
  JSON. Rotate it if it ever appears in plaintext.

## Versioning

- Bridge pin: **`@cueai/omni-reader-mcp@1.5.5`** (audited; never an implicit `latest`).
- `@deepseek-ai/dsh-mcp-client` is a **peer** dependency (declared as `^0.1.1-rc.2`); the Harness profile provides it. Align it to the Harness release you run if needed.

## Rollback

```sh
dsh plugin --profile web remove @cueai/dsh-omni-reader
# or delete the `mcp-omni` insert from your profile's cordis.patch.yml.
```

## License

MIT — see [LICENSE](../../LICENSE).
