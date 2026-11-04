/**
 * 设备码 OAuth 令牌的落盘、**文件锁**与静默刷新（wayfinder #71 / #72 裁定⑤⑥）。
 *
 * ## 为什么需要文件锁（这条不是洁癖）
 *
 * 服务端的 refresh 是**轮换 + fail-closed 重放检测**：旧的 `wkr_` 一旦被用过就立即失效，
 * 而「同一个 refresh token 被用第二次」会被判为重放 —— 处置是**撤销整个令牌家族**
 * （`app/services/oauth_token.py` 的 `rotate_refresh_token` 与
 * `app/api/oauth.py` 的 `_handle_replay`，后者连并发 TOCTOU 落败都按重放处理）。
 *
 * 而 WorkBuddy 可能**并发跑多个 `cue` 进程**。若两个进程同时拿同一个 `wkr_` 去刷新，
 * 一个成功、另一个被判重放 ⇒ **整族被撤销 ⇒ 用户莫名其妙被登出**，且事后极难定位。
 *
 * ⇒ 本模块的做法（#71 的裁定）：**加锁 → 锁内重读 → 若令牌已被别的进程换过就直接用它，
 * 不发起刷新**。
 */

import fs from 'node:fs';
import path from 'node:path';

import { credentialsPath, DEFAULT_BASE, configDir } from './config.js';
import { CueError, EXIT } from './errors.js';

/** 落盘形状。字段名沿用 OAuth 的 snake_case，便于直接对照协议 */
export interface CredentialsFile {
  access_token: string;
  refresh_token?: string;
  base: string;
  /** 写入时间（Unix 秒），仅供诊断 */
  obtained_at?: number;
}

const LOCK_FILE = '.credentials.lock';
const LOCK_RETRY_MS = 50;
const LOCK_TIMEOUT_MS = 5_000;
/** 持有者崩了没释放时的陈旧阈值 —— 超过即可抢占 */
const LOCK_STALE_MS = 15_000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function lockPath(): string {
  return path.join(configDir(), LOCK_FILE);
}

function readJson(file: string): Record<string, unknown> | null {
  try {
    if (!fs.existsSync(file)) return null;
    const parsed: unknown = JSON.parse(fs.readFileSync(file, 'utf-8'));
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function str(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

export function readCredentials(): CredentialsFile | null {
  const blob = readJson(credentialsPath());
  if (!blob) return null;
  const access = str(blob.access_token);
  if (!access) return null;
  return {
    access_token: access,
    refresh_token: str(blob.refresh_token) || undefined,
    base: str(blob.base) || DEFAULT_BASE,
    obtained_at: typeof blob.obtained_at === 'number' ? blob.obtained_at : undefined,
  };
}

/** 写入（0600）。整体替换而非合并 —— 避免上一轮的字段残留成幽灵状态 */
export function writeCredentials(creds: CredentialsFile): string {
  const file = credentialsPath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const payload = { ...creds, obtained_at: creds.obtained_at ?? Math.floor(Date.now() / 1000) };
  fs.writeFileSync(file, `${JSON.stringify(payload, null, 2)}\n`, { encoding: 'utf-8', mode: 0o600 });
  try {
    fs.chmodSync(file, 0o600);
  } catch {
    /* chmod is best effort */
  }
  return file;
}

export function clearCredentials(): boolean {
  const file = credentialsPath();
  if (!fs.existsSync(file)) return false;
  fs.unlinkSync(file);
  return true;
}

/**
 * 以**独占文件锁**执行一段临界区（`open(..., 'wx')` = 原子创建）。
 *
 * 锁只在本地进程间起作用（同一台机器、同一个 `CUE_HOME`），这正是要防的场景：
 * WorkBuddy 在同一台机器上并发拉起多个 CLI。
 */
export async function withCredentialsLock<T>(fn: () => Promise<T> | T): Promise<T> {
  const file = lockPath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const deadline = Date.now() + LOCK_TIMEOUT_MS;
  let fd: number | null = null;

  for (;;) {
    try {
      fd = fs.openSync(file, 'wx');
      break;
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== 'EEXIST') throw err;
      // 陈旧锁（持有者崩了）：抢占
      try {
        const stat = fs.statSync(file);
        if (Date.now() - stat.mtimeMs > LOCK_STALE_MS) {
          fs.unlinkSync(file);
          continue;
        }
      } catch {
        /* 锁刚好被释放 —— 下一圈重试即可 */
      }
      if (Date.now() > deadline) {
        throw new CueError(
          '等待凭证锁超时（可能另一个 cue 进程正在刷新令牌）',
          EXIT.ERROR,
        );
      }
      await sleep(LOCK_RETRY_MS);
    }
  }

  try {
    return await fn();
  } finally {
    try {
      if (fd !== null) fs.closeSync(fd);
    } catch {
      /* ignore */
    }
    try {
      fs.unlinkSync(file);
    } catch {
      /* ignore */
    }
  }
}

// --------------------------------------------------------------------------
// 静默刷新
// --------------------------------------------------------------------------

export interface RefreshResult {
  accessToken: string;
  /** 是否真的发起过刷新（false = 复用别的进程刚换来的令牌） */
  refreshed: boolean;
}

/**
 * 刷新 access token。
 *
 * `staleAccessToken` = **触发本次刷新时那个已经 401 的访问令牌**。
 * 锁内重读时若发现它已被换掉，说明别的进程刚刷过 —— 直接复用，**不发起刷新**
 * （这正是避免重放家族撤销的关键）。
 *
 * 返回 `null` 表示无法刷新（没有 refresh token / 服务端拒绝），调用方据此提示重新登录。
 */
export async function refreshAccessToken(
  base: string,
  staleAccessToken: string,
): Promise<RefreshResult | null> {
  return withCredentialsLock(async () => {
    const current = readCredentials();
    if (!current || !current.refresh_token) return null;

    // ⚠️ 锁内重读：已被别的进程换过 ⇒ 复用，绝不重复刷新
    if (current.access_token && current.access_token !== staleAccessToken) {
      return { accessToken: current.access_token, refreshed: false };
    }

    const endpoint = `${base.replace(/\/+$/, '')}/oauth/token`;
    const body = new URLSearchParams({
      grant_type: 'refresh_token',
      refresh_token: current.refresh_token,
      client_id: 'cue-cli',
    });

    let response: Response;
    try {
      response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      });
    } catch {
      return null;
    }
    if (!response.ok) return null;

    const payload = (await response.json().catch(() => null)) as
      | { access_token?: string; refresh_token?: string }
      | null;
    const accessToken = str(payload?.access_token);
    if (!accessToken) return null;

    // 轮换：新的 refresh token 必须**立刻写回**，否则下次刷新会被判重放
    writeCredentials({
      access_token: accessToken,
      refresh_token: str(payload?.refresh_token) || current.refresh_token,
      base: current.base || base,
    });
    return { accessToken, refreshed: true };
  });
}

/** 供测试与诊断：当前锁文件路径 */
export function credentialsLockPath(): string {
  return lockPath();
}
