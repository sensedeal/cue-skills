# Omni Reader setup reference

- **Audited package:** `@cueai/omni-reader-mcp@1.1.2`
- **Runtime:** Node.js 20.12 or newer
- **Credential:** `CUE_API_KEY`, obtained from <https://cuecue.cn/api-key>

Use an existing official Omni MCP connection when it already supports the requested source. A URL does not require local Bridge installation. Install the Bridge only when a local source requires it or the user explicitly wants the unified local facade.

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
npx -y @cueai/omni-reader-mcp@1.1.2 setup
```

The interactive setup supports native configuration for Hermes, Cursor, and Claude Desktop. Choose **Other** for another client. Generic setup prints a reviewed stdio entry; apply it through that client's documented MCP configuration mechanism. Do not invent a configuration path or claim a client adapter is supported when it has not been verified.

The command forms, native-adapter source, root semantics, and trusted rollback logic below were checked against the exact packaged source and README; see the [Bridge CLI package-source audit](../docs/verification-reports/2026-08-08-bridge-cli-audit.md). No live client configuration write was performed for this skill release.

Supported non-interactive native-adapter examples:

```sh
npx -y @cueai/omni-reader-mcp@1.1.2 setup --client hermes --allowed-root /absolute/minimum/root --yes --json
npx -y @cueai/omni-reader-mcp@1.1.2 setup --client cursor --add-root /absolute/minimum/root --yes --json
npx -y @cueai/omni-reader-mcp@1.1.2 setup --client claude-desktop --allowed-root /absolute/minimum/root --yes --json
```

Use `--allowed-root` to replace the explicit additional-root set with one minimum directory. Use `--add-root` to append one minimum directory to roots already configured for that client. Both require an absolute path and cannot be combined.

When a controlling agent is attached to a TTY but must not read stdin, use `--headless --json` with an explicit client. The user-level confirmation must already have happened before an agent uses `--yes` or `--headless`.

## Allowed roots

`OMNI_ALLOWED_ROOTS` contains only explicitly authorized absolute directories. Separate multiple roots with `:` on macOS/Linux and `;` on Windows. Do not authorize a whole home directory or disk by default. The current agent workspace remains the default allowed area.

After changing roots, reload or restart the MCP client so it receives the new environment. A parse request for a file already inside an allowed root needs no second generic confirmation.

## Verify after setup

Run:

```sh
npx -y @cueai/omni-reader-mcp@1.1.2 doctor --json
```

Verify package version, key presence, root safety, endpoint compatibility, cache/artifact mode, and the client reload instruction. Reload or restart the client, then verify these tools are visible: `parse`, `get_parse_status`, `cancel_parse`, `read_result`, and `discard_result`.

`doctor --json` must not reveal the API key, a private source path, or source content.

## Roll back

```sh
npx -y @cueai/omni-reader-mcp@1.1.2 uninstall --yes --json
```

Uninstall removes the trusted Bridge entry and restores a matching trusted URL-only entry when available. It does not delete user source files or silently discard unexpired local results. Recover any existing operation before starting replacement work.
