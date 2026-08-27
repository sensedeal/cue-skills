# DSH 组合包

**中文** · [English](README.md)

本目录存放 **DeepSeek Harness (DSH) 组合包(bundle)** —— 装入 DSH profile 后,把 Cue 的能力(或任意外部 MCP server)以原生工具形式暴露给 Harness 的小型组成包。

不要混淆本仓库的两类产物:

| 类型 | 位置 | 是什么 | 如何加载 |
|---|---|---|---|
| **Skill** | 顶层目录(`cue-omni-reader/`、`cue-buddy/`…) | 可被 agent 加载的*指令包*(`SKILL.md`) | agent 按需读 `SKILL.md` |
| **DSH bundle** | `dsh/<name>/` | 一个组成包(`package.json` + `cordis.patch.yml`),负责**把 MCP server 接进来** | 在 DSH profile 里暴露为 `mcp__<server>__*` |

bundle 声明 `dsh.bundle.patch`;`dsh plugin` 识别后会自动加入 profile 的 bundle 层栈。DSH 自己桥接 MCP server(`@deepseek-ai/dsh-mcp-client`),所以 bundle 很薄:只声明 server 行与其配置,不含解析器、协议驱动或 MCP client。

> 安装、配置与排障见 [usage.md](usage.md)(EN)·[中文](usage.zh-CN.md)。

## 组合包列表

| Bundle | 作用 | 包名 |
|---|---|---|
| [`cue-omni-reader/`](cue-omni-reader) | 接入审校版 **Cue Omni Reader** MCP server → 工具 `mcp__omni__parse`、`…read_result`、`…save_result` 等 | `@cueai/dsh-omni-reader` |
| [`cue-omni-reader-guard/`](cue-omni-reader-guard) | 可选加固:`tools/pre-execute` 护栏,拒绝 SSRF(私网/保留主机),并对 `mcp__omni__parse` 施加白名单/同意 | `@cueai/dsh-omni-reader-guard` |
| [`cue-data-mcp/`](cue-data-mcp) | 把 Cue 的**公开数据** MCP 服务(制裁/监管/宏观/披露/法规/持仓/主体/学术/IPO/ESOP/回购/脚注/事实索引…)以原生 `mcp__cue_<domain>__*` 暴露(15 域 / ~104 工具,streamable-http) | `@cueai/dsh-cue-data-mcp` |

## 安装与使用

```sh
# 装入 profile(自动加入 bundle 层栈;要求包可解析——已注册、git 或本地路径)
dsh plugin --profile web add @cueai/dsh-omni-reader

# 或一次性应用 patch(不打成包)
dsh web --patch ./dsh/cue-omni-reader/cordis.patch.yml
```

重启后模型即见 `mcp__omni__*`;每个 bundle 的 `README.md` 里有前置(`CUE_API_KEY`、`OMNI_ALLOWED_ROOTS`)与安全说明。

## 新增一个 bundle

新建 `dsh/<name>/`,内含 `package.json`(声明 `dsh.bundle.patch` + server 插件作为依赖)与对应的 `cordis.patch.yml`。跑 `python3 scripts/verify_dsh_bundles.py`(及 CI 门禁)校验。
