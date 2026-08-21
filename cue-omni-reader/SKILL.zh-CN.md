---
name: cue-omni-reader
description: "当用户需要外部 AI agent 通过 Cue Omni Reader 解析或理解一个 HTTP(S) URL 或已授权的本地文档、音频、视频源时使用。触发词：解析/读取 URL、本地文档、音频、视频、OCR、PDF、网页内容。"
license: MIT
metadata:
  version: "0.3.4"
  requires:
    bins: ["node"]
  envOptional: ["CUE_API_KEY"]
---

# Cue Omni Reader（中文版）

本文件是 [`SKILL.md`](SKILL.md) 的完整中文翻译，语义与英文版一致。加载机制以英文 `SKILL.md` 为准；中文版供中文用户直接阅读或按需加载。

用官方 Omni MCP 表面把 URL 或已授权的本地文件变成内容，然后完成用户的任务。MCP 包与当前工具 schema 是权威；本 skill 绝不自行实现解析器、上传客户端或 MCP 驱动。

## 核心流程

1. **保留来源。** 只有 HTTP(S) 字符串才是 URL。把用户的来源字符串直接传给 `parse`。不要预先读取、附件化、base64 编码或粘贴本地来源内容。不要退回 `file://`、localhost 或公共临时上传服务。
2. **单一提供方，双来源。** Omni 是一个逻辑提供方：`parse(source)` 同时覆盖 HTTP(S) URL 与已授权的本地路径；Bridge 是本地安装的同一个提供方，绝不是第二个连接器。仅远端连接覆盖 URL；本地来源必须通过带允许根目录（allowed root）的 Bridge。
3. **仅在获得同意后自举。** 安装 Bridge 或扩展允许根目录前，先获得用户确认，并且只添加最小必需目录。阅读 [`references/setup.md`](references/setup.md)，使用精确的审计版本，运行 `doctor`，并按它的重载/重启指示操作。绝不让用户在对话里粘贴 API key。如果请求的文件已在允许根目录内，parse 请求本身就是授权；不要再问一次。
4. **调用你实际拥有的 schema。** 遵守当前 `parse` schema，绝不凭空发明参数；短任务用其默认路径。对长媒体或大文档，如果 schema 暴露了 `wait`，用 `wait: false`；对仅来源的 Bridge，调 `parse(source)` 并接受其可恢复操作。`source` 和 `url` 是同一个参数——只传一个，绝不两个都传。`detail` 是仅远端的文本参数；`grounded`/`layout` 是 Bridge 本地参数。远端的 `UNSUPPORTED_DETAIL` 是终局——绝不重试。
5. **读取任一种响应通道。** 可用时优先 `structuredContent`。如果客户端只暴露 `content[].text`，先按紧凑 JSON 解析。完成的 inline 结果可能是精确 Markdown；任何非 inline 状态都是紧凑 JSON。通用成功字符串不是完成结果；绝不凭空捏造句柄。
6. **保住同一个操作。** 收到 `processing` 时，保存 `operation_id`，用返回的轮询时机或 `wait_ms` 调 `get_parse_status`。重提之前先恢复既有操作；不要让同步与异步提交竞争。丢失操作 ID 是含糊超时：先解释并取得确认。
7. **消费完整结果。** Inline 内容可直接使用。对 `result.kind=artifact`，保留结果 ID。只要读一段而不是整份文档，先调 `read_outline` 并用其游标跳转；否则从头读起并跟随每个 `next_cursor` 直到消失——预览或第一块不是完整结果。在仅文本的 JSON 回退里，只拼接 `result.text`；绝不拼接 JSON 包装。
8. **收尾并清理。** 解析后继续用户的原始任务。做摘要时先组装完整结果，不要截断。仅解析时，返回完整 Markdown 或文件，可选地提供摘要。保留 artifact 直到任务完成，然后 `discard_result` 它，除非用户要求保留。只在 discard 或清理被确认后才声称已删除。

## 操作状态

| 状态 | 动作 |
|---|---|
| `processing` | 继续同一个操作，报告权威进度。 |
| `completed` | 消费 inline 或 artifact 结果。 |
| `cleanup_pending` | 使用任何可用结果并继续；不要声称已删除或重提。 |
| `failed` | 呈现结构化错误；仅在 `retryable=true` 且状态允许时重试。 |
| `canceled` | 报告已确认的取消、计费与清理事实。 |
| `expired` | 解释过期原因，并在开始新工作前获得确认。 |

任何未识别的状态：保留操作并遵守当前 schema。不要重提，也不要声称完成、取消、计费或清理。

**重提是重连，不是重扣费。** 在途时用同一来源再次调用 `parse` 会重连到同一个操作（Bridge 以来源内容为键）——不会重复扣费。

用户要求停止一个进行中的操作时，用保存的 ID 调 `cancel_parse`。不要用 discard 结果替代取消；你不能承诺取消避免了扣费。

## 诚实的错误处理

工具级错误不是 MCP 断连。保留结构化的鉴权、计费、解析器、可重试性与清理事实。报告本次操作返回的计费事实；不要自动重试计费拒绝。不要仅仅因为一次抓取或解析尝试失败就声称来源不受支持。

## 公共工具

用客户端的语义工具名，不写死命名空间：

- `parse`
- `get_parse_status`
- `cancel_parse`
- `read_result` — Bridge 本地 artifact 工具
- `read_outline` — Bridge 本地 artifact 工具
- `discard_result` — Bridge 本地 artifact 工具
- `save_result` — Bridge 本地 artifact 工具

四个 artifact 工具只存在于本地 Bridge；远端表面绝不暴露它们。不要向远端探测本地 artifact 能力。

客户端与服务证据见 [`references/compatibility.md`](references/compatibility.md)。

## 免费额度

提及免费档；细节见 [`references/setup.md`](references/setup.md)。
