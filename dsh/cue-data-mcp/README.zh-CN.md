# @cueai/dsh-cue-data-mcp

**[English](README.md)** · [中文](README.zh-CN.md)

一个 [DeepSeek Harness](https://github.com/deepseek-harness) **bundle**,把 Cue 的**公开数据** MCP 服务以原生 `mcp__cue_<domain>__*` 工具形式暴露到任何 Harness profile。每个"活"数据域作为一条 [`@deepseek-ai/dsh-mcp-client`](https://github.com/deepseek-harness) 实例(`transport: streamable-http`)接入 Cue 自有端点——**无需 SSRF 护栏**(URL 为 Cue 固定端点,工具集即数据面)。

15 个活域 / **约 104 个工具**(截至 2026-08-24):制裁与执法(OFAC/EU/BIS,11)、中国监管(16)、宏观(15)、美股披露 SEC EDGAR(5)、中国披露(5)、法规全文(3)、机构持仓(2)、主体数据(2)、学术(3)、事实索引(4)、IPO(9)、ESOP(10)、回购(2)、脚注(14)、两融(3)。`omni-reader` 已排除——它有独立的 `cue-omni-reader` skill。

## 安装

```sh
dsh plugin --profile web add @cueai/dsh-cue-data-mcp
# 或一次性
dsh web --patch ./dsh/cue-data-mcp/cordis.patch.yml
```

## 配置

只需一个凭据,走环境变量:

```sh
# $DSH_HOME/.env(或启动 dsh 前 export)
CUE_API_KEY=sk-...     # 来自 https://cuecue.cn/hub/api-key
```

每个 server 发送 `Authorization: Bearer $CUE_API_KEY` 与 streamable-http 所需的 `Accept` 头。

## 使用

重启后模型可见各域的 `mcp__cue_<domain>__*`(如 `mcp__cue_regulatory__*`、`mcp__cue_macro__*`、`mcp__cue_ipo__*`)。用各端点的 `tools/list` 发现实际工具名,再以 `tools/call` 调用。

## 验证

```sh
dsh --profile web --dump-config     # 应列出 15 条 `mcp-cue_*`
# 然后在会话里确认 mcp__cue_* 工具出现、一次小数据查询成功。
```

## 安全与范围

- 需要 `CUE_API_KEY`;模型可查询 Cue 的数据工具集,但端点是 Cue 自有且固定,无任意出网/SSRF 面。
- 不要把 key 放聊天、命令参数、本文件、日志或生成的 JSON。
- 数据端点走 `streamable-http`,由 `@deepseek-ai/dsh-mcp-client`(peer 依赖,`^0.1.1-rc.2`)桥接。

## 版本 / 回滚

- `@deepseek-ai/dsh-mcp-client` 是 **peer** 依赖(由 Harness profile 提供)。
- 回滚:`dsh plugin --profile web remove @cueai/dsh-cue-data-mcp`。

## 许可

MIT — 见 [LICENSE](../../LICENSE)。
