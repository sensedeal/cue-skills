// Unit tests for the guard policy core (policy.js). Runs with Node's built-in
// test runner:  node --test dsh/cue-omni-reader-guard/test/policy.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { join } from 'node:path'
import {
  isHttpSource,
  parseHostOf,
  isPrivateIPv4,
  isPrivateIPv6,
  isPrivateHost,
  isReservedHostname,
  inAllowlist,
  isUnderRoot,
  classifySource,
  decideTool,
} from '../policy.js'

// isUnderRoot / classifySource is pure prefix matching on paths — no file or
// temp dir is created, so the test needs no writable temp location.
const wrk = join(process.cwd(), 'dsh', 'cue-omni-reader-guard')

test('isHttpSource / parseHostOf', () => {
  assert.ok(isHttpSource('https://example.com/a'))
  assert.ok(isHttpSource('http://192.168.1.1'))
  assert.ok(!isHttpSource('http'))
  assert.ok(!isHttpSource('/home/x/a.pdf'))
  assert.equal(parseHostOf('https://Example.COM/x'), 'example.com')
  assert.equal(parseHostOf('not a url'), null)
})

test('private IPv4 ranges', () => {
  for (const ip of ['10.0.0.1', '127.0.0.1', '192.168.1.1', '172.16.0.1', '172.31.255.1', '169.254.169.254', '100.64.0.1', '0.0.0.0'])
    assert.ok(isPrivateIPv4(ip), ip)
  for (const ip of ['8.8.8.8', '1.1.1.1', '172.15.0.1', '100.63.0.1'])
    assert.ok(!isPrivateIPv4(ip), ip)
})

test('private IPv6 / reserved hostnames', () => {
  assert.ok(isPrivateIPv6('::1'))
  assert.ok(isPrivateIPv6('fe80::1'))
  assert.ok(isPrivateIPv6('fc00::1'))
  assert.ok(isPrivateIPv6('fd12::1'))
  assert.ok(!isPrivateIPv6('2606:4700:4700::1111'))
  assert.ok(isReservedHostname('localhost'))
  assert.ok(isReservedHostname('db.local'))
  assert.ok(isReservedHostname('metadata.google.internal'))
  assert.ok(!isReservedHostname('example.com'))
})

test('inAllowlist', () => {
  const list = ['api.example.com', '*.foo.dev', 'trusted.com']
  assert.ok(inAllowlist('api.example.com', list))
  assert.ok(inAllowlist('sub.api.example.com', list)) // bare domain admits subdomains
  assert.ok(inAllowlist('a.foo.dev', list))          // wildcard
  assert.ok(!inAllowlist('evil.com', list))
  assert.ok(!inAllowlist('example.com', list))        // api.example.com only
})

test('isUnderRoot', () => {
  assert.ok(isUnderRoot(join(wrk, 'f.pdf'), [wrk]))
  assert.ok(isUnderRoot(wrk, [wrk]))
  assert.ok(!isUnderRoot('/etc/passwd', [wrk]))
})

test('classifySource: SSRF deny for private hosts', () => {
  const opts = { blockPrivate: true, allowList: [], allowedRoots: [wrk] }
  for (const src of ['http://127.0.0.1/x', 'http://10.0.0.5/', 'http://192.168.1.1/', 'http://169.254.169.254/latest', 'http://localhost/x', 'http://db.local/'])
    assert.equal(classifySource(src, opts).kind, 'deny', src)
})

test('classifySource: allow-list wins', () => {
  const opts = { blockPrivate: true, allowList: ['api.example.com'], allowedRoots: [wrk] }
  assert.equal(classifySource('https://api.example.com/v1', opts).kind, 'allow')
})

test('classifySource: policyForUnknown deny|ask|allow', () => {
  const base = { blockPrivate: true, allowList: [], allowedRoots: [wrk] }
  assert.equal(classifySource('https://evil.com/', { ...base, policyForUnknown: 'deny' }).kind, 'deny')
  assert.equal(classifySource('https://evil.com/', { ...base, policyForUnknown: 'ask' }).kind, 'ask')
  assert.equal(classifySource('https://evil.com/', { ...base, policyForUnknown: 'allow' }).kind, 'allow')
})

test('classifySource: local path within/outside roots', () => {
  const opts = { blockPrivate: true, allowList: [], allowedRoots: [wrk] }
  assert.equal(classifySource(join(wrk, 'sub', 'doc.pdf'), opts).kind, 'allow')
  assert.equal(classifySource('/etc/passwd', opts).kind, 'deny')
})

test('classifySource: empty allowedRoots denies local files (fail-closed)', () => {
  // allowedRoots omitted -> defaults to [] -> no implicit cwd root
  const opts = { blockPrivate: true, allowList: [] }
  assert.equal(classifySource(join(wrk, 'doc.pdf'), opts).kind, 'deny')
  assert.equal(classifySource(process.cwd(), opts).kind, 'deny')
})

test('decideTool: only mcp__omni__parse is gated', () => {
  const opts = { blockPrivate: true, allowList: [], allowedRoots: [wrk] }
  assert.equal(decideTool({ name: 'mcp__omni__get_parse_status', arguments: {} }, opts).kind, 'allow')
  assert.equal(decideTool({ name: 'other_tool', arguments: {} }, opts).kind, 'allow')
  assert.equal(decideTool({ name: 'mcp__omni__parse', arguments: { source: 'http://127.0.0.1/' } }, opts).kind, 'deny')
  assert.equal(decideTool({ name: 'mcp__omni__parse', arguments: { source: 'http://evil.com/' } }, opts).kind, 'deny')
  assert.equal(decideTool({ name: 'mcp__omni__parse', arguments: {} }, opts).kind, 'allow') // no source
})
