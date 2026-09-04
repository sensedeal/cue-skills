# DSH bundles — overview

**[English](dsh-bundles.md)** · [中文](dsh-bundles.zh-CN.md)

This repository ships, alongside its agent **skills**, a set of
[DeepSeek Harness](https://github.com/deepseek-harness) **bundles** under
[`dsh/`](../dsh) — thin composition packages that wire a Cue (or any external)
MCP server into a Harness profile so its tools surface as native
`mcp__<server>__*` tools.

A **skill** is agent-loadable *instructions* (`SKILL.md`); a **bundle** is a
*composition package* (`package.json` declaring `dsh.bundle.patch` + the
referenced `cordis.patch.yml`). `dsh plugin` recognizes the bundle declaration
and auto-joins the profile's bundle stack. DSH bridges the MCP server itself
(`@deepseek-ai/dsh-mcp-client`), so a bundle only wires the server row and its
config — it ships no parser, protocol driver, or MCP client.

## Shipped bundles

| Bundle | Package | What it does |
|---|---|---|
| [`cue-omni-reader`](../dsh/cue-omni-reader) | `@cueai/dsh-omni-reader` | Wires the audited **Cue Omni Reader** MCP server → tools `mcp__omni__parse`, `…get_parse_status`, `…read_result`, `…read_outline`, `…save_result`, etc. |
| [`cue-omni-reader-guard`](../dsh/cue-omni-reader-guard) | `@cueai/dsh-omni-reader-guard` | Optional `tools/pre-execute` guard: denies SSRF (private/reserved hosts), enforces an allow-list or consent for `mcp__omni__parse`. Fail-closed on an empty `allowedRoots`. |
| [`cue-data-mcp`](../dsh/cue-data-mcp) | `@cueai/dsh-cue-data-mcp` | Exposes Cue's **public data** MCP services (regulatory, macro, disclosures, statute, holdings, entity, academic, IPO, ESOP, buyback, footnote, fact index) as native `mcp__cue_<domain>__*` tools (15 domains / ~104 tools) via streamable-http. |

All three are `@cueai/*` (public scope), MIT, and ship `README.zh-CN.md` alongside
the English README.

## Distribution & validation

- **Install**: `dsh plugin --profile web add @cueai/dsh-omni-reader` (+
  `…-guard` for the hardening layer). See each bundle's `README.md` and
  [`dsh/usage.md`](../dsh/usage.md) for configuration and FAQ.
- **Validation** ([`scripts/verify_dsh_bundles.py`](../scripts/verify_dsh_bundles.py)):
  structure + bilingual docs (`README.zh-CN.md` required for every bundle and
  the index), `--publish-check` (scope/semver/metadata + plugin-entry syntax),
  and `--check-translation-parity` (heading level+order skeleton + fenced-code
  count between each EN/zh doc pair).
- **CI** (`.github/workflows/skill-regression.yml` → `verify-dsh-bundles` job)
  runs the bundle validation, the guard policy unit tests (`node --test`), and
  the guard glue smoke test (`node test/smoke.mjs`).

The wiring bundle wires the server; the guard bundle (optional) bounds SSRF and
cost. Together they let a Harness profile expose Cue Omni Reader as native
`mcp__omni__*` tools with a fail-closed safety layer.
