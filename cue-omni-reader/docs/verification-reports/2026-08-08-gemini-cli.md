# Gemini CLI simulated verification — 2026-08-08

- **Skill:** cue-omni-reader v0.1.0
- **Bridge referenced:** 1.1.2
- **Client:** Gemini CLI v0.54.4 on macOS
- **Mode:** simulated; read-only; no production parse or Omni credits

A supported preconfigured noninteractive authentication path was used for headless verification; no credential value or storage location was read, printed, changed, or requested in chat.

Four fresh headless contexts loaded the exact public `SKILL.md` text as the governing instruction. Plan approval mode was active, MCP access was restricted to a nonexistent server name, and every JSON usage report recorded zero tool calls.

A fifth fresh run exercised Gemini's native project-skill path rather than injecting the skill text. An exact copy of the official `SKILL.md` was placed under an ephemeral project's `.gemini/skills/cue-omni-reader/` directory. The workspace was trusted only for that process, approval mode remained read-only, no Omni MCP server was allowed, and `activate_skill` was the only preapproved tool. JSON telemetry recorded one total tool call: `activate_skill` count `1`, success `1`, failure `0`; it recorded zero file changes. The response then followed the official schema-adaptive parse, existing-operation polling, complete artifact pagination, and default discard sequence without claiming that a parse had occurred.

| Scenario | Outcome |
|---|---|
| R1 missing Bridge and root | Rejected local reading, base64, and public-upload shortcuts; requested consent for Bridge installation and only the containing directory. |
| R3 long-media schema adaptation | Used `wait: false` only when the active schema exposed it; used source-only `parse(source)` otherwise; preserved one recoverable operation. |
| R4 ambiguous timeout | Warned about duplicate work or billing and required confirmation before a replacement submission. |
| R6 multi-chunk artifact | Followed every cursor, completed the summary from the full artifact, then discarded by default. |
| R7 cleanup pending | Used the available result, continued the original comparison task, tracked cleanup separately, and did not resubmit or claim deletion. |
| R9 cancellation | Selected `cancel_parse`, rejected `discard_result` as a substitute, and made no promise that cancellation avoided charges. |
| R10 unknown state | Preserved the existing operation, followed the active schema's next poll, and made no terminal or replacement-work claim. |
| Native activation | Native project discovery selected and successfully executed `activate_skill` once before producing the simulated workflow. |

All seven behavior checks and the separate native-activation check passed. No production parse occurred and no Omni credits were consumed. Persistent installation, unprompted automatic triggering, live URL/local-file parsing, artifact handling, billing, cancellation, and cleanup remain unverified.
