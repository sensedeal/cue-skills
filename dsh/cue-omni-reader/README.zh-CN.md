# @cueai/dsh-omni-reader

**中文** · [English](README.md)

一个 [DeepSeek Harness](https://github.com/deepseek-harness) **bundle**,把审校版的 **Cue Omni Reader** MCP server 接进 Harness,让它的工具以原生 `mcp__omni__*` 形式暴露给任何 harness profile。它是薄组成层——DSH 通过 `@deepseek-ai/dsh-mcp-client` 桥接 MCP;本包只负责声明 server 行及其配置,不含自定义解析器或 MCP driver。

工具能力:`parse` / `get_parse_status` / `cancel_parse` / `read_result` / `read_outline` / `discard_result` / `save_result` —— 把一个 HTTP(S) URL 或已授权的本地文档、音频、视频源转成内容。

> 面向 skill 的引导(同一能力,可被 agent 加载的指令包)在本仓库单独以 [`cue-omni-reader/`](../../cue-omni-reader) 发布。两者都装,才能既拿到工具**又**有引导流程。

## 前置条件

- **Node.js ≥ 20.12**(Bridge 运行时)。
- **Cue API key**:<https://cuecue.cn/hub/api-key>。新账号有免费额度(当前额度见 skill 的 setup 参考)。
- Bridge 通过 `npx -y @cueai/omni-reader-mcp@1.7.1` 拉起,所以 npm registry 需可达,或安装一个二进制在 `PATH` 上的版本。

## 安装

把 bundle 装入某个 profile(pnpm 管理;因为它声明了 `dsh.bundle`,会自动加入 profile 的 bundle 层栈):

```sh
dsh plugin --profile web add @cueai/dsh-omni-reader
# 或从本地 checkout / git spec:
dsh plugin --profile web add ./dsh/cue-omni-reader
```

一次性应用(不打成包):

```sh
dsh web --patch ./dsh/cue-omni-reader/cordis.patch.yml
```

## 配置

server 行的 env 由环境变量驱动(文件里不含密钥或绝对路径):

| Env | 含义 | 默认 |
|---|---|---|
| `CUE_API_KEY` | Cue Omni 凭据 | 必填——在 `$DSH_HOME/.env` 里设置,或在启动 dsh 前 export |
| `OMNI_ALLOWED_ROOTS` | Bridge 可读的 `:` 分隔绝对目录 | `process.cwd()`(dsh 工作目录) |

配置好 key(和可选根)后重启 dsh,让分层的 `.env`/config 生效:

```sh
# ~/.dsh/.env
CUE_API_KEY=sk-...
OMNI_ALLOWED_ROOTS=/home/you/workspace
```

## 使用

重启后模型可见:

```
mcp__omni__parse mcp__omni__get_parse_status mcp__omni__cancel_parse
mcp__omni__read_result mcp__omni__read_outline mcp__omni__discard_result
mcp__omni__save_result
```

用 `source`(URL 或在允许根内的路径)调 `mcp__omni__parse`,轮询 `mcp__omni__get_parse_status`,再消费结果。

## 验证

```sh
dsh --profile web --dump-config      # 应包含一个 `mcp-omni` 行
# 然后在会话里确认工具出现、一次小解析成功。
```

## 安全与范围

- Omni 可解析**任意 URL** —— 这是任意网络/出网面。把 `OMNI_ALLOWED_ROOTS` 收到 agent 真正需要的最小目录,并在把 URL 解析交给无人值守 agent 前征得同意。
- 本地文件读取受 `OMNI_ALLOWED_ROOTS` 约束;Bridge 在拉起子进程前会 scrubbing(清除)环境里像凭据的变量。
- 不要把 API key 放进聊天、命令参数、本文件、日志或生成的 JSON;一旦明文出现过就轮换它。

## 版本

- Bridge 固定:**`@cueai/omni-reader-mcp@1.7.1`**(审校版;永远不用隐式 `latest`)。
- `@deepseek-ai/dsh-mcp-client` 是 **peer** 依赖(声明为 `^0.1.1-rc.2`),由 Harness profile 提供;如需要,对齐到你所跑的 Harness 版本。

## 回滚

```sh
dsh plugin --profile web remove @cueai/dsh-omni-reader
# 或删除你 profile cordis.patch.yml 里的 `mcp-omni` insert。
```

## 许可

MIT — 见 [LICENSE](../../LICENSE)。
