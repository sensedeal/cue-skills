---
name: cue-data-mcp
description: "Use when the user wants an external AI agent to query Cue's public MCP data services — regulatory, macro, disclosures, market data, legal full text, holdings, entity data, academic, IPO, ESOP, buyback, footnote details — by discovering and connecting to live MCP endpoints."
license: MIT
metadata:
  version: "0.3.6"
  requires: {}
  envOptional: ["CUE_API_KEY"]
---

# Cue Data MCP

Use Cue's public MCP data catalog to answer research questions with live external data. The catalog API and the MCP endpoint schemas are authoritative; this skill never implements an MCP client or hardcodes endpoints, domains, or tool names.

## Core flow

1. **Discover live domains.** Call `GET https://cuecue.cn/api/mcp-catalog` — anonymous, no key required. It returns the current domains with `external_status` (`live` / `coming_soon`), `tool_count`, `example_prompts`, and — for live domains — the full `routing` contract.
2. **Match the user's topic to domains.** Pick only the domains that cover the question (e.g. sanctions/KYC → `regulatory`; CPI/GDP → `macro`; SEC filings → `disclosure`; IPO → `ipo`). This catalog covers **15 data domains**; the `omni-reader` (document/web parsing) domain is out of scope here — use the dedicated cue-omni-reader skill for that.
3. **Connect through the routing DTO.** Use the live domain's `routing` verbatim: `url` (e.g. `https://mcp.cuecue.cn/api/<group>/mcp/`), `transport: streamable-http`, `protocol_version: 2025-03-26`. Send `Authorization: Bearer <CUE_API_KEY>` and the `Accept: application/json, text/event-stream` header (streamable-http returns HTTP 406 without it).
4. **Discover tools per domain with `tools/list`.** Never hardcode tool names — the catalog only projects names/titles for logged-in users, and the served tool set changes over time. `tools/list` on the connected endpoint is the live truth.
5. **Call the schema you actually have.** Obey the active tool schema from `tools/list`; never invent arguments. Prefer the domain with the smallest surface that covers the question; do not connect to all domains at once.

## Rules

- **The catalog is the only source of truth for reachability.** Always fetch it at the start; a domain can flip `coming_soon` ↔ `live` and routing values can change. Never reuse a stale connection string.
- **One domain per session unless the question spans several.** Each MCP connection advertises dozens of tools; connecting everywhere at once is slow and unnecessary.
- **Never paste the API key into chat, command arguments, skill files, logs, or generated JSON.** The user configures `CUE_API_KEY` in their own secret facility; the agent never obtains, stores, or transmits it. If a key has appeared in chat, ask the user to rotate it before continuing.
- **Report failures truthfully.** A connection error is not a data-absence claim; a tool error is not a domain-wide outage. Retry only what the error says is retryable. Never report a domain as unsupported because one call failed.

## Free credits and billing

Cue credits are the shared wallet behind the data MCP services (and Omni Reader). New users can try the data services without paying:

- every account receives **10 free credits daily** — at 0.625 credits per data call (current standard), roughly **16 data queries per day**;
- new accounts receive a **one-time 50-credit gift** when obtaining `CUE_API_KEY` (~96 queries on day one, including the daily grant);
- inviting a new user who registers gives both parties 50 credits.

The exact allowances and per-call costs follow the server-side billing policy; if a live value differs from the numbers above, report the live value.

When the user has no `CUE_API_KEY` yet, direct them to <https://cuecue.cn/hub/api-key> to register and get the key. Never obtain, store, or transmit the key yourself.
