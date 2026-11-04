/**
 * 两族端点，两个前缀（wayfinder #93）。
 *
 * 同一个 host 上，**AS（cubeauth）的端点与产品的业务 API 不在同一前缀**：
 *
 *   - **AS 端点**   → `{origin}/{sso}/api/…`  如 `https://x.cuecue.cn/dgts/api/cli/device/code`
 *   - **业务 API**  → `{origin}/api/…`        如 `https://x.cuecue.cn/api/templates`
 *
 * 实测（dev，2026-10-09）：
 *
 *   | 端点 | `/{sso}/api` | host 根 `/api` |
 *   |---|---|---|
 *   | `POST /cli/device/code` | **200** | 404 |
 *   | `GET /templates`        | 404     | **200**（带令牌） |
 *   | `POST /chat/stream`     | 404     | 存在（401/503） |
 *
 * 生产同形（`/a/api/templates` 404、`/a/api/oauth/token` 400）。机制是 AS 前端的
 * nginx 把 `^/{SSO}/api/` **只**代理给 cubeauth 后端（`nginx.conf.template` 的
 * `location ~ ^/SSO_PATH_PLACEHOLDER/api/`）。
 *
 * ⇒ **单 base 不可能同时服务两族**。本模块把这件事显式化：AS 那族**枚举**（它封闭、
 * 且由本 CLI 自己拥有），**其余一律走业务 base**。
 *
 * ⚠️ 为什么枚举 AS 而不枚举业务：业务端点面是**开放的**（产品会持续加），枚举它必然漏；
 * AS 那族的清单是**封闭的**（OAuth 元数据 + 设备码三端点），枚举得完。
 *
 * ⚠️ 为什么不「发现」：AS 的 `/.well-known/oauth-authorization-server` 与设备码响应
 * **只**广告 AS 自己的端点（`{issuer}/api/…`），**推不出**业务 base —— 实测两份文档里
 * 都没有 `/templates`、`/chat/stream` 的影子。所以「业务在 host 根 `/api`」是**约定**，
 * 必须写在这里并由 `test/bases.test.ts` 钉住。
 *
 * ⚠️ 历史：这一条正是 #87 那次 base 变更**打死的**那半张表 —— 默认 base 从根 `/api`
 * （业务通、认证断）挪到 `/{sso}/api`（认证通、业务断）。现在两族各归各位。
 */

/**
 * AS（cubeauth）端点族的路径前缀。
 *
 * 覆盖：OAuth 元数据（`/.well-known/`）、`/oauth/*`（refresh 用的 token 端点）、
 * `/cli/device/*`（设备码三端点）。**新增 AS 端点时必须加到这里** —— 否则它会被
 * 当成业务端点打到 host 根，表现为 404。
 */
const AS_ENDPOINT_PREFIXES = ['/.well-known/', '/oauth/', '/cli/'] as const;

/** 业务 API 在 host 根下的固定一段 */
const BUSINESS_BASE_PATH = '/api';

export interface ApiBases {
  /** AS（cubeauth）的 base —— 即 `config.base` 一直以来的那个值 */
  auth: string;
  /** 产品业务 API 的 base */
  business: string;
}

/**
 * 由一个 base 推出两族 base。
 *
 * 业务 base = **origin + `/api`** —— 直接取 origin，**不数路径分段**，所以不必假设
 * `{sso}` 有几段（三环境分别是 `dgts` / `dgts` / `a`，但推导不依赖这一点）。
 *
 * base 不是合法绝对 URL 时**退回单 base**（两族同值），让请求以与改动前**完全相同**
 * 的方式失败 —— 而不是在这里把它变成另一种错。
 */
export function resolveBases(authBase: string): ApiBases {
  const auth = authBase.replace(/\/+$/, '');
  try {
    return { auth, business: `${new URL(auth).origin}${BUSINESS_BASE_PATH}` };
  } catch {
    return { auth, business: auth };
  }
}

/**
 * 这个端点该打哪个 base。
 *
 * `endpoint` 形如 `/cli/device/code` 或 `/templates?mode=is_me`（可带可不带前导斜杠）。
 */
export function baseForEndpoint(endpoint: string, bases: ApiBases): string {
  const path = `/${endpoint.replace(/^\/+/, '').split('?')[0]}`;
  const isAs = AS_ENDPOINT_PREFIXES.some((prefix) => path.startsWith(prefix));
  return isAs ? bases.auth : bases.business;
}
