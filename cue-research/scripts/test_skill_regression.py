#!/usr/bin/env python3
"""cue-research skill regression — stdlib unittest.

Checks the skill's structural contract:
  - SKILL.md frontmatter shape (CI also enforces this globally).
  - SKILL.md declares every verb its decision-tree references.
  - Shared cue-buddy scripts (cue_api, sse_report) are importable from
    cue-research/scripts/ via the documented sys.path pattern.
  - The functions cue-research depends on actually exist in cue_api +
    sse_report (catches accidental rename/drift).
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_DIR = _HERE.parent
_REPO_ROOT = _SKILL_DIR.parent
_BUDDY_SCRIPTS = _REPO_ROOT / "cue-buddy" / "scripts"

# This sys.path pattern is the one SKILL.md tells the agent/scripts to use.
sys.path.insert(0, str(_BUDDY_SCRIPTS))


class TestSkillMd(unittest.TestCase):
    def setUp(self):
        self.md = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    def test_frontmatter_has_required_keys(self):
        m = re.match(r"^---\n(.*?)\n---\n", self.md, re.S)
        self.assertIsNotNone(m, "missing frontmatter")
        fm = m.group(1)
        for required in ("name:", "description:"):
            self.assertIn(required, fm)

    def test_every_declared_verb_appears_in_decision_tree(self):
        # Verbs declared in the verb table (e.g. backtick `+ask` etc.)
        verbs = set(re.findall(r"`\+([a-z]+)`", self.md))
        self.assertIn("ask", verbs)
        self.assertIn("match", verbs)
        self.assertIn("rewrite", verbs)
        self.assertIn("save", verbs)
        self.assertIn("upgrade", verbs)  # skill self-upgrade (not +update)

    def test_freeform_path_mentions_rewrite_endpoint(self):
        # Codex Block C fix: free-form path must call /api/rewrite first
        # AND disable backend need_analysis. SKILL.md still owns the rewrite
        # rule; the need_analysis=False enforcement moved into research_run.py
        # (the runner builds the payload now — agent no longer hand-writes it),
        # so the invariant is asserted there.
        self.assertIn("/api/rewrite", self.md)
        runner = (_HERE / "research_run.py").read_text(encoding="utf-8")
        self.assertRegex(
            runner,
            r'["\']?need_analysis["\']?\s*[=:]\s*["\']?\s*[Ff]alse\b',
            "research_run.py must set need_analysis False in the payload",
        )

    def test_never_autoselects_buddy_hard_rule(self):
        # Codex Block B fix: matching is low-confidence, never auto-pick.
        self.assertRegex(self.md, r"不自动选搭子|never auto-?select")

    def test_stage6_save_prompt_does_not_leak_internal_verbs_to_user(self):
        """Codex onboarding review F: Stage 6 prompt previously read
        `1. 沉淀(handoff 给 cue-buddy 的 +author / +validate / 人工确认 +create)`,
        which leaks internal verb names to the user — directly contradicting
        the elsewhere-stated rule that user-facing prose must not mention
        +author / +validate / +create. Test the literal blockquote line
        shown to the user under Stage 6 doesn't contain those verbs."""
        import re as _re
        # Find the Stage 6 question blockquote (lines after '## Stage 6'
        # heading that start with '>' and form the user-facing prompt).
        stage6_match = _re.search(
            r"###?\s*Stage 6:.*?(?=###?\s*Stage|\Z)", self.md, _re.S
        )
        self.assertIsNotNone(stage6_match, "Stage 6 section not found")
        stage6_text = stage6_match.group(0)
        # User-facing lines are inside `> ...` blockquotes; collect them.
        user_facing = _re.findall(r"^>.*$", stage6_text, _re.M)
        joined = "\n".join(user_facing)
        for forbidden in ("+author", "+validate", "+create"):
            self.assertNotIn(
                forbidden, joined,
                f"Stage 6 user-facing prompt must not leak `{forbidden}` "
                f"(internal verb); use natural language like '存' / '做成搭子'.",
            )

    def test_weak_match_nudge_uses_user_facing_phrasing(self):
        """When all candidates are weak matches, surface a one-liner that
        nudges toward building a new buddy. The user-facing text MUST use
        natural Chinese ('做个新搭子') — leaking the internal verb name
        `+author` directly to the user would be jargon.

        Empirical basis: across 7 real queries against the live catalog of
        106 templates, weak/zero-match cases were common enough (e.g. 毛利
        / 业绩超预期) that surfacing this escape hatch matters."""
        self.assertIn("要不做个新搭子", self.md)
        self.assertRegex(self.md, r"弱匹配|匹配.*?不强")
        # User-facing nudge prose must NOT leak the internal verb name.
        # Check inside the literal blockquote line only — agent-routing
        # guidance further down may legitimately mention +author internally.
        nudge_lines = re.findall(r"> 匹配都不强.*$", self.md, re.M)
        for line in nudge_lines:
            self.assertNotIn(
                "+author", line,
                "user-facing weak-match prose must not leak +author verb",
            )

    def test_no_delete_verb_in_verb_table(self):
        # Hard rule 5: skill must not DECLARE +delete in the verb table.
        # Scoped to verb-table row form `| `+delete`` so the hard-rule prose
        # ("**不实现 `+delete`**") explaining WHY we don't have it is allowed.
        self.assertNotRegex(
            self.md, r"\|\s*`\+delete`",
            "SKILL.md verb table must not declare +delete — deletion is web-only",
        )

    def test_credit_confirmation_hard_rule_present(self):
        # Hard rule 2: every real run must explicitly confirm credits.
        self.assertRegex(
            self.md, r"确认\s*credits|confirm credits",
            "SKILL.md hard rules must mention credit confirmation",
        )

    def test_stage2_uses_full_list_semantic_picking(self):
        """Stage 2 must use single-stage full-list + agent semantic picking,
        NOT the old keyword-search-variants approach. Empirically verified
        across 6 real queries against the live 106-template catalog:
        full-list picking won 4/6 vs backend keyword search; 1 tie; 1
        honest weak-match fallback (instead of the old confident-but-wrong
        keyword approach which mapped 「比亚迪 vs 长城混动竞争」 to 「对公竞品
        情报速递」 — banking, not auto).
        """
        import re as _re
        stage2 = _re.search(r"###?\s*Stage 2:.*?(?=###?\s*Stage|\Z)", self.md, _re.S)
        self.assertIsNotNone(stage2, "Stage 2 section not found")
        s2 = stage2.group(0)
        # Must instruct fetching the full pool (keyword=" " + include_system=True).
        self.assertRegex(
            s2, r'keyword\s*=\s*[\'"]\s+[\'"].*include_system\s*=\s*True|拉(?:取)?(?:所有|全集|完整)',
            "Stage 2 must instruct fetching the full visible pool",
        )
        # Must use secondary_category as the grouping axis (it has cleaner
        # use-case-oriented clusters than primary_category — verified
        # empirically: 34 cats vs 46, top 12 cover ~80% of templates).
        self.assertIn("secondary_category", s2)
        # Must distinguish entity vs intent.
        self.assertRegex(s2, r"主体.*意图|实体.*意图")
        # Must NOT advise the OLD keyword-variant search strategy.
        self.assertNotRegex(
            s2, r"2-3 个 keyword 变体.*分别搜|keyword 变体.*合并去重",
            "Stage 2 should no longer use keyword-search variants — switched to full-list",
        )

    def test_hard_rule_entity_goes_to_task_input_only(self):
        """Hard Rule 6 (mechanism-agnostic): entity names ONLY go into
        task_input — never enter template matching, regardless of which
        matching mechanism is in use (today: full-list + semantic picking;
        future: maybe two-stage with secondary-cat as Stage A). Earlier
        we drafted a narrower version of this rule tied to keyword-search
        strip; the reframed version generalizes."""
        import re as _re
        hr = _re.search(r"##\s*Hard rules.*?(?=^##\s|\Z)", self.md, _re.S | _re.M)
        self.assertIsNotNone(hr)
        hr_text = hr.group(0)
        self.assertRegex(
            hr_text,
            r"主体名.*task_input|task_input.*主体|绝不进模板匹配",
            "Hard Rule 6 must codify entity→task_input only (mechanism-agnostic)",
        )

    def test_no_client_side_rewrite_reimpl_rule_present(self):
        # Hard rule 4: don't reimplement backend rewrite logic in the agent.
        # Look for either a Chinese phrasing or an English one.
        self.assertRegex(
            self.md,
            r"不在 agent 侧重写|不重写深研逻辑|don'?t (?:re-?implement|reimplement) (?:the )?rewrite",
            "SKILL.md must forbid client-side rewrite reimplementation",
        )


class TestSharedScriptImports(unittest.TestCase):
    def test_cue_api_search_templates_exists(self):
        import cue_api
        self.assertTrue(hasattr(cue_api, "search_templates"),
                        "cue_api.search_templates missing — Task 2 not applied?")
        self.assertTrue(callable(cue_api.search_templates))

    def test_cue_api_rewrite_exists(self):
        import cue_api
        self.assertTrue(hasattr(cue_api, "rewrite"),
                        "cue_api.rewrite missing — Task 3 not applied?")
        self.assertTrue(callable(cue_api.rewrite))

    def test_cue_api_chat_stream_and_replay_exist(self):
        import cue_api
        for fn in ("chat_stream", "replay", "create_template", "generate_template"):
            self.assertTrue(hasattr(cue_api, fn), f"cue_api.{fn} missing")

    def test_cue_api_has_upload_helper_for_mimic(self):
        # Sample-document mimic needs a file -> file_hash upload helper.
        import cue_api
        for fn in ("upload_file", "get_accept_type"):
            self.assertTrue(hasattr(cue_api, fn), f"cue_api.{fn} missing")
            self.assertTrue(callable(getattr(cue_api, fn)))

    def test_sse_report_helpers_exist(self):
        import sse_report
        for fn in ("extract_reporter_content", "diagnose_empty_report",
                   "extract_tool_calls", "extract_agent_timeline"):
            self.assertTrue(hasattr(sse_report, fn),
                            f"sse_report.{fn} missing — Task 1 not applied?")

    def test_skill_md_python_imports_resolve(self):
        """Every name SKILL.md tells the agent to import from the shared
        modules must actually exist there. Catches the class of bug where a
        code/prose snippet references a non-importable name — e.g. the old
        Stage 4a wording read like `stream_cut_before_reporter` was a function
        to import, when it is only a `kind` string returned by
        diagnose_empty_report. A doc that hands the agent a phantom import
        makes the agent's first attempt fail, exactly as observed in the
        field. We only resolve imports from the local shared modules
        (cue_api / sse_report); stdlib imports (uuid/json/...) are skipped."""
        import importlib

        md = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        local_modules = {"cue_api", "sse_report"}
        checked = 0
        for block in re.findall(r"```python\n(.*?)```", md, re.S):
            for line in block.splitlines():
                m = re.match(r"\s*from\s+(\w+)\s+import\s+(.+)$", line)
                if not m:
                    continue
                module, names_part = m.group(1), m.group(2)
                if module not in local_modules:
                    continue  # stdlib / third-party — not our contract
                mod = importlib.import_module(module)
                # strip trailing inline comment, then split the import list
                names_part = names_part.split("#", 1)[0]
                for raw in names_part.split(","):
                    name = raw.strip().split(" as ")[0].strip()
                    if not name:
                        continue
                    self.assertTrue(
                        hasattr(mod, name),
                        f"SKILL.md code block imports `{name}` from "
                        f"`{module}`, but it does not exist there — phantom "
                        f"import will break the agent's first run.",
                    )
                    checked += 1
        self.assertGreater(
            checked, 0,
            "expected SKILL.md to contain at least one resolvable "
            "`from cue_api/sse_report import ...` to validate",
        )


class TestResearchRunner(unittest.TestCase):
    """research_run.py is the one runtime script — a thin composer over the
    shared cue-buddy primitives. SKILL.md routes Stage 4 through it (background
    + replay-as-primary + file output) instead of hand-writing the stream loop
    in prose, which was the original phantom-import / empty-report root cause."""

    def test_runner_exists_and_parses(self):
        import ast
        runner = _HERE / "research_run.py"
        self.assertTrue(runner.exists(), "scripts/research_run.py missing")
        ast.parse(runner.read_text(encoding="utf-8"))  # raises on syntax error

    def test_runner_imports_shared_primitives_not_duplicates(self):
        """Must IMPORT from cue_api/sse_report (compose), never define its own
        chat_stream/replay/extract (which would drift from cue-buddy)."""
        src = (_HERE / "research_run.py").read_text(encoding="utf-8")
        self.assertRegex(src, r"from cue_api import")
        self.assertRegex(src, r"from sse_report import")
        for dup in ("def chat_stream", "def replay(", "def extract_reporter_content"):
            self.assertNotIn(
                dup, src,
                f"research_run.py must not redefine `{dup}` — import it, don't copy",
            )

    def test_runner_exposes_expected_cli_flags(self):
        src = (_HERE / "research_run.py").read_text(encoding="utf-8")
        for flag in ("--query", "--template-id", "--conversation-id",
                     "--output", "--timeout"):
            self.assertIn(flag, src, f"research_run.py must expose {flag}")

    def test_skill_md_routes_stage4_through_runner(self):
        md = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("research_run.py", md,
                      "SKILL.md must route Stage 4 through research_run.py")
        # background execution + file output are the borrowed patterns
        self.assertRegex(md, r"run_in_background", )
        self.assertRegex(md, r"--output|cue-reports")

    def test_runner_exposes_mimic_flags(self):
        """Phase 1 + sample-document mimic: URL and local-file mimic flags,
        one-shot (need_confirm=False), free-form only."""
        src = (_HERE / "research_run.py").read_text(encoding="utf-8")
        self.assertIn("--mimic-url", src)
        self.assertIn("--mimic-file", src)
        # builds the backend mimic payload shape ({url} or {file_hash})
        self.assertRegex(src, r'["\']url["\']\s*:')
        self.assertRegex(src, r'["\']file_hash["\']\s*:')

    def test_runner_mimic_is_freeform_only(self):
        """mimic must be refused alongside --template-id (backend lets
        template_id silently override mimic, so refuse rather than no-op)."""
        src = (_HERE / "research_run.py").read_text(encoding="utf-8")
        self.assertRegex(
            src, r"mimic.*template_id|template_id.*mimic",
            "runner must guard mimic-vs-template_id mutual exclusivity",
        )

    def test_skill_md_documents_mimic_option(self):
        md = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(md, r"仿写|mimic")
        self.assertIn("--mimic-url", md)
        self.assertIn("--mimic-file", md)


class TestNormalizeTemplateId(unittest.TestCase):
    """A bare `<id>` (prefix dropped while copying from chat/notes) must still
    resolve — both a human user and an agent hit the backend 404
    "模板不存在" this way. normalize_template_id prepends, never strips."""

    def _fn(self):
        import research_run

        return research_run.normalize_template_id

    def test_bare_suffix_gets_prefixed(self):
        self.assertEqual(self._fn()("8qNgr5"), "template_8qNgr5")

    def test_already_prefixed_is_untouched(self):
        self.assertEqual(self._fn()("template_8qNgr5"), "template_8qNgr5")

    def test_none_passes_through(self):
        self.assertIsNone(self._fn()(None))


class TestReplayableEmptyKinds(unittest.TestCase):
    """A live stream that ends without reporter text may still have a report
    persisted server-side; replay (no credit cost) should be attempted for
    BOTH cut-before-reporter and reporter-started-no-text — not only the
    former. no_agent_events (auth/template failure) has nothing to recover."""

    def _kinds(self):
        import research_run

        return research_run.REPLAYABLE_EMPTY_KINDS

    def test_reporter_started_no_text_is_replayable(self):
        self.assertIn("reporter_started_no_text", self._kinds())

    def test_stream_cut_before_reporter_is_replayable(self):
        self.assertIn("stream_cut_before_reporter", self._kinds())

    def test_no_agent_events_is_not_replayable(self):
        self.assertNotIn("no_agent_events", self._kinds())

    def test_run_routes_replay_off_the_kind_set(self):
        # Guard against regressing to a hard-coded single-kind check.
        src = (_HERE / "research_run.py").read_text(encoding="utf-8")
        self.assertIn("diag[\"kind\"] in REPLAYABLE_EMPTY_KINDS", src)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
