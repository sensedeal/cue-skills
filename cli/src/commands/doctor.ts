/**
 * `cue doctor` — environment self-check (no side effects).
 *
 * Prints a JSON report: runtime, credential source, and connectivity to
 * GET /tools/capabilities. Exit 0 when key present AND API reachable.
 *
 * ⚠️ wayfinder #93：这个自检**本来只探了一个 base** —— 那时 CLI 以为所有端点都在同一
 * 前缀下。实测打脸（业务端点在 host 根 `/api`、AS 端点在 `/{sso}/api`），单探一个会
 * 把「业务通但认证断」报成全绿。所以现在**两族各探一次**，并把两个 base 都印出来。
 *
 * 退出码**仍只看业务侧**（与改动前一致）：`/.well-known/` 在某个环境缺失不该把自检
 * 判成故障；AS 侧结果作为信息呈现。
 */

import { resolveBases } from '../bases.js';
import { API_KEY_PAGE, configPath, loadConfig, maskKey } from '../config.js';
import { requestJson } from '../http.js';

export interface DoctorOptions {
  base?: string;
}

interface ProbeResult {
  ok: boolean;
  latencyMs: number;
  error?: string;
}

async function probe(endpoint: string, apiKey: string | undefined, base: string): Promise<ProbeResult> {
  const started = Date.now();
  try {
    await requestJson({ method: 'GET', endpoint, apiKey, base, timeoutMs: 15_000 });
    return { ok: true, latencyMs: Date.now() - started };
  } catch (err) {
    return {
      ok: false,
      latencyMs: Date.now() - started,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export async function doctor(opts: DoctorOptions = {}): Promise<number> {
  const cfg = loadConfig();
  const base = opts.base?.trim() || cfg.base;
  const bases = resolveBases(base);

  // 业务侧：带令牌，代表「核心功能能不能跑」
  const connectivity = await probe('/tools/capabilities', cfg.apiKey || undefined, base);
  // AS 侧：OAuth 元数据端点（公开、只读、无副作用）——200 即代表 AS base 通
  const authorizationServer = await probe('/.well-known/oauth-authorization-server', undefined, base);

  const report = {
    node: process.version,
    platform: process.platform,
    cliVersion: '1.0.0',
    configFile: cfg.filePath ?? configPath(),
    apiKey: cfg.apiKey ? maskKey(cfg.apiKey) : null,
    base,
    bases: { auth: bases.auth, business: bases.business },
    connectivity,
    authorizationServer,
    apiKeyPage: API_KEY_PAGE,
  };
  console.log(JSON.stringify(report, null, 2));
  return cfg.apiKey && connectivity.ok === true ? 0 : 1;
}
