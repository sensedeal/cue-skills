# cue-omni-reader

**[English](README.md) · [中文](README.zh-CN.md)**

> 一个 AI agent skill，通过官方 [Cue Omni Reader](https://cuecue.cn) MCP 工具面把 HTTP(S) URL 或已授权的本地文档、音频、视频解析成内容——薄指令层，绝不自行实现解析器或协议驱动。

> **兄弟 skill:** [`cue-buddy`](../cue-buddy)（搭子 authoring）· [`cue-research`](../cue-research)（在 agent 里跑调研）。本 skill 负责**文档/URL 解析**，另两个负责**调研**。

## 本 skill 做什么

`cue-omni-reader` 能装进任意 AI agent（Claude Code / Codex CLI / Gemini CLI / WorkBuddy 等），指导它用官方 Omni MCP 工具把来源变成内容：URL，或用户已授权的本地文件。MCP 包与当前工具 schema 是权威；skill 只教 agent 怎么驱动它们——可恢复 operation、artifact 读取、清理、诚实的计费/错误处理。

**单一提供方，唯一首次调用。** `parse` 是 HTTP(S) URL 与本地路径唯一的首次调用；不要让用户选择本地/远端、上传/URL 模式。**Bridge**（`@cueai/omni-reader-mcp`）是本地安装的同一个提供方——绝不是第二个连接器。默认安装 Bridge；仅远端连接覆盖 URL、无需本地安装，但读不了本地文件。

## 协议边界

仅远端表面恰好暴露 `parse`、`get_parse_status`、`cancel_parse`。Bridge 暴露同样三个工具，再加 `read_result`、`read_outline`、`discard_result`、`save_result`。只有 `parse` 是首次调用；其余六个是根据结构化状态选择的后续与生命周期原语，不是让用户选择的模式。根据结构化结果选择后续工具；绝不把工具列表作为菜单交给用户选择。

## 结果交付

直接回答时使用 inline；否则读取 retained result。定位一个章节时先 `read_outline`，再 `read_result(cursor)`——目录导航不要求先 `save_result`。读取全部内容要跟随 `next_cursor` 直到消失；需要交付文件时用 `save_result`。文本输出是 Markdown，可保留标题、列表、GFM 表格或原始 HTML 表格；它缺少 grounding/layout sidecar，不是完全没有结构。空 outline 只表示没有识别到标题，不表示文本没有结构。保存、章节导航、多份文档或严格控制上下文时选择 `result_delivery="artifact"`。多来源采用有界的独立 parse 调用，各自保留 handle。

客户端能力必须有证据。Tasks、Roots、宿主超时或 cwd/workspace 行为未知时，分别回退到普通 parse/status 轮询、进程 cwd 加显式 roots、Bridge 有界 status wait，以及不自动扩大根目录。

## 安装审计版 Bridge

需要 Node.js 20.12+。绝不用隐式 `latest`：

```sh
npx -y @cueai/omni-reader-mcp@1.6.0 setup
```

交互式 setup 原生支持 Hermes、Cursor、Claude Desktop；其他客户端选 **Other**。然后验证：

```sh
npx -y @cueai/omni-reader-mcp@1.6.0 doctor --json
```

`doctor` 检查包版本、key 是否存在、根目录安全性、缓存/artifact 模式与客户端重载指引；它仅检查已鉴权的 Cube 控制面/配置事实。它不会探测已授权数据平面；只有真实本地文件 parse 才能端到端验证该路由。它不泄露 API key 或私有路径。回滚：`npx -y @cueai/omni-reader-mcp@1.6.0 uninstall --yes --json`（可用时恢复受信任的 URL-only 条目）。

完整 setup 规则（同意、允许根目录、非交互示例、回滚）：[`references/setup.md`](references/setup.md)。

## Windows

当前 setup 会**自动生成可用的 Windows 条目**（spawn 走 `cmd /d /c npx`，解决了 WorkBuddy `MCP error -32000: Connection closed` 背后的 `npx.cmd` ENOENT）。三种可运行形态：

1. **生成的 setup 条目**（默认，推荐）——平台正确的 spawn + 信任校验
2. **`npx` shell 形态** —— 在能解析 `.cmd` 的 shell 里跑 `npx -y @cueai/omni-reader-mcp@1.6.0`
3. **`node` + 绝对路径** —— `node "<绝对路径>/dist/index.js"`；npx 本身不可用时最稳

**务必用稳定路径**，不要用 session 时间戳目录——路径一变，MCP 客户端保存的配置在每次缓存清扫后就失效。

## 网络诊断

先运行 `npx -y @cueai/omni-reader-mcp@1.6.0 doctor --json`，再按结构化错误码诊断，并严格区分控制面与上传阶段：

- `CUBE_UNAVAILABLE` 是文件上传前的控制面失败；绝不能用上传阶段的端点探针解释它。
- `OMNI_NOT_ENTITLED` / HTTP 403 才是账号 entitlement 信号。
- `DIRECT_UPLOAD_DISABLED`（旧版）或 `DIRECT_UPLOAD_UNAVAILABLE` 表示直传路由/能力不可用，不表示账号被禁用或账号只能使用 text。
- `DETAIL_CAPABILITIES_UNAVAILABLE` 表示服务未声明 grounded/layout；text 仍是 Markdown，可保留标题、列表和表格。
- `UNSUPPORTED_DETAIL` 表示请求的 representation/profile 不可用；不要原样重试，也不要把账号描述成只能使用 text。
- grant 创建后的失败表示安全上传阶段没有完成。
- `CUBE_PROTOCOL_ERROR` 是响应契约不匹配，不是通用 DNS 诊断。

只依据 `doctor` 报告的已鉴权 Cube 控制面/配置事实。它不会探测已授权数据平面；只有真实本地文件 parse 才能端到端验证该路由。不要猜主机名或端口，也不要把内部上传入口当作常规用户排障项。更多客户端与服务证据：[`references/compatibility.md`](references/compatibility.md)。

## 免费额度

新用户可以试用 Omni；key 在 <https://cuecue.cn/hub/api-key> 获取。当前额度以服务端 onboarding 策略和 live `doctor` 输出为权威，不要把页数或媒体时长换算复制进指引。细节：[`references/setup.md`](references/setup.md)。

## 目录结构

```
cue-omni-reader/
├── SKILL.md                # agent 加载的 skill spec（加载契约）
├── SKILL.zh-CN.md          # SKILL.md 完整中文翻译
├── README.md               # 本文件（英文）
├── README.zh-CN.md         # 本文件（中文）
├── references/
│   ├── setup.md            # 审计过的安装 / 允许根目录 / 回滚契约
│   └── compatibility.md    # wire/工具面兼容性证据
├── docs/verification-reports/
│   └── ...                 # Bridge 版本、客户端实跑、审计
└── scripts/
    ├── sync_bridge_pin.py         # 每版 Bridge 一键同步 pin
    └── test_skill_regression.py   # Skill 回归测试
```

## 依赖

- Node.js 20.12+（Bridge 运行时）；skill 本身只含指令——无 Python、无额外依赖

## License

MIT — 见根目录 [LICENSE](../LICENSE)。
