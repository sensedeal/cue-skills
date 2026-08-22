// policy.js — pure, dependency-free SSRF / allow-list / consent policy for the
// Cue Omni Reader `parse` tool. Deterministic on (source, opts) so it is unit
// testable with Node's test runner; the DSH glue lives in index.js.
//
// classifySource().kind is one of 'allow' | 'deny' | 'ask' — the same vocabulary
// as the DSH `tools/pre-execute` PreToolDecision, so the glue maps directly.
import { URL } from 'node:url'
import { isIP } from 'node:net'
import { resolve, join, sep } from 'node:path'

export function isHttpSource(source) {
  return typeof source === 'string' && /^https?:\/\//i.test(source.trim())
}

export function parseHostOf(source) {
  try {
    const host = new URL(source.trim()).hostname.toLowerCase()
    return host || null
  } catch {
    return null
  }
}

export function isIpLiteral(host) {
  return isIP(host) !== 0
}

export function isPrivateIPv4(ip) {
  const parts = ip.split('.').map(Number)
  if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) return false
  const [a, b] = parts
  return (
    a === 0 || a === 10 || a === 127 ||
    (a === 100 && b >= 64 && b <= 127) || // CGNAT 100.64/10
    (a === 169 && b === 254) ||           // link-local / cloud metadata
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168)
  )
}

export function isPrivateIPv6(ip) {
  const lower = ip.toLowerCase()
  return (
    lower === '::' || lower === '::1' ||
    lower.startsWith('fe80:') ||           // link-local
    /^(fc|fd)[0-9a-f]/.test(lower)         // unique-local fc00::/7
  )
}

export function isPrivateHost(host) {
  if (isIP(host) === 4) return isPrivateIPv4(host)
  if (isIP(host) === 6) return isPrivateIPv6(host)
  return false
}

export function isReservedHostname(host) {
  return (
    host === 'localhost' ||
    host.endsWith('.local') ||
    /(^|\.)(localhost|metadata|metadata\.google\.internal)$/i.test(host)
  )
}

export function inAllowlist(host, allowList = []) {
  for (const raw of allowList) {
    const entry = String(raw).trim().toLowerCase()
    if (!entry) continue
    const suffix = entry.replace(/^\*\./, '')
    if (entry.startsWith('*.')) {
      if (host.endsWith('.' + suffix) || host === suffix) return true
    } else if (host === entry || host.endsWith('.' + entry)) {
      // a bare domain also admits its subdomains
      return true
    }
  }
  return false
}

export function isUnderRoot(absPath, roots) {
  const p = resolve(absPath)
  for (const root of roots || []) {
    const r = resolve(String(root))
    if (p === r || p.startsWith(r.endsWith(sep) ? r : r + sep)) return true
  }
  return false
}

export function defaultOpts() {
  return {
    blockPrivate: true,
    allowList: [],
    allowedRoots: [], // empty -> resolved to [process.cwd()] at normalize time
    policyForUnknown: 'deny', // 'deny' | 'ask' | 'allow'
    consentReason: '解析外部 URL 前请确认(将消耗 Cue 积分)',
  }
}

export function normalizeOpts(raw = {}) {
  const d = defaultOpts()
  const o = { ...d, ...raw }
  if (!Array.isArray(o.allowList)) throw new Error('allowList must be an array')
  if (!Array.isArray(o.allowedRoots)) throw new Error('allowedRoots must be an array')
  if (!(o.blockPrivate === true || o.blockPrivate === false)) {
    throw new Error('blockPrivate must be a boolean')
  }
  if (!['deny', 'ask', 'allow'].includes(o.policyForUnknown)) {
    throw new Error("policyForUnknown must be 'deny' | 'ask' | 'allow'")
  }
  if (o.allowedRoots.length === 0) o.allowedRoots = [join(process.cwd())]
  return o
}

export function classifySource(source, rawOpts = {}) {
  const o = normalizeOpts(rawOpts)
  const value = typeof source === 'string' ? source.trim() : source

  if (!isHttpSource(value)) {
    // treat as a local path
    if (typeof value === 'string' && isUnderRoot(value, o.allowedRoots)) {
      return { kind: 'allow' }
    }
    return {
      kind: 'deny',
      reason: 'local source is outside the allowed roots; authorize a root first',
    }
  }

  const host = parseHostOf(value)
  if (!host) {
    return { kind: 'deny', reason: 'unparseable URL' }
  }

  if (o.blockPrivate && (isPrivateHost(host) || isReservedHostname(host))) {
    return {
      kind: 'deny',
      reason: `URL host "${host}" is private/local/reserved (SSRF guard). ` +
        'Only public allow-listed hosts may be parsed.',
    }
  }

  if (inAllowlist(host, o.allowList)) {
    return { kind: 'allow' }
  }

  switch (o.policyForUnknown) {
    case 'allow':
      return { kind: 'allow' }
    case 'ask':
      return { kind: 'ask', reason: o.consentReason }
    case 'deny':
    default:
      return {
        kind: 'deny',
        reason: `URL host "${host}" is not allow-listed and policyForUnknown=deny.`,
      }
  }
}

// Decide for a DSH tool execution: only Omni parse calls are gated; every
// other tool is allowed through untouched.
export function decideTool(exec, rawOpts = {}) {
  if (!exec || exec.name !== 'mcp__omni__parse') {
    return { kind: 'allow' }
  }
  const source = exec.arguments && exec.arguments.source
  if (source === undefined || source === null) {
    return { kind: 'allow' } // no source argument; let the bridge schema handle it
  }
  return classifySource(source, rawOpts)
}
