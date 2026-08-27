# cue-omni-reader

**[English](README.md) · [中文](README.zh-CN.md)**

> An AI-agent skill that parses an HTTP(S) URL or an authorized local document, audio, or video source through the official [Cue Omni Reader](https://cuecue.cn) MCP surface — a thin instruction layer, never a custom parser or protocol driver.

> **Sibling skills:** [`cue-buddy`](../cue-buddy) (author research buddies) · [`cue-research`](../cue-research) (run research in your agent). This skill handles *document/URL parsing*; the others handle *research*.

## What this skill is

`cue-omni-reader` plugs into any AI agent (Claude Code, Codex CLI, Gemini CLI, WorkBuddy, etc.) and tells it how to use the official Omni MCP tools to turn a source into content: a URL, or a local file the user has authorized. The MCP package and its active tool schemas are authoritative; the skill only instructs the agent how to drive them — recoverable operations, artifact reading, cleanup, truthful billing/error handling.

**One provider, both sources.** Omni is one logical provider: `parse(source)` covers an HTTP(S) URL *or* an authorized local path. The **Bridge** (`@cueai/omni-reader-mcp`) is that same provider installed locally — never a second connector. Install the Bridge as the default; a remote-only connection covers URLs with no local install, but cannot read local files.

## Public tools (seven)

- `parse` — URL or authorized local source → Markdown content (recoverable operation after the foreground budget)
- `get_parse_status` / `cancel_parse` — poll and cancel an in-flight operation
- `read_result` / `read_outline` / `discard_result` / `save_result` — **Bridge-local** artifact tools (never exposed on the remote surface)

## Install the audited Bridge version

Node.js 20.12+ is required. Never use an implicit `latest`:

```sh
npx -y @cueai/omni-reader-mcp@1.5.5 setup
```

Interactive setup supports Hermes, Cursor, and Claude Desktop natively; choose **Other** for any other client. Then verify:

```sh
npx -y @cueai/omni-reader-mcp@1.5.5 doctor --json
```

`doctor` checks package version, key presence, root safety, cache/artifact mode, and the client reload instruction; it reports only authenticated Cube control/configuration facts. The granted data plane is not probed; only a real local-file parse validates the route end-to-end. It does not reveal the API key or private paths. Roll back with `npx -y @cueai/omni-reader-mcp@1.5.5 uninstall --yes --json` (restores a trusted URL-only entry when available).

Full setup rules (consent, allowed roots, non-interactive examples, rollback): [`references/setup.md`](references/setup.md).

## Windows

The current setup generates a working Windows entry automatically (spawn goes through `cmd /d /c npx`, which resolves the `npx.cmd` ENOENT that produced WorkBuddy's `MCP error -32000: Connection closed`). Three runnable config shapes:

1. **Generated setup entry** (default, recommended) — platform-correct spawn with trust validation
2. **`npx` shell form** — `npx -y @cueai/omni-reader-mcp@1.5.5` from a shell that resolves `.cmd`
3. **`node` + absolute path** — `node "<absolute-path-to>/dist/index.js"`; most robust when npx itself is unavailable

**Use a stable path**, never a session-timestamped cache directory — a changing path breaks the MCP client's saved config after each cache sweep.

## Network diagnostics

Run `npx -y @cueai/omni-reader-mcp@1.5.5 doctor --json` first, then diagnose by structured error code and keep the control-plane and upload stages separate:

- `CUBE_UNAVAILABLE` is a control-plane failure before any file upload. Do not diagnose it through upload-stage endpoint probes.
- A failure after grant creation means the secure upload stage did not complete.
- `CUBE_PROTOCOL_ERROR` is a response-contract mismatch, not a generic DNS diagnosis.

Use only authenticated Cube control/configuration facts `doctor` reports. The granted data plane is not probed; only a real local-file parse validates the route end-to-end. Do not guess a hostname or port, and do not expose an internal upload endpoint as routine user troubleshooting. Further client/service evidence: [`references/compatibility.md`](references/compatibility.md).

## Free credits

New users get a one-time 50-credit gift plus 10 free credits daily (≈150 pages of ordinary documents, ≈150 scanned pages, 30 min of audio, or 4 min of video per day). Get a key at <https://cuecue.cn/hub/api-key>. Exact current allowances follow the server-side policy — report the live `doctor` value if it differs. Details: [`references/setup.md`](references/setup.md).

## Repo layout

```
cue-omni-reader/
├── SKILL.md                # Skill spec read by the calling agent (loading contract)
├── SKILL.zh-CN.md          # Complete Chinese translation of SKILL.md
├── README.md               # This file
├── README.zh-CN.md         # Chinese version of this file
├── references/
│   ├── setup.md            # Audited install / allowed-roots / rollback contract
│   └── compatibility.md    # Wire/tool-surface compatibility evidence
├── docs/verification-reports/
│   └── ...                 # Bridge releases, client runs, audits
└── scripts/
    ├── sync_bridge_pin.py         # One-command pin sync per Bridge release
    └── test_skill_regression.py   # 30 skill regression tests
```

## Dependencies

- Node.js 20.12+ (the Bridge runtime); the skill itself is instruction-only — no Python, no extra packages

## License

[MIT](../LICENSE)
