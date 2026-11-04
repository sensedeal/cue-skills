/**
 * `cue auth` 的三条命令与轮询语义（wayfinder #72 的裁定）。
 *
 * 钉住的是**最容易悄悄坏掉**的那几处：
 * - 轮询**只认响应体里的 `error`**（不认状态码）—— 这条一坏，服务端按 RFC 8628 返 400
 *   时 CLI 会在**第一次轮询就抛错退出**，而 428 是 1.0.0 自己发明的、服务端不该迁就；
 * - `status` 是**纯本地**判定（有 refresh 即已登录），且输出必须继续命中连接器包的
 *   `statusMatch`（`已登录|logged in|loggedIn|authenticated`）；
 * - `logout` 发的是 RFC 7009 的 `{token}`，且对**不可自撤销的长期 api_key** 如实说明。
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { login, logout, pollError, status } from '../src/commands/auth.js';
import { configPath, credentialsPath, saveConfig } from '../src/config.js';
import { readCredentials, writeCredentials } from '../src/credentials.js';
import { CueApiError } from '../src/errors.js';

const BASE = 'https://x/a/api';

let home: string;
let originalHome: string | undefined;
let out: string[];
let err: string[];

function capture(): void {
  vi.spyOn(console, 'log').mockImplementation((...args: unknown[]) => {
    out.push(args.join(' '));
  });
  vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
    err.push(args.join(' '));
  });
}

beforeEach(() => {
  home = fs.mkdtempSync(path.join(os.tmpdir(), 'cue-auth-'));
  originalHome = process.env.CUE_HOME;
  process.env.CUE_HOME = home;
  delete process.env.CUE_API_KEY;
  delete process.env.CUE_API_BASE;
  out = [];
  err = [];
  capture();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  try {
    fs.rmSync(home, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
  if (originalHome === undefined) delete process.env.CUE_HOME;
  else process.env.CUE_HOME = originalHome;
});

// --------------------------------------------------------------------------
// 轮询错误的判定（#72 裁决③ —— 本票最要紧的那条）
// --------------------------------------------------------------------------

describe('pollError 的判定规则', () => {
  const apiError = (status: number, detail: string) => new CueApiError(status, detail, '/cli/device/token');

  it.each([
    [400, 'authorization_pending'],
    [400, 'slow_down'],
    [400, 'expired_token'],
    [400, 'access_denied'],
    [400, 'invalid_grant'],
  ])('HTTP %i + body.error=%s 时按 body 取值（RFC 8628 的状态码就是 400）', (status, code) => {
    const parsed = pollError(apiError(status, JSON.stringify({ error: code })));
    expect(parsed).toEqual({ status, error: code });
  });

  it('428 + body.error 也认（不为客户端的历史写法设障，但也不依赖它）', () => {
    expect(pollError(apiError(428, JSON.stringify({ error: 'authorization_pending' })))).toEqual({
      status: 428,
      error: 'authorization_pending',
    });
  });

  it('**取不到 error 就不猜**（交给调用方抛出，别伪装成 pending 挂到超时）', () => {
    expect(pollError(apiError(500, 'internal boom'))).toEqual({ status: 500, error: '' });
    expect(pollError(apiError(428, 'not json at all'))).toEqual({ status: 428, error: '' });
    expect(pollError(new Error('nope'))).toEqual({ status: 0, error: '' });
  });
});

// --------------------------------------------------------------------------
// 登录：设备码流程
// --------------------------------------------------------------------------

interface StubCall {
  url: string;
  body: unknown;
}

/** 用 stub 的 fetch 依次应答：device/code → 若干次 device/token */
function stubDeviceFlow(codeResponse: Record<string, unknown>, tokenResponses: Array<Record<string, unknown> | number>) {
  const calls: StubCall[] = [];
  let tokenIndex = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ url: String(url), body });
      if (String(url).endsWith('/cli/device/code')) {
        return new Response(JSON.stringify(codeResponse), { status: 200 });
      }
      const next = tokenResponses[Math.min(tokenIndex, tokenResponses.length - 1)];
      tokenIndex += 1;
      if (typeof next === 'number') return new Response('{}', { status: next });
      return new Response(JSON.stringify(next), { status: 200 });
    }),
  );
  return calls;
}

describe('cue auth login（设备码）', () => {
  it('申请设备码用的是 mcp:invoke（#71：不新增 research scope）', async () => {
    const calls = stubDeviceFlow(
      {
        device_code: 'dev-1',
        user_code: 'WDJB-MJHT',
        verification_uri: 'https://x/device',
        verification_uri_complete: 'https://x/device?user_code=WDJB-MJHT',
        expires_in: 600,
        interval: 2,
      },
      [{ access_token: 'wka_new', refresh_token: 'wkr_new' }],
    );

    await login({ base: BASE });

    expect(calls[0].url).toBe(`${BASE}/cli/device/code`);
    expect(calls[0].body).toEqual({ client_id: 'cue-cli', scope: 'mcp:invoke' });
  });

  it('授权 URL 裸打印（前后留白），且令牌落入 credentials.json 而不是 config.json', async () => {
    stubDeviceFlow(
      {
        device_code: 'dev-1',
        user_code: 'WDJB-MJHT',
        verification_uri: 'https://x/device',
        verification_uri_complete: 'https://x/device?user_code=WDJB-MJHT',
        expires_in: 600,
        interval: 2,
      },
      [{ access_token: 'wka_new', refresh_token: 'wkr_new' }],
    );

    const exit = await login({ base: BASE });

    expect(exit).toBe(0);
    expect(out.join('\n')).toContain('https://x/device?user_code=WDJB-MJHT');
    // 裸打印：URL 前后必须有空白，供 WorkBuddy 用正则提取
    expect(out.join('\n')).toMatch(/\shttps:\/\/x\/device\?user_code=WDJB-MJHT\s/);

    const creds = readCredentials();
    expect(creds?.access_token).toBe('wka_new');
    expect(creds?.refresh_token).toBe('wkr_new');
    // 长期 key 的坑位不该被设备码令牌占用
    expect(fs.existsSync(configPath())).toBe(false);
  });
});

// --------------------------------------------------------------------------
// status：纯本地
// --------------------------------------------------------------------------

describe('cue auth status', () => {
  it('有 OAuth 令牌 → 已登录 / 退出码 0，且**不发任何请求**', async () => {
    writeCredentials({ access_token: 'wka_a', refresh_token: 'wkr_r', base: BASE });
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    expect(await status({})).toBe(0);
    expect(out.join('\n')).toContain('已登录');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('只有长期 api_key 也算已登录（老用户不受影响）', async () => {
    saveConfig({ api_key: 'skn_legacy', base: BASE });

    expect(await status({})).toBe(0);
    expect(out.join('\n')).toContain('已登录');
  });

  it('无凭据 → 未登录 / 退出码 2', async () => {
    expect(await status({})).toBe(2);
    expect(out.join('\n')).toContain('未登录');
  });

  it('输出必须命中连接器包的 statusMatch（`已登录|logged in|loggedIn|authenticated`）', async () => {
    saveConfig({ api_key: 'skn_legacy', base: BASE });
    await status({});

    // 连接器包 cli.json 里的正则，逐字复制过来 —— 它变了这里就该红
    expect(out.join('\n')).toMatch(/已登录|logged in|loggedIn|authenticated/);
  });

  it('access 过期但 refresh 仍在 → 仍报已登录（WorkBuddy 每次重启都会跑它）', async () => {
    // 这里刻意用一个「明显不是有效 access」的值，status 不做任何远端校验
    writeCredentials({ access_token: 'wka_stale_looking', refresh_token: 'wkr_r', base: BASE });

    expect(await status({})).toBe(0);
    expect(out.join('\n')).toContain('已登录');
  });
});

// --------------------------------------------------------------------------
// logout
// --------------------------------------------------------------------------

describe('cue auth logout', () => {
  it('OAuth 凭据：发 RFC 7009 的 {token} 到 /cli/device/revoke，再清本地', async () => {
    writeCredentials({ access_token: 'wka_a', refresh_token: 'wkr_r', base: BASE });
    const calls: StubCall[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url: String(url), body: init?.body ? JSON.parse(String(init.body)) : undefined });
        return new Response('{}', { status: 200 });
      }),
    );

    expect(await logout({ base: BASE })).toBe(0);

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe(`${BASE}/cli/device/revoke`);
    // ⚠️ 是 {token}，不是 1.0.0 那时的 {client_id, api_key}
    expect(calls[0].body).toEqual({ token: 'wkr_r' });
    expect(fs.existsSync(credentialsPath())).toBe(false);
  });

  it('远端撤销失败也照样清本地（best-effort），且输出如实说明', async () => {
    writeCredentials({ access_token: 'wka_a', refresh_token: 'wkr_r', base: BASE });
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('offline');
      }),
    );

    expect(await logout({ base: BASE })).toBe(0);
    expect(fs.existsSync(credentialsPath())).toBe(false);
    expect(out.join('\n')).toContain('远端撤销未能确认');
  });

  it('长期 api_key：**不发撤销请求**，并明确说明服务端不支持自撤销', async () => {
    saveConfig({ api_key: 'skn_legacy', base: BASE });
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    expect(await logout({ base: BASE })).toBe(0);

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(out.join('\n')).toContain('不支持');
    // 本地 key 必须清掉
    const blob = JSON.parse(fs.readFileSync(configPath(), 'utf-8')) as Record<string, unknown>;
    expect(blob.api_key).toBeUndefined();
  });

  it('没有凭据时幂等返回 0', async () => {
    expect(await logout({ base: BASE })).toBe(0);
    expect(out.join('\n')).toContain('本地无凭据可清除');
  });
});
