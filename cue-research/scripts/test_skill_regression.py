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

import inspect
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_version_matches_root_readme(self):
        """cue-research SKILL.md version must match the version advertised in
        the root README.md Skills table — these have drifted before (SKILL.md
        stuck at 0.3.0 while README reached 0.3.2)."""
        m = re.search(r'^\s*version:\s*"([^"]+)"', self.md, re.M)
        self.assertIsNotNone(m, "SKILL.md missing frontmatter version")
        skill_ver = m.group(1)
        readme_path = _REPO_ROOT / "README.md"
        if not readme_path.exists():
            self.skipTest("root README.md absent (standalone sibling-skills layout)")
        readme = readme_path.read_text(encoding="utf-8")
        row = re.search(r'cue-research.*?\| v(\d+\.\d+\.\d+) \|', readme)
        self.assertIsNotNone(row, "root README.md missing cue-research version row")
        self.assertEqual(
            skill_ver, row.group(1),
            f"version drift: SKILL.md={skill_ver} vs README.md=v{row.group(1)}",
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

    def test_cue_api_has_material_upload_helper(self):
        # 文档接地(素材) needs a file -> file_id SSE upload helper, distinct
        # from upload_file (mimic file_hash). Posts to /file/upload_stream.
        import cue_api
        self.assertTrue(hasattr(cue_api, "upload_material"),
                        "cue_api.upload_material missing — 素材接地 not applied?")
        self.assertTrue(callable(cue_api.upload_material))
        src = inspect.getsource(cue_api.upload_material)
        self.assertIn("/file/upload_stream", src,
                      "upload_material must POST to /file/upload_stream")
        # must block until the terminal completed event, not the early file_id
        self.assertIn("completed", src)
        # form field is plural `files` (route takes List[UploadFile])
        self.assertRegex(src, r'name="files"')

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


class TestUploadMaterialSSE(unittest.TestCase):
    """Hermetic coverage of upload_material's SSE parsing — the riskiest new
    logic. No network: a fake byte-line iterable stands in for the response."""

    class _FakeResp:
        def __init__(self, lines):
            self._lines = lines
            self.closed = False

        def __iter__(self):
            return iter(self._lines)

        def close(self):
            self.closed = True

    def _call(self, frames):
        import cue_api
        self._last_resp = None

        def fake_urlopen(req, timeout=None):
            self._last_resp = self._FakeResp(frames)
            return self._last_resp

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
            tf.write(b"hi")
            tpath = tf.name
        try:
            with mock.patch.object(cue_api, "load_config",
                                   lambda: ("sk", "https://x/api")), \
                 mock.patch.object(cue_api, "get_accept_type", lambda: []), \
                 mock.patch("cue_api.urllib.request.urlopen", fake_urlopen):
                return cue_api.upload_material(tpath)
        finally:
            os.unlink(tpath)

    def test_binds_on_completed_not_early_file_id(self):
        # file_id present at `parsing` must be ignored; only `completed` binds.
        frames = [
            b'data: {"status":"parsing","file_id":"cf_EARLY"}\n',
            b'data: {"status":"completed","progress":100,"file_id":"cf_DONE"}\n',
            b"data: [DONE]\r\n",
        ]
        self.assertEqual(self._call(frames), "cf_DONE")
        # the try/finally must close the response (success path)
        self.assertTrue(self._last_resp.closed)

    def test_done_marker_is_not_json_parsed(self):
        # The bare [DONE] terminal frame must not crash the parse loop.
        frames = [
            b'data: {"status":"completed","file_id":"cf_X"}\n',
            b"data: [DONE]\n",
        ]
        self.assertEqual(self._call(frames), "cf_X")

    def test_no_completed_raises_non_network(self):
        import cue_api
        frames = [
            b'data: {"status":"parsing","file_id":"cf_EARLY"}\n',
            b"data: [DONE]\n",
        ]
        with self.assertRaises(cue_api.CueAPIError) as cm:
            self._call(frames)
        # must NOT be status 0 (which user_hint renders as "网络不可达").
        self.assertNotEqual(cm.exception.status, 0)
        self.assertNotIn("网络不可达", cm.exception.user_hint())
        # the try/finally must close the response on the raise path too
        self.assertTrue(self._last_resp.closed)

    def test_failed_frame_surfaces_error_field(self):
        # The route puts the failure reason under `error` (not `message`).
        import cue_api
        frames = [
            b'data: {"status":"failed","error":"\xe6\x96\x87\xe4\xbb\xb6\xe5\xa4\xa7\xe5\xb0\x8f\xe8\xb6\x85\xe8\xbf\x87\xe9\x99\x90\xe5\x88\xb6 50MB"}\n',
            b"data: [DONE]\n",
        ]
        with self.assertRaises(cue_api.CueAPIError) as cm:
            self._call(frames)
        self.assertIn("50MB", cm.exception.detail)
        self.assertEqual(cm.exception.status, 422)
        # 422 must render an actionable file-reject hint, not "未预期的错误".
        hint = cm.exception.user_hint()
        self.assertNotIn("网络不可达", hint)
        self.assertNotIn("未预期的错误", hint)
        self.assertIn("拒绝", hint)
        self.assertTrue(self._last_resp.closed)


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

    def test_report_finalized_breaks_live_loop(self):
        """report_finalized must break the live SSE loop. The stream often
        stays open after the report is done; without the break the run
        holds until the 60min timeout and the agent stays stuck at
        '已开跑' with the report already in the DB.

        Pin the actual loop exit, not a source substring: monkeypatch
        chat_stream to yield report_finalized followed by a poison event
        whose consumption raises — run() must return the report without
        iterating past report_finalized. (The old source-regex pin matched
        _emit_progress's elif branch + the timeout break via re.S, so a
        silent revert left the suite green.)"""
        import json
        from unittest.mock import patch
        import research_run

        def poison_stream(*a, **kw):
            yield "tool_chunk", json.dumps({"chunk": {"0": {"type": "mcp", "data": {
                "tool_name": "scan_x", "tool_title": "财报检索",
                "input": {"query": "资产减值"},
                "output": '{"rows":[{"source":{"pdf_url":"http://example.com/a.pdf"}}]}',
            }}}})
            yield "start_of_agent", json.dumps({"agent_name": "reporter"})
            yield "message", json.dumps({"delta": {"content": "报告正文"}})
            yield "report_finalized", json.dumps({"agent_name": "reporter"})
            yield "POISON", "should-not-be-consumed"
            raise AssertionError("stream iterated past report_finalized")

        with patch.object(research_run, "chat_stream", poison_stream):
            report, sources, conv_id = research_run.run(
                query="q", template_id=None, conversation_id="c1", timeout=60.0
            )
        self.assertEqual(report, "报告正文",
                         "run() should extract the report and return it")
        self.assertEqual(conv_id, "c1")
        self.assertEqual(len(sources), 1, "run() should return the tool_chunk source")
        self.assertEqual(sources[0]["tool_name"], "scan_x")
        self.assertEqual(sources[0]["rows"][0]["pdf_url"], "http://example.com/a.pdf")

    def test_inline_citations(self):
        """inline_citations replaces 【N-M】 with markdown links — search_snippet
        → data.url, scan → rows[M].pdf_url, mcp (no url) → text kept."""
        import research_run
        sources = [
            {"index": 0, "tool_name": "search_tool", "url": "http://a.pdf",
             "title": "来源A", "rows": []},
            {"index": 1, "tool_name": "scan_x", "url": "", "title": "",
             "rows": [{"m": 0, "company": "002385", "title": "商誉减值",
                       "pdf_url": "http://b.pdf", "summary": "", "page_range": ""}]},
            {"index": 2, "tool_name": "get_section", "url": "", "title": "",
             "rows": []},  # mcp class, no url → text kept
        ]
        report = "引用A【0-0】; 引用B【1-0】; 引用C【2-0】; 无来源【9-9】"
        out = research_run.inline_citations(report, sources)
        # search_snippet: [0-0](http://a.pdf "来源A")
        self.assertIn('[0-0](http://a.pdf "来源A")', out)
        # scan: [1-0](http://b.pdf "002385 商誉减值")
        self.assertIn('[1-0](http://b.pdf "002385 商誉减值")', out)
        # mcp (no url): 【2-0】 kept as text (no link)
        self.assertIn("【2-0】", out)
        # unknown source: 【9-9】 kept as text
        self.assertIn("【9-9】", out)
        # no tail appendix
        self.assertNotIn("## 数据来源详情", out)

    def test_inline_citations_no_truncate(self):
        # scan class: high M rows all get links (no cap, positional).
        import research_run
        rows = [{"m": m, "company": f"c{m}", "title": "",
                 "pdf_url": f"http://x{m}.pdf", "summary": "", "page_range": ""}
                for m in range(32)]
        sources = [{"index": 0, "url": "", "title": "", "rows": rows}]
        out = research_run.inline_citations("ref【0-31】", sources)
        self.assertIn("[0-31](http://x31.pdf", out)

    def test_runner_mimic_is_freeform_only(self):
        """mimic must be refused alongside --template-id (backend lets
        template_id silently override mimic, so refuse rather than no-op)."""
        src = (_HERE / "research_run.py").read_text(encoding="utf-8")
        self.assertRegex(
            src, r"mimic.*template_id|template_id.*mimic",
            "runner must guard mimic-vs-template_id mutual exclusivity",
        )

    def test_runner_exposes_material_flag(self):
        """文档接地: --material (repeatable) uploads docs and threads their
        file_ids into the payload as conversation_file_ids."""
        src = (_HERE / "research_run.py").read_text(encoding="utf-8")
        self.assertIn("--material", src)
        self.assertIn("upload_material", src)
        # threaded into the payload as the conversation_file_ids key
        self.assertRegex(src, r'["\']conversation_file_ids["\']')

    def test_runner_build_payload_includes_material_ids(self):
        """build_payload must emit conversation_file_ids only when non-empty
        (mirrors the `if mimic:` guard), and omit it otherwise."""
        import research_run
        with_ids = research_run.build_payload(
            "q", None, "conv1", None, ["cf_a", "cf_b"]
        )
        self.assertEqual(with_ids.get("conversation_file_ids"), ["cf_a", "cf_b"])
        without = research_run.build_payload("q", None, "conv1")
        self.assertNotIn("conversation_file_ids", without)

    def test_runner_allows_material_with_template(self):
        """Behavioral: unlike mimic (which is refused with --template-id),
        --material is orthogonal — main() must accept the combo (not return 2)
        and pass BOTH template_id and the file_ids through to run().

        (A source-regex 'no guard' check is unreliable here — single-line regex
        misses a multi-line guard, and re.DOTALL over-matches — so assert the
        actual behavior instead.)"""
        import research_run

        captured = {}

        def fake_run(query, template_id, conv, timeout,
                     mimic=None, conversation_file_ids=None):
            captured["template_id"] = template_id
            captured["cfids"] = conversation_file_ids
            return "REPORT", [], conv

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
            tf.write(b"hi")
            tpath = tf.name
        out = tpath + ".out.md"
        try:
            with mock.patch.object(research_run, "load_config",
                                   lambda: ("sk", "https://x/api")), \
                 mock.patch.object(research_run, "upload_material",
                                   lambda p: "cf_fake"), \
                 mock.patch.object(research_run, "run", fake_run):
                rc = research_run.main(
                    ["--query", "q", "--template-id", "template_X",
                     "--material", tpath, "--output", out]
                )
        finally:
            os.unlink(tpath)
            if os.path.exists(out):
                os.unlink(out)
        self.assertEqual(rc, 0, "material+template must be accepted, not refused")
        self.assertEqual(captured.get("template_id"), "template_X")
        self.assertEqual(captured.get("cfids"), ["cf_fake"])

    def test_runner_material_upload_failure_aborts_before_chat(self):
        """Fail-fast: a failed --material upload returns 1 and never reaches
        chat_stream (don't burn a research run on missing grounding)."""
        import cue_api
        import research_run

        chat = mock.Mock()

        def boom(path):
            raise cue_api.CueAPIError(422, "bad file", "/file/upload_stream")

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
            tf.write(b"hi")
            tpath = tf.name
        out = tpath + ".out.md"
        try:
            with mock.patch.object(research_run, "load_config",
                                   lambda: ("sk", "https://x/api")), \
                 mock.patch.object(research_run, "upload_material", boom), \
                 mock.patch.object(research_run, "chat_stream", chat):
                rc = research_run.main(
                    ["--query", "q", "--material", tpath, "--output", out]
                )
        finally:
            os.unlink(tpath)
            if os.path.exists(out):
                os.unlink(out)
        self.assertEqual(rc, 1)
        chat.assert_not_called()

    def test_skill_md_documents_mimic_option(self):
        md = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(md, r"仿写|mimic")
        self.assertIn("--mimic-url", md)
        self.assertIn("--mimic-file", md)

    def test_skill_md_documents_material_option(self):
        md = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--material", md)
        self.assertRegex(md, r"素材|接地|file_retrieval")
        # security rule must scope the "don't upload local files" default to
        # explicitly-confirmed material uploads, not contradict it.
        self.assertRegex(md, r"默认不上传本地材料|经用户确认后才上传")


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


class TestEmitProgress(unittest.TestCase):
    """_emit_progress prints flushed, human+machine-readable progress lines
    for key SSE events so the agent (and user reading backgrounded stdout)
    can see research steps: agent phase + task_requirement, tool calls,
    report finalization. Other events are ignored (too noisy / report
    content). Lets the agent confirm startup, check progress mid-run, and
    see completion — fixing the fire-and-retrieve black-box."""

    def _emit(self, event, payload):
        import contextlib
        import io
        import json
        import research_run
        data = json.dumps(payload) if payload is not None else ""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            research_run._emit_progress(event, data)
        return buf.getvalue()

    def test_start_of_agent_with_task_requirement(self):
        out = self._emit("start_of_agent", {
            "agent_name": "researcher",
            "task_requirement": "扫描年报资产减值",
        })
        self.assertIn("▶ agent=researcher task=扫描年报资产减值", out)

    def test_start_of_agent_without_task_requirement(self):
        out = self._emit("start_of_agent", {"agent_name": "coordinator"})
        self.assertIn("▶ agent=coordinator", out)
        self.assertNotIn("task=", out)

    def test_tool_call_with_title(self):
        out = self._emit("tool_call", {
            "tool_name": "scan_financial_report_evidence",
            "tool_title": "财报章节语义检索",
        })
        self.assertIn("🔧 tool=scan_financial_report_evidence (财报章节语义检索)", out)

    def test_tool_call_without_title(self):
        out = self._emit("tool_call", {"tool_name": "scan_x"})
        self.assertIn("🔧 tool=scan_x", out)
        self.assertNotIn("(", out)

    def test_report_finalized(self):
        out = self._emit("report_finalized", {"agent_name": "reporter"})
        self.assertIn("✓ report finalized", out)

    def test_message_event_ignored(self):
        # message events carry report content delta — too noisy, must skip.
        out = self._emit("message", {"delta": {"content": "报告正文..."}})
        self.assertEqual("", out)

    def test_empty_data_ignored(self):
        out = self._emit("message", None)
        self.assertEqual("", out)

    def test_malformed_json_ignored(self):
        import contextlib
        import io
        import research_run
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            research_run._emit_progress("start_of_agent", "{not json")
        self.assertEqual("", buf.getvalue())

    def test_non_dict_json_ignored(self):
        # valid JSON but not a dict (null/list/string) — must not AttributeError
        import contextlib
        import io
        import research_run
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            research_run._emit_progress("tool_call", "[1, 2, 3]")
            research_run._emit_progress("start_of_agent", '"a string"')
            research_run._emit_progress("tool_call", "null")
        self.assertEqual("", buf.getvalue())

    def test_tool_call_nested_live_shape(self):
        # live chat_stream wraps payload in {"data": {...}}; replay is flat.
        # _emit_progress must handle both (via _event_data) — flat-only access
        # degrades to 🔧 tool=? on live streams, exactly where the feature matters.
        out = self._emit("tool_call", {"data": {
            "tool_name": "scan_financial_report_evidence",
            "tool_title": "财报章节语义检索",
        }})
        self.assertIn("🔧 tool=scan_financial_report_evidence (财报章节语义检索)", out)

    def test_start_of_agent_nested_live_shape(self):
        out = self._emit("start_of_agent", {"data": {
            "agent_name": "researcher",
            "task_requirement": "扫描年报资产减值",
        }})
        self.assertIn("▶ agent=researcher task=扫描年报资产减值", out)

    def test_nested_data_non_dict_no_crash(self):
        # payload is a dict but payload["data"] is a truthy non-dict (str) —
        # _agent_name used to do (payload.get("data") or {}).get(...) which
        # raised AttributeError on the str, killing run() mid-stream. The
        # isinstance(nested, dict) guard in _agent_name prevents this.
        out = self._emit("start_of_agent", {"data": "oops"})
        self.assertIn("▶ agent=?", out)  # degraded, not crashed


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
