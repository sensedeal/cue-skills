# cue-research

**Sibling to [`cue-buddy`](../cue-buddy).** Where cue-buddy is for **authoring** Cue templates, cue-research is for **using** them from inside your AI agent.

Conversational loop: ask a question → skill matches ≤2 candidate buddies from your library (or offers free-form deep research) → you confirm → it runs → on satisfaction, you can distill a free-form run into a saved buddy that hands off to cue-buddy.

A single deep-research run **typically takes 3–15 minutes** (longer for complex subjects), with a **60-minute server-side hard timeout** — set client/agent waits accordingly and don't treat a long-running task as failed.

## Requires cue-buddy alongside

cue-research ships **one thin runtime script** — `scripts/research_run.py` (fire a run → retrieve report → save to file), which *composes* `cue_api` / `sse_report` from the sibling [`../cue-buddy/scripts`](../cue-buddy/scripts) (via a `sys.path` bootstrap; see `SKILL.md`) rather than duplicating them. Install **both skills as sibling folders** under the same parent (e.g. both in `~/.claude/skills/`). Installing cue-research alone will fail at import. (The shared primitives are intentionally *not* copied here, to avoid version drift from cue-buddy.)

`research_run.py` runs in the **background** (SKILL.md launches it with `run_in_background`) and treats **replay as the primary report-retrieval path** — long live SSE streams routinely drop the reporter segment, so it extracts from the live stream and falls back to replay (same parser, reads the full record from the backend DB). Patterns borrowed from the `cuecue-deep-research` sibling skill (async + file output).

**仿写 / mimic** (free-form only): `--mimic-url <URL>` or `--mimic-file <path>` makes a free-form report imitate the **writing style/structure** of a reference page or sample document (the file is uploaded to get a `file_hash`; the backend parses it to text). One-shot by design (`need_confirm=False`) so it doesn't break background execution; mimic copies style, not conclusions. Mutually exclusive with a buddy `--template-id`.

Status: v0.3.5 — see `SKILL.md`.

> **v0.3.4 path consolidation:** runtime files (reports / logs / runs) now land under a single resolved root `<root>` = `python3 ../cue-buddy/scripts/cue_api.py root` (default `~/.cue`; falls back to agent cwd or temp if home isn't writable - portable, no `/tmp/` dependency on Windows). Reports moved from `~/cue-reports/` to `<root>/reports/` - **old reports in `~/cue-reports/` are not moved**; new runs go to the new default. The progress log moved from a shell `> ./cue-run.log` redirect to the runner's own `--log` (tee), so launch and completion-tail Bash calls share one resolver-chosen path instead of a hardcoded one. Set `CUE_HOME` to relocate everything.

## License

[MIT](../LICENSE)
