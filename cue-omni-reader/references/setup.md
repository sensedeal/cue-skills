# Omni Reader setup reference

- **Audited package:** `@cueai/omni-reader-mcp@1.8.8`
- **Runtime:** Node.js 20.12 or newer
- **Credential:** `CUE_API_KEY`, obtained from <https://cuecue.cn/hub/api-key>

Omni is one logical provider: the same `parse(source)` surface covers URLs and authorized local paths, and the agent never presents them to the user as two different connectors or products. Install the Bridge as the default — it handles a URL and a local file uniformly, so neither the agent nor the user has to reason about which kind of source it is. The only exception is a deployment that will genuinely never need local files, where an existing remote-only Omni connection already covers URLs with no local installation.

## Consent and credential rules

Before installation or allowed-root expansion:

1. explain that Omni will process the requested source;
2. explain that the Bridge receives access only to the workspace and explicitly added roots;
3. obtain confirmation;
4. add only the minimum required directory.

Do not paste an API key into chat, command arguments, skill files, logs, or generated JSON. Configure it through the agent's secure environment or local secret facility. If a key has appeared in chat, rotate it before continuing.

## Install the audited version

Never use an implicit `latest`:

```sh
npx -y @cueai/omni-reader-mcp@1.8.8 setup
```

The interactive setup supports native configuration for Hermes, Cursor, and Claude Desktop. Choose **Other** for another client. Generic setup prints a reviewed stdio entry; apply it through that client's documented MCP configuration mechanism. Do not invent a configuration path or claim a client adapter is supported when it has not been verified.

The setup, root, and rollback contract was separately audited against packaged Bridge 1.1.2 source; see the [Bridge CLI package-source audit](../docs/verification-reports/2026-08-08-bridge-cli-audit.md) and the [content-only compatibility report](../docs/verification-reports/2026-08-11-content-only-compat.md).

Current audited release: **Bridge 1.8.8** — delivery parity for structured billing details, with no tool-shape change on the seven local tools. A completed remote URL result now carries the same optional `billing.units` a direct-upload result has carried since 1.8.7: the bridge reads the server's `get_billing_details` tool once behind a 2-second, 16 KiB-bounded call, validates the closed `omni.billing_details.v1` envelope (credits must equal the settled facts), and binds the measurement into the durable journal with the same monotonic rules — restart keeps it. Every absence (an older server without the tool, a timeout, a malformed envelope, a credits mismatch) keeps the completed content and credits; units are never invented and never re-priced. The remote surface itself now exposes `get_billing_details` (read-only, never billed). The local output contract is `omni.local_bridge_tools.v6`; capability and grant negotiation stay `omni.local_bridge_tools.v5`. The trusted managed-entry pair advances to **1.8.7 / 1.8.8** — a 1.8.6 entry is no longer a trusted managed entry; the only bare-`npx` Windows migration exception remains 1.5.1. See the [1.8.8 publication report](../docs/verification-reports/2026-10-24-bridge-1.8.8-published.md); per-release history is in [`compatibility.md`](./compatibility.md).


Supported non-interactive native-adapter examples:

```sh
npx -y @cueai/omni-reader-mcp@1.8.8 setup --client hermes --allowed-root /absolute/minimum/root --yes --json
npx -y @cueai/omni-reader-mcp@1.8.8 setup --client cursor --add-root /absolute/minimum/root --yes --json
npx -y @cueai/omni-reader-mcp@1.8.8 setup --client claude-desktop --allowed-root /absolute/minimum/root --yes --json
```

Use `--allowed-root` to replace the explicit additional-root set with one minimum directory. Use `--add-root` to append one minimum directory to roots already configured for that client. Both require an absolute path and cannot be combined.

When a controlling agent is attached to a TTY but must not read stdin, use `--headless --json` with an explicit client. The user-level confirmation must already have happened before an agent uses `--yes` or `--headless`.

## Allowed roots

`OMNI_ALLOWED_ROOTS` contains only explicitly authorized absolute directories. Separate multiple roots with `:` on macOS/Linux and `;` on Windows. Do not authorize a whole home directory or disk by default. The current agent workspace remains the default allowed area.

After changing roots, reload the MCP connection so it receives the new environment — most clients only need a reconnect (Claude Code / WorkBuddy: `/mcp` → `omni-reader` → reconnect), not a full restart. A parse request for a file already inside an allowed root needs no second generic confirmation.

## Verify after setup

Run:

```sh
npx -y @cueai/omni-reader-mcp@1.8.8 doctor --json
```

`doctor` checks package version, key presence, root safety, cache/artifact mode, and the client reload instruction; it reports only authenticated Cube control/configuration facts. The granted data plane is not probed; only a real local-file parse validates the route end-to-end. Reload the MCP connection (most clients: `/mcp` → `omni-reader` → reconnect; a full client restart is usually unnecessary), then verify these tools are visible: `parse`, `get_parse_status`, `cancel_parse`, `read_result`, `read_outline`, `discard_result`, and `save_result`.

`doctor --json` must not reveal the API key, a private source path, or source content.

## Update check

On the first Omni use in a session, run the cheap probe:

```sh
npx -y @cueai/omni-reader-mcp@1.8.8 doctor --json --silent-check
```

It does **only** a version comparison against npm `latest` (no API, onboarding, or artifact work), caches the verdict for 24 hours so it never hammers the registry, and fails open when the registry is unreachable or the cache is unwritable. Read `version_check.status`:

- `current` / `ahead` → continue silently;
- `outdated` → tell the user `installed → latest` in one line and ask whether to upgrade. Only on explicit confirmation run the `upgrade` command it reports (`npx -y @cueai/omni-reader-mcp@<latest> setup`), then reconnect the MCP server (most clients: `/mcp` → `omni-reader` → reconnect).

Never auto-upgrade; check at most once per session. A cached verdict is only trusted for the same installed version, so an upgrade is never masked by a stale cache.

## Roll back

```sh
npx -y @cueai/omni-reader-mcp@1.8.8 uninstall --yes --json
```

Uninstall removes a normal trusted 1.8.7 or 1.8.8 Bridge entry; it also removes the exact broken bare-npx Windows entry written by 1.5.1 and restores a matching trusted URL-only entry when available. It does not delete user source files or silently discard unexpired local results. Recover any existing operation before starting replacement work.

## Granted credits and onboarding

New users can try Omni without paying. The server-side onboarding policy and live `doctor` output are the authority for current allowances; do not copy static page, image, audio, or video conversions into guidance.

When the user has no `CUE_API_KEY`, direct them to <https://cuecue.cn/hub/api-key>. Never obtain, store, or transmit the key yourself; the user configures it in their own secret facility.
