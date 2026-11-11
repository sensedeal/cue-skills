#!/usr/bin/env node
/**
 * Authenticated MCP probe for an OAuth-only plugin.
 *
 * Run: node scripts/oauth-probe.mjs
 *
 * This plugin has NO static credentials. To verify the authenticated tool
 * surface outside the Doubao/WorkBuddy client, this script performs the same
 * standard MCP OAuth flow the client performs:
 *
 *   401 discovery -> protected-resource metadata -> authorization-server metadata
 *   -> dynamic client registration (RFC 7591) -> PKCE S256 authorization code
 *   -> local loopback callback -> token exchange -> initialize + tools/list
 *
 * The access token stays in memory: it is never printed, logged, written to
 * disk, placed in a URL, or added to the plugin package. Do not paste tokens
 * into chats. This script calls only initialize and tools/list - it never
 * submits a parse, so it cannot incur parsing charges.
 *
 * Each run dynamically registers a temporary OAuth client on the authorization
 * server. It opens your browser; you must log in and approve once.
 */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const mcp = JSON.parse(fs.readFileSync(path.join(ROOT, 'mcp.json'), 'utf8'));
const svc = Object.values(mcp.mcpServers)[0];
const mcpUrl = svc.url;
const TIMEOUT_MS = Number(process.env.CUE_OAUTH_TIMEOUT_MS || 600_000);

const ok = (m) => console.log(`  PASS  ${m}`);
const info = (m) => console.log(`  INFO  ${m}`);
const die = (m) => { console.error(`\n  FAIL  ${m}`); process.exit(1); };

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
const rpc = (id, method, params = {}) => JSON.stringify({ jsonrpc: '2.0', id, method, params });

/* ---------- 1. discovery ---------- */
console.log('Cue omni-parser / OAuth probe\n');
console.log('[1] Discovery');
const probe = await request(mcpUrl, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream' },
  body: rpc(1, 'initialize', {
    protocolVersion: '2025-06-18',
    capabilities: {},
    clientInfo: { name: 'cue-omni-parser-oauth-probe', version: '1.2.3' },
  }),
});
if (probe.res.status !== 401) die(`expected 401 without credentials, got ${probe.res.status}`);
ok('unauthenticated request rejected with 401');
const prmUrl = (probe.res.headers.get('www-authenticate') || '').match(/resource_metadata="([^"]+)"/)?.[1]
  || `${new URL(mcpUrl).origin}/.well-known/oauth-protected-resource`;
const { json: prm } = await request(prmUrl);
const asUrl = (prm?.authorization_servers || [])[0];
if (!asUrl) die('no authorization server in protected-resource metadata');
ok(`authorization server: ${asUrl}`);
const { json: meta } = await request(`${asUrl.replace(/\/$/, '')}/.well-known/oauth-authorization-server`);
for (const f of ['authorization_endpoint', 'token_endpoint', 'registration_endpoint']) {
  if (!meta?.[f]) die(`authorization server metadata missing ${f}`);
}
if (!(meta.code_challenge_methods_supported || []).includes('S256')) die('PKCE S256 not supported');
ok('metadata complete, PKCE S256 supported');

/* ---------- 2. loopback callback server ---------- */
console.log('\n[2] Loopback redirect');
const server = http.createServer();
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
// The authorization server's DCR whitelist requires the exact loopback path
// "/oauth/callback" (verified 2026-11-09). A bare "/callback" is rejected with
// invalid_redirect_uri. Both 127.0.0.1 and localhost are accepted.
const CALLBACK_PATH = '/oauth/callback';
const redirectUri = `http://127.0.0.1:${port}${CALLBACK_PATH}`;
info(`listening on ${redirectUri}`);
let pending;
const authCode = new Promise((resolve, reject) => { pending = { resolve, reject }; });
server.on('request', (req, res) => {
  const u = new URL(req.url, `http://127.0.0.1:${port}`);
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end('<!doctype html><meta charset="utf-8"><p>授权完成，可关闭此页面并返回终端。</p>');
  if (u.pathname !== CALLBACK_PATH) return;
  const err = u.searchParams.get('error');
  if (err) pending.reject(new Error(`authorization denied: ${err}`));
  else pending.resolve({ code: u.searchParams.get('code'), state: u.searchParams.get('state') });
});
const timer = setTimeout(() => {
  pending.reject(new Error(`timed out waiting for browser authorization (${TIMEOUT_MS / 1000}s)`));
}, TIMEOUT_MS);

/* ---------- 3. dynamic client registration ---------- */
console.log('\n[3] Dynamic client registration');
const reg = await request(meta.registration_endpoint, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    client_name: 'cue-omni-parser-oauth-probe',
    redirect_uris: [redirectUri],
    grant_types: ['authorization_code', 'refresh_token'],
    response_types: ['code'],
    token_endpoint_auth_method: 'none',
    scope: 'mcp:invoke',
  }),
});
if (reg.res.status < 200 || reg.res.status >= 300 || !reg.json?.client_id) {
  die(`DCR failed (${reg.res.status}): ${reg.text.slice(0, 300)}`);
}
const clientId = reg.json.client_id;
ok(`registered temporary client ${clientId}`);

/* ---------- 4. PKCE + browser authorization ---------- */
const verifier = crypto.randomBytes(32).toString('base64url');
const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
const state = crypto.randomBytes(16).toString('base64url');
const authUrl = new URL(meta.authorization_endpoint);
authUrl.searchParams.set('response_type', 'code');
authUrl.searchParams.set('client_id', clientId);
authUrl.searchParams.set('redirect_uri', redirectUri);
authUrl.searchParams.set('code_challenge', challenge);
authUrl.searchParams.set('code_challenge_method', 'S256');
authUrl.searchParams.set('state', state);
authUrl.searchParams.set('scope', 'mcp:invoke');
authUrl.searchParams.set('resource', prm?.resource || new URL(mcpUrl).origin);

console.log('\n[4] Browser authorization');
console.log(`  URL: ${authUrl.toString()}`);
info('opening browser; log in and approve, then return here');
const opener = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'cmd' : 'xdg-open';
const openerArgs = process.platform === 'win32' ? ['/c', 'start', '', authUrl.toString()] : [authUrl.toString()];
execFile(opener, openerArgs, () => { /* URL is printed above as a fallback */ });

let callback;
try { callback = await authCode; } catch (e) { die(e.message); }
clearTimeout(timer);
server.close();
if (callback.state !== state) die('state mismatch - refusing to exchange the code');
if (!callback.code) die('authorization response contained no code');
ok('authorization code received, state verified');

/* ---------- 5. token exchange (in memory only) ---------- */
console.log('\n[5] Token exchange');
const form = new URLSearchParams({
  grant_type: 'authorization_code',
  code: callback.code,
  redirect_uri: redirectUri,
  client_id: clientId,
  code_verifier: verifier,
});
const tok = await request(meta.token_endpoint, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: form.toString(),
});
if (tok.res.status < 200 || tok.res.status >= 300 || !tok.json?.access_token) {
  die(`token exchange failed (${tok.res.status}): ${tok.text.slice(0, 300)}`);
}
const accessToken = tok.json.access_token;
ok(`obtained ${tok.json.token_type || 'Bearer'} token (${tok.json.expires_in ?? '?'}s), held in memory only`);

/* ---------- 6. authenticated MCP surface ---------- */
console.log('\n[6] Authenticated MCP tools/list');
const authHeaders = {
  'Content-Type': 'application/json',
  'Accept': 'application/json, text/event-stream',
  Authorization: `Bearer ${accessToken}`,
};
const init = await request(mcpUrl, {
  method: 'POST', headers: authHeaders,
  body: rpc(1, 'initialize', {
    protocolVersion: '2025-06-18', capabilities: {},
    clientInfo: { name: 'cue-omni-parser-oauth-probe', version: '1.2.3' },
  }),
});
if (init.res.status !== 200) die(`initialize with token -> ${init.res.status}: ${init.text.slice(0, 200)}`);
ok(`initialize OK, protocol ${init.json?.result?.protocolVersion || '(unknown)'}`);
const sessionId = init.res.headers.get('mcp-session-id') || '';
const tl = await request(mcpUrl, {
  method: 'POST',
  headers: { ...authHeaders, ...(sessionId ? { 'Mcp-Session-Id': sessionId } : {}) },
  body: rpc(2, 'tools/list', {}),
});
const tools = (tl.json?.result?.tools || []).map((t) => t.name);
if (tl.res.status !== 200 || tools.length === 0) die(`tools/list -> ${tl.res.status}, ${tools.length} tools: ${tl.text.slice(0, 200)}`);
ok(`tools/list returned ${tools.length}: ${tools.join(', ')}`);
const skill = fs.readFileSync(path.join(ROOT, 'skills', 'cue-omni-parser', 'SKILL.md'), 'utf8');
const documented = [...skill.matchAll(/^### `([a-z_]+)`/gm)].map((m) => m[1]);
const missing = documented.filter((d) => !tools.includes(d));
if (missing.length) die(`SKILL.md documents tools absent from server: ${missing.join(', ')}`);
ok(`SKILL.md tool names match server: ${documented.join(', ')}`);

console.log('\nOK: OAuth + MCP surface verified. No parse was submitted, no token was persisted.');
