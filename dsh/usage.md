# Using the Cue DSH bundles — usage & FAQ

**English** · 中文

Two publishable bundles make the Cue Omni Reader available to a DeepSeek Harness
profile, then let you harden it:

| Package | Purpose | Install |
|---|---|---|
| [`@cueai/dsh-omni-reader`](../cue-omni-reader) | Wire the audited Omni Reader MCP server → tools `mcp__omni__*` | always |
| [`@cueai/dsh-omni-reader-guard`](../cue-omni-reader-guard) | Optional `tools/pre-execute` guard (SSRF / allow-list / consent) | optional, after the above |

## 中文

| 包 | 作用 |
|---|---|
| `@cueai/dsh-omni-reader` | 把审校版 Omni Reader MCP server 接进 DSH → 工具 `mcp__omni__*` |
| `@cueai/dsh-omni-reader-guard` | 可选护栏(SSRF / 白名单 / 同意),安装在 wiring 之后 |

---

## Install

```sh
dsh plugin --profile web add @cueai/dsh-omni-reader
dsh plugin --profile web add @cueai/dsh-omni-reader-guard   # optional
dsh --profile web --dump-config            # confirm mcp-omni + guard rows
```

After a restart the model sees `mcp__omni__parse` / `…get_parse_status` /
`…cancel_parse` / `…read_result` / `…read_outline` / `…discard_result` /
`…save_result`.

## Configure the wiring bundle

Everything is env-driven (no secrets/paths in the patch). Set in `$DSH_HOME/.env`
or export before launching dsh:

```sh
CUE_API_KEY=sk-...                    # required — from https://cuecue.cn/hub/api-key
OMNI_ALLOWED_ROOTS=/home/you/workspace  # optional; defaults to the dsh cwd
```

The Bridge is **pinned to `@cueai/omni-reader-mcp@1.5.2`** (audited; never an
implicit `latest`). Requires Node ≥ 20.12.

## Configure the guard bundle (defaults are fail-closed)

```yaml
config:
  blockPrivate: true          # deny private/loopback/link-local/metadata hosts (SSRF)
  allowList: []               # hosts that bypass consent; bare domain admits subdomains
  allowedRoots: []            # OPT-IN: set explicit absolute dirs to allow LOCAL files
  policyForUnknown: deny      # deny | ask | allow  (external, non-allow-listed)
  consentReason: '解析外部 URL 前请确认(将消耗 Cue 积分)'
```

| Outcome | When |
|---|---|
| **deny** | private/reserved host; local path when `allowedRoots` empty; external host with `policyForUnknown=deny` |
| **allow** | allow-listed host; local path inside `allowedRoots` |
| **ask** | external host with `policyForUnknown=ask` (needs DSH's approval service returning `allowed-once`; otherwise becomes deny) |

`allowedRoots` is **empty by default → local file sources are denied**. To parse
local files you must opt in:

```yaml
config:
  allowedRoots: [!!js process.cwd()]   # or an explicit absolute dir
```

## FAQ

**Q. Why is my local file denied?**
The guard defaults `allowedRoots` to `[]` (fail-closed). Add an explicit
absolute dir (above) to allow local parsing.

**Q. Why is this public URL denied?** It is not in `allowList` and
`policyForUnknown=deny`. Either add the host/domain to `allowList` or set
`policyForUnknown: ask` to require a one-time confirmation.

**Q. Why is a private / `localhost` URL denied?** That is the SSRF gate
(`blockPrivate: true`). It exists because Omni can fetch arbitrary URLs; the
guard stops it from reaching internal / metadata hosts.

**Q. How do I allow a whole domain?** `allowList: ['example.com']` admits the
domain and its subdomains; `allowList: ['*.example.com']` admits subdomains only.

**Q. What does `ask` actually need?** It emits a consent prompt only when the
DSH approval channel returns `allowed-once`; without one the call is denied
(fail-closed). Prefer `allowList` + `deny` for unattended agents.

**Q. Do I need the guard?** No — the wiring bundle works alone. The guard is
for deployments that want to bound SSRF and cost when an agent can choose
parse targets.

**Q. How do I verify?** `dsh --profile web --dump-config`, then try a small parse;
run the repo checks: `node --test dsh/cue-omni-reader-guard/test/policy.test.js`,
`node dsh/cue-omni-reader-guard/test/smoke.mjs`,
`python3 scripts/verify_dsh_bundles.py`.

## Licensing / scope

Both bundles are `@cueai/*` (public scope) and MIT; ship tests and CI
(`verify-dsh-bundles`) so changes stay gated.
