# cue-omni-reader

**[English](README.md) · [中文](README.zh-CN.md)**

> 一个 AI agent skill，通过官方 [Cue Omni Reader](https://cuecue.cn) MCP 工具面把 HTTP(S) URL 或已授权的本地文档、音频、视频解析成内容——薄指令层，绝不自行实现解析器或协议驱动。

> **兄弟 skill:** [`cue-buddy`](../cue-buddy)（搭子 authoring）· [`cue-research`](../cue-research)（在 agent 里跑调研）。本 skill 负责**文档/URL 解析**，另两个负责**调研**。

## 本 skill 做什么

`cue-omni-reader` 能装进任意 AI agent（Claude Code / Codex CLI / Gemini CLI / WorkBuddy 等），指导它用官方 Omni MCP 工具把来源变成内容：URL，或用户已授权的本地文件。MCP 包与当前工具 schema 是权威；skill 只教 agent 怎么驱动它们——可恢复 operation、artifact 读取、清理、诚实的计费/错误处理。

**单一提供方，双来源。** Omni 是一个逻辑提供方：`parse(source)` 同时覆盖 HTTP(S) URL 与已授权的本地路径。**Bridge**（`@cueai/omni-reader-mcp`）是本地安装的同一个提供方——绝不是第二个连接器。默认安装 Bridge；仅远端连接覆盖 URL、无需本地安装，但读不了本地文件。

## 公共工具（七个）

- `parse` — URL 或已授权本地来源 → Markdown 内容（前台预算后用尽即返回可恢复 operation）
- `get_parse_status` / `cancel_parse` — 轮询与取消在途操作
- `read_result` / `read_outline` / `discard_result` / `save_result` — **仅 Bridge 本地**的 artifact 工具（远端表面绝不暴露）

## 安装审计版 Bridge

需要 Node.js 20.12+。绝不用隐式 `latest`：

```sh
npx -y @cueai/omni-reader-mcp@1.5.2 setup
```

交互式 setup 原生支持 Hermes、Cursor、Claude Desktop；其他客户端选 **Other**。然后验证：

```sh
npx -y @cueai/omni-reader-mcp@1.5.2 doctor --json
```

`doctor` 检查包版本、key 是否存在、根目录安全性、端点兼容性、缓存/artifact 模式与客户端重载指引——不泄露 API key 或私有路径。回滚：`npx -y @cueai/omni-reader-mcp@1.5.2 uninstall --yes --json`（可用时恢复受信任的 URL-only 条目）。

完整 setup 规则（同意、允许根目录、非交互示例、回滚）：[`references/setup.md`](references/setup.md)。

## Windows

1.5.2 的 setup 会**自动生成可用的 Windows 条目**（spawn 走 `cmd /d /c npx`，解决了 WorkBuddy `MCP error -32000: Connection closed` 背后的 `npx.cmd` ENOENT）。三种可运行形态：

1. **生成的 setup 条目**（默认，推荐）——平台正确的 spawn + 信任校验
2. **`npx` shell 形态** —— 在能解析 `.cmd` 的 shell 里跑 `npx -y @cueai/omni-reader-mcp@1.5.2`
3. **`node` + 绝对路径** —— `node "<绝对路径>/dist/index.js"`；npx 本身不可用时最稳

**务必用稳定路径**，不要用 session 时间戳目录——路径一变，MCP 客户端保存的配置在每次缓存清扫后就失效。

## 网络诊断

`CUBE_PROTOCOL_ERROR` 通常**不是** Bridge 的 bug——是客户端环境与 Omni 服务端点之间的 DNS/路由错配。先查：

- `cubefile.ai.iiis.co` 解析到的地址是否是你的网络真正可达的？(私有/公网 DNS 分流会让同一主机名映射到不同 IP——核对记录与当前网络一致)
- 是否有 HTTP(S) 代理截断了连接？某些环境把 MCP 流量导向代理，会破坏 MCP stdio/HTTP 传输。

跑 `npx -y @cueai/omni-reader-mcp@1.5.2 doctor --json`，把它的端点报告和你的实际网络路径对照。更多客户端与服务证据：[`references/compatibility.md`](references/compatibility.md)。

## 免费额度

新用户一次性 50 积分赠礼 + 每天 10 免费积分（约每天 150 页普通文档 / 75 页扫描件 / 30 分钟音频 / 4 分钟视频）。key 在 <https://cuecue.cn/hub/api-key> 获取。确切额度以服务端策略为准——与 live `doctor` 输出不同时报告 live 值。细节：[`references/setup.md`](references/setup.md)。

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
    └── test_skill_regression.py   # 29 个 skill 回归测试
```

## 依赖

- Node.js 20.12+（Bridge 运行时）；skill 本身只含指令——无 Python、无额外依赖

## License

MIT — 见根目录 [LICENSE](../LICENSE)。
