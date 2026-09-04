# cue-data-mcp

**[English](README.md) · [中文](README.zh-CN.md)**

> 一个让 AI agent 通过 Cue 官方 `/hub/mcp` 数据服务面查询外部数据的 skill——监管、宏观、披露、市场数据、法律全文、持仓、实体数据、学术、IPO、股权激励、回购、财报附注等。薄指令层：无运行时代码，不硬编码端点或工具名。

> **兄弟 skills：**[`cue-buddy`](../cue-buddy)（起草调研搭子）· [`cue-research`](../cue-research)（在 agent 里跑深度研究）· [`cue-omni-reader`](../cue-omni-reader)（文档/URL 解析）。本 skill 负责*外部数据查询*；其余负责*研究*与*解析*。

## 这个 skill 是什么

`cue-data-mcp` 可加载进任意 AI agent（Claude Code、Codex CLI、Gemini CLI、OpenClaw 等），告诉它如何通过标准 MCP 协议直接调用 Cue 的数据工具——无需在页面手动配置 MCP client，也没有自定义解析器：agent 加载 skill → 发现 live 域 → 直接调数据工具。

live catalog 是唯一事实源：

1. **发现**——`GET https://cuecue.cn/api/mcp-catalog`（匿名，无需 key）列出各域；live 域带完整 `routing` DTO。
2. **按主题选域**——截至 2026-08-24 共 15 个数据域（约 104 个工具）；`omni-reader` 已排除，它有专门 skill。
3. **直连**——逐字使用 live 域的 `routing`：`url`、`transport: streamable-http`、`protocol_version: 2025-03-26`，以及必需 headers（`Authorization: Bearer <CUE_API_KEY>`；`Accept` 头——streamable-http 端点缺它会返回 HTTP 406）。
4. **自发现工具**——对端点发 `tools/list` 拿 active schema；绝不硬编码工具名。
5. **按 schema 调用**——用 live schema 定义的参数调 `tools/call`。

## 连接方式

任何标准 MCP client 都可按 live 域配置；没有 client 的 agent 也可以直接对端点走 JSON-RPC：

```sh
curl -sS https://mcp.cuecue.cn/api/<group>/mcp/ \
  -H "Authorization: Bearer $CUE_API_KEY" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

**凭据：** 数据服务与 Cue 其余功能共用同一个 `CUE_API_KEY`，从 <https://cuecue.cn/hub/api-key> 获取。agent 自身不获取、不存储、不传输 key——由用户在**自己的 secret facility** 里配置。绝不把 key 粘进 chat、命令行参数、skill 文件、日志或生成的 JSON；若出现在任何地方，先轮换再继续。

完整的客户端配置形态、JSON-RPC 直连示例与排障表（406 / 401 / 域翻转）：[`references/setup.md`](references/setup.md)。

## 赠送积分

每个 Cue 账号每天送 10 积分——约合 **每天 16 次数据查询**（0.625 积分/次）；新账号申请 `CUE_API_KEY` 时另送一次性 50 积分（首日约 96 次）。在 <https://cuecue.cn/hub/api-key> 获取 key。具体额度以服务端计费政策为准——live 值不同时报 live 值。

## 仓库布局

```
cue-data-mcp/
├── SKILL.md                # 调用 agent 读取的 skill 规范（加载契约）
├── SKILL.zh-CN.md          # SKILL.md 的完整中文翻译
├── README.md               # 本文件
├── README.zh-CN.md         # 本文件的中文版
├── references/
│   └── setup.md            # 凭据规则、客户端配置、JSON-RPC、排障
└── scripts/
    └── test_skill_regression.py   # 11 个 skill 回归测试
```

## License

[MIT](../LICENSE)
