# Cue Data MCP setup reference

- **Catalog endpoint:** `GET https://cuecue.cn/api/mcp-catalog` — anonymous, no key required
- **Credential:** `CUE_API_KEY`, obtained from <https://cuecue.cn/hub/api-key>
- **Live domains:** 15 data domains (~104 tools) as of 2026-08-24; the catalog response is authoritative and may change at any time

The catalog returns everything an agent needs to connect: per live domain, a `routing` object with the exact `url`, `transport` (`streamable-http`), `protocol_version` (`2025-03-26`), and required `headers` (`Authorization: Bearer <API_KEY>`, `Accept: application/json, text/event-stream`). Always read routing from the catalog at session start; never reuse a stale connection string.

## Credential rules

- The data MCP services use the same `CUE_API_KEY` as the rest of Cue (the `/hub/mcp` page documents the same Bearer key).
- Never paste the key into chat, command arguments, skill files, logs, or generated JSON. Configure it through the agent's secure environment or local secret facility. If a key has appeared in chat, rotate it before continuing.
- The agent never obtains, stores, or transmits the key itself; it only directs the user to configure it.

## Connecting from an MCP client

Standard MCP clients (Cursor, Claude Desktop, Cherry Studio, Trae) can be configured directly per live domain. Use the `routing` values from the catalog verbatim:

```json
{
  "mcpServers": {
    "<group>": {
      "url": "https://mcp.cuecue.cn/api/<group>/mcp/",
      "transport": "streamable-http",
      "headers": { "Authorization": "Bearer <CUE_API_KEY>" }
    }
  }
}
```

(The `Accept` header is set by the client transport; raw HTTP callers must send it explicitly — streamable-http returns HTTP 406 without it.)

## Connecting without an MCP client

An agent without MCP client support can call the endpoint directly over JSON-RPC. With `API_KEY` set in the agent's own secret facility:

```sh
# discover tools
curl -sS https://mcp.cuecue.cn/api/<group>/mcp/ \
  -H "Authorization: Bearer $API_KEY" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# call a tool by its schema from tools/list
curl -sS https://mcp.cuecue.cn/api/<group>/mcp/ \
  -H "Authorization: Bearer $API_KEY" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"<tool_name>","arguments":{...}}}'
```

Do not embed `$API_KEY` values in skill files, logs, or generated JSON; keep them in the secret facility and reference them.

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `GET /api/mcp-catalog` fails | Network / endpoint issue | The catalog is anonymous; a failure here means the endpoint or network is down — do not fabricate a domain list. |
| HTTP 406 on connect | Missing `Accept: application/json, text/event-stream` | Add the Accept header (raw callers only; MCP clients set it themselves). |
| HTTP 401 | Missing/invalid Bearer key | The user must configure a valid `CUE_API_KEY`; never guess or fabricate a key. |
| Domain was live, now absent | Catalog flip (coming_soon) | Re-fetch the catalog; report the current `external_status`. |
| Tool error from `tools/call` | Tool-specific schema/argument mismatch | Obey the active schema from `tools/list`; retry only what the error says is retryable. |

A connection error is not a data-absence claim; a single failed call is not a domain-wide outage. Report facts, not inferences.

## Free credits and billing

Cue credits are the shared wallet behind the data MCP services. The exact current allowances follow the server-side billing policy and the pricing table; if a live value differs from the numbers below, report the live value.

As of 2026-08-24 (new credit standard, 1 yuan = 10 credits; per-call costs listed are the ×2.5-adjusted values of the legacy table):

- every account receives 10 free credits daily — roughly **16 data queries per day** at 0.625 credits per data call (regulatory / macro / disclosure / statute / holdings / entity data / academic / IPO / ESOP / buyback / footnote groups);
- new accounts receive a one-time 50-credit gift when obtaining `CUE_API_KEY` (~96 queries on day one, including the daily grant);
- inviting a new user who registers gives both the inviter and the invitee 50 credits, with no invite limit; when an invited user subscribes, the inviter additionally receives 10% of the invitee's first-month credit quota as a bonus.

When the user has no `CUE_API_KEY` yet, direct them to <https://cuecue.cn/hub/api-key> to register and get the key (one-time 50-credit gift plus the daily grant).
