# 安装到本机「豆包工作」

## 结论：能，而且本机条件已经齐了

本机其实装了三个豆包客户端（2026-11-09 复核）：

| App | Bundle ID | 版本 | 渠道 |
|---|---|---|---|
| **`/Applications/DoubaoWork.app`（豆包工作）** | `com.work.pc.doubao` | **2.35.23** | 官网直装，正在运行 |
| `/Applications/Doubao 2.app` | `com.bot.pc.doubao` | 2.34.6 | 官网直装，2026-11-09 安装 |
| `/Applications/Doubao.app` | `com.bot.neotix.doubao` | 2.24.10 | Mac App Store（旧版） |

之前判断"本机客户端没有连接器入口"是基于 **MAS 版 2.24.10** 的，漏看了官网直装版。
**豆包工作 2.35.23 具备完整的插件与技能入口**，所以这条路现在是通的。

依据官方帮助中心：

- [《使用插件》](https://www.doubao.com/work/docs/zh-cn/articles/705018132598)（更新于 2026-11-06）
- [《使用技能》](https://www.doubao.com/work/docs/zh-cn/articles/081010973544-skills)（更新于 2026-11-02）

## 仍需说明的一点

`dist/cue-omni-parser-1.2.3.zip` 是**开放平台插件包**，不能像安装包一样双击侧载。
客户端里装的是「自定义连接器 + 上传技能」这两样，组合起来就是同一个 MCP + 同一份 Skill，
能力完全一致，只是没有商店展示信息和版本号。这一步零代码改动，也不需要企业资质。

GUI 里的点击、保存和 OAuth 授权**必须你本人操作**，我无法代做；能准备的产物和字段值都已备好。

## 路径 A：能力等价安装（推荐，几分钟）

### 1. 新建自定义连接器

左侧「**插件·技能·伙伴**」→ 切到「**插件**」页 → 右上角「**+ 添加**」→「**新建自定义连接器**」：

| 字段 | 值 |
|---|---|
| 服务器名称 | `cue-parser`（与 `mcp.json` 服务键、SKILL.md 描述一致） |
| 传输类型 | **HTTP**（云端程序；不要选 STDIO） |
| 服务器 URL | `https://mcp.cuecue.cn/api/omni-reader/mcp/` |
| 自定义 Headers | **留空** —— 服务端走标准 MCP OAuth，不要手填 Token / API Key |

保存后按提示完成授权，浏览器会打开 `https://cuecue.cn/a`；登录 Cue 账号并允许。
凭据由客户端托管并静默续期。授权链路已于 2026-11-09 用 `scripts/oauth-probe.mjs` 实测跑通
（DCR → PKCE S256 → 换票 → `tools/list` 返回 5 个工具）。

> 官方文档提到「如需鉴权，可在自定义 Headers 里添加请求头和密钥」，那是给静态凭据型 MCP 用的。
> 我们这个是 OAuth，**Headers 留空**，让客户端走标准发现与授权流程。

### 2. 上传技能

同一左侧栏切到「**技能**」页 → 右上角「**+ 添加**」→「**上传技能**」，
选择**文件夹**或 ZIP 均可：

```text
文件夹：/Users/mac/workspace/cue-skills/connectors/doubao/omni-parser/skills/cue-omni-parser
ZIP   ：/Users/mac/workspace/cue-skills/connectors/doubao/omni-parser/dist/cue-omni-parser-skill.zip
```

要求：至少包含 `SKILL.md`，且开头有 YAML 格式的 `name` / `description` —— 我们的文件已满足。
ZIP 内结构是 `cue-omni-parser/SKILL.md`（一层目录，不是裸文件、也不是多套一层）。
上传后在「我安装的」里可查看、替换或删除。

> 客户端可能只读取 frontmatter 的 `name` / `description` 而不读 `metadata` 展示字段，
> 此时列表里显示 `cue-omni-parser` 而不是「Cue 全能解析」，属正常，不影响调用。

### 3. 验证

1. 新开一个「新工作任务」，在对话框输入 `/` 或 `@` 搜索并选中技能 / 插件。
2. 若看不到自定义连接器，把工作模式切到「**本地电脑**」再试（部分版本只在本地模式加载）。
3. 发一句：「解析这个链接，把正文整理成 Markdown：https://example.com」
   （换成任意公网可访问的网页/在线文档链接）。
4. 正常结果：调用 `parse` 返回结构化 Markdown；长文档返回 `processing` + operation ID，
   技能会指导用 `get_parse_status` 轮询到终态。

## 路径 B：作为正式插件同步到个人账号（无需提审）

依据[《快速开始：用豆包开发插件》](https://open.doubao.com/document/plugin-docs-center/getting-started/quick-start-doubao-work)：
豆包插件市场里的「**创建插件**」助手可以把工程同步安装到开发者自己的账号，**无需发布提审**。

1. 插件市场搜索安装「创建插件」，在对话中选中。
2. 告诉它用已有工程（不要重新初始化），示例话术见 `README.md`「同步安装到个人豆包账号」章节。
   工程根目录的 `AGENTS.md` 已写好结构约束，防止助手把普通插件改成应用插件。
3. 完成一次开发者账号授权，回复「已授权」。
4. 之后在输入框下方选「插件」或 `@` 插件名使用。

## 可选：设置 → 数据导入与同步

豆包工作支持从 ChatGPT / Claude Code / TRAE Work 等一键导入本地的**技能与连接器**。
本机已存在 `~/.claude/`、`~/.claude.json`、`~/.codex/`、`~/.trae-cn/`，客户端可扫描到。

但这是一次性批量导入（本机 Claude Code 下有几十个技能、63 个项目的 MCP 配置），
不够精准，且需要改动第三方工具的本地配置 —— **我没有擅自修改**，需要你确认后才会做。
只想装这一个插件的话，用路径 A 更干净。

## 为什么我不直接写客户端的本地文件

只读检查过豆包工作的存储：

```text
~/Library/Application Support/DoubaoWork/Default/.doubaowork/agent_mode/workspace/.user_skills/
```

目录当前为空，且 `Preferences` 里的 `user_skill_sync_info_v2` / `remote_skill_install_info_v2`
带 `install_id`、`progress`、`status: READY` 等同步状态 —— 说明它由客户端与服务端同步管理。
直接手写文件不会被正确加载，还可能被覆盖或破坏应用状态，因此不走这条路。

## 与上架插件的差别

| | 路径 A（本机） | 路径 B（个人同步） | 公开上架 |
|---|---|---|---|
| 可见范围 | 仅本机账号 | 仅自己 | 插件市场全量用户 |
| 展示信息 | 无图标 / 多语言名 / 版本号 | 有 | 有 |
| 前置 | 无 | 开发者账号授权一次 | ISV 企业资质 + 评测报告 + 审核 |
| MCP + Skill 能力 | 完全一致 | 完全一致 | 完全一致 |

## 排障

- **看不到连接器**：切「本地电脑」模式；确认连接器开关已开、授权状态正常。
- **401 / 授权失效**：在插件页「管理」里重新授权，不要删掉重建，也不要把 Token 贴进对话。
- **技能上传被拒**：确认包内是 `cue-omni-parser/SKILL.md` 一层结构，且 `SKILL.md` 有 YAML `name` / `description`。
- **改了本地 SKILL.md 没生效**：需在客户端重新上传技能，改本地文件不会同步。
- **DCR 报 `invalid_redirect_uri`**：授权服务器只接受 loopback 的 `/oauth/callback` 路径，
  见 `README.md` 实测记录；用 `scripts/oauth-probe.mjs` 可自查。

## 相关文件

- `dist/cue-omni-parser-1.2.3.zip` — 开放平台提审用（**不是**本机安装包）
- `dist/cue-omni-parser-skill.zip` — 本机「上传技能」用
- `skills/cue-omni-parser/` — 可直接上传的技能文件夹
- `AGENTS.md` — 给「创建插件」助手 / coding agent 的工程规则
- `node scripts/pack.mjs` — 重新生成两个 ZIP；`node scripts/validate.mjs` 静态校验
- `README.md` — 字段映射、鉴权实测、调试通道、提审清单
