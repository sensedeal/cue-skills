/**
 * 版本号的**单一真相**守卫。
 *
 * `src/version.ts` 里的 `CLI_VERSION` 与 `package.json` 的 `version` 是两处字面量 ——
 * 分开写是必然的（ESM 导入 JSON 有额外约束），但**漂移会静默发生**，而它影响的是
 * 连接器包的 `versionCheck.minVersion`（不满足会**重跑安装**，用户可见）。
 * 所以用断言把这份副本钉住。
 *
 * ⚠️ 钉**一个文件**曾经不够：`doctor` 那时自己硬编码了 `1.0.0`，而旧守卫只扫
 * `index.ts` ⇒ 自检报告报了一年的错版本号没人发现。所以除钉 `version.ts` 之外，
 * 还要扫全 `src/`，保证**不存在第二处**版本号字面量（wayfinder #93）。
 */

import { readdirSync, readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const pkg = JSON.parse(
  readFileSync(new URL('../package.json', import.meta.url), 'utf-8'),
) as { version: string; bin: Record<string, string> };

const versionSource = readFileSync(new URL('../src/version.ts', import.meta.url), 'utf-8');

/** `src/` 下全部 `.ts` 的绝对 URL */
function sourceFiles(): URL[] {
  return readdirSync(new URL('../src/', import.meta.url), { recursive: true, encoding: 'utf-8' })
    .filter((entry) => entry.endsWith('.ts'))
    .map((entry) => new URL(`../src/${entry}`, import.meta.url));
}

describe('版本号', () => {
  it('version.ts 的 CLI_VERSION 与 package.json 一致', () => {
    const match = versionSource.match(/export const CLI_VERSION = '([^']+)'/);
    expect(match, 'version.ts 里找不到 CLI_VERSION 字面量').not.toBeNull();
    expect(match?.[1]).toBe(pkg.version);
  });

  it('src/ 下不存在第二处版本号字面量（doctor 曾硬编码 1.0.0）', () => {
    const offenders = sourceFiles()
      .filter((file) => !file.pathname.endsWith('/version.ts'))
      .filter((file) => /(['"])\d+\.\d+\.\d+\1/.test(readFileSync(file, 'utf-8')))
      .map((file) => file.pathname.replace(/^.*\/src\//, 'src/'));
    expect(offenders, '这些文件里有第二处版本号字面量').toEqual([]);
  });

  it('bin 仍指向 dist/index.js（连接器包的 init/versionCheck 都按这个入口）', () => {
    expect(pkg.bin.cue).toBe('dist/index.js');
  });
});
