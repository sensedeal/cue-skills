/**
 * 「两族端点、两个前缀」这条约定的钉子（wayfinder #93）。
 *
 * 为什么值得钉：这条约定**推不出来**（AS 的 well-known 与设备码响应只广告 AS 自己的端点），
 * 只能硬编码 —— 而硬编码的约定漂移时**没人会注意到**，直到某条命令在用户那里 404。
 * 历史上它已经被漂移过一次：#87 把默认 base 从根 `/api` 挪到 `/{sso}/api`，
 * 修好了认证、**静默打死了业务端点**。
 *
 * 钉三件事：
 * 1. 业务 base 由 origin 推出（不数分段，三环境都要对）；
 * 2. 分族白名单：AS 端点走认证 base，其余走业务 base；
 * 3. 两个「绝不能发生」的方向 —— 业务端点不得带 `{sso}` 段，AS 端点不得落 host 根。
 */

import { describe, expect, it } from 'vitest';

import { baseForEndpoint, resolveBases } from '../src/bases.js';

/** 三环境的实配 base（#78 地址表：dev 的 sso 段是 `dgts`，生产是 `a`） */
const DEV_BASE = 'https://cuecuewxx.cuecue.cn/dgts/api';
const DGTS_BASE = 'https://dgts.cuecue.cn/dgts/api';
const PROD_BASE = 'https://cuecue.cn/a/api';

describe('resolveBases —— 业务 base 由 origin 推出', () => {
  it.each([
    ['dev', DEV_BASE, 'https://cuecuewxx.cuecue.cn/api'],
    ['dgts', DGTS_BASE, 'https://dgts.cuecue.cn/api'],
    ['生产', PROD_BASE, 'https://cuecue.cn/api'],
  ])('%s：业务 base 剥掉 /{sso}/api、只留 origin + /api', (_label, authBase, expected) => {
    const bases = resolveBases(authBase);
    expect(bases.auth).toBe(authBase);
    expect(bases.business).toBe(expected);
  });

  it('尾斜杠不影响（auth 归一化，business 仍取 origin）', () => {
    const bases = resolveBases(`${PROD_BASE}/`);
    expect(bases.auth).toBe(PROD_BASE);
    expect(bases.business).toBe('https://cuecue.cn/api');
  });

  it('base 不是合法绝对 URL ⇒ 退回单 base（与改动前同样地失败，而不是变成另一种错）', () => {
    const bases = resolveBases('/relative/api');
    expect(bases.business).toBe(bases.auth);
  });
});

describe('baseForEndpoint —— 分族白名单', () => {
  const bases = resolveBases(DEV_BASE);

  it.each([
    ['设备码申请', '/cli/device/code'],
    ['设备码换令牌', '/cli/device/token'],
    ['设备码撤销', '/cli/device/revoke'],
    ['OAuth token（refresh 用）', '/oauth/token'],
    ['OAuth 元数据', '/.well-known/oauth-authorization-server'],
  ])('%s → AS base', (_label, endpoint) => {
    expect(baseForEndpoint(endpoint, bases)).toBe(bases.auth);
  });

  it.each([
    ['研究流', '/chat/stream'],
    ['模板列表（带 query）', '/templates?mode=is_me&include_system=false'],
    ['模板详情', '/templates/template_cQW2Ta'],
    ['能力清单', '/tools/capabilities'],
  ])('%s → 业务 base', (_label, endpoint) => {
    expect(baseForEndpoint(endpoint, bases)).toBe(bases.business);
  });

  it('无前导斜杠也认（`templates` 与 `/templates` 同族）', () => {
    expect(baseForEndpoint('templates', bases)).toBe(bases.business);
    expect(baseForEndpoint('cli/device/code', bases)).toBe(bases.auth);
  });
});

describe('两个「绝不能发生」的方向', () => {
  const bases = resolveBases(DEV_BASE);

  it('业务端点**不得**带 `{sso}` 段 —— 那正是 #87 打死业务的那个错', () => {
    for (const endpoint of ['/templates', '/chat/stream', '/tools/capabilities']) {
      expect(baseForEndpoint(endpoint, bases)).not.toContain('/dgts/');
    }
  });

  it('AS 端点**不得**落 host 根 —— 根 `/api` 上没有到 cubeauth 的反代规则', () => {
    for (const endpoint of ['/cli/device/code', '/oauth/token']) {
      expect(baseForEndpoint(endpoint, bases)).not.toBe(bases.business);
      expect(baseForEndpoint(endpoint, bases)).toContain('/dgts/api');
    }
  });
});
