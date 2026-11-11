#!/usr/bin/env node
/**
 * Local static validation for the Doubao plugin package.
 *
 * Mirrors the publish-time checks documented at:
 *   https://open.doubao.com/document/plugin-docs-center/build/mcp-server-development/plugin-development-spec/plugin-development-specification-overview
 *   .../mcp-server-development  .../skill-development  .../display-information
 *
 * Run: node scripts/validate.mjs
 * It does NOT replace the platform's upload validation or dbx check.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { collectPackageFiles, INCLUDE } from './package-files.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const errors = [];
const warnings = [];
const err = (m) => errors.push(m);
const warn = (m) => warnings.push(m);
const cpLen = (s) => [...String(s)].length;
const isNonEmpty = (s) => typeof s === 'string' && s.trim().length > 0;
const readJSON = (rel) => {
  const p = path.join(ROOT, rel);
  if (!fs.existsSync(p)) { err(`${rel}: missing`); return null; }
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); }
  catch (e) { err(`${rel}: invalid JSON (${e.message})`); return null; }
};

/* ---------- image helpers (PNG / JPEG header only, no dependencies) ---------- */
function imageInfo(abs) {
  const buf = fs.readFileSync(abs);
  const ext = path.extname(abs).toLowerCase();
  if (buf.length >= 24 && buf.subarray(1, 4).toString() === 'PNG') {
    return { format: 'png', width: buf.readUInt32BE(16), height: buf.readUInt32BE(20), bytes: buf.length };
  }
  if (ext === '.jpg' || ext === '.jpeg') {
    if (buf[0] !== 0xff || buf[1] !== 0xd8) return { format: 'jpeg', width: 0, height: 0, bytes: buf.length };
    let i = 2;
    while (i < buf.length - 9) {
      if (buf[i] !== 0xff) { i++; continue; }
      const marker = buf[i + 1];
      if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
        return { format: 'jpeg', width: buf.readUInt16BE(i + 7), height: buf.readUInt16BE(i + 5), bytes: buf.length };
      }
      const len = buf.readUInt16BE(i + 2);
      i += 2 + len;
    }
    return { format: 'jpeg', width: 0, height: 0, bytes: buf.length };
  }
  return { format: ext, width: 0, height: 0, bytes: buf.length };
}

function checkIcon(relPath, base, label) {
  if (!isNonEmpty(relPath)) { err(`${label}: icon must be a non-empty string`); return; }
  if (!relPath.startsWith('./')) { err(`${label}: icon must start with "./" (got ${relPath})`); return; }
  const abs = path.resolve(base, relPath);
  const relToRoot = path.relative(ROOT, abs);
  const relToBase = path.relative(base, abs);
  if (relToRoot.startsWith('..') || relToBase.startsWith('..') || path.isAbsolute(relToBase)) {
    err(`${label}: icon escapes its allowed directory (${relPath})`); return;
  }
  if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) { err(`${label}: icon file missing (${relPath})`); return; }
  const info = imageInfo(abs);
  if (!['png', 'jpeg'].includes(info.format)) err(`${label}: icon must be PNG or JPEG (${info.format})`);
  if (info.width !== 512 || info.height !== 512) err(`${label}: icon must be 512x512 (got ${info.width}x${info.height})`);
  if (info.bytes > 500 * 1024) err(`${label}: icon exceeds 500 KiB (${info.bytes} bytes)`);
}

/* ---------- language maps ---------- */
function checkLangMap(value, label, maxLen, required) {
  if (value === undefined || value === null) {
    if (required) err(`${label}: required`);
    return;
  }
  if (typeof value !== 'object' || Array.isArray(value)) { err(`${label}: must be a map of language code -> string`); return; }
  const entries = Object.entries(value);
  if (entries.length === 0) { err(`${label}: needs at least one non-empty value`); return; }
  for (const [lang, text] of entries) {
    if (!/^[a-z]{2}$/.test(lang)) err(`${label}: invalid language key "${lang}" (use zh / en)`);
    if (typeof text !== 'string' || text === null) { err(`${label}.${lang}: must be a string`); continue; }
    if (cpLen(text) > maxLen) err(`${label}.${lang}: exceeds ${maxLen} characters`);
  }
  if (!entries.some(([, t]) => typeof t === 'string' && t.trim().length > 0)) err(`${label}: needs at least one non-empty value`);
}

/* ---------- frontmatter ---------- */
function parseFrontmatter(text, label) {
  const lines = text.split(/\r?\n/);
  if (lines[0]?.trim() !== '---') { err(`${label}: missing YAML frontmatter`); return null; }
  const end = lines.findIndex((l, i) => i > 0 && l.trim() === '---');
  if (end < 0) { err(`${label}: unterminated YAML frontmatter`); return null; }
  const top = {};
  const metadata = {};
  const topSeen = new Set();
  const metaSeen = new Set();
  let inMetadata = false;
  for (let i = 1; i < end; i++) {
    const raw = lines[i];
    if (!raw.trim() || raw.trim().startsWith('#')) continue;
    const indented = /^\s+/.test(raw);
    const m = raw.match(/^\s*([A-Za-z_][\w-]*)\s*:\s*(.*)$/);
    if (!m) { warn(`${label}: cannot parse frontmatter line ${i + 1}`); continue; }
    const [, key, rawVal] = m;
    let val = rawVal.trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) val = val.slice(1, -1);
    if (/^[|>]$/.test(val)) { warn(`${label}: block scalar "${key}" not supported by this validator`); val = ''; }
    if (indented && inMetadata) {
      if (metaSeen.has(key)) err(`${label}: duplicate metadata key "${key}"`);
      metaSeen.add(key);
      metadata[key] = val;
    } else {
      inMetadata = key === 'metadata';
      if (topSeen.has(key)) err(`${label}: duplicate top-level key "${key}"`);
      topSeen.add(key);
      top[key] = val;
    }
  }
  return { top, metadata, body: lines.slice(end + 1).join('\n') };
}

/* ================================ plugin.json ================================ */
const plugin = readJSON('plugin.json') || {};
if (typeof plugin !== 'object' || Array.isArray(plugin)) err('plugin.json: root must be a JSON object');
else {
  const name = plugin.name;
  if (!isNonEmpty(name)) err('plugin.json.name: required');
  else {
    if (cpLen(name) > 64) err(`plugin.json.name: exceeds 64 characters`);
    if (!/^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(name)) err('plugin.json.name: only lowercase letters, digits, "-" and "."; must start/end with a letter or digit');
    if (name.includes('--') || name.includes('..')) err('plugin.json.name: must not contain "--" or ".."');
  }
  if (plugin.version !== undefined && typeof plugin.version !== 'string') err('plugin.json.version: must be a string');
  if (plugin.description !== undefined) {
    if (typeof plugin.description !== 'string') err('plugin.json.description: must be a string');
    else if (cpLen(plugin.description) > 1024) err('plugin.json.description: exceeds 1024 characters');
  }
  const allowedTop = new Set(['name', 'id', 'version', 'description', 'extensions']);
  for (const k of Object.keys(plugin)) if (!allowedTop.has(k)) err(`plugin.json: unknown top-level field "${k}" (Doubao forbids custom root fields)`);

  const ext = plugin.extensions;
  if (typeof ext !== 'object' || ext === null || Array.isArray(ext)) err('plugin.json.extensions: must be an object');
  else {
    const db = ext['com.doubao'];
    if (typeof db !== 'object' || db === null || Array.isArray(db)) err('plugin.json.extensions["com.doubao"]: must be an object');
    else {
      checkLangMap(db.displayName, 'extensions["com.doubao"].displayName', 128, false);
      checkLangMap(db.displayDescription, 'extensions["com.doubao"].displayDescription', 1024, false);
      if (db.icon !== undefined) checkIcon(db.icon, ROOT, 'extensions["com.doubao"].icon');
      if (db.chatIcon !== undefined) checkIcon(db.chatIcon, ROOT, 'extensions["com.doubao"].chatIcon');
      var displayServers = db.mcpServers; // reused below
    }
  }
}

/* ================================ mcp.json ================================ */
const mcp = readJSON('mcp.json') || {};
let serviceKeys = [];
if (typeof mcp !== 'object' || Array.isArray(mcp) || typeof mcp.mcpServers !== 'object' || mcp.mcpServers === null || Array.isArray(mcp.mcpServers)) {
  err('mcp.json: missing "mcpServers" object');
} else {
  serviceKeys = Object.keys(mcp.mcpServers);
  if (serviceKeys.length === 0) err('mcp.json: mcpServers must not be empty');
  if (serviceKeys.length > 10) err(`mcp.json: ${serviceKeys.length} services exceeds the limit of 10`);
  for (const key of serviceKeys) {
    if (!isNonEmpty(key)) { err('mcp.json: service key must be non-empty'); continue; }
    if (/[/\\]/.test(key)) err(`mcp.json: service key "${key}" must be usable as a file name`);
    const svc = mcp.mcpServers[key];
    const label = `mcp.json.mcpServers.${key}`;
    if (typeof svc !== 'object' || svc === null) { err(`${label}: must be an object`); continue; }
    if (!['streamable-http', 'sse'].includes(svc.type)) err(`${label}.type: must be "streamable-http" or "sse" (got "${svc.type}")`);
    if (!isNonEmpty(svc.url)) { err(`${label}.url: required`); }
    else {
      try {
        const u = new URL(svc.url);
        if (u.protocol !== 'https:') err(`${label}.url: must be an absolute HTTPS address`);
        if (u.username || u.password) err(`${label}.url: must not contain a username or password`);
        if (u.hash) err(`${label}.url: must not contain a fragment`);
        const host = u.hostname.toLowerCase();
        if (host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '0.0.0.0' || host.startsWith('127.')) err(`${label}.url: loopback / local addresses are not allowed`);
        if (!u.hostname.includes('.')) err(`${label}.url: hostname looks invalid`);
      } catch (e) { err(`${label}.url: invalid URL (${e.message})`); }
    }
    if (svc.headers !== undefined) {
      if (typeof svc.headers !== 'object' || svc.headers === null || Array.isArray(svc.headers)) err(`${label}.headers: must be a map`);
      else {
        const seen = new Set();
        for (const [h, v] of Object.entries(svc.headers)) {
          const lower = h.toLowerCase();
          if (seen.has(lower)) err(`${label}.headers: duplicate header "${h}" (case-insensitive)`);
          seen.add(lower);
          if (typeof v !== 'string') err(`${label}.headers.${h}: must be a string`);
          if (lower === 'authorization') err(`${label}.headers: Authorization must not be hardcoded; use MCP OAuth or com.doubao/auth`);
        }
      }
    }
    for (const k of Object.keys(svc)) if (!['type', 'url', 'headers'].includes(k)) warn(`${label}: unknown field "${k}" is ignored by Doubao`);
  }
}

/* ---------- display config must match mcp.json service keys exactly ---------- */
if (mcp.mcpServers) {
  if (typeof displayServers !== 'object' || displayServers === null || Array.isArray(displayServers)) {
    err('plugin.json.extensions["com.doubao"].mcpServers: required when mcp.json declares services');
  } else {
    const displayKeys = Object.keys(displayServers);
    for (const k of serviceKeys) if (!displayKeys.includes(k)) err(`display config missing for MCP service "${k}"`);
    for (const k of displayKeys) if (!serviceKeys.includes(k)) err(`display config has extra MCP service "${k}" with no mcp.json entry`);
    for (const k of displayKeys) {
      const d = displayServers[k];
      const label = `extensions["com.doubao"].mcpServers.${k}`;
      if (typeof d !== 'object' || d === null) { err(`${label}: must be an object`); continue; }
      checkLangMap(d.displayName, `${label}.displayName`, 128, true);
      checkLangMap(d.displayDescription, `${label}.displayDescription`, 1024, true);
      if (d.icon !== undefined) checkIcon(d.icon, ROOT, `${label}.icon`);
    }
  }
}

/* ---------- static credentials ---------- */
const authDir = path.join(ROOT, 'com.doubao', 'auth');
if (fs.existsSync(authDir)) {
  for (const f of fs.readdirSync(authDir)) {
    if (!f.endsWith('.json')) continue;
    const key = f.slice(0, -5);
    if (!serviceKeys.includes(key)) err(`com.doubao/auth/${f}: no matching mcp.json service key "${key}"`);
    const cfg = readJSON(path.posix.join('com.doubao', 'auth', f));
    if (!cfg) continue;
    const ids = new Set();
    for (const c of cfg.credentials || []) {
      if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(c.id || '')) err(`${f}: invalid credential id "${c.id}"`);
      if (ids.has(c.id)) err(`${f}: duplicate credential id "${c.id}"`);
      ids.add(c.id);
      if (!isNonEmpty(c.label)) err(`${f}: credential label is required`);
      if (typeof c.secret !== 'boolean') err(`${f}: credential secret must be a boolean`);
    }
    const names = new Set();
    for (const inj of cfg.injections || []) {
      if (inj.target !== 'header') err(`${f}: injection target must be "header"`);
      const lower = (inj.name || '').toLowerCase();
      if (names.has(lower)) err(`${f}: duplicate injection header "${inj.name}"`);
      names.add(lower);
      for (const v of String(inj.value || '').matchAll(/\$\{([^}]+)\}/g)) if (!ids.has(v[1])) err(`${f}: injection references undeclared credential "${v[1]}"`);
    }
  }
} else {
  console.log('  auth: no com.doubao/auth/ directory - MCP standard OAuth will be used');
}

/* ================================ skills ================================ */
const skillsDir = path.join(ROOT, 'skills');
const skillDirs = fs.existsSync(skillsDir)
  ? fs.readdirSync(skillsDir).filter((n) => fs.statSync(path.join(skillsDir, n)).isDirectory())
  : [];
if (skillDirs.length === 0) warn('skills/: no Skill directories found');
if (skillDirs.length > 10) err(`skills/: ${skillDirs.length} Skills exceeds the limit of 10`);
for (const dir of skillDirs) {
  const label = `skills/${dir}/SKILL.md`;
  const abs = path.join(skillsDir, dir, 'SKILL.md');
  if (!fs.existsSync(abs)) { err(`${label}: missing`); continue; }
  const fm = parseFrontmatter(fs.readFileSync(abs, 'utf8'), label);
  if (!fm) continue;
  const { top, metadata } = fm;
  if (!isNonEmpty(top.name)) err(`${label}: frontmatter name is required`);
  else {
    if (top.name !== dir) err(`${label}: name "${top.name}" must equal directory name "${dir}"`);
    if (cpLen(top.name) > 64 || !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(top.name) || top.name.includes('--')) err(`${label}: name must be 1-64 lowercase letters/digits/hyphens, no leading/trailing or doubled hyphen`);
  }
  if (!isNonEmpty(top.description)) err(`${label}: frontmatter description is required`);
  else if (cpLen(top.description) > 1024) err(`${label}: description exceeds 1024 characters`);
  if (typeof metadata !== 'object') err(`${label}: frontmatter metadata map is required`);
  else {
    if (!isNonEmpty(metadata.display_name)) err(`${label}: metadata.display_name is required`);
    else if (cpLen(metadata.display_name) > 128) err(`${label}: metadata.display_name exceeds 128 characters`);
    if (!isNonEmpty(metadata.display_description)) err(`${label}: metadata.display_description is required`);
    else if (cpLen(metadata.display_description) > 1024) err(`${label}: metadata.display_description exceeds 1024 characters`);
    if (metadata.icon !== undefined) checkIcon(metadata.icon, path.join(skillsDir, dir), `${label} metadata.icon`);
  }
  for (const m of fm.body.matchAll(/\]\(([^)]+)\)/g)) {
    const ref = m[1].trim();
    if (/^(https?:|#|mailto:)/.test(ref)) continue;
    const target = path.resolve(path.join(skillsDir, dir), ref.split('#')[0]);
    if (!fs.existsSync(target)) err(`${label}: referenced resource missing (${ref})`);
  }
}

/* ---------- CLI connector (optional, not used by this plugin) ---------- */
const cliPath = path.join(ROOT, 'com.doubao', 'cli.json');
if (fs.existsSync(cliPath)) {
  const cli = readJSON(path.posix.join('com.doubao', 'cli.json'));
  if (cli && (typeof cli.connectors !== 'object' || Object.keys(cli.connectors).length === 0)) err('com.doubao/cli.json: connectors must be a non-empty object');
  if (cli?.connectors) for (const k of Object.keys(cli.connectors)) if (serviceKeys.includes(k)) err(`com.doubao/cli.json: connector "${k}" collides with an MCP service key`);
}

/* ================================ ZIP limits ================================ */
const files = collectPackageFiles(ROOT);
const total = files.reduce((n, f) => n + f.size, 0);
if (files.length > 1024) err(`ZIP entries: ${files.length} exceeds 1024`);
for (const f of files) if (f.size > 2 * 1024 * 1024) err(`uncompressed file ${f.rel}: ${f.size} bytes exceeds 2 MB`);
if (total > 16 * 1024 * 1024) err(`uncompressed total ${total} bytes exceeds 16 MB`);
console.log(`  package: ${files.length} files, ${(total / 1024).toFixed(1)} KiB uncompressed`);
console.log(`  include: ${INCLUDE.join(', ')}`);

/* ---------- output ---------- */
for (const w of warnings) console.log(`  WARN  ${w}`);
for (const e of errors) console.log(`  ERROR ${e}`);
if (errors.length) {
  console.error(`\nFAILED: ${errors.length} error(s), ${warnings.length} warning(s)`);
  process.exit(1);
}
console.log(`\nOK: local static validation passed (${warnings.length} warning(s)).`);
console.log('Note: this does not replace Doubao platform upload validation or `dbx check`.');
