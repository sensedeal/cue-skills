/**
 * 连接器包（`connector/` + `skills/`）的**防漂移**守卫（wayfinder #88）。
 *
 * 为什么值得单独钉：
 * - `versionCheck.minVersion` 与 CLI 版本不一致的后果是**用户可见**的
 *   （#68 实测：不满足时 WorkBuddy 会**重跑 `init` 重装**，不是硬阻断）；
 * - SKILL.md 的 frontmatter `name` 与目录名不一致会**静默失效** ——
 *   本包改名（`cue-research` → `cue-research-cli`）正是因为仓里已有一个同名但
 *   形态完全不同的 Python skill，撞名的代价在**授权/调用说明**上会被放大。
 *
 * 打包脚本（`scripts/build-connector.mjs`）会**派生**版本号；这里断言的是
 * 「派生结果确实落在仓里的文件上」。
 */

import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const root = new URL('..', import.meta.url).pathname;
const read = (rel: string) => fs.readFileSync(path.join(root, rel), 'utf-8');
const readJson = (rel: string) => JSON.parse(read(rel)) as Record<string, any>;

const pkg = readJson('package.json');
const cliJson = readJson('connector/cli.json');
const metaJson = readJson('connector/connector-meta.json');

describe('连接器包的结构（#68 查实的官方必需件）', () => {
  it.each(['connector/connector-meta.json', 'connector/cli.json', 'connector/icon.svg'])(
    '%s 存在',
    (rel) => {
      expect(fs.existsSync(path.join(root, rel))).toBe(true);
    },
  );

  it('skills 下恰好一个目录，且 SKILL.md 的 name 与目录名一致', () => {
    const dirs = fs
      .readdirSync(path.join(root, 'skills'), { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => d.name);

    expect(dirs).toHaveLength(1);
    const [skillName] = dirs;
    const frontmatter = read(`skills/${skillName}/SKILL.md`).match(/^---\n([\s\S]*?)\n---/);
    expect(frontmatter, 'SKILL.md 缺少 frontmatter').not.toBeNull();
    const declared = frontmatter![1].match(/^name:\s*(.+)$/m)?.[1]?.trim();
    expect(declared).toBe(skillName);
  });

  it('CLI 形态的 skill 不与仓里既有的 Python 形态撞名', () => {
    // 仓根那个 `cue-research/` 是另一个东西（Python 脚本形态，requires python3）。
    // 本包的 skill 叫 `cue-research-cli` —— 名字若退回 `cue-research`，这条会红。
    expect(fs.existsSync(path.join(root, 'skills/cue-research'))).toBe(false);
    expect(fs.existsSync(path.join(root, 'skills/cue-research-cli/SKILL.md'))).toBe(true);
  });
});

describe('版本号不漂移（打包脚本的派生结果）', () => {
  it('cli.json 的 versionCheck.minVersion === package.json 的 version', () => {
    expect(cliJson.versionCheck.minVersion).toBe(pkg.version);
  });

  it('connector-meta.json 的 version === package.json 的 version', () => {
    expect(metaJson.version).toBe(pkg.version);
  });

  it('SKILL.md frontmatter 的 version 也跟着同一个数字', () => {
    const frontmatter = read('skills/cue-research-cli/SKILL.md').match(/^---\n([\s\S]*?)\n---/)![1];
    const declared = frontmatter.match(/^version:\s*"?([^"\n]+)"?$/m)?.[1]?.trim();
    expect(declared).toBe(pkg.version);
  });
});

describe('cli.json 里与行为强相关的字段', () => {
  it('CLI 形态与 WorkBuddy 的既有约定保持不变', () => {
    expect(metaJson.type).toBe('cli');
    expect(metaJson.minWorkbuddyVersion).toBe('5.0.0'); // 用了 authDeviceFlow(5.0.0) 就必须声明
    expect(cliJson.authWaitForExit).toBe(true); // 不设它 → 子进程被立刻杀掉 → 无法轮询换 token
    expect(cliJson.authUrlDomain).toBe('cuecue.cn'); // 授权页必须在 cuecue.cn 域内
    expect(cliJson.authDeviceFlow.codeEmbeddedInUri).toBe(true);
  });

  it('auth 子命令三件套与 CLI 实际命令一致', () => {
    expect(cliJson.auth.darwin).toBe('cue auth login');
    expect(cliJson.unAuth.darwin).toBe('cue auth logout');
    expect(cliJson.status.darwin).toBe('cue auth status');
  });

  it('statusMatch 与 CLI 的输出文案对得上（#72 裁定⑦：文案仍是契约）', () => {
    // CLI 在已登录时打印「已登录 — key=… base=… (来源: credentials)」
    const re = new RegExp(cliJson.statusMatch);
    expect(re.test('已登录 — key=wka****abcd base=https://cuecue.cn/a/api (来源: credentials)')).toBe(true);
  });

  it('设备码有效期与后端 cli_auth.device_code_ttl 对齐（600s）', () => {
    expect(cliJson.authDeviceFlow.defaultExpiresInSeconds).toBe(600);
  });

  it('init 仍从 npm 装（WorkBuddy 负责安装）', () => {
    expect(cliJson.init.darwin).toBe('npm install -g @cueai/cue-cli');
  });
});
