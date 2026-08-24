# cue-data-mcp

**[English](README.md) · [中文](README.zh-CN.md)**

> An AI-agent skill that queries Cue's public MCP **data services** — regulatory, macro, disclosures, market data, statute full text, holdings, entity data, academic, IPO, ESOP, buyback, footnote details — through the official `/hub/mcp` surface. A thin instruction layer: no runtime code, no hardcoded endpoints or tool names.

> **Sibling skills:** [`cue-buddy`](../cue-buddy) (author research buddies) · [`cue-research`](../cue-research) (run deep research in your agent) · [`cue-omni-reader`](../cue-omni-reader) (document/URL parsing). This skill handles *external data queries*; the others handle *research* and *parsing*.

## What this skill is

`cue-data-mcp` plugs into any AI agent (Claude Code, Codex CLI, Gemini CLI, OpenClaw, etc.) and tells it how to reach Cue's data tools over the standard MCP protocol — no page configuration of an MCP client needed, and no custom parser: the agent loads the skill, discovers the live domains, and calls the data tools directly.

The live catalog is the only source of truth:

1. **Discover** — `GET https://cuecue.cn/api/mcp-catalog` (anonymous, no key required) lists the domains; live ones carry a full `routing` DTO.
2. **Pick a domain** by topic — 15 data domains as of 2026-08-24 (~104 tools); `omni-reader` is excluded here because it has its own dedicated skill.
3. **Connect** — use the live domain's `routing` verbatim: `url`, `transport: streamable-http`, `protocol_version: 2025-03-26`, and the required headers (`Authorization: Bearer <CUE_API_KEY>`; the `Accept` header — a streamable-http endpoint returns HTTP 406 without it).
4. **Self-discover tools** — `tools/list` on the endpoint returns the active schemas; never hardcode tool names.
5. **Call per schema** — `tools/call` with the arguments the live schema defines.

## Connect

Any standard MCP client can be configured per live domain, or an agent without a client can call the endpoint directly over JSON-RPC:

```sh
curl -sS https://mcp.cuecue.cn/api/<group>/mcp/ \
  -H "Authorization: Bearer $CUE_API_KEY" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

**Credentials:** the data services use the same `CUE_API_KEY` as the rest of Cue, from <https://cuecue.cn/hub/api-key>. The agent never obtains, stores, or transmits the key — the user configures it in their own secret facility. Never paste the key into chat, command arguments, skill files, logs, or generated JSON; if it has appeared anywhere, rotate it before continuing.

Full client-config shapes, raw JSON-RPC examples, and a troubleshooting table (406 / 401 / domain flips): [`references/setup.md`](references/setup.md).

## Free credits

Every Cue account receives 10 free credits daily — roughly **16 data queries per day** at 0.625 credits per data call — and new accounts get a one-time 50-credit gift when obtaining `CUE_API_KEY` (~96 queries on day one). Get a key at <https://cuecue.cn/hub/api-key>. Exact current allowances follow the server-side billing policy — report the live value if it differs.

## Repo layout

```
cue-data-mcp/
├── SKILL.md                # Skill spec read by the calling agent (loading contract)
├── SKILL.zh-CN.md          # Complete Chinese translation of SKILL.md
├── README.md               # This file
├── README.zh-CN.md         # Chinese version of this file
├── references/
│   └── setup.md            # Credential rules, client config, JSON-RPC, troubleshooting
└── scripts/
    └── test_skill_regression.py   # 11 skill regression tests
```

## License

[MIT](../LICENSE)
