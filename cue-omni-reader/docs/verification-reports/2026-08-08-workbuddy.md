# WorkBuddy provenance and prior live evidence — 2026-08-08

- **Official skill target:** cue-omni-reader v0.1.0
- **Client:** WorkBuddy
- **Mode:** historical authorized service observation plus source-artifact provenance; no new production parse or Omni credits

A WorkBuddy-generated pre-release artifact provided the initial orchestration concepts and historical long-media behavior used to design the official rewrite. The artifact itself is not included in this repository.

## Prior live observation

In an earlier authorized WorkBuddy run, a long public-video request timed out at the client while the asynchronous path returned a recoverable operation and later completed with the expected media modalities. This established that a client timeout does not prove backend failure and that agents must preserve and recover one operation instead of racing submissions.

## Publication boundary

The pre-release artifact failed public release-hygiene checks because it contained local-only configuration, stale bundled material, incident-specific guidance, and an unsupported custom runtime. The official `cue-omni-reader` rewrite retains only the reusable orchestration rules and relies exclusively on the official MCP surface.

WorkBuddy therefore has verified provenance and prior live async service evidence. The exact rewritten official v0.1.0 text has not yet been natively loaded and pressure-tested inside WorkBuddy, so that narrower client-loading claim remains unverified.
