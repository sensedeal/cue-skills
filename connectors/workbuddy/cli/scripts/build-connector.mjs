#!/usr/bin/env node
/**
 * 组装 WorkBuddy 连接器包（wayfinder #77 的裁定）。
 *
 * ## 它存在的理由：消灭 `minVersion` 漂移
 *
 * `cli.json` 的 `versionCheck.minVersion` 必须与 **npm 上真实发布的 CLI 版本**一致 ——
 * 不一致的后果是**用户可见**的：`versionCheck` 不满足时 WorkBuddy 会**重跑 `init`
 * 重装**（#68 实测，不是硬阻断）。手工同步两处数字早晚会忘，所以这里**从
 * `package.json` 派生**。
 *
 * ⚠️ `connector-meta.json` 的 `version` 是**连接器在 WorkBuddy 市场的版本**，随每次
 *    送审递增；它与 CLI 二进制版本**不是同一个数字**（2026-11-11 实测：连接器送审
 *    1.1.1 时 npm 上 CLI 仍是 1.1.0）。故 meta 的版本不再由本脚本改写，只做校验；
 *    两者不同仅告警，不阻断。
 *
 * ## 产物形态（#68 查实的官方要求）
 *
 * zip **根目录即连接器内容**：`connector-meta.json` / `cli.json` / 图标（`icon.svg`
 * 或 `icon.png`，官方二者皆可）/ `skills/<name>/SKILL.md` —— 没有外层目录、没有
 * `__MACOSX`。
 *
 * 用法：
 *     node scripts/build-connector.mjs            # 同步版本号 + 重新打包
 *     node scripts/build-connector.mjs --check    # 只校验，不改文件（CI/评审用）
 */

import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(fileURLToPath(new URL('.', import.meta.url)), '..');
const checkOnly = process.argv.includes('--check');

const CONNECTOR_DIR = path.join(root, 'connector');
const SKILLS_DIR = path.join(root, 'skills');
/** zip 里的连接器名（同时是产物文件名） */
const PACKAGE_NAME = 'cue-research-connector';

function fail(message) {
  console.error(`❌ ${message}`);
  process.exit(1);
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf-8'));
  } catch (err) {
    fail(`读取 ${path.relative(root, file)} 失败: ${err.message}`);
  }
}

function writeJsonIfChanged(file, data) {
  const next = `${JSON.stringify(data, null, 2)}\n`;
  const current = fs.existsSync(file) ? fs.readFileSync(file, 'utf-8') : null;
  if (current === next) return false;
  if (checkOnly) {
    fail(`${path.relative(root, file)} 与 package.json 的版本不一致（用不带 --check 的方式重跑以同步）`);
  }
  fs.writeFileSync(file, next, 'utf-8');
  return true;
}

// --------------------------------------------------------------------------
// 1. 版本号派生
// --------------------------------------------------------------------------

const pkg = readJson(path.join(root, 'package.json'));
const version = String(pkg.version || '').trim();
if (!/^\d+\.\d+\.\d+$/.test(version)) fail(`package.json 的 version 不是语义化版本: ${version}`);

const cliJsonPath = path.join(CONNECTOR_DIR, 'cli.json');
const metaJsonPath = path.join(CONNECTOR_DIR, 'connector-meta.json');

const cliJson = readJson(cliJsonPath);
const metaJson = readJson(metaJsonPath);

const changed = [];
if (cliJson.versionCheck?.minVersion !== version) {
  const previous = cliJson.versionCheck?.minVersion;
  cliJson.versionCheck = { ...cliJson.versionCheck, minVersion: version };
  if (writeJsonIfChanged(cliJsonPath, cliJson)) changed.push(`cli.json minVersion: ${previous} → ${version}`);
}

// 连接器版本（WorkBuddy 市场）由 connector-meta.json 自己持有，不再被 package.json 覆盖。
const connectorVersion = String(metaJson.version || '').trim();
if (!/^\d+\.\d+\.\d+$/.test(connectorVersion)) {
  fail(`connector-meta.json 的 version 不是语义化版本: ${connectorVersion || '(空)'}`);
}
if (connectorVersion !== version) {
  console.warn(
    `ℹ️ connector 版本 ${connectorVersion} 与 CLI 版本 ${version} 不同（允许：minVersion 指向已发布的 CLI）`
  );
}

// --------------------------------------------------------------------------
// 2. 结构校验（缺件早失败，别等送审被退回来）
// --------------------------------------------------------------------------

// 官方允许 icon.svg 或 icon.png（docs「准备图标」），二者取其一即可。
const ICON_CANDIDATES = ['icon.svg', 'icon.png'];
const iconName = ICON_CANDIDATES.find((name) => fs.existsSync(path.join(CONNECTOR_DIR, name)));
if (!iconName) fail(`connector/ 缺少图标（${ICON_CANDIDATES.join(' 或 ')}）`);

const REQUIRED_IN_CONNECTOR = ['connector-meta.json', 'cli.json', iconName];
for (const name of REQUIRED_IN_CONNECTOR) {
  if (!fs.existsSync(path.join(CONNECTOR_DIR, name))) fail(`connector/ 缺少必需文件: ${name}`);
}

if (metaJson.source !== PACKAGE_NAME) {
  // ⚠️ `source` 是 WorkBuddy 市场的**全局唯一 id**，它不必等于 skill 目录名
  //    （目录名要与 SKILL.md 的 `name` 一致）。这里的相等只是本包的既有事实，
  //    改任何一边都要同步确认另一边的语义。
  console.warn(`⚠️ connector-meta.source=${metaJson.source} 与产物名 ${PACKAGE_NAME} 不同名，请确认这是有意的`);
}

const skillDirs = fs.existsSync(SKILLS_DIR)
  ? fs.readdirSync(SKILLS_DIR).filter((d) => fs.statSync(path.join(SKILLS_DIR, d)).isDirectory())
  : [];
if (skillDirs.length !== 1) {
  fail(`skills/ 下应当恰好有一个 skill 目录，实际: ${skillDirs.join(', ') || '(空)'}`);
}
const [skillName] = skillDirs;
const skillFile = path.join(SKILLS_DIR, skillName, 'SKILL.md');
if (!fs.existsSync(skillFile)) fail(`缺少 ${path.relative(root, skillFile)}`);

// SKILL.md 的 frontmatter `name` 必须与目录名一致 —— 这条能挡住「目录改名了但
// frontmatter 没跟」这种静默失效（也正是本包要从 `cue-research` 改名的原因）
const frontmatter = fs.readFileSync(skillFile, 'utf-8').match(/^---\n([\s\S]*?)\n---/);
if (!frontmatter) fail('SKILL.md 缺少 frontmatter');
const declaredName = frontmatter[1].match(/^name:\s*(.+)$/m)?.[1]?.trim();
if (declaredName !== skillName) {
  fail(`SKILL.md 的 name=${declaredName} 与目录名 ${skillName} 不一致`);
}

// --------------------------------------------------------------------------
// 3. 组装 zip（根即内容，无外层目录、无 __MACOSX）
// --------------------------------------------------------------------------

const staging = path.join(root, 'dist', `.staging-${PACKAGE_NAME}`);
const distDir = path.join(root, 'dist');
fs.rmSync(staging, { recursive: true, force: true });
fs.mkdirSync(staging, { recursive: true });

for (const name of REQUIRED_IN_CONNECTOR) {
  fs.copyFileSync(path.join(CONNECTOR_DIR, name), path.join(staging, name));
}
fs.mkdirSync(path.join(staging, 'skills', skillName), { recursive: true });
fs.copyFileSync(skillFile, path.join(staging, 'skills', skillName, 'SKILL.md'));

const zipPath = path.join(distDir, `${PACKAGE_NAME}.zip`);
fs.rmSync(zipPath, { force: true });
try {
  // -r 递归、-X 去掉多余的文件属性（时间戳/权限）；排除 dotfile 与 __MACOSX。
  // ⚠️ 这套参数与该仓既有的 16 个 MCP 连接器**逐字一致** —— 官方要求 zip 根即连接器内容，
  //    多一层目录或混进 `__MACOSX` 会在送审时被退回来。
  execFileSync('zip', ['-r', '-X', zipPath, '.', '-x', '.*', '-x', '__MACOSX/*'], {
    cwd: staging,
    stdio: 'pipe',
  });
} catch (err) {
  fail(`打包失败（需要系统有 zip 命令）: ${err.message}`);
}
fs.rmSync(staging, { recursive: true, force: true });

// --------------------------------------------------------------------------
// 4. 报告
// --------------------------------------------------------------------------

const size = fs.statSync(zipPath).size;
const listed = execFileSync('unzip', ['-Z1', zipPath], { encoding: 'utf-8' })
  .split('\n')
  .filter(Boolean)
  .sort();

console.log(`连接器包: ${path.relative(root, zipPath)} (${size} B)`);
console.log(`  内容: ${listed.join(', ')}`);
console.log(`  connector 版本: ${connectorVersion}（取自 connector-meta.json）`);
console.log(`  CLI minVersion: ${version}（取自 package.json，须是 npm 已发布版本）`);
if (changed.length) console.log(`  已同步: ${changed.join('; ')}`);
else console.log('  版本号已是最新，未改动任何文件');
