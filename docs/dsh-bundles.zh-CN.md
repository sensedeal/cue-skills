# DSH 组合包 —— 总览

**[English](dsh-bundles.md)** · [中文](dsh-bundles.zh-CN.md)

本仓库在 agent **skills** 之外,还提供一组 [DeepSeek Harness](https://github.com/deepseek-harness) **组合包(bundle)**,位于 [`dsh/`](../dsh):把 Cue(或任意外部)的 MCP server 接入 Harness profile,让它的工具以原生 `mcp__<server>__*` 形式暴露。

**skill** 是可被 agent 加载的*指令包*(`SKILL.md`);**bundle** 是*组合包*(`package.json` 声明 `dsh.bundle.patch` + 对应的 `cordis.patch.yml`)。`dsh plugin` 识别该 bundle 声明后会自动加入 profile 的 bundle 层栈。DSH 自己桥接 MCP server(`@deepseek-ai/dsh-mcp-client`),所以 bundle 只负责声明 server 行与其配置——不含解析器、协议驱动或 MCP client。

## 已提供的 bundle

| Bundle | 包名 | 作用 |
|---|---|---|
| [`cue-omni-reader`](../dsh/cue-omni-reader) | `@cueai/dsh-omni-reader` | 接入审校版 **Cue Omni Reader** MCP server → 工具 `mcp__omni__parse`、`…get_parse_status`、`…read_result`、`…read_outline`、`…save_result` 等 |
| [`cue-omni-reader-guard`](../dsh/cue-omni-reader-guard) | `@cueai/dsh-omni-reader-guard` | 可选 `tools/pre-execute` 护栏:拒绝 SSRF(私网/保留主机),对 `mcp__omni__parse` 施加白名单/同意。`allowedRoots` 为空时 fail-closed。 |
| [`cue-data-mcp`](../dsh/cue-data-mcp) | `@cueai/dsh-cue-data-mcp` | 暴露 Cue 的**公开数据** MCP 服务(监管/宏观/披露/法规/持仓/实体/学术/IPO/ESOP/回购/脚注/事实索引)为原生 `mcp__cue_<domain>__*` 工具(15 域 / ~104 工具,streamable-http)。 |

三者都是 `@cueai/*`(公开 scope)、MIT,并在英文 README 旁提供 `README.zh-CN.md`。

## 分发与校验

- **安装**:`dsh plugin --profile web add @cueai/dsh-omni-reader`(+ `…-guard` + `…-cue-data-mcp`);配置与 FAQ 见各 bundle 的 `README.md` 与 [`dsh/usage.md`](../dsh/usage.md)。
- **校验**([`scripts/verify_dsh_bundles.py`](../scripts/verify_dsh_bundles.py)):结构 + 双语文档(每个 bundle 与索引都要求 `README.zh-CN.md`)、`--publish-check`(scope/semver/元数据 + 插件入口语法)、`--check-translation-parity`(每对英中文档的标题层级+顺序骨架与代码块数)。
- **CI**(`.github/workflows/skill-regression.yml` 的 `verify-dsh-bundles` job)会跑 bundle 校验、护栏策略单测(`node --test`)与护栏 glue smoke(`node test/smoke.mjs`)。

wiring bundle 负责接入 Cue Omni Reader(解析);guard bundle(可选)负责 SSRF/费用护栏;cue-data-mcp 暴露 Cue 的公开数据工具。三者一起,让 Harness profile 把 Cue Omni Reader 暴露成原生 `mcp__omni__*` 工具、把 Cue 数据以 `mcp__cue_*` 工具暴露,并带一层 fail-closed 的安全护栏。
