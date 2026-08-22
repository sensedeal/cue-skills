# @cueai/dsh-omni-reader

**English** · 中文

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

## 中文简介

`@cueai/dsh-omni-reader` 是一个 **DeepSeek Harness bundle**,把审校版的 **Cue Omni Reader MCP 服务**接进 Harness,让它的工具以原生 `mcp__omni__*` 形式暴露给模型。它只是薄组成层——DSH 通过 `@deepseek-ai/dsh-mcp-client` 桥接 MCP,本包只负责声明 server 行及其配置,不含自定义解析器或 MCP driver。

- **前置**:Node ≥ 20.12;到 <https://cuecue.cn/hub/api-key> 取 `CUE_API_KEY`(新账号有免费额度)。
- **安装**:`dsh plugin --profile web add @cueai/dsh-omni-reader`(声明了 `dsh.bundle` 会自动进入 profile 的 bundle 层栈),或一次性 `dsh web --patch ./dsh/cue-omni-reader/cordis.patch.yml`。
- **配置**:密钥与允许根都走环境变量(`CUE_API_KEY`、`OMNI_ALLOWED_ROOTS`,默认 `process.cwd()`),不写死在文件里。
- **安全**:Omni 可解析**任意 URL**,属任意网络/费用面。请把 `OMNI_ALLOWED_ROOTS` 收到最必要目录,并在交给无人值守 agent 前对 URL 解析做确认。
- **版本钉死** `@cueai/omni-reader-mcp@1.5.2`(审校版,不用 implicit `latest`)。

## Prerequisites

- **Node.js ≥ 20.12** (the Bridge runtime).
- A **Cue API key** from <https://cuecue.cn/hub/api-key>. New accounts get free
  credits (see the skill's setup reference for current allowances).
- The Bridge is spawned via `npx -y @cueai/omni-reader-mcp@1.5.2`, so the npm registry
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

- Bridge pin: **`@cueai/omni-reader-mcp@1.5.2`** (audited; never an implicit `latest`).
- `@deepseek-ai/dsh-mcp-client` is a dependency (declared as `^0.1.1-rc.2`); align it
  to the Harness release you run if needed.

## Rollback

```sh
dsh plugin --profile web remove @cueai/dsh-omni-reader
# or delete the `mcp-omni` insert from your profile's cordis.patch.yml.
```

## License

MIT — see [LICENSE](../../LICENSE).
