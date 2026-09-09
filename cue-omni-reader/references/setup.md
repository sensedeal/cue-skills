# Omni Reader setup reference

- **Audited package:** `@cueai/omni-reader-mcp@1.7.3`
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
npx -y @cueai/omni-reader-mcp@1.7.3 setup
```

The interactive setup supports native configuration for Hermes, Cursor, and Claude Desktop. Choose **Other** for another client. Generic setup prints a reviewed stdio entry; apply it through that client's documented MCP configuration mechanism. Do not invent a configuration path or claim a client adapter is supported when it has not been verified.

The setup, root, and rollback contract was separately audited against packaged Bridge 1.1.2 source; see the [Bridge CLI package-source audit](../docs/verification-reports/2026-08-08-bridge-cli-audit.md) and the [content-only compatibility report](../docs/verification-reports/2026-08-11-content-only-compat.md).

Current audited release: **Bridge 1.7.3** — metadata-only (`license` `UNLICENSED` → `MIT`; no tool-surface or parsing change). The trusted managed-entry pair is **1.7.2 / 1.7.3**; the only bare-`npx` Windows migration exception remains 1.5.1. See the [1.7.3 publication report](../docs/verification-reports/2026-09-08-bridge-1.7.3-published.md); per-release history is in [`compatibility.md`](./compatibility.md).


Supported non-interactive native-adapter examples:

```sh
npx -y @cueai/omni-reader-mcp@1.7.3 setup --client hermes --allowed-root /absolute/minimum/root --yes --json
npx -y @cueai/omni-reader-mcp@1.7.3 setup --client cursor --add-root /absolute/minimum/root --yes --json
npx -y @cueai/omni-reader-mcp@1.7.3 setup --client claude-desktop --allowed-root /absolute/minimum/root --yes --json
```

Use `--allowed-root` to replace the explicit additional-root set with one minimum directory. Use `--add-root` to append one minimum directory to roots already configured for that client. Both require an absolute path and cannot be combined.

When a controlling agent is attached to a TTY but must not read stdin, use `--headless --json` with an explicit client. The user-level confirmation must already have happened before an agent uses `--yes` or `--headless`.

## Allowed roots

`OMNI_ALLOWED_ROOTS` contains only explicitly authorized absolute directories. Separate multiple roots with `:` on macOS/Linux and `;` on Windows. Do not authorize a whole home directory or disk by default. The current agent workspace remains the default allowed area.

After changing roots, reload or restart the MCP client so it receives the new environment. A parse request for a file already inside an allowed root needs no second generic confirmation.

## Verify after setup

Run:

```sh
npx -y @cueai/omni-reader-mcp@1.7.3 doctor --json
```

`doctor` checks package version, key presence, root safety, cache/artifact mode, and the client reload instruction; it reports only authenticated Cube control/configuration facts. The granted data plane is not probed; only a real local-file parse validates the route end-to-end. Reload or restart the client, then verify these tools are visible: `parse`, `get_parse_status`, `cancel_parse`, `read_result`, `read_outline`, `discard_result`, and `save_result`.

`doctor --json` must not reveal the API key, a private source path, or source content.

## Roll back

```sh
npx -y @cueai/omni-reader-mcp@1.7.3 uninstall --yes --json
```

Uninstall removes a normal trusted 1.7.2 or 1.7.3 Bridge entry; it also removes the exact broken bare-npx Windows entry written by 1.5.1 and restores a matching trusted URL-only entry when available. It does not delete user source files or silently discard unexpired local results. Recover any existing operation before starting replacement work.

## Granted credits and onboarding

New users can try Omni without paying. The server-side onboarding policy and live `doctor` output are the authority for current allowances; do not copy static page, image, audio, or video conversions into guidance.

When the user has no `CUE_API_KEY`, direct them to <https://cuecue.cn/hub/api-key>. Never obtain, store, or transmit the key yourself; the user configures it in their own secret facility.
