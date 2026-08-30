---
name: cue-omni-reader
description: "当用户需要外部 AI agent 通过 Cue Omni Reader 解析或理解一个 HTTP(S) URL 或已授权的本地文档、音频、视频源时使用。触发词：解析/读取 URL、本地文档、音频、视频、OCR、PDF、网页内容。"
license: MIT
metadata:
  version: "0.4.0"
  requires:
    bins: ["node"]
  envOptional: ["CUE_API_KEY"]
---

# Cue Omni Reader（中文版）

本文件是 [`SKILL.md`](SKILL.md) 的完整中文翻译，语义与英文版一致。加载机制以英文 `SKILL.md` 为准。

用官方 Omni MCP 表面把 URL 或已授权的本地文件变成内容，然后完成用户的任务。MCP 包与当前工具 schema 是权威；本 skill 绝不自行实现解析器、上传客户端或 MCP 驱动。

## 核心流程

1. **保留来源。** 只有 HTTP(S) 字符串才是 URL。把用户的来源字符串直接传给 `parse`。不要预读、附件化、base64 编码或粘贴本地来源内容；不要使用 `file://`、localhost 或公共临时上传服务。
2. **单一提供方，双来源。** `parse(source)` 同时覆盖 HTTP(S) URL 与已授权本地路径。本地 Bridge 是同一个 Omni 提供方，不是第二个连接器；仅远端连接可处理 URL，但不能读取本地文件。
3. **仅在同意后自举。** 安装 Bridge 或扩展允许根目录前，先获得用户确认，并只加入最小必需目录。阅读 [`references/setup.md`](references/setup.md)，使用其精确审计 pin，运行 `doctor`，再按指示重载或重启。绝不让用户在对话里粘贴 API key。文件已在允许根目录内时，不要再要求一次确认。
4. **调用当前 schema。** 遵守当前 `parse` schema，绝不发明参数。如果 schema 暴露 `wait`，长媒体或大文档使用 `wait: false`；仅来源的 Bridge 会返回可恢复 operation。`source`/`url` 只传一个。`grounded`/`layout` 仅 Bridge 本地支持；远端 `UNSUPPORTED_DETAIL` 是终局。不要让同步与异步提交竞争。
5. **读取任一种响应通道。** 有 `structuredContent` 时优先使用；只有 `content[].text` 时，先解析紧凑 JSON。完成的 inline 内容可能是精确 Markdown；非 inline 状态是紧凑 JSON。通用成功字符串不等于完成。只拼接 `result.text`；绝不追加 JSON 包装。
6. **保住同一个操作。** 收到 `processing` 时保存 `operation_id`，按返回时机或 `wait_ms` 调 `get_parse_status`。重提之前先恢复既有操作。丢失 operation ID 是含糊超时：解释重复工作/计费风险，取得确认后才能替换提交。
7. **有意选择结果交付。** 使用以下决策表：

   ```text
   直接回答 → 有 inline 就直接用；否则 `read_result`
   定位一个章节 → `read_outline` → `read_result(cursor)`
   读取全部内容 → 反复 `read_result`，直到没有 `next_cursor`
   交付文件 → `save_result`
   ```

   保存、章节导航、多份文档或严格控制上下文时使用 `result_delivery="artifact"`；省略/`auto` 会在可行时让有界小文本 inline。对于 `result.kind=artifact`，preview 并非完整内容；读取到 `next_cursor` 消失为止。`read_outline` 不要求先调用 `save_result`。多来源使用有界并发的独立 `parse` 调用，并把每个 operation/result handle 分开。
8. **收尾并清理。** 解析后继续用户的原始任务。摘要前先组装完整结果，不要截断。仅解析时交付完整 Markdown 或文件，可选地提供摘要。任务完成前保留 artifact；除非用户要求保留，之后调用 `discard_result`。只在 discard 或清理被确认后声称已删除。

## 操作状态

| 状态 | 动作 |
|---|---|
| `processing` | 继续同一个操作并报告权威进度。 |
| `completed` | 消费 inline 或 artifact 结果。 |
| `cleanup_pending` | 使用可用结果；不要声称已删除或重提。 |
| `failed` | 呈现结构化错误；仅当 `retryable=true` 且状态允许时重试。 |
| `canceled` | 报告已确认的取消、计费与清理事实。 |
| `expired` | 解释过期；开始新工作前取得确认。 |

任何未识别状态：保留操作；不要重提，也不要声称完成、取消、计费或清理。

同来源重试只复用可恢复或仍保留的已完成记录；失败、已取消、已过期或超出交付窗口的重试可能新建 operation 并计费。仅在记录可复用时，`auto`→`artifact` 才加强交付且不创建第二个 operation。用户要求停止在途操作时，用保存的 ID 调 `cancel_parse`。不要用 discard 替代取消；不能承诺取消避免了扣费。

## 未知的客户端能力

Tasks、Roots、宿主超时及 cwd/workspace 行为，只能依据客户端直接证据分类；不能从成功 parse 推断。

- **Tasks 未知** → 使用普通 `parse` 加有界 `get_parse_status` 轮询。
- **Roots 未知** → 只使用进程 cwd 与显式 roots。
- **宿主超时未知** → 保持 Bridge 有界的 20 秒 status wait。
- **cwd/workspace 关系未知** → 不扩大授权，也不猜当前 workspace。

## 诚实的错误与计费处理

工具级错误不是 MCP 断连。保留鉴权、计费、解析器、可重试性、operation 与清理事实。只报告本次 operation 返回的计费事实；仅在 `retryable=true` 时重试。绝不估算费用或复制页数/媒体时长换算。

先运行 `npx -y @cueai/omni-reader-mcp@1.6.0 doctor --json`。`CUBE_UNAVAILABLE` 是上传前的控制面失败；grant 后失败属于安全上传阶段；`CUBE_PROTOCOL_ERROR` 是响应契约不匹配。只依据已报告的端点事实——绝不猜测或发布内部主机名、端口。

## 公共工具

使用语义工具名，不写死命名空间：

- `parse`
- `get_parse_status`
- `cancel_parse`
- `read_result` — Bridge 本地 artifact 工具
- `read_outline` — Bridge 本地 artifact 工具
- `discard_result` — Bridge 本地 artifact 工具
- `save_result` — Bridge 本地 artifact 工具

四个 artifact 工具只存在于本地 Bridge；远端表面绝不暴露。客户端与服务证据见 [`references/compatibility.md`](references/compatibility.md)。

## 免费额度

可以说明新用户能试用 Omni，但以服务端实时策略与 `doctor` 为权威；细节见 [`references/setup.md`](references/setup.md)。
