// smoke.mjs — exercise the DSH plugin glue (index.js) without a live Harness.
//
// Confirms apply() registers a `tools/pre-execute` listener and that the
// listener maps representative tool calls onto allow / deny / ask decisions,
// using a minimal fake `ctx.tools.on`. Pure Node: `node test/smoke.mjs`.
import assert from 'node:assert/strict'
import { apply, name, inject } from '../index.js'

// --- minimal ctx with a call-capturing tools.on ---------------------------
const listeners = {}
const ctx = {
  tools: {
    on(event, listener) {
      listeners[event] = listener
      return () => { delete listeners[event] }
    },
  },
}

const config = { blockPrivate: true, allowList: ['api.example.com'], policyForUnknown: 'deny' }
const dispose = apply(ctx, config)

assert.ok(listeners['tools/pre-execute'], 'plugins must register a tools/pre-execute listener')

const listener = listeners['tools/pre-execute']

let nextCount = 0
const next = async () => { nextCount += 1; return 'NEXT' }

const gate = async (exec) => {
  nextCount = 0
  const decision = await listener(exec, next)
  return { decision, nextCount }
}

const runs = []
const expect = (name1, args, kind, wantNext, label) => {
  runs.push({ label, exec: { name: name1, arguments: args }, kind, wantNext })
}

expect('mcp__omni__parse', { source: 'http://127.0.0.1/x' }, 'deny', false, 'loopback denied')
expect('mcp__omni__parse', { source: 'https://api.example.com/v1' }, 'allow', true, 'allow-listed host allowed')
expect('mcp__omni__parse', { source: 'https://evil.com/' }, 'deny', false, 'unknown host denied (policyForUnknown=deny)')
expect('mcp__omni__get_parse_status', { operation_id: 'op_x' }, 'allow', true, 'non-parse tool untouched')
expect('mcp__omni__parse', { source: '/home/cue/dsh/x.pdf' }, 'deny', false, 'local path denied (empty allowedRoots)')

for (const r of runs) {
  const { decision, nextCount } = await gate(r.exec)
  if (r.kind === 'allow') {
    // allow delegates via next(); the returned value is the downstream result
    assert.ok(nextCount > 0, `${r.label}: allow must delegate via next()`)
  } else {
    assert.equal(decision.kind, r.kind, `${r.label}: expected kind ${r.kind}, got ${decision && decision.kind}`)
    assert.equal(nextCount, 0, `${r.label}: deny/ask must not call next()`)
  }
}

// --- ask path ------------------------------------------------------------
const askConfig = { ...config, policyForUnknown: 'ask' }
apply(ctx, askConfig) // re-register the listener with the ask config
const askListener = listeners['tools/pre-execute']
const askResult = await askListener({ name: 'mcp__omni__parse', arguments: { source: 'https://nope.com/' } }, next)
assert.equal(askResult.kind, 'ask', 'policyForUnknown=ask returns ask for unknown host')

// --- uninteresting tool passes through ------------------------------------
const pass = await askListener({ name: 'mcp__omni__read_result', arguments: { result_id: 'r' } }, next)
assert.equal(typeof pass, 'string', 'non-parse tool still delegates under ask config')

dispose?.()
console.log(`smoke OK: ${runs.length + 2} cases passed (register + allow/deny/ask decision mapping)`)
