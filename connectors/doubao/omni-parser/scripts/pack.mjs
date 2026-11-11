#!/usr/bin/env node
/**
 * Build the ZIP that is uploaded to the Doubao plugin console.
 *
 * Run: node scripts/pack.mjs
 * Output:
 *   dist/cue-omni-parser-<version>.zip        -> open platform upload (full plugin)
 *   dist/cue-omni-parser-skill.zip            -> "upload skill" in the local Doubao desktop app
 *
 * The plugin ZIP root contains plugin.json, mcp.json, com.doubao/ and skills/ only.
 * Local tooling (scripts/, README.md, dist/, .gitignore) is excluded.
 * The skill ZIP keeps the skills/<name>/SKILL.md layout that the desktop app expects.
 */
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { collectPackageFiles, INCLUDE } from './package-files.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const plugin = JSON.parse(fs.readFileSync(path.join(ROOT, 'plugin.json'), 'utf8'));
const name = plugin.name;
const version = plugin.version || '0.0.0';
const outDir = path.join(ROOT, 'dist');
const out = path.join(outDir, `${name}-${version}.zip`);

const files = collectPackageFiles(ROOT);
const total = files.reduce((n, f) => n + f.size, 0);
if (files.length > 1024) throw new Error(`too many ZIP entries: ${files.length} > 1024`);
if (total > 16 * 1024 * 1024) throw new Error(`uncompressed size ${total} exceeds 16 MB`);
if (files.some((f) => f.size > 2 * 1024 * 1024)) throw new Error('a single file exceeds 2 MB uncompressed');

fs.mkdirSync(outDir, { recursive: true });
if (fs.existsSync(out)) fs.unlinkSync(out);

// `zip` keeps the relative paths, so plugin.json ends up at the ZIP root.
execFileSync('zip', ['-X', '-q', '-r', out, ...INCLUDE, '-x', '*.DS_Store', '*__MACOSX*'], {
  cwd: ROOT,
  stdio: 'inherit',
});

const zipSize = fs.statSync(out).size;
if (zipSize > 16 * 1024 * 1024) throw new Error(`ZIP ${zipSize} bytes exceeds 16 MB`);
console.log(`\nBuilt ${path.relative(ROOT, out)}`);
console.log(`  entries: ${files.length}   uncompressed: ${(total / 1024).toFixed(1)} KiB   ZIP: ${(zipSize / 1024).toFixed(1)} KiB`);

// Second artifact: a Skill-only ZIP for the local desktop client's "upload skill" flow.
// The app expects <skill-name>/SKILL.md inside the archive, not a bare SKILL.md.
const skillsRoot = path.join(ROOT, 'skills');
const skillNames = fs.readdirSync(skillsRoot).filter((n) => fs.statSync(path.join(skillsRoot, n)).isDirectory());
for (const s of skillNames) {
  if (!fs.existsSync(path.join(skillsRoot, s, 'SKILL.md'))) throw new Error(`skills/${s}: missing SKILL.md`);
}
const skillOut = path.join(outDir, `${name}-skill.zip`);
if (fs.existsSync(skillOut)) fs.unlinkSync(skillOut);
execFileSync('zip', ['-X', '-q', '-r', skillOut, ...skillNames, '-x', '*.DS_Store', '*__MACOSX*'], {
  cwd: skillsRoot,
  stdio: 'inherit',
});
console.log(`Built ${path.relative(ROOT, skillOut)}  (${(fs.statSync(skillOut).size / 1024).toFixed(1)} KiB) - local desktop "upload skill"`);
console.log('  Tip: run `node scripts/validate.mjs` before uploading. See LOCAL-INSTALL.md for local setup.');
