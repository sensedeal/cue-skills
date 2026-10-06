# Cue Omni Reader verification reports

Verification reports are evidence, not evergreen instructions. Each report records, where applicable:

- skill and Bridge versions relevant to that evidence;
- agent/client and operating system;
- whether each scenario was simulated or live;
- the active `parse` schema shape;
- the exact decision and observable outcome;
- billing and cleanup facts returned by tools;
- gaps that remain unverified.

Reports must not contain API keys, authorization headers, account balances, personal paths, source contents, full operation/result IDs, private client configuration, or client-generated MCP namespaces. Replace source paths with a source category, replace generated tool namespaces with semantic tool names, and retain only the minimum evidence needed to reproduce the behavior.

A resolved incident may explain why a stable rule exists, but it must not remain as a hostname-specific routing rule. Never upgrade simulated evidence into a live compatibility claim.

## Publication confirmations

- [Bridge 1.5.5](2026-08-26-bridge-1.5.5-published.md) — package publication, artifact, doctor, and clean-consumer evidence.
- [Bridge 1.6.0](2026-08-30-bridge-1.6.0-published.md) — byte-identical registry publication, exact Cube admission, and one bounded production result-delivery acceptance identity.
- [Bridge 1.7.1](2026-09-04-bridge-1.7.1-published.md) — byte-identical registry publication, non-circular upgrade guidance, exact Cube admission, and production rollout health evidence without a new billable parse.
- [Bridge 1.7.2](2026-09-06-bridge-1.7.2-published.md) — byte-identical registry publication and reproducible-tarball evidence for a client-side extension-allowlist catch-up; no `cube-mcp` admission-list claim (open follow-up).
- [Bridge 1.7.3](2026-09-08-bridge-1.7.3-published.md) — byte-identical registry publication and reproducible-tarball evidence for a metadata-only license correction (`UNLICENSED` → `MIT`, version `1.7.2` → `1.7.3`); no tool-surface or `cube-mcp` claim.
- [Bridge 1.8.0](2026-09-09-bridge-1.8.0-published.md) — byte-identical registry publication and reproducible-tarball evidence for the `doctor --silent-check` update probe and reconnect guidance; no tool-surface or `cube-mcp` claim.
- [Bridge 1.8.1](2026-09-22-bridge-1.8.1-published.md) — byte-identical registry publication for client-side tolerance of an optional inline `media_type` (result-bundle label installed as a local `kind: bundle`); no Omni service emits the label yet, so no remote `grounded`/`layout` or `cube-mcp` claim.
- [Bridge 1.8.3](2026-09-23-bridge-1.8.3-published.md) — byte-identical registry publication; pin-sync release with data-plane error codes renamed to `OMNI_READER_*` / `INSECURE_OMNI_READER_URL` (hard cut, no alias).
- [Bridge 1.8.2](2026-09-23-bridge-1.8.2-published.md) — byte-identical registry publication; capability negotiation reaches the live service and completed bundles recover locally across processes; remote URL `grounded`/`layout` verified end to end in production (cube-mcp 1.5.52, Omni Reader 0.3.66).
- [Bridge 1.8.5](2026-10-06-bridge-1.8.5-published.md) — byte-identical registry publication; WorkBuddy dogfood blockers: `KEY_DELIVERY_FAILED` / `GRANT_SIZE_LIMIT_EXCEEDED`, deployment-tunable clamped budgets, first-class `setup --client workbuddy`, `doctor` workbuddy adapter + real-process `stdio_probe`, allowed-root skip, field-level `INVALID_GRANT_REQUEST`; no tool-shape change; trust pair 1.8.4/1.8.5.
- [Bridge 1.8.4](2026-09-28-bridge-1.8.4-published.md) — byte-identical registry publication; local-file `grounded`/`layout` preflight resolves the same v2 advertisement the grant uses (v1 only as a 404 fallback for a non-text detail), ending a spurious `DETAIL_CAPABILITIES_UNAVAILABLE`. TEST detail smokes passed; PROD deployment/health verified, paid PROD detail parse not verified.
