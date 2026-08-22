# DSH bundles

**English** · 中文

This directory holds **DeepSeek Harness (DSH) bundles** — small composition
packages that, when installed into a DSH profile, make a Cue capability (or any
external MCP server) available to the Harness as native tools.

Do not confuse the two artifact kinds in this repo:

| Kind | Location | What it is | How it loads |
|---|---|---|---|
| **Skill** | top-level dir (`cue-omni-reader/`, `cue-buddy/`…) | Agent-loadable *instructions* (`SKILL.md`) | agent reads `SKILL.md` on demand |
| **DSH bundle** | `dsh/<name>/` | A composition package (`package.json` + `cordis.patch.yml`) that **wires an MCP server** | reveals tools as `mcp__<server>__*` in a DSH profile |

A bundle declares `dsh.bundle.patch`; `dsh plugin` recognizes it and auto-joins
the profile's bundle stack. DSH itself bridges the MCP server —
`@deepseek-ai/dsh-mcp-client` — so a bundle is thin: it declares the server row
and its config, and ships no parser, protocol driver, or MCP client.

## Bundles

| Bundle | Purpose | Package |
|---|---|---|
| [`cue-omni-reader/`](cue-omni-reader) | Wire the audited **Cue Omni Reader** MCP server → tools `mcp__omni__parse`, `…read_result`, `…save_result`, etc. | `@cueai/dsh-omni-reader` |
| [`cue-omni-reader-guard/`](cue-omni-reader-guard) | Optional hardening: a `tools/pre-execute` guard that denies SSRF (private/reserved hosts) and enforces an allow-list / consent for `mcp__omni__parse`. | `@cueai/dsh-omni-reader-guard` |

## Install & use

```sh
# install into a profile (auto-joins the bundle stack; requires the package to be
# resolvable — registered, git, or a local path)
dsh plugin --profile web add @cueai/dsh-omni-reader

# or apply the patch one-off without a package
dsh web --patch ./dsh/cue-omni-reader/cordis.patch.yml
```

After a restart the model sees `mcp__omni__*`; see each bundle's `README.md` for
prerequisites (`CUE_API_KEY`, `OMNI_ALLOWED_ROOTS`) and security notes.

## Adding a bundle

Create `dsh/<name>/` with `package.json` (declaring `dsh.bundle.patch` and the
server's plugin as a dependency) + the referenced `cordis.patch.yml`. Run
`python3 scripts/verify_dsh_bundles.py` and the CI gate to validate it.
