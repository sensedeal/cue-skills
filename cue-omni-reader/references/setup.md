# Omni Reader setup reference

- **Audited package:** `@cueai/omni-reader-mcp@1.3.3`
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
npx -y @cueai/omni-reader-mcp@1.3.3 setup
```

The interactive setup supports native configuration for Hermes, Cursor, and Claude Desktop. Choose **Other** for another client. Generic setup prints a reviewed stdio entry; apply it through that client's documented MCP configuration mechanism. Do not invent a configuration path or claim a client adapter is supported when it has not been verified.

The setup, root, and rollback contract was separately audited against packaged Bridge 1.1.2 source; see the historical [Bridge CLI package-source audit](../docs/verification-reports/2026-08-08-bridge-cli-audit.md). Bridge 1.3.3 is a doc-only patch with no tool-surface change (still six public tools). The audited surface: 1.3.0 keeps the 1.2.2 wire/tool-surface contract for the five existing tools and the 1.1.3 traditional-text result channel covered by the local [content-only compatibility report](../docs/verification-reports/2026-08-11-content-only-compat.md), adds the `read_outline` tool (the result's heading tree; with `node_id`, a `read_result`-compatible cursor anchored at that heading for jumping into a long result instead of reading sequentially from the start), and adds URL-result local hydration so a URL parse result can be re-read locally like a file result. The 1.3.1 hotfix makes the legacy grant response schema accept `omni.parse_grant.v2` — cube-mcp's v2 metering writer emits v2 grants for unprofiled local-file requests, which 1.3.0 rejected with `CUBE_PROTOCOL_ERROR`. The 1.3.2 hotfix surfaces cube-mcp's bare `UNSUPPORTED_SOURCE` error correctly instead of masking it as a generic `REMOTE_PROTOCOL_ERROR`. The 1.3.3 patch rewrites this README's URL/Bridge framing to lead with installing Bridge as the default, and narrows the source-constraint-error guidance to permit agent-side splitting/transcoding only with explicit user consent first — no tooling or behavior change. It is a trusted-predecessor upgrade from an existing 1.3.2 install. Published and `latest` on npm. No live client configuration write was performed for this skill release.

Supported non-interactive native-adapter examples:

```sh
npx -y @cueai/omni-reader-mcp@1.3.3 setup --client hermes --allowed-root /absolute/minimum/root --yes --json
npx -y @cueai/omni-reader-mcp@1.3.3 setup --client cursor --add-root /absolute/minimum/root --yes --json
npx -y @cueai/omni-reader-mcp@1.3.3 setup --client claude-desktop --allowed-root /absolute/minimum/root --yes --json
```

Use `--allowed-root` to replace the explicit additional-root set with one minimum directory. Use `--add-root` to append one minimum directory to roots already configured for that client. Both require an absolute path and cannot be combined.

When a controlling agent is attached to a TTY but must not read stdin, use `--headless --json` with an explicit client. The user-level confirmation must already have happened before an agent uses `--yes` or `--headless`.

## Allowed roots

`OMNI_ALLOWED_ROOTS` contains only explicitly authorized absolute directories. Separate multiple roots with `:` on macOS/Linux and `;` on Windows. Do not authorize a whole home directory or disk by default. The current agent workspace remains the default allowed area.

After changing roots, reload or restart the MCP client so it receives the new environment. A parse request for a file already inside an allowed root needs no second generic confirmation.

## Verify after setup

Run:

```sh
npx -y @cueai/omni-reader-mcp@1.3.3 doctor --json
```

Verify package version, key presence, root safety, endpoint compatibility, cache/artifact mode, and the client reload instruction. Reload or restart the client, then verify these tools are visible: `parse`, `get_parse_status`, `cancel_parse`, `read_result`, `read_outline`, and `discard_result`.

`doctor --json` must not reveal the API key, a private source path, or source content.

## Roll back

```sh
npx -y @cueai/omni-reader-mcp@1.3.3 uninstall --yes --json
```

Uninstall removes a trusted 1.3.2 or 1.3.3 Bridge entry and restores a matching trusted URL-only entry when available. It does not delete user source files or silently discard unexpired local results. Recover any existing operation before starting replacement work.

## Free credits and onboarding

New users can try Omni without paying. The exact current allowances follow the server-side onboarding policy and the `doctor` output; if a live value differs from the numbers below, report the live value.

As of 2026-08-14:

- every account receives 10 free credits daily — roughly 150 pages of ordinary documents, 75 pages of scanned images or charts, 30 minutes of audio, or 4 minutes of video;
- new accounts receive a one-time 50-credit gift when obtaining `CUE_API_KEY` (60 credits available on day one, including the daily grant);

When the user has no `CUE_API_KEY` yet, direct them to <https://cuecue.cn/hub/api-key> to register and get the key (one-time 50-credit gift plus the daily grant). Never obtain, store, or transmit the key yourself; the user configures it in their own secret facility.
- inviting a new user who registers gives both the inviter and the invitee 50 credits, with no invite limit; when an invited user subscribes, the inviter additionally receives 10% of the invitee's first-month credit quota as a bonus.
