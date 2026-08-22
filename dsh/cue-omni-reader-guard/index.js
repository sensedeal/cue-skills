// index.js — DSH plugin entry for @cueai/dsh-omni-reader-guard.
//
// Registers a `tools/pre-execute` waterfall listener. Only the Omni Reader
// `parse` tool is gated; every other tool passes through untouched. Decisions
// map directly onto DSH's PreToolDecision ({kind:'allow'|'deny'|'ask'}).
//
// The bundle's cordis.patch.yml mounts this package and supplies `config`:
//   blockPrivate, allowList, allowedRoots, policyForUnknown, consentReason.
// Secrets never appear here; see policy.js for the pure rule set.
import { decideTool, normalizeOpts } from './policy.js'

export const name = 'cue-omni-reader-guard'
export const inject = ['tools']

export function apply(ctx, config = {}) {
  const opts = normalizeOpts(config)

  return ctx.tools.on('tools/pre-execute', async (exec, next) => {
    try {
      const decision = decideTool(exec, opts)
      if (decision.kind === 'allow') return next()
      return decision
    } catch (err) {
      // fail-closed: an unexpected guard error must not let the call through
      return { kind: 'deny', reason: `cue-omni-reader-guard error: ${(err && err.message) || 'unknown'}` }
    }
  })
}
