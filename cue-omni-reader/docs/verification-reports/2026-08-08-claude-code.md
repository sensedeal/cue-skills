# Claude Code simulated verification — 2026-08-08

- **Skill:** cue-omni-reader v0.1.0
- **Bridge referenced:** 1.1.2
- **Client:** Claude Code v2.1.223
- **Mode:** simulated; no Omni tools; no production parse or Omni credits

Fresh instruction-text contexts first loaded the exact public `SKILL.md` as the system prompt for R1, R3, R5, R7, and R9.

A separate native-loading run copied the exact official package into an ephemeral project's `.claude/skills/cue-omni-reader/` directory. Claude Code loaded only project settings, used a strict empty MCP configuration, exposed only the native `Skill` tool, ran in plan mode without session persistence, and received an explicit instruction to activate any relevant discovered skill. Stream-JSON telemetry recorded one native `Skill` tool call with `skill=cue-omni-reader`. The final response stated that no parse or summary had occurred and prescribed only the official parse, same-operation polling, complete artifact reading, and post-task discard sequence.

| Area | Outcome |
|---|---|
| Missing Bridge | Requested install consent, minimum directory authorization, doctor/reload, and direct-source parsing. |
| Long-media schema adaptation | Used `wait: false` only for a schema that exposes `wait`; used source-only parse otherwise. |
| Operation recovery | Queried the saved operation without resubmitting. |
| Cleanup pending | Kept usable content separate from unconfirmed cleanup. |
| Cancellation | Used `cancel_parse` and avoided billing or deletion promises. |
| Native activation | Native project discovery selected `cue-omni-reader` through one successful `Skill` call before producing the simulated workflow. |

All five behavior checks and the separate native-activation check passed. No production parse occurred and no Omni credits were consumed. Persistent installation, unprompted automatic triggering, live URL/local-file parsing, artifact handling, billing, cancellation, and cleanup remain unverified.
