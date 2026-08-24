---
name: cue-data-mcp
description: "当用户需要外部 AI agent 通过 Cue 的公共 MCP 数据服务查询外部数据——监管、宏观、披露、市场数据、法律全文、持仓、实体数据、学术、IPO、股权激励、回购、财报附注——通过发现并直连 live MCP 端点时使用。触发词：查询监管/制裁、宏观数据、财报、公告、IPO、股权激励、回购、法规全文、13F、LEI、学术文献。"
license: MIT
metadata:
  version: "0.3.6"
  requires: {}
  envOptional: ["CUE_API_KEY"]
---

# Cue Data MCP（中文版）

本文件是 [`SKILL.md`](SKILL.md) 的完整中文翻译，语义与英文版一致。加载机制以英文 `SKILL.md` 为准；中文版供中文用户直接阅读或按需加载。

用 Cue 的公共 MCP 数据目录，以实时外部数据回答研究问题。目录 API 与 MCP 端点 schema 是权威；本 skill 绝不自行实现 MCP 客户端，也绝不硬编码端点、域或工具名。

## 核心流程

1. **发现 live 域。** 调用 `GET https://cuecue.cn/api/mcp-catalog`——匿名访问，无需 key。它返回当前域列表，含 `external_status`（`live` / `coming_soon`）、`tool_count`、`example_prompts`，以及 live 域完整的 `routing` 连接契约。
2. **把用户主题匹配到域。** 只挑选覆盖该问题的域（例如制裁/KYC → `regulatory`；CPI/GDP → `macro`；SEC 披露 → `disclosure`；IPO → `ipo`）。本目录覆盖 **15 个数据域**；`omni-reader`（文档/网页解析）域不在此范围内——那请用专门的 cue-omni-reader skill。
3. **通过 routing DTO 直连。** 逐字使用 live 域的 `routing`：`url`（如 `https://mcp.cuecue.cn/api/<group>/mcp/`）、`transport: streamable-http`、`protocol_version: 2025-03-26`。发送 `Authorization: Bearer <CUE_API_KEY>` 与 `Accept: application/json, text/event-stream` 头（streamable-http 缺 Accept → HTTP 406）。
4. **用 `tools/list` 按域发现工具。** 绝不硬编码工具名——目录只对登录用户投影名称/标题，且实际服务的工具集会随时间变化。已连接端点上的 `tools/list` 才是 live 事实。
5. **调用你实际拥有的 schema。** 遵守 `tools/list` 返回的当前工具 schema，绝不凭空发明参数。优先选择覆盖面满足问题的最小域；不要一次连接所有域。

## 规则

- **目录是可达性的唯一事实源。** 一开始就拉取它；一个域随时可能在 `coming_soon` ↔ `live` 之间翻转，routing 值也可能变化。绝不复用陈旧的连接串。
- **一次会话一个域，除非问题横跨多个。** 每个 MCP 连接会广播几十个工具；一次全连既慢又没必要。
- **绝不把 API key 粘贴进对话、命令行参数、skill 文件、日志或生成的 JSON。** 用户在自己的 secret facility 里配置 `CUE_API_KEY`；agent 绝不获取、存储或传输它。如果 key 已出现在对话中，先请用户轮换再继续。
- **如实报告失败。** 连接错误不是"无数据"的声明；工具错误不是域级故障。只重试错误信息里明确可重试的。绝不因为一次调用失败就声称域不受支持。

## 免费积分与计费

Cue 积分是数据 MCP 服务（以及 Omni Reader）背后的共享钱包。新用户无需付费即可试用数据服务：

- 每个账号每日获赠 **10 积分**——按每次数据调用 0.625 积分（现行标准）计，约 **每天 16 次数据查询**；
- 新账号申请 `CUE_API_KEY` 时一次性获赠 **50 积分**（含每日赠礼，首日约 96 次查询）；
- 邀请新用户注册，邀请方与被邀请方各得 50 积分。

具体额度与单次成本以服务端计费策略为准；如果 live 值与上述数字不同，报告 live 值。

用户还没有 `CUE_API_KEY` 时，指引其前往 <https://cuecue.cn/hub/api-key> 注册并获取 key。你自己绝不获取、存储或传输 key。
