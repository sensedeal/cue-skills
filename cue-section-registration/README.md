# cue-section-registration

Cue skill: emit a **管理人尽调 · 登记与合规** draft section from live AMAC data, then create or merge a minimal manuscript shell in the **user Agent workspace**.

## Install

```sh
npx skills add sensedeal/cue-skills --skill cue-section-registration
```

Requires `CUE_API_KEY` (same wallet as `cue-data-mcp`). Never paste the key into chat.

## Quick run

```sh
python3 scripts/emit_and_merge.py --keyword '重阳投资'
```

## Not in scope

Full DD books, sanctions sections, expanding the template library, or product-site first-glance UI.
