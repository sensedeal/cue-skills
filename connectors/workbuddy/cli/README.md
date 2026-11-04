# @cueai/cue-cli

Cue（[cuecue.cn](https://cuecue.cn)）深度研究的本地 CLI 桥梁。定位与 `@cueai/omni-reader-mcp` 一致：只做本地客户端，凭证自己管，命令可被 WorkBuddy 之类的宿主调度。

- 命令名：`cue`
- Node：>= 20.12（只用 global `fetch`，无 HTTP 依赖）
- 凭证（`CUE_HOME` 可重定向，均为 0600）——**两者刻意分开**：
  - `~/.cue/credentials.json`：设备码 OAuth 令牌（`access_token` + `refresh_token`），1 小时过期、可刷新、可撤销；
  - `~/.cue/config.json`：你自己配置的**长期** api_key（`cue auth login --api-key` 写入）。
  读取优先级 **环境变量 `CUE_API_KEY` > `credentials.json` > `config.json`**。
- API base：默认 `https://cuecue.cn/a/api`
  （⚠️ **必须带 `/{sso-path}`**（生产为 `/a`）—— 少了它请求会打到产品前端的根 `/api/*`，那里没有到授权服务器的反代规则，返回 404 而非 401。dev / dgts 用 `--base-url` 或 `CUE_API_BASE` 覆盖。）
- ⚠️ **两族端点、两个前缀**：上面那个 base **只服务授权服务器（AS）的端点** —— `/{sso}/api/…` 下的
  `/cli/device/*`、`/oauth/*`、`/.well-known/*`。而**业务 API 在 host 根 `/api/…`**
  （`/templates*`、`/chat/stream`、`/tools/capabilities`）。CLI 会把业务端点**自动改派**到
  `{origin}/api`，所以**你只需要配 AS 那个 base**，业务侧不用另配。
  分族规则、实测依据与「为什么不能靠发现（AS 的 well-known 推不出业务 base）」见 `src/bases.ts`。

## 安装

```bash
npm install -g @cueai/cue-cli
cue doctor
```

## 认证

```bash
cue auth login          # 设备码授权：打印 https:// 授权 URL，轮询换 token
cue auth login --api-key sk-...   # 已有 key，直接写入，跳过浏览器
cue auth status         # 无副作用，退出码 0=已登录 / 2=未登录
cue auth logout         # 撤销远端会话（best-effort）+ 清除本地凭证
```

设备码流程遵循 RFC 8628，服务端需提供：

| 端点 | 方法 | 说明 |
|---|---|---|
| `{base}/cli/device/code` | POST | 入参 `{client_id:"cue-cli", scope:"mcp:invoke"}`，返回 `{device_code, user_code, verification_uri, verification_uri_complete?, expires_in?, interval?}` |
| `{base}/cli/device/token` | POST | 入参 `{grant_type:"urn:ietf:params:oauth:grant-type:device_code", device_code, client_id}`；**未授权按 RFC 8628 返回 HTTP 400** + `{error:"authorization_pending"}`（`slow_down` 时客户端把间隔 +5 秒）；成功返回 `{access_token, refresh_token}` |
| `{base}/cli/device/revoke` | POST | RFC 7009 语义：入参 `{token: <refresh_token>}`（也接受 access token），**恒返回 200**、幂等 |

> ⚠️ 判定**只看响应体里的 `error`，不看状态码**：`authorization_pending` / `slow_down` /
> `expired_token` / `access_denied` / `invalid_grant` 由服务端按 RFC 8628 用 **400** 表达。
> （CLI 1.0.0 曾只认非标准的 428 —— 那样服务端按 RFC 实现时会在**第一次轮询就退出**。）

`access_token` 有效期 1 小时。任何 API 调用遇到 **401 时会静默刷新一次并重试**；
刷新是**轮换式**的（旧 refresh token 立即失效），所以新的 refresh token 会立刻写回。
由于服务端把「同一个 refresh token 用第二次」判为重放并**撤销整个令牌家族**，
刷新前会先取文件锁并重读凭据 —— 避免**并发的 `cue` 进程**互相踩成「莫名其妙被登出」。

服务端尚未开放设备码时，`cue auth login` 会提示改用 `--api-key`。

## 研究

```bash
cue research "比亚迪 DM-i 与长城 Hi4 混动技术路线差异"
cue research "万科合规风险体检" -o reports/vanke.md
cue research "再补一节供应商集中度" --conversation-id cue-cli-9f3c1a
cue research "第四范式基本面" --template-id template_fnig0i --json
```

参数：

| 参数 | 说明 |
|---|---|
| `--template-id <id>` | 搭子模板；裸 id 自动补 `template_` 前缀，纯数字后缀直接报错 |
| `--conversation-id <id>` | 续接会话追问 |
| `-o, --output <file>` | 报告落盘（Markdown，附来源清单），支持 `~/` |
| `--timeout <seconds>` | 整轮超时，默认 1200 |
| `--json` | 输出 `{conversationId, elapsedMs, report, sources, timeline}` |
| `-q, --quiet` | 不打印进度（进度默认走 stderr） |

调用 `POST {业务 base}/chat/stream`（SSE；业务 base = host 根 `/api`，见上文「两族端点、两个前缀」），按 `start_of_agent(reporter)` → `message.delta.content` → `end_of_agent(reporter)` 窗口抽取正文，与 cue-buddy Python 客户端同一套契约。

## 其他

```bash
cue playbook list [--mode is_me] [--include-system] [--json]
cue playbook get <template_id>
cue doctor          # JSON：node 版本、配置文件、key（脱敏）、连通性
```

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 缺少 / 失效凭证（含 401、403） |
| 3 | 入参错误 |
| 4 | 网络不可达 |
| 5 | 超时 |

## 开发

```bash
npm install
npm run typecheck
npm test
npm run build     # tsc → dist/
```

结构：`src/config.ts`（凭证）、`src/http.ts`（fetch + SSE）、`src/report.ts`（流→报告）、`src/commands/*`（auth / research / playbook / doctor）。

## 安全

- 设备码 OAuth 令牌只写入 `~/.cue/credentials.json`（0600）；自填的长期 key 只写入 `~/.cue/config.json`（0600）。两者不进日志、不进 argv（除非显式 `--api-key`）；
- 输出中的 key 一律脱敏（`sk-****mnop`）；
- `--api-key` 明文会出现在进程列表，非必要不使用，用后建议到 cuecue.cn/api-key 轮换。
- ⚠️ **`cue auth logout` 对长期 api_key 只能清本地**：服务端不提供由 CLI 自撤销这类 key 的接口，
  所以它会**如实告诉你**需要到 cuecue.cn/api-key 页面删除，而不是假装撤销成功。
  设备码 OAuth 令牌则会被真正撤销（撤销即时生效）。
