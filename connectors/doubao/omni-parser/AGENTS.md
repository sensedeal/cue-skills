# AGENTS.md — cue-omni-parser 项目规则

给接手本工程的 coding agent / 豆包「创建插件」助手阅读。目标是**在不破坏结构的前提下，
把这个已有工程同步安装到开发者的豆包个人账号用于体验与调试**。

## 这是什么

豆包开放平台的**普通插件（Plugin）**，形态是「远程 MCP + Skill」，不是应用插件。
功能与 WorkBuddy 的 `connectors/workbuddy/cube-cubemanus-connector` 一致：
把公网可达的链接解析成 Markdown、带来源定位的正文或检索分块。

- 插件标识：`cue-omni-parser`，版本 `1.2.3`
- MCP 端点：`https://mcp.cuecue.cn/api/omni-reader/mcp/`（服务端独立部署，**不在本工程内**）
- 服务端工具（实测 2026-11-09）：`parse`、`get_parse_status`、`cancel_parse`、
  `get_billing_details`、`get_balance`。SKILL.md 只把前三个作为工作流工具。

## 目录结构（不要重排）

```text
omni-parser/
├── AGENTS.md                         # 本文件，工程规则
├── README.md                         # 字段映射、鉴权、提审清单、调试通道
├── LOCAL-INSTALL.md                  # 客户端「自定义连接器 + 上传技能」步骤
├── plugin.json                       # 根清单 + extensions["com.doubao"] 展示配置
├── mcp.json                          # 远程 MCP 连接，服务键 cue-parser
├── com.doubao/assets/plugin-icon.png # 512×512 插件图标
├── skills/cue-omni-parser/SKILL.md   # 工作流说明（frontmatter 带展示 metadata）
├── scripts/                          # 本地校验 / 调试 / 打包，不进 ZIP
└── dist/                             # 生成的 ZIP 产物，不进仓库
```

## 硬性约束（改动前必读）

1. **不要把它改成「应用插件」。** 不要新建 `com.doubao/app/manifest.yaml`、`src/`、`package.json`
   前端工程、`skill/` 目录或 Widget/Page。它没有 UI，`dbx init` 生成的脚手架不适用于本工程。
2. `mcp.json` 的 `type` 必须是 **`streamable-http`**（带连字符）。`streamableHttp` 是 WorkBuddy 的写法，
   豆包静态校验会直接拒绝；也不要改成 `sse` / `stdio`——豆包 MCP 只支持远程服务。
3. 服务键 `cue-parser` 必须与 `plugin.json` 的
   `extensions["com.doubao"].mcpServers` 下的键**逐一对应**，每个都要有
   `displayName` / `displayDescription`（`{zh, en}` 语言对象）。
4. **鉴权是标准 MCP OAuth，包内零凭据。** 不要放任何 Token / API Key / `Authorization` 头，
   不要创建 `com.doubao/auth/`（那是静态凭据用的）。凭据由豆包客户端托管。
   - 授权服务器 `https://cuecue.cn/a` 的 DCR 对 `redirect_uris` 有形态白名单：
     **只接受 loopback 的 `/oauth/callback` 路径**（`http://127.0.0.1:<port>/oauth/callback`
     或 `localhost`）。`/callback` 会被 `invalid_redirect_uri` 拒绝。
5. `SKILL.md` 必须位于 `skills/<name>/SKILL.md`（`skills/` 的直接子目录），
   frontmatter 的 `name` 与目录名一致，且必须带 `metadata.display_name` /
   `metadata.display_description`。正文沿用现有三工具与错误恢复约定。
6. 图标必须 512×512 PNG/JPG、≤500 KiB；所有包内资源路径以 `./` 开头。
7. ZIP 限额：整包 ≤16 MB、条目 ≤1024、单文件解压 ≤2 MB、Skill ≤10、MCP 服务 ≤10。
8. `scripts/`、`README.md`、`LOCAL-INSTALL.md`、`AGENTS.md`、`dist/` **不进插件 ZIP**。
   以 `scripts/package-files.mjs` 的 `INCLUDE` 为准。

## 常用命令

```bash
node scripts/validate.mjs     # 发布约束静态校验
node scripts/smoke-test.mjs   # 零凭据：401 发现 / PRM / AS 元数据 / PKCE
node scripts/oauth-probe.mjs  # 完整 OAuth（会打开浏览器）→ tools/list 比对
node scripts/pack.mjs         # 生成插件 ZIP 与技能上传 ZIP
```

## 同步安装到个人账号（无需提审）

依据《快速开始：用豆包开发插件》：客户端插件市场安装「创建插件」→ 在对话中告知
**本工程路径 `/Users/mac/workspace/cue-skills/connectors/doubao/omni-parser`**，
请它在原工程继续开发而非重新初始化 → 完成一次开发者账号授权 → 回复「已授权」→
助手同步安装到账号。之后在输入框下方选「插件」或 `@` 插件名即可使用。
**公开发布**才需要企业资质、上传草稿与审核，两者不要混淆。

若客户端没有插件市场入口（Mac App Store 版 2.24.10 可能没有），改走
`LOCAL-INSTALL.md` 的「自定义连接器 + 上传技能」，能力等价且不需要资质。
