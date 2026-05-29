# cue-research

**Sibling to [`cue-buddy`](../cue-buddy).** Where cue-buddy is for **authoring** Cue templates, cue-research is for **using** them from inside your AI agent.

Conversational loop: ask a question → skill matches ≤2 candidate buddies from your library (or offers free-form deep research) → you confirm → it runs → on satisfaction, you can distill a free-form run into a saved buddy that hands off to cue-buddy.

A single deep-research run **typically takes 3–15 minutes** (longer for complex subjects), with a **60-minute server-side hard timeout** — set client/agent waits accordingly and don't treat a long-running task as failed.

## Requires cue-buddy alongside

cue-research ships **no runtime scripts of its own** — it imports `cue_api` / `sse_report` from the sibling [`../cue-buddy/scripts`](../cue-buddy/scripts) (via a `sys.path` bootstrap; see `SKILL.md`). Install **both skills as sibling folders** under the same parent (e.g. both in `~/.claude/skills/`). Installing cue-research alone will fail at import. (Scripts are intentionally *not* copied here, to avoid version drift from cue-buddy.)

Status: v0.2.0 — see `SKILL.md`.

## License

[MIT](../LICENSE)
