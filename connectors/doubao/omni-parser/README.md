# Cue 全能解析助手 · 豆包插件（omni-parser）

把 WorkBuddy 的 `connectors/workbuddy/cube-cubemanus-connector` 平移成豆包插件：**同一个远程 MCP 服务、
同一套解析能力、同一份 Skill 工作流**，只重写打包清单与展示配置。服务端零改动。

- WorkBuddy 侧：`type: mcp`、`streamableHttp`、`connector-meta.json`、根目录 `icon.png`
- 豆包侧：`plugin.json` + `extensions["com.doubao"]`、`streamable-http`、`com.doubao/assets/` 图标
- MCP 端点不变：`https://mcp.cuecue.cn/api/omni-reader/mcp/`

## 目录结构

```text
omni-parser/
├── plugin.json                       # 根清单：name / version / description / com.doubao 扩展
├── mcp.json                          # 远程 MCP 连接，服务键 cue-parser
├── com.doubao/
│   └── assets/
│       └── plugin-icon.png           # 512x512 PNG，由 WorkBuddy icon.png 缩放而来
├── skills/
│   └── cue-omni-parser/
│       └── SKILL.md                  # parse / get_parse_status / cancel_parse 工作流
├── scripts/
│   ├── package-files.mjs             # ZIP 文件清单（校验与打包共用）
│   ├── validate.mjs                  # 本地静态校验
│   └── pack.mjs                      # 生成提审 ZIP
├── .gitignore
└── README.md
```

## 与 WorkBuddy 连接器的字段映射

| WorkBuddy `connector-meta.json` | 豆包落点 |
|---|---|
| `source: cue-parser` | `plugin.json.name`（本包用 `cue-omni-parser`）与 `mcp.json` 服务键 `cue-parser` |
| `version: 1.2.3` | `plugin.json.version`，须与提审时填写的版本一致 |
| `description_zh` | `plugin.json.description` |
| `name_zh` / `description_zh` | `extensions["com.doubao"].displayName` / `displayDescription`（`{zh, en}` 语言对象） |
| `icon.png` | `com.doubao/assets/plugin-icon.png`，由 `icon` / `chatIcon` 引用 |
| `name_en` / `examples_zh` / `examples_en` / `type` | 删除。示例提示词在控制台提审材料中单独填写 |
| `mcp.json.type: streamableHttp` | **`streamable-http`**（带连字符，写错会直接静态校验失败） |

### 按现行豆包规范补齐的两处（飞书迁移文档未写到）

1. **MCP 服务展示配置是必填的**：`extensions["com.doubao"].mcpServers.<服务键>` 中的
   `displayName` / `displayDescription` 必填，且服务键必须与 `mcp.json` 逐一对应，缺一个或多一个都不通过。
2. **Skill frontmatter 必须带 `metadata`**：`display_name`（≤128）与 `display_description`（≤1024）
   为发布必填；`name` 必须与 `skills/` 直接子目录名一致。图标需 512×512 PNG/JPG、单张 ≤500 KiB，
   且资源路径以 `./` 开头。

Skill 目录从 `cube-tools` 改名为 `cue-omni-parser`：豆包要求 Skill 名称在**全平台范围**唯一，
`cube-tools` 过于通用容易撞名；frontmatter 的 `name` 已同步改为与目录名一致。飞书文档里建议的
「正文整份沿用」仍然成立，这里只改了 frontmatter 与「授权」一节的措辞。

另外，现行豆包规范已有 `com.doubao/cli.json`（CLI 连接器）章节，但**只支持 npm 安装、命令通过受控
Shell 执行，单个包最多 1 个 CLI**；MCP 侧则只支持远程 `streamable-http` / `sse`，**不支持 stdio 本地进程**。
因此飞书文档里「豆包没有 CLI 生命周期」的结论已过时。本插件对齐的是 WorkBuddy 的 MCP 形态连接器，
不包含 CLI；`cue-research` 那条 CLI 链路若要在豆包上架，应另做 MCP 出口或用 `com.doubao/cli.json` 重新评估。

## 鉴权：无需改服务端，也无需静态凭据文件

线上服务已实现标准 MCP OAuth，实测（2026-11-06）：

| 检查 | 结果 |
|---|---|
| `GET https://mcp.cuecue.cn/.well-known/oauth-protected-resource` | 200，`authorization_servers: ["https://cuecue.cn/a"]` |
| `GET https://cuecue.cn/a/.well-known/oauth-authorization-server` | 200，含 `authorization_endpoint` / `token_endpoint` / `registration_endpoint`，PKCE `S256` |
| 未授权 `POST .../api/omni-reader/mcp/` | 401，`WWW-Authenticate: Bearer resource_metadata=...` |

豆包对远程 MCP 走同一套「元数据发现 → 动态客户端注册 → 浏览器授权」流程，所以：

- 不提供 `com.doubao/auth/cue-parser.json`（那是给 API Key / 固定 Bearer Token 用的）；
- `mcp.json` 不写 `headers.Authorization`，包内不含任何真实凭据；
- 授权范围由服务端 entitlement（`omni_reader`）决定，用户只需在浏览器授权一次。

> 顺带记录：WorkBuddy 侧现有 `connector-meta.json` 未声明 `auth_mode`，按规范等价于「无需认证」，
> 而 SKILL.md 描述的是标准 MCP OAuth。需要识别用户身份时应补 `auth_mode: "server-side"` 与
> `server_auth`，否则文档描述与实际授权行为不一致。此为 WorkBuddy 侧待办，本包不改动它。

## 本地校验与打包

```bash
cd connectors/doubao/omni-parser

node scripts/validate.mjs     # 静态校验：清单字段、语言对象、图标、URL、服务键对应、Skill frontmatter、ZIP 限额
node scripts/smoke-test.mjs   # 零凭据探测：401 发现 → PRM → AS 元数据 → PKCE
node scripts/oauth-probe.mjs  # 走完整 OAuth（DCR + PKCE + 浏览器授权）→ tools/list 比对
node scripts/pack.mjs         # 产出 dist/cue-omni-parser-1.2.3.zip 与 dist/cue-omni-parser-skill.zip
```

想**在本机豆包客户端里先用起来**（不走上架）：见 [LOCAL-INSTALL.md](LOCAL-INSTALL.md)。
插件 ZIP 不能侧载进客户端，但可以用「自定义连接器 + 上传技能」复现同样的能力，
后者用的技能包由 `pack.mjs` 一并生成。

## 同步安装到个人豆包账号（无需提审）

依据[《快速开始：用豆包开发插件》](https://open.doubao.com/document/plugin-docs-center/getting-started/quick-start-doubao-work)：
豆包插件市场里的「创建插件」助手可以把工程**同步安装到开发者自己的账号**，之后直接在对话里使用，
**无需走发布提审**。这和「公开发布」是两条独立的路：

| | 个人账号同步安装 | 公开发布 |
|---|---|---|
| 前置条件 | 开发者账号授权一次 | ISV 企业资质 + 评测报告 + 示例提示词 + 审核 |
| 可见范围 | 仅自己 | 插件市场全量用户 |
| 操作路径 | 「创建插件」对话里完成 | 控制台上传草稿 → 提审 → 平台运营发版 |

操作：

1. 豆包插件市场搜索并安装「**创建插件**」，在对话中选中它。
2. 告诉它用**已有工程**（不要重新初始化），例如：

   ```text
   请基于已有工程 /Users/mac/workspace/cue-skills/connectors/doubao/omni-parser 继续。
   这是一个纯 MCP + Skill 的普通插件，不是应用插件，不要改成应用插件、不要加 manifest.yaml
   或前端工程。请帮我同步安装到我的豆包账号。
   ```

   工程根目录的 `AGENTS.md` 已写好结构说明与硬性约束，助手接手时会读到。
3. 完成一次开发者账号授权，回复「已授权」，助手继续登录并同步安装。
4. 安装后在输入框下方选「插件」，或直接 `@` 插件名，发解析指令验证。

> ✅ 本机已复核（2026-11-09）：除 Mac App Store 版 `Doubao.app` 2.24.10 外，还装有
> 官网直装的 **`DoubaoWork.app`（豆包工作）2.35.23** 与 `Doubao 2.app` 2.34.6，
> 均具备「插件·技能·伙伴」入口。具体安装步骤见 [LOCAL-INSTALL.md](LOCAL-INSTALL.md)。

`dbx` CLI（`@doubao-dev/cli`）的命令总览里**没有**「同步安装到个人账号」的命令；
`build` / `build --release` 面向含 `manifest.yaml` + 前端工程的应用插件云构建。
本地 coding agent 用 dbx 做开发与校验，同步安装仍走「创建插件」对话。

## 调试插件的三层通道

| 层 | 手段 | 前置条件 | 适用形态 |
|---|---|---|---|
| L1 客户端 | 「新建自定义连接器」填 MCP URL +「上传技能」，保存即时生效 | 无资质、无开发者账号，仅需客户端有该入口 | **普通插件（本包）** |
| L2 开发者工具 | `dbx dev` → `web` Web 模拟器（对话 / 卡片 / 工具 / Agent Trace）、`dbx check --query` 链路校验、`dbx build` 测试版本、`desktop --mcp` 端到端 | 企业账号 + AppID + 前端工程 | 应用插件 |
| L3 真机预览 | 版本列表 → 体验二维码 → 豆包 App 扫码 → 「应用插件 Debugger」发 Query（体验白名单配 UID） | 目标版本已上传 | 应用插件 |

L2 / L3 都绑定**应用插件**形态，要求包内有 `com.doubao/app/manifest.yaml` 与前端工程；
本包是纯 MCP + Skill 的普通插件，没有 app 模块，因此用不上，也不需要为了调试去补一个前端工程。
另外开放平台要求「完成企业资质认证后，企业成员才可创建并提交 Skill、插件」，
所以 L2 / L3 还被 ISV 资质卡住，而 L1 不受影响。

**不依赖任何客户端的本地调试**（推荐先跑）：

```bash
node scripts/smoke-test.mjs    # 零凭据：清单一致性、401 发现、PRM、AS 元数据、PKCE
node scripts/oauth-probe.mjs  # 真实 OAuth：DCR → PKCE S256 → 浏览器授权 → tools/list 比对
```

### 这个插件是 OAuth 认证，包内零凭据

鉴权走标准 MCP OAuth（元数据发现 → 动态客户端注册 → PKCE S256 → 浏览器授权），
**凭据由豆包／WorkBuddy 客户端托管并静默续期**：

- `plugin.json` / `mcp.json` 里没有任何 Token、API Key 或 `Authorization` 头；
- 没有 `com.doubao/auth/`（那是给 API Key / 固定 Bearer Token 用的静态凭据文件）；
- `smoke-test.mjs` 完全不接触凭据，只验证发现链路；
- `oauth-probe.mjs` 走完整的标准授权流程，token **只存在于内存**：不打印、不落盘、
  不写进包、不放进 URL、不要贴进对话。每次运行会在授权服务器动态注册一个临时客户端。

两个脚本都只做 `initialize` 与 `tools/list`，**不会发起 parse，因此不产生解析计费**。
它们验证的正是客户端接入时会走的同一套契约，能在装进豆包之前提前暴露
传输类型写错、服务键不匹配、OAuth 端点变更、Skill 工具名漂移等问题。

### 实测记录（2026-11-09）

`node scripts/oauth-probe.mjs` 全流程通过：DCR → PKCE S256 → 浏览器授权 → 换票
（Bearer，3600s）→ `initialize`（protocol `2025-06-18`）→ `tools/list`。服务端实际返回 5 个工具：

```text
parse, get_parse_status, cancel_parse, get_billing_details, get_balance
```

`SKILL.md` 与 WorkBuddy 参考连接器保持一致，只把前三个作为工作流工具；
`get_billing_details` / `get_balance` 是服务端额外的计费与额度查询工具，不纳入本插件的工作流。

> ⚠️ 授权服务器的 DCR 对 `redirect_uris` 有形态白名单：**只接受 loopback 的
> `/oauth/callback` 路径**（`http://127.0.0.1:<port>/oauth/callback` 或 `localhost`）。
> 常见的 `/callback` 会被 `invalid_redirect_uri` 拒绝。`oauth-probe.mjs` 里的
> `CALLBACK_PATH` 已按此设置，改动时不要改回去。

> 对比 WorkBuddy：WorkBuddy 的调试是**文件级**的 —— 用户级 `~/.workbuddy/mcp.json` /
> 项目级 `<项目>/.workbuddy/mcp.json` 直接编辑即生效，连接器页有「自定义连接器」与状态灯。
> 豆包桌面端对应的是 GUI 表单版自定义连接器，没有公开的等价本地 mcp.json 编辑入口；
> 但它用 `dbx` 补上了更重的 Web 模拟器 / 真机 Debugger 链路，只是那条链路只服务应用插件。

`validate.mjs` 覆盖的发布约束：ZIP ≤16 MB、条目 ≤1024、单文件解压后 ≤2 MB、Skill ≤10、MCP 服务 ≤10、
名称字符集、展示文案长度与语言键、图标 512×512 / ≤500 KiB、`./` 路径不越界、HTTPS 非回环 URL、
请求头大小写判重、静态凭据与服务键匹配。它**不替代**平台上传校验或 `dbx check`。

按官方快速开始，也可使用 `@doubao-dev/cli`（`dbx`）做 `dbx check` / `dbx build`；但那条链路面向
「应用插件」（含 `com.doubao/app/manifest.yaml` 与前端工程）。本插件是纯 MCP + Skill 的普通插件，
按开放平台「创建插件 → 上传 ZIP → 静态校验」提交即可。

## 示例提示词（提审时在控制台单独填写）

`examples_zh` 不能写进 `plugin.json`，沿用 WorkBuddy 连接器的三条示例，提审时填入控制台：

1. 请调用 Cue 全能解析助手，解析这个 B 站视频链接，把口播内容整理成逐字稿。
2. 请调用 Cue 全能解析助手，解析这份 PDF 研报，提取正文并整理出其中的表格数据。
3. 请调用 Cue 全能解析助手，解析这段会议录音，转成文字并按议题整理成纪要。

## 提审前清单

- [ ] 已通过豆包 ISV 企业资质认证（成立满 1 年、B 端商业化 6 个月以上且客户 >50 家、团队 ≥3 人、企业租户认证，约 3 个工作日）
- [ ] `plugin.json.version` 与控制台提交的版本号一致
- [ ] 控制台补充分类、评测报告（**飞书云文档链接，需给审核人员开阅读权限**）与 5–10 条示例提示词
- [ ] 先用豆包「自定义连接器」直接填 `https://mcp.cuecue.cn/api/omni-reader/mcp/`，验证工具调用与 OAuth 跳转（零改动，能提前暴露协议层问题）
- [ ] 上传 ZIP 后检查静态校验结果，再由平台运营在测试商店验收、统一发版（开发者无需自行发布）

参考文档：

- [WorkBuddy Connector 规范](https://open.workbuddy.cn/docs/connector)
- [豆包开放平台 · 快速开始](https://open.doubao.com/document/plugin-docs-center/getting-started/quick-start-cli-tabs)
- [插件总览](https://open.doubao.com/document/plugin-docs-center/build/mcp-server-development/plugin-development-spec/plugin-development-specification-overview) ·
  [MCP Server](https://open.doubao.com/document/plugin-docs-center/build/mcp-server-development/plugin-development-spec/mcp-server-development) ·
  [Skills](https://open.doubao.com/document/plugin-docs-center/build/mcp-server-development/plugin-development-spec/skill-development) ·
  [展示信息](https://open.doubao.com/document/plugin-docs-center/build/mcp-server-development/plugin-development-spec/display-information) ·
  [包构成](https://open.doubao.com/document/plugin-docs-center/getting-started/core-concepts/plugin-package-structure-plugin-json)
