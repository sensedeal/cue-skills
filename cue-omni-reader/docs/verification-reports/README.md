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
