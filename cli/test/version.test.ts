/**
 * 版本号的**单一真相**守卫。
 *
 * `src/index.ts` 里的 `CLI_VERSION` 与 `package.json` 的 `version` 是两处字面量 ——
 * 分开写是必然的（ESM 导入 JSON 有额外约束），但**漂移会静默发生**，而它影响的是
 * 连接器包的 `versionCheck.minVersion`（不满足会**重跑安装**，用户可见）。
 * 所以用一条断言把这份副本钉住。
 */

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const pkg = JSON.parse(
  readFileSync(new URL('../package.json', import.meta.url), 'utf-8'),
) as { version: string; bin: Record<string, string> };

const source = readFileSync(new URL('../src/index.ts', import.meta.url), 'utf-8');

describe('版本号', () => {
  it('index.ts 的 CLI_VERSION 与 package.json 一致', () => {
    const match = source.match(/const CLI_VERSION = '([^']+)'/);
    expect(match, 'index.ts 里找不到 CLI_VERSION 字面量').not.toBeNull();
    expect(match?.[1]).toBe(pkg.version);
  });

  it('bin 仍指向 dist/index.js（连接器包的 init/versionCheck 都按这个入口）', () => {
    expect(pkg.bin.cue).toBe('dist/index.js');
  });
});
