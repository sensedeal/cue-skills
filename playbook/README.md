# Cue Playbook Scene Skills

**[English](README.md) · [中文](README.zh-CN.md)**

Each subdirectory here is an **agent skill for one playbook scene** (`<slug>/SKILL.md`). Loaded into an external coding agent (Claude Code / third-party), it runs that scene's deep research with Cue and returns a source-cited report.

## Two ways to publish / use

1. **Bundled**: install the whole `cue-skills` repo (with `cue-research` + `cue-buddy`); the scene skill's runner is already in place, use directly.
2. **Standalone (third-party skill market)**: ship a single `<slug>/SKILL.md`. It **self-bootstraps** — on load, if no runner is detected locally, it follows the in-body instructions and `git clone`s this open repo (the full cue-research + cue-buddy set) to `~/.cue/cue-skills`; when GitHub is unreachable it falls back to the **Gitee mirror** `https://gitee.com/sensedeal/cue-skills`, idempotently (`git pull` if already present). So a single file runs end-to-end by itself.

## How to use

1. Load a `<slug>/SKILL.md` into your agent.
2. Follow the skill's instructions: **prepare the runner** (skip if bundled; otherwise self-bootstrap-clone per the "准备 Cue runner" section) → pull the scene's **current** buddies live from `https://cuecue.cn/api/playbook` → pick one → run via `research_run.py --template-id <id>` → retrieve the report via replay.
3. Prerequisites: `git` + `python3`; a Cue account API key (after `cue` CLI login at `~/.cue/config.json`); deep research **consumes credits**. New accounts get free credits (50 on signup + 10 daily) — try it for free first.

## Design points

- **Query live at runtime**: the skill bakes no `template_id`; it fetches the current buddies from `/api/playbook` at runtime → buddy add/edit/remove **reflects automatically**, no regeneration.
- **Auto-generated**: by `scripts/gen_scene_skills.py` from `/api/playbook` + `GET /api/playbook/scenes/<scene>/skill`. When the **scene set changes** (scenes added/removed), re-run the generator (`python3 scripts/gen_scene_skills.py --apply`); buddy changes need no re-run.
- The single generation source lives in the Cue backend service; this directory is its snapshot.
