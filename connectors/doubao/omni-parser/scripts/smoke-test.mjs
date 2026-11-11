#!/usr/bin/env node
/**
 * Credential-free smoke test for the plugin's MCP + OAuth wiring.
 *
 * Run: node scripts/smoke-test.mjs
 *
 * This plugin authenticates with standard MCP OAuth (DCR + PKCE S256); the
 * client owns the tokens and the package contains none. This script therefore
 * handles NO credentials at all - it only verifies the discovery contract:
 *   config consistency -> 401 discovery -> protected-resource metadata ->
 *   authorization-server metadata.
 *
 * To exercise an authenticated tools/list, run `node scripts/oauth-probe.mjs`,
 * which performs the real OAuth flow and keeps the token in memory only.
 * Never paste a token into a chat or write one into the plugin package.
 *
 * This script never submits a parse call, so it cannot incur parsing charges.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const plugin = JSON.parse(fs.readFileSync(path.join(ROOT, 'plugin.json'), 'utf8'));
const mcp = JSON.parse(fs.readFileSync(path.join(ROOT, 'mcp.json'), 'utf8'));

const errors = [];
const ok = (m) => console.log(`  PASS  ${m}`);
const bad = (m) => { console.log(`  FAIL  ${m}`); errors.push(m); };
const info = (m) => console.log(`  INFO  ${m}`);

async function request(url, init = {}) {
  const res = await fetch(url, { redirect: 'follow', ...init });
  const text = await res.text();
  let json = null;
  try { json = JSON.parse(text); } catch { /* SSE or plain text */ }
  if (!json && text.includes('data:')) {
    for (const line of text.split(/\r?\n/)) {
      if (!line.startsWith('data:')) continue;
      try { json = JSON.parse(line.slice(5).trim()); break; } catch { /* next */ }
    }
  }
  return { res, text, json };
}

const RPC = (id, method, params = {}) => JSON.stringify({ jsonrpc: '2.0', id, method, params });
const rpcInit = () => request(mcpUrl, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/event-stream',
  },
  body: RPC(1, 'initialize', {
    protocolVersion: '2025-06-18',
    capabilities: {},
    clientInfo: { name: 'cue-omni-parser-smoke', version: '1.2.3' },
  }),
});

console.log('Cue omni-parser / MCP + OAuth smoke test\n');

/* ---------- 1. package config ---------- */
console.log('[1] Package config');
const services = Object.entries(mcp.mcpServers || {});
if (services.length !== 1) bad(`expected exactly 1 MCP service, got ${services.length}`);
const [serviceKey, svc] = services[0] || [];
const displayServers = plugin.extensions?.['com.doubao']?.mcpServers || {};
if (Object.keys(displayServers).join() !== Object.keys(mcp.mcpServers || {}).join()) {
  bad('display config service keys do not match mcp.json');
} else ok(`service keys aligned: ${Object.keys(displayServers).join(', ')}`);
if (svc?.type !== 'streamable-http') bad(`type must be "streamable-http", got "${svc?.type}"`);
else ok('transport type: streamable-http');
let mcpUrl;
try {
  mcpUrl = new URL(svc.url).toString();
  const u = new URL(svc.url);
  if (u.protocol !== 'https:') bad('url must be HTTPS');
  else ok(`endpoint: ${u.origin}${u.pathname}`);
} catch { bad(`invalid url: ${svc?.url}`); }
if (Object.keys(svc?.headers || {}).some((h) => h.toLowerCase() === 'authorization')) {
  bad('mcp.json hardcodes an Authorization header');
} else ok('no hardcoded credentials in mcp.json');
if (!fs.existsSync(path.join(ROOT, 'com.doubao', 'auth'))) ok('no static auth file -> standard MCP OAuth');
else bad('unexpected com.doubao/auth directory for an OAuth service');

/* ---------- 2. unauthenticated discovery ---------- */
console.log('\n[2] MCP 401 / protected-resource discovery');
let asUrl = '';
try {
  const { res, json } = await rpcInit();
  if (res.status === 401) ok(`unauthenticated request -> 401 ${json?.detail || ''}`.trim());
  else info(`expected 401, got ${res.status} (server may allow anonymous access)`);
  const wa = res.headers.get('www-authenticate') || '';
  const prm = wa.match(/resource_metadata="([^"]+)"/)?.[1];
  if (!prm) info('no resource_metadata in WWW-Authenticate; falling back to origin well-known');
  const prmUrl = prm || `${new URL(mcpUrl).origin}/.well-known/oauth-protected-resource`;
  const { res: pr, json: prJson } = await request(prmUrl);
  if (pr.status !== 200) bad(`protected-resource metadata ${pr.status} at ${prmUrl}`);
  else {
    ok(`protected-resource metadata: ${prJson?.resource}`);
    asUrl = (prJson?.authorization_servers || [])[0] || '';
    if (asUrl) ok(`authorization server: ${asUrl}`);
    else bad('authorization_servers is empty');
  }
} catch (e) { bad(`discovery request failed: ${e.message}`); }

/* ---------- 3. authorization server metadata ---------- */
console.log('\n[3] OAuth authorization server');
if (asUrl) {
  try {
    const metaUrl = `${asUrl.replace(/\/$/, '')}/.well-known/oauth-authorization-server`;
    const { res, json } = await request(metaUrl);
    if (res.status !== 200) bad(`AS metadata ${res.status} at ${metaUrl}`);
    else {
      for (const f of ['authorization_endpoint', 'token_endpoint', 'registration_endpoint']) {
        if (json?.[f]) ok(`${f}: ${json[f]}`); else bad(`AS metadata missing ${f}`);
      }
      if ((json?.code_challenge_methods_supported || []).includes('S256')) ok('PKCE S256 supported');
      else bad('PKCE S256 not advertised');
      if ((json?.grant_types_supported || []).includes('authorization_code')) ok('authorization_code grant supported');
    }
  } catch (e) { bad(`AS metadata request failed: ${e.message}`); }
} else info('skipped (no authorization server discovered)');

/* ---------- 4. authenticated surface is delegated to the OAuth probe ---------- */
console.log('\n[4] Authenticated tools/list');
info('Standard MCP OAuth: credentials are held by the client, not by this package.');
info('Run `node scripts/oauth-probe.mjs` for a real DCR + PKCE flow and tools/list.');
if (asUrl) ok(`authorization server ready for the probe: ${asUrl}`);
else bad('cannot run oauth-probe: no authorization server discovered');

console.log('');
if (errors.length) { console.error(`FAILED: ${errors.length} check(s) failed.`); process.exit(1); }
console.log('OK: MCP + OAuth wiring looks healthy. This does not replace validation inside the Doubao client.');
