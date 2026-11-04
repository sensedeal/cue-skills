/**
 * Credential & config loading.
 *
 * ## 读取优先级（wayfinder #72 裁定⑤）
 *
 *   1. 环境变量 `CUE_API_KEY`（base 取 `CUE_API_BASE`）
 *   2. `$CUE_HOME/credentials.json`（**设备码 OAuth 令牌**，本方案新增）
 *   3. `$CUE_HOME/config.json`（用户自己配置的长期 api_key，向后兼容）
 *
 * ## 为什么令牌要与长期 key 分文件
 *
 * 两者的生命周期完全不同：OAuth 令牌 1 小时过期、可被服务端撤销、需要 refresh 轮换；
 * 而用户自填的 api_key 长期有效、**服务端根本不支持自撤销**（唯一的删除端点要配置里的
 * 服务级 key）。混在一个文件里，`logout` 与 `status` 都只能含糊其辞。
 *
 * ## 凭证边界（沿用既有约束）
 *
 * **提供 key 的文件同时提供 base，绝不跨文件拼**：一把 key 只能发给它自己那个文件
 * 指定的服务端。
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

/**
 * 默认 base。
 *
 * ⚠️ wayfinder #72/#78：路径里**必须带 `/{sso-path}`**（生产为 `/a`）。
 * 少这一段会打到产品前端的根 `/api/*` —— 那里没有到 cubeauth 的反代规则，
 * 结果是 404 而不是 401（实测：`/{sso}/api/oauth/token` 三环境全 405，
 * 而根 `/api/oauth/token` 全 404）。
 */
export const DEFAULT_BASE = 'https://cuecue.cn/a/api';
export const API_KEY_PAGE = 'https://cuecue.cn/api-key';

/** 凭证来源 —— `status` 与刷新逻辑据此分支 */
export type CredentialSource = 'env' | 'credentials' | 'config' | 'none';

export interface LoadedConfig {
  /** 实际用于 `Authorization` 的令牌（OAuth access token 或长期 api_key） */
  apiKey: string;
  base: string;
  /** 提供凭据的文件路径（env 来源时为空） */
  filePath?: string;
  /** 设备码 OAuth 的刷新令牌；仅当来源是 `credentials.json` 时存在 */
  refreshToken?: string;
  /** 凭据来自哪里 */
  source: CredentialSource;
}

export function configDir(): string {
  const home = process.env.CUE_HOME?.trim();
  return home ? home : path.join(os.homedir(), '.cue');
}

export function configPath(): string {
  return path.join(configDir(), 'config.json');
}

/** 设备码 OAuth 令牌的落盘位置（与安装目录、与长期 key 都分离） */
export function credentialsPath(): string {
  return path.join(configDir(), 'credentials.json');
}

export function legacyConfigPath(): string {
  return path.join(os.homedir(), '.cue', 'config.json');
}

function readJsonFile(file: string): Record<string, unknown> | null {
  try {
    if (!fs.existsSync(file)) return null;
    const raw = fs.readFileSync(file, 'utf-8');
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function str(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

export function loadConfig(): LoadedConfig {
  const envKey = (process.env.CUE_API_KEY ?? '').trim();
  const envBase = (process.env.CUE_API_BASE ?? '').trim();

  if (envKey) {
    return { apiKey: envKey, base: envBase || DEFAULT_BASE, source: 'env' };
  }

  // ② credentials.json —— 设备码 OAuth 令牌（access + refresh 成对）
  const credsFile = credentialsPath();
  const creds = readJsonFile(credsFile);
  const accessToken = str(creds?.access_token);
  if (accessToken) {
    return {
      apiKey: accessToken,
      base: envBase || str(creds?.base) || DEFAULT_BASE,
      filePath: credsFile,
      refreshToken: str(creds?.refresh_token) || undefined,
      source: 'credentials',
    };
  }

  // ③ config.json —— 用户自填的长期 api_key（含 legacy 路径）
  const candidates = Array.from(new Set([configPath(), legacyConfigPath()]));
  for (const candidate of candidates) {
    const blob = readJsonFile(candidate);
    if (!blob) continue;
    const key = str(blob.api_key);
    if (!key) continue;
    return {
      apiKey: key,
      base: envBase || str(blob.base) || DEFAULT_BASE,
      filePath: candidate,
      source: 'config',
    };
  }

  return { apiKey: '', base: envBase || DEFAULT_BASE, source: 'none' };
}

/**
 * 写入长期 api_key（`cue auth login --api-key` 这条路）。
 *
 * ⚠️ 它**不写** credentials.json —— 用户自填的 key 属于 config.json。
 * 两者分开正是为了让 `logout` / `status` 能说清自己在处理哪一种凭据。
 */
export function saveConfig(patch: { api_key?: string; base?: string }): string {
  const file = configPath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const current = readJsonFile(file) ?? {};
  const next = { ...current, ...patch };
  fs.writeFileSync(file, `${JSON.stringify(next, null, 2)}\n`, { encoding: 'utf-8', mode: 0o600 });
  try {
    fs.chmodSync(file, 0o600);
  } catch {
    /* chmod is best effort (not supported on all filesystems) */
  }
  return file;
}

/** Remove only the credential; keep base and any other user settings. */
export function clearApiKey(): boolean {
  const file = configPath();
  const blob = readJsonFile(file);
  if (!blob || typeof blob.api_key !== 'string') return false;
  delete blob.api_key;
  fs.writeFileSync(file, `${JSON.stringify(blob, null, 2)}\n`, { encoding: 'utf-8', mode: 0o600 });
  return true;
}

export function maskKey(key: string): string {
  if (!key) return '(none)';
  const tail = key.slice(-4);
  const head = key.slice(0, 3);
  return `${head}${'*'.repeat(Math.max(4, key.length - head.length - tail.length))}${tail}`;
}
