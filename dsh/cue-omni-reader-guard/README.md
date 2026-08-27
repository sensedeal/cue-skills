# @cueai/dsh-omni-reader-guard

**[English](README.md)** · [中文](README.zh-CN.md)

An optional **DeepSeek Harness** bundle that hardens the Omni Reader `parse` tool.
It registers a `tools/pre-execute` listener that gates `mcp__omni__parse` so a
model cannot silently parse an arbitrary URL. Install it **after/alongside** the
[`@cueai/dsh-omni-reader`](../cue-omni-reader) wiring bundle.

## What it does

Before a `mcp__omni__parse` call dispatches, the guard classifies the `source`:

| source | outcome |
|---|---|
| **private / loopback / link-local / cloud-metadata host** (`10/8`, `172.16/12`, `192.168/16`, `127/8`, `169.254.169.254`, `100.64/10`, `fe80::`, `fc00::`, `::1`, `localhost`, `*.local`, `metadata…`) | **deny** (SSRF guard) |
| **allow-listed host** (`allowList`) | **allow** |
| other external host | `policyForUnknown` — `deny` (default), `ask`, or `allow` |
| **local path** inside an explicitly configured `allowedRoots` | **allow** |
| **local path** outside `allowedRoots`, or no `allowedRoots` set | **deny** (fail-closed) |

Every other tool passes through untouched (the guard keys on `mcp__omni__parse`). It gates
the `source` argument **and** the `url` alias (Bridge 1.5+ accepts exactly one of the two).

## Install

```sh
dsh plugin --profile web add @cueai/dsh-omni-reader-guard
# or one-off
dsh web --patch ./dsh/cue-omni-reader-guard/cordis.patch.yml
```

## Configure

Via the bundle's `cordis.patch.yml` `config` (no secrets, no hardcoded deployment paths):

| Field | Type | Default | Meaning |
|---|---|---|---|
| `blockPrivate` | boolean | `true` | deny private/reserved hosts (the SSRF gate) |
| `allowList` | string[] | `[]` | hosts/domains that bypass consent (a bare domain also admits subdomains; `*.x` for subdomains only) |
| `allowedRoots` | string[] | `[]` (local files **denied**) | absolute dirs a local `source` must fall under. **Set explicitly** to allow local parsing; empty = fail-closed |
| `policyForUnknown` | `'deny'`\|`'ask'`\|`'allow'` | `'deny'` | outcome for an external host not in `allowList` |
| `consentReason` | string | … | prompt text for `policyForUnknown: ask` |

Example: allow a trusted API host and require consent elsewhere.

```yaml
config:
  blockPrivate: true
  allowList: ['api.example.com']
  policyForUnknown: ask
```

## Verify

```sh
node --test dsh/cue-omni-reader-guard/test/policy.test.js
python3 scripts/verify_dsh_bundles.py
```

## Notes

- `ask` requires DSH's approval service to return `allowed-once`; without one it
  becomes a denial (fail-closed) — see the `tools/pre-execute` waterfall contract.
- This is a guard, not a sandbox: it filters hosts and local roots, it does not
  rewrite arguments. Keep `allowedRoots` minimal and prefer `deny` + an explicit
  `allowList` for unattended agents.
- The core policy (`policy.js`) is pure Node (`node:url`/`node:net`), so the
  security logic is testable without a live DSH.

## License

MIT — see [LICENSE](../../LICENSE).
