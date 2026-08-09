# Bridge CLI package-source audit — 2026-08-08

- **Package:** `@cueai/omni-reader-mcp@1.1.2`
- **Mode:** read-only package-source and packaged-README audit
- **Scope:** setup arguments, native adapters, root semantics, rollback, doctor contract, and uninstall restoration

The exact npm package was downloaded to a temporary audit directory and inspected without installing an MCP entry. No live client configuration write, API-key read, health request, production parse, or Omni call occurred.

## Verified command and adapter contract

The packaged argument parser accepts `setup`, `doctor --json`, and the required `uninstall --yes --json` form. Setup accepts explicit clients for Hermes, Cursor, Claude Desktop, and generic/Other configuration. The adapter source defines user-scope configuration targets and reload instructions for the three native clients, while generic setup returns a reviewed stdio entry instead of inventing a client path.

Both root flags are intentional and mutually exclusive: `--allowed-root` replaces the explicit additional-root set, while `--add-root` appends one absolute directory to roots already configured for that client. Both reject non-absolute paths.

## Verified write and rollback contract

Before a native write, the package validates the user-scope path, rejects symlink or conflicting entries, verifies that credentials remain references rather than literals, uses a private lock and atomic replacement, and records a trusted backup. If the post-write health check fails, setup attempts to restore the exact prior serialized configuration and reports when restoration cannot be confirmed.

Uninstall removes only the expected pinned Bridge entry. A matching trusted backup is required before it can restore a prior canonical URL-only entry; an unmatched or untrusted previous entry is not restored. Its structured result records that local artifacts are preserved and user source files are unchanged.

## Evidence boundary

This audit supports the command forms and package semantics documented by the official skill. It does not prove a successful live write to every supported client, a real health check, reload behavior, or production parsing; those remain live-unverified.
