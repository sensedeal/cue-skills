---
name: cue-section-registration
description: >-
  Use when the user (or host Agent) needs a Cue private-fund manager DD
  「登记与合规」section written into their own draft workspace—create a
  minimal manuscript shell on first section, or merge into an existing shell.
  Not for full DD books, sanctions sections, or evidence dumps.
license: MIT
metadata:
  version: "0.1.0"
  requires:
    bins: ["python3"]
  envOptional: ["CUE_API_KEY"]
  dependsConceptually: ["cue-data-mcp"]
---

# Cue section · 管理人尽调 · 登记与合规

Locked closed loop: **AMAC → 登记与合规 section payload → create/merge minimal 管理人尽调 draft shell.**

## Triggers

- 管理人尽调登记合规 / 写入登记与合规节 / cue section 登记
- first section creates draft shell

## What this skill does / does not

| Does | Does not |
|------|----------|
| Emit ≤3 judgments + boundaries + takeaway for **登记与合规** only | Write a full diligence book |
| Create minimal `管理人尽调-{name}.md` shell if missing | Expand templates / lock verticals |
| Replace only `## 登记与合规` when file exists | Sanctions / 处罚 / 产品清单 sections |
| Write sidecar `.json` next to the md | Affirmative forbidden phrases (见禁句) |

## Recipe (host Agent)

1. **Resolve subject keyword** from the user (e.g. `重阳投资`). If missing, ask once; do not invent a subject.
2. **Prefer the helper script** when `python3` + network are available:
   ```bash
   python3 scripts/emit_and_merge.py --keyword '重阳投资' [--workspace PATH] [--dry-run]
   ```
   - Reads `CUE_API_KEY` from env or `~/.cue/config.json` (**never print the key**).
   - Calls AMAC manager lookup via Cue regulatory MCP (discover live tool name with `tools/list`; do not hardcode forever).
   - Requires **exactly 1** manager hit; otherwise exits with disambiguation (0 or N>1 → refuse judgments).
   - Emits ≤3 judgments per `references/TEMPLATE-登记合规.md`, plus boundaries, takeaway, forbidden list.
   - Affirmative ban-check: phrase hits inside `不得` / `禁止` / `不得据此` windows are OK.
   - Workspace default: `~/work/cue-agent-workspace/drafts/` (override via `--workspace`).
   - If `管理人尽调-{safe_name}.md` missing → **CREATE** minimal shell with only 登记与合规 filled + empty later slots.
   - If file **EXISTS** → **REPLACE** only the `## 登记与合规` section (until next `## `); keep the rest; write/update sidecar `.json`.
3. **Else (no script / no network):** use the `cue-data-mcp` skill to discover live regulatory routing, call the AMAC manager tool, then write files with the **same** create/merge rules.
4. **Obey** `references/CONTRACT-CORE.md` + `references/TEMPLATE-登记合规.md` (+ `references/DRAFT-SLICE.md`).
5. **Never** write a full diligence book — only this section (+ minimal shell if first).
6. **Never** output forbidden affirmative phrases (准入通过 / 尽调通过 / 无风险 / 合规良好 / 登记合规通过 / …). Negated forms inside 不得/禁止 windows are allowed.
7. **Report back:** md path; created vs merged; the ≤3 judgments; boundaries.

## Forbidden affirmatives (hard stop)

Do not deliver if the section contains any of these **outside** a 不得/禁止/不得据此 window:

合规良好 · 合规情况良好 · 暂无明显合规问题 · 建议通过 · 可作为尽调通过的依据 · 无风险 · 无处罚 · 已合规 · 准入通过 · 尽调通过 · 登记合规通过

## Success shape

```
action: created|merged
md: ~/work/cue-agent-workspace/drafts/管理人尽调-….md
sidecar: …json
subject: 全称 | 登记编号 | 类型
judgments: (≤3)
boundaries: …
```
