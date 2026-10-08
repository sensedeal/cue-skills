/**
 * 凭证层：读取优先级、落盘权限、**文件锁**与静默刷新（wayfinder #71 / #72）。
 *
 * 这一批用例存在的理由：刷新路径一旦写错，症状是「用户偶发莫名其妙被登出」
 * （服务端的重放检测撤销整个令牌家族），事后极难定位 —— 所以这里把三件事钉死：
 * 读取优先级、锁内重读、轮换后的 refresh token 必须写回。
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { loadConfig, credentialsPath, configPath, saveConfig, DEFAULT_BASE } from '../src/config.js';
import {
  clearCredentials,
  readCredentials,
  refreshAccessToken,
  withCredentialsLock,
  writeCredentials,
  credentialsLockPath,
} from '../src/credentials.js';

let home: string;
let originalHome: string | undefined;

beforeEach(() => {
  home = fs.mkdtempSync(path.join(os.tmpdir(), 'cue-cred-'));
  originalHome = process.env.CUE_HOME;
  process.env.CUE_HOME = home;
  delete process.env.CUE_API_KEY;
  delete process.env.CUE_API_BASE;
});

afterEach(() => {
  try {
    fs.rmSync(home, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
  if (originalHome === undefined) delete process.env.CUE_HOME;
  else process.env.CUE_HOME = originalHome;
  vi.unstubAllGlobals();
});

describe('凭证落盘', () => {
  it('写入 0600，且能读回', () => {
    const file = writeCredentials({ access_token: 'wka_a', refresh_token: 'wkr_r', base: 'https://x/a/api' });

    expect(file).toBe(credentialsPath());
    const mode = fs.statSync(file).mode & 0o777;
    expect(mode.toString(8)).toBe('600');

    const back = readCredentials();
    expect(back?.access_token).toBe('wka_a');
    expect(back?.refresh_token).toBe('wkr_r');
    expect(back?.base).toBe('https://x/a/api');
  });

  it('clearCredentials 删掉整个文件', () => {
    writeCredentials({ access_token: 'wka_a', base: DEFAULT_BASE });
    expect(clearCredentials()).toBe(true);
    expect(readCredentials()).toBeNull();
    expect(clearCredentials()).toBe(false); // 幂等
  });
});

describe('loadConfig 的读取优先级（#72 裁定⑤）', () => {
  it('env > credentials.json > config.json', () => {
    saveConfig({ api_key: 'skn_config', base: 'https://cfg/a/api' });
    writeCredentials({ access_token: 'wka_cred', refresh_token: 'wkr_r', base: 'https://cred/a/api' });

    // ② credentials.json 压过 ③ config.json
    let cfg = loadConfig();
    expect(cfg.apiKey).toBe('wka_cred');
    expect(cfg.source).toBe('credentials');
    expect(cfg.refreshToken).toBe('wkr_r');
    expect(cfg.base).toBe('https://cred/a/api');

    // ① env 最高
    process.env.CUE_API_KEY = 'skn_env';
    cfg = loadConfig();
    expect(cfg.apiKey).toBe('skn_env');
    expect(cfg.source).toBe('env');
    expect(cfg.refreshToken).toBeUndefined();
  });

  it('只有 config.json 时回落为 config 来源（老用户不受影响）', () => {
    saveConfig({ api_key: 'skn_only', base: 'https://cfg/a/api' });

    const cfg = loadConfig();
    expect(cfg.apiKey).toBe('skn_only');
    expect(cfg.source).toBe('config');
    expect(cfg.refreshToken).toBeUndefined();
    expect(cfg.filePath).toBe(configPath());
  });

  it('都没有时来源为 none，base 用默认值（含 /{sso-path} 的 /a）', () => {
    const cfg = loadConfig();
    expect(cfg.source).toBe('none');
    expect(cfg.apiKey).toBe('');
    expect(cfg.base).toBe(DEFAULT_BASE);
    expect(DEFAULT_BASE).toMatch(/\/a\/api$/);
  });
});

describe('文件锁（并发 cue 进程的护栏）', () => {
  it('并发临界区被串行化', async () => {
    const order: string[] = [];
    const slow = async (tag: string) => {
      order.push(`${tag}:enter`);
      await new Promise((r) => setTimeout(r, 60));
      order.push(`${tag}:exit`);
    };

    await Promise.all([
      withCredentialsLock(() => slow('a')),
      withCredentialsLock(() => slow('b')),
    ]);

    // 不许交错：每个 enter 后面必须紧跟自己的 exit
    expect(order).toEqual(['a:enter', 'a:exit', 'b:enter', 'b:exit']);
  });

  it('临界区抛错也会释放锁（不留死锁）', async () => {
    await expect(
      withCredentialsLock(() => {
        throw new Error('boom');
      }),
    ).rejects.toThrow('boom');

    expect(fs.existsSync(credentialsLockPath())).toBe(false);
    // 释放后可再次获取
    await expect(withCredentialsLock(() => 'ok')).resolves.toBe('ok');
  });

  it('陈旧锁（持有者崩了）可被抢占', async () => {
    fs.writeFileSync(credentialsLockPath(), '');
    const old = new Date(Date.now() - 60_000);
    fs.utimesSync(credentialsLockPath(), old, old);

    await expect(withCredentialsLock(() => 'ok')).resolves.toBe('ok');
  });
});

describe('静默刷新（#71 的「锁内重读」）', () => {
  it('没有 refresh token 时直接返回 null（不猜）', async () => {
    saveConfig({ api_key: 'skn_only', base: DEFAULT_BASE });
    expect(await refreshAccessToken(DEFAULT_BASE, 'skn_only')).toBeNull();
  });

  it('令牌已被别的进程换过：**不发起刷新**，直接复用', async () => {
    writeCredentials({
      access_token: 'wka_rotated',
      refresh_token: 'wkr_r',
      base: 'https://x/a/api',
    });
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    // 传进来的是**过期的那个**令牌（触发 401 的那把）
    const result = await refreshAccessToken('https://x/a/api', 'wka_stale');

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(result).toEqual({ accessToken: 'wka_rotated', refreshed: false });
  });

  it('正常刷新：表单编码打到 {base}/oauth/token，且**轮换后的 refresh token 必须写回**', async () => {
    writeCredentials({ access_token: 'wka_stale', refresh_token: 'wkr_old', base: 'https://x/a/api' });
    const fetchSpy = vi.fn(async (_url: string, init: RequestInit) => {
      return new Response(JSON.stringify({ access_token: 'wka_new', refresh_token: 'wkr_new' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchSpy);

    const result = await refreshAccessToken('https://x/a/api', 'wka_stale');

    expect(result).toEqual({ accessToken: 'wka_new', refreshed: true });
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe('https://x/a/api/oauth/token');
    expect((init as RequestInit).method).toBe('POST');
    // RFC 6749 的刷新用表单编码，不是 JSON
    expect((init as { headers: Record<string, string> }).headers['Content-Type']).toBe(
      'application/x-www-form-urlencoded',
    );
    const body = String((init as RequestInit).body);
    expect(body).toContain('grant_type=refresh_token');
    expect(body).toContain('refresh_token=wkr_old');

    // ⚠️ 这是本次改造最容易漏的一步：不写回新的 refresh token，下次刷新就是「重放」
    const persisted = readCredentials();
    expect(persisted?.access_token).toBe('wka_new');
    expect(persisted?.refresh_token).toBe('wkr_new');
  });

  it('服务端拒绝（401）→ null，且**不改动**本地凭据', async () => {
    writeCredentials({ access_token: 'wka_stale', refresh_token: 'wkr_old', base: 'https://x/a/api' });
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 401 })));

    expect(await refreshAccessToken('https://x/a/api', 'wka_stale')).toBeNull();
    expect(readCredentials()?.refresh_token).toBe('wkr_old');
  });

  it('网络异常 → null（不把异常抛给调用链）', async () => {
    writeCredentials({ access_token: 'wka_stale', refresh_token: 'wkr_old', base: 'https://x/a/api' });
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('network down');
      }),
    );

    expect(await refreshAccessToken('https://x/a/api', 'wka_stale')).toBeNull();
  });
});
