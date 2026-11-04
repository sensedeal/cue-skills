/**
 * `cue auth` — device-flow login, status check, logout.
 *
 * WorkBuddy 调度约定：
 *   - auth 必须在 10 秒内输出完整 https:// 认证 URL，且前后有空白字符分隔；
 *   - auth 不得进入交互式输入（无 TTY），也不得自行打开浏览器；
 *   - status 必须无副作用、跨进程可重复、10 秒内返回；
 *   - unAuth 清理本地凭证并尽力撤销远端会话。
 *
 * 本文件按 wayfinder #72 的裁决改造（八项），逐条理由见各处注释。
 */

import {
  API_KEY_PAGE,
  configPath,
  clearApiKey,
  credentialsPath,
  loadConfig,
  maskKey,
  saveConfig,
  DEFAULT_BASE,
} from '../config.js';
import { clearCredentials, readCredentials, writeCredentials } from '../credentials.js';
import { CueApiError, CueError, EXIT } from '../errors.js';
import { requestJson } from '../http.js';

const CLIENT_ID = 'cue-cli';

/**
 * 设备码请求的 scope。
 *
 * ⚠️ wayfinder #71 的裁定：**复用 `mcp:invoke`**，**不新增 `research`**。
 * 理由：MCP 形态的令牌（scope 就是 `mcp:invoke`）**今天已经在调研究 API** —— 两个形态的
 * 能力集本来就是同一个。若为 CLI 新增 `research`，会埋一个阱：它暗示「研究能力 =
 * `research` scope」，而 MCP 令牌没有它却一直在用研究 API ⇒ 将来 scope 真被强制时，
 * **MCP 侧会突然失去权限**。CLI 与 MCP 的区分由服务端的来源标签/计费口径承担，不压在 scope 上。
 */
const DEVICE_SCOPE = 'mcp:invoke';

const DEVICE_GRANT_TYPE = 'urn:ietf:params:oauth:grant-type:device_code';

interface DeviceCodeResponse {
  device_code: string;
  user_code?: string;
  verification_uri: string;
  verification_uri_complete?: string;
  expires_in?: number;
  interval?: number;
  token_endpoint?: string;
  revocation_endpoint?: string;
}

interface DeviceTokenResponse {
  access_token?: string;
  refresh_token?: string;
  scope?: string;
  error?: string;
  error_description?: string;
}

export interface AuthOptions {
  base?: string;
  apiKey?: string;
  json?: boolean;
  timeoutMs?: number;
}

function resolveBase(explicit?: string): string {
  const cfg = loadConfig();
  return explicit?.trim() || process.env.CUE_API_BASE?.trim() || cfg.base || DEFAULT_BASE;
}

function isNotFound(err: unknown): boolean {
  return err instanceof CueApiError && (err.status === 404 || err.status === 405 || err.status === 0);
}

/**
 * 从失败的轮询里取出 OAuth 错误码。
 *
 * ⚠️ wayfinder #72 裁决③：**状态码按 RFC 8628 是 400**（428 是 CLI 1.0.0 自己发明的），
 * 而 CLI 1.0.0 的轮询**只 catch 428** ⇒ 服务端按 RFC 返 400 时它会在**第一次轮询就抛错退出**。
 *
 * 修法是：**不看状态码判语义，只认响应体里的 `error` 字段** —— 这样 400 与 428
 * 两条路都能走通（服务端按 RFC 实现即 400，不必为客户端的历史写法让步）。
 *
 * 取不到 `error` 时返回空串，由调用方**原样抛出**（不猜、不当成 pending）：
 * 把无法识别的失败伪装成「继续等」会让登录挂到超时，反而**掩盖**真实错误。
 */
export function pollError(err: unknown): { status: number; error: string } {
  if (!(err instanceof CueApiError)) return { status: 0, error: '' };
  try {
    const parsed = JSON.parse(err.detail) as { error?: string };
    if (parsed && typeof parsed.error === 'string') {
      return { status: err.status, error: parsed.error };
    }
  } catch {
    /* 响应体不是 JSON —— 交给调用方抛出 */
  }
  return { status: err.status, error: '' };
}

export async function login(opts: AuthOptions): Promise<number> {
  const base = resolveBase(opts.base);

  // Fallback path: an API key supplied directly (env CUE_API_KEY wins) is
  // persisted without any browser step.
  const directKey = opts.apiKey?.trim() || process.env.CUE_API_KEY?.trim() || '';
  if (directKey) {
    const file = saveConfig({ api_key: directKey, base });
    if (opts.json) {
      console.log(JSON.stringify({ authenticated: true, method: 'api_key', base, configFile: file }, null, 2));
    } else {
      console.log(`已登录 (api_key) — key=${maskKey(directKey)} base=${base}\n配置文件: ${file}`);
    }
    return EXIT.OK;
  }

  // Device Authorization Grant (RFC 8628).
  let code: DeviceCodeResponse;
  try {
    code = await requestJson<DeviceCodeResponse>({
      method: 'POST',
      endpoint: '/cli/device/code',
      body: { client_id: CLIENT_ID, scope: DEVICE_SCOPE },
      base,
      timeoutMs: 10_000,
    });
  } catch (err) {
    if (isNotFound(err)) {
      console.error(
        `\n[cue] 服务端尚未开放设备码授权 (POST ${base}/cli/device/code)。\n` +
          `  → 临时方案：到 ${API_KEY_PAGE} 创建 key，然后执行\n` +
          `    cue auth login --api-key <key>\n` +
          `  或 export CUE_API_KEY=sk-... 后重跑。\n`,
      );
      return EXIT.ERROR;
    }
    throw err;
  }

  const url =
    code.verification_uri_complete ||
    (code.user_code
      ? `${code.verification_uri}${code.verification_uri.includes('?') ? '&' : '?'}user_code=${encodeURIComponent(code.user_code)}`
      : code.verification_uri);

  if (!/^https:\/\//.test(url)) {
    throw new CueError(`服务端返回的认证地址不是 https: ${url}`, EXIT.ERROR);
  }

  // 关键：URL 必须裸打印、前后有空白，且 10 秒内输出。
  console.log(`\n请在浏览器中完成 Cue 授权：\n\n${url}\n`);

  let intervalMs = Math.max(2, code.interval ?? 3) * 1000;
  const expiresInMs = (code.expires_in ?? 300) * 1000;
  const deadline = Date.now() + expiresInMs;

  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    let res: DeviceTokenResponse;
    try {
      res = await requestJson<DeviceTokenResponse>({
        method: 'POST',
        endpoint: '/cli/device/token',
        body: {
          grant_type: DEVICE_GRANT_TYPE,
          device_code: code.device_code,
          client_id: CLIENT_ID,
        },
        base,
        timeoutMs: 10_000,
      });
    } catch (err) {
      const { error } = pollError(err);
      if (error === 'authorization_pending') continue;
      if (error === 'slow_down') {
        // RFC 8628：客户端应把轮询间隔 +5 秒
        intervalMs += 5_000;
        continue;
      }
      if (error === 'expired_token') {
        console.error('\n[cue] 授权码已过期，请重试 cue auth login。\n');
        return EXIT.TIMEOUT;
      }
      if (error === 'access_denied') {
        console.error('\n[cue] 授权被拒绝。\n');
        return EXIT.ERROR;
      }
      if (error === 'invalid_grant') {
        console.error('\n[cue] 授权请求已失效（可能已在别处完成或已过期），请重试 cue auth login。\n');
        return EXIT.ERROR;
      }
      throw err;
    }

    // 兼容「200 + body.error」这种形状（非标准，但解析成本为零）
    if (res?.error === 'authorization_pending') continue;
    if (res?.error === 'slow_down') {
      intervalMs += 5_000;
      continue;
    }
    if (res?.error) {
      throw new CueError(`授权失败: ${res.error}`, EXIT.ERROR);
    }

    const accessToken = res?.access_token;
    if (!accessToken) continue;

    // 落盘到 credentials.json（**与用户的长期 api_key 分开**，wayfinder #72 裁决⑤）
    const file = writeCredentials({
      access_token: accessToken,
      refresh_token: res.refresh_token,
      base,
    });
    if (opts.json) {
      console.log(
        JSON.stringify(
          { authenticated: true, method: 'device', base, credentialsFile: file, scope: res.scope },
          null,
          2,
        ),
      );
    } else {
      console.log(`\n已登录 — key=${maskKey(accessToken)} base=${base}\n凭据文件: ${file}`);
    }
    return EXIT.OK;
  }

  console.error('\n[cue] 授权超时，请重试 cue auth login。\n');
  return EXIT.TIMEOUT;
}

/**
 * `cue auth status` —— **纯本地判定，无副作用、无网络**。
 *
 * wayfinder #72 的裁定：**有 refresh token 即算「已登录」**（长期 api_key 同理）。
 *
 * 为什么按「有没有可用的凭据」判、而不是去校验 access token：
 * WorkBuddy **每次重启都会跑一次 status**、授权期间还**每 3 秒轮询**它；而 access
 * token 只有 1 小时。若按 access 是否有效判，用户每小时都会被判「未登录」。
 * 联网校验还会给一个「无副作用」的命令引入网络依赖与失败模式（超时/离线时判什么？
 * 而且 3 秒一次的轮询会反复打服务端）。
 *
 * **接受的代价**：服务端已撤销时，status 会**短暂报「已登录」**，直到下一次实际调用
 * 才暴露（那时 `research` 会 401，并触发一次静默刷新；刷新失败再提示重新登录）。
 *
 * ⚠️ 输出必须继续命中连接器包的 `statusMatch`（`已登录|logged in|loggedIn|authenticated`），
 *    退出码仍为 0 / 2。
 */
export async function status(opts: AuthOptions): Promise<number> {
  const cfg = loadConfig();
  const authenticated = cfg.apiKey.length > 0;

  const detail = {
    authenticated,
    method: cfg.source,
    api_key: authenticated ? maskKey(cfg.apiKey) : null,
    can_refresh: Boolean(cfg.refreshToken),
    base: cfg.base,
    credentialsFile: cfg.source === 'credentials' ? credentialsPath() : null,
    configFile: cfg.filePath ?? configPath(),
  };

  if (opts.json) {
    console.log(JSON.stringify(detail, null, 2));
  } else if (authenticated) {
    // 「已登录」这三个字是**契约**（连接器包的 statusMatch），不要改写
    console.log(`已登录 — key=${maskKey(cfg.apiKey)} base=${cfg.base} (来源: ${cfg.source})`);
  } else {
    console.log(`未登录 — 配置文件: ${configPath()}`);
  }
  return authenticated ? EXIT.OK : EXIT.NO_CREDENTIALS;
}

/**
 * `cue auth logout` —— 先尽力撤销远端，再清本地。
 *
 * ⚠️ wayfinder #72 裁决④：撤销请求体是 **RFC 7009 的 `{token}`**，不是 CLI 1.0.0 那时的
 * `{client_id, api_key}` —— 后者是 legacy 残留，而且 `api_key` **服务端根本不支持自撤销**
 * （唯一的删除端点要配置文件里的服务级 key）⇒ 那条路连「尽力」都做不到。
 *
 * ⇒ 两条路分开如实报告：
 *   - 设备码 OAuth 令牌：尽力撤销（成功与否都清本地），
 *   - 长期 api_key：**明确告诉用户服务端不支持自撤销**，只清本地，不假装成功。
 */
export async function logout(opts: AuthOptions): Promise<number> {
  const cfg = loadConfig();
  const base = resolveBase(opts.base);
  const creds = readCredentials();

  let remoteRevoked: boolean | null = null;

  if (creds?.refresh_token) {
    try {
      await requestJson({
        method: 'POST',
        endpoint: '/cli/device/revoke',
        body: { token: creds.refresh_token },
        base: creds.base || base,
        timeoutMs: 10_000,
      });
      remoteRevoked = true;
    } catch {
      // 远端撤销是 best-effort：本地清理必须成功
      remoteRevoked = false;
    }
  }

  const removedCredentials = clearCredentials();
  const removedLocalKey = clearApiKey();

  if (opts.json) {
    console.log(
      JSON.stringify(
        { authenticated: false, removedCredentials, removedLocalKey, remoteRevoked },
        null,
        2,
      ),
    );
    return EXIT.OK;
  }

  if (removedCredentials) {
    console.log(
      remoteRevoked
        ? '已登出 — 远端令牌已撤销，本地凭据已清除'
        : '已登出 — 本地凭据已清除（远端撤销未能确认，令牌将在到期后自动失效）',
    );
  } else if (removedLocalKey) {
    // 如实说：这个 key 是用户自己在网页上创建的长期凭证，服务端没有自撤销接口
    console.log(
      `已登出 — 本地的长期 api_key 已清除。\n` +
        `  注意：这类 key 服务端**不支持**由 CLI 撤销，如需作废请到 ${API_KEY_PAGE} 删除。`,
    );
  } else {
    console.log('已登出 — 本地无凭据可清除');
  }

  // 即便本地没有凭据，也提示一下当前 base 里是否还残留 env 变量
  if (!removedCredentials && !removedLocalKey && cfg.source === 'env') {
    console.log('  （当前凭据来自环境变量 CUE_API_KEY，请自行取消该环境变量）');
  }
  return EXIT.OK;
}
