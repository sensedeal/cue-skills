# Content-only MCP compatibility — 2026-08-11

> **Resolution (2026-08-13):** Bridge 1.1.3 was published on 2026-08-11 and is the npm `latest` dist-tag; it is live on the IIIS/TEST Omni Hub. See the [publication confirmation](2026-08-13-bridge-1.1.3-published.md). The "candidate" wording below reflects the pre-publication state on the day this report was written and is retained for history.

- **Skill candidate:** `cue-omni-reader` v0.1.1
- **Bridge candidate:** `@cueai/omni-reader-mcp@1.1.3`
- **Mode:** local regression and simulated client-channel verification
- **Scope:** traditional MCP text responses for clients that do not expose `structuredContent`

No production parse occurred and no Omni credits were consumed. No live client installation, native skill loading, MCP configuration write, deployment, or release acceptance was performed.

## Contract under test

The strict `structuredContent` response and output schemas remain authoritative. Candidate Bridge 1.1.3 adds an equivalent traditional text channel:

- a completed inline parse returns the exact Markdown in `content[].text`;
- every non-inline state returns compact JSON with the same actionable fields as the structured state;
- artifact reads expose each payload chunk as `result.text` plus an optional `next_cursor`;
- clients append only `result.text`, follow every cursor, and confirm `discard_result` from its returned state.

The covered non-inline states include processing, completed artifact, cleanup, cancellation, expiration, failure, artifact reads, and discard confirmation.

## Failing-first evidence

Before the result-channel implementation, the focused compatibility tests produced four expected failures: completed inline text was a generic success string, while processing and artifact responses were not actionable JSON. Existing tests remained green, isolating the missing traditional-text contract.

## Local verification evidence

After the minimal result-channel change:

- the complete Bridge runtime suite passed: 18 test files and 291 tests;
- production and test TypeScript typechecking passed;
- real child-process stdio coverage verified exact inline Markdown through `content[].text`;
- real child-process stdio coverage assembled an artifact larger than 64 KiB by reading every cursor and appending only `result.text`;
- cancellation and discard states remained actionable through compact traditional-text JSON;
- the package prepack dry run completed for exact candidate version 1.1.3.

These checks were local and simulated. They do not establish npm publication, deployment, a successful live client reload, client-native skill activation, production service behavior, or WorkBuddy acceptance.

## Remaining release gates

Resolved by the [2026-08-13 publication confirmation](2026-08-13-bridge-1.1.3-published.md): npm publication (2026-08-11, `latest`) and IIIS/TEST Hub live state are confirmed. WorkBuddy exact native loading and live acceptance remain unverified as of 2026-08-13.
