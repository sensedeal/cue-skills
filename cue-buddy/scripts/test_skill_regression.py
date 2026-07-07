#!/usr/bin/env python3
"""Skill-level regression tests (stdlib only, no pytest needed).

Run after editing tune_template.py / cue_api.py / validate_template.py to
catch drift against the Cue public API contract. Covers codex
review findings:

1. +tune prompt 不能再含 `introduction`(后端契约改造已落地)
2. cue_api 接受 legacy `task_configs` payload 转换为 `schedules`
3. search_plan 某个维度缺三件套 → error(block-level)
4. report_format 某节缺执行蓝图 → error(block-level)
5. search_tool_company / crawl_tool_site 在工具名 lint 被拦

Usage:
    python3 scripts/test_skill_regression.py

Exit 0 = all passed; non-zero = at least one failed (with detail).
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# Loaded lazily inside each test so import errors point to the right file.


class Case1_TunePromptUsesCanonicalName(unittest.TestCase):
    """codex !450 r3 #1 — tune prompt must use input_form_spec, not introduction."""

    def test_build_user_requirement_omits_introduction(self) -> None:
        from tune_template import build_user_requirement

        current = {
            "title": "示例",
            "primary_category": "投研",
            "secondary_category": "财报点评",
            "input_form_spec": "需提供: [目标_点评_公司]",
            "goal": "测试目标",
            "search_plan": "测试",
            "report_format": "## 1. 测试",
        }
        prompt = build_user_requirement(current, "略")
        # Prompt 必须用 canonical 名字,不应再提 introduction
        self.assertNotIn("introduction", prompt, "+tune prompt 仍含 'introduction'")
        self.assertIn("input_form_spec", prompt, "+tune prompt 缺 'input_form_spec'")


class Case2_LegacyTaskConfigsNormalizedToSchedules(unittest.TestCase):
    """codex !450 r3 #2 — cue_api 把 legacy task_configs 自动转 schedules,
    并 strip server-internal keys。"""

    def test_task_configs_to_schedules(self) -> None:
        from cue_api import _normalize_template_payload

        payload = {
            "title": "X",
            "task_input": "宁德时代",
            "task_cron_expressions": ["0 9 * * *", "0 9 * * 1"],
            "task_configs": [
                {
                    "type": "daily",
                    "time": "09:00",
                    "date_param": None,
                    "dates": None,
                    "name": "should-be-dropped",
                },
                {
                    "type": "weekly",
                    "time": "09:00",
                    "date_param": "1",
                    "dates": None,
                    "name": "weekly",
                },
            ],
        }
        out = _normalize_template_payload(payload)
        # task_cron_expressions / task_configs 必须从 outbound 抹除
        self.assertNotIn("task_cron_expressions", out)
        self.assertNotIn("task_configs", out)
        # schedules 必须从 task_configs 派生,带正确 4 字段且无 name
        self.assertIn("schedules", out)
        self.assertEqual(len(out["schedules"]), 2)
        for s in out["schedules"]:
            self.assertEqual(set(s.keys()), {"type", "time", "date_param", "dates"})
        self.assertEqual(out["schedules"][0]["type"], "daily")
        self.assertEqual(out["schedules"][1]["date_param"], "1")

    def test_schedules_present_wins_over_task_configs(self) -> None:
        """如果 caller 已传 schedules,不被 task_configs 覆盖。"""
        from cue_api import _normalize_template_payload

        payload = {
            "schedules": [
                {"type": "daily", "time": "10:00", "date_param": None, "dates": None}
            ],
            "task_configs": [
                {"type": "weekly", "time": "11:00", "date_param": "2", "dates": None}
            ],
        }
        out = _normalize_template_payload(payload)
        self.assertEqual(out["schedules"][0]["time"], "10:00")
        self.assertNotIn("task_configs", out)


class Case3_SearchPlanMissingTripletInOneDimension(unittest.TestCase):
    """codex !450 r3 #3 — block-level check finds per-dimension misses
    that global count would mask."""

    def test_dimension_missing_validation_strategy(self) -> None:
        from validate_template import validate

        # 3 维度,前 2 个完整,第 3 缺验证策略。全局 count=2/3/2 都 ≥ 2,
        # 旧 lint 全过;block-level 必须抓出第 3 维度缺。
        sp = (
            "**[[主体核验] 公开身份信息]**\n"
            "- **数据路由**: 工商 / 上市公告\n"
            "- **执行动作**: 法定代表人 / 注册资本\n"
            "- **验证策略**: 不一致时以披露为准\n\n"
            "**[[财务实证] 三年财务]**\n"
            "- **数据路由**: 年报\n"
            "- **执行动作**: 营收 / 净利润\n"
            "- **验证策略**: 评级最新\n\n"
            "**[[行业景气] 行业]**\n"
            "- **数据路由**: 协会数据\n"
            "- **执行动作**: 行业增长\n"
            # 故意缺 **验证策略**
        )
        payload = {
            "title": "x",
            "primary_category": "x",
            "secondary_category": "x",
            # 三段式变量必须中文(R1);用合规 `[目标_授信_企业]` 避免 fixture 污染
            # (codex !450 r3 review: 旧 `[目标_X_主体]` 含英文 X 会污染 errors)
            "input_form_spec": "需提供: [目标_授信_企业]，可提供: [关注_风险_主题] (默认: 通用)",
            "goal": "作为银行客户经理的预尽调助手，识别风险信号",
            "search_plan": sp,
            "report_format": (
                "> **关键配置**\n> - **目标对象**: [目标_授信_企业]\n\n"
                "# [目标_授信_企业] 测试\n\n"
                "## 1. A\n> **[执行蓝图]**\n> - **研究目标**: x\n"
                "> - **逻辑链条**: x\n> - **信息需求**: x\n> - **输出形式**: 段落\n"
                "## 2. B\n> **[执行蓝图]**\n> - **研究目标**: x\n"
                "> - **逻辑链条**: x\n> - **信息需求**: x\n> - **输出形式**: 段落\n"
                "## 3. C\n> **[执行蓝图]**\n> - **研究目标**: x\n"
                "> - **逻辑链条**: x\n> - **信息需求**: x\n> - **输出形式**: 段落\n"
                "本报告基于公开信息编制\n"
            ),
        }
        findings = validate(payload)
        errors = [f for f in findings if f.severity == "error"]
        # 必须有一条 error 指向 search_plan 第 3 维度 + 验证策略 缺失
        relevant = [
            f
            for f in errors
            if f.field == "search_plan" and "验证策略" in f.message and "行业" in f.message
        ]
        self.assertTrue(
            relevant,
            f"block-level lint 没抓到第 3 维度缺验证策略;all errors: {[str(f) for f in errors]}",
        )
        # 且其他字段不应被该 fixture 污染产生 errors (codex !450 r3 NICE)
        unrelated = [f for f in errors if f.field != "search_plan"]
        self.assertEqual(
            unrelated, [], f"fixture 污染:非 search_plan field 也报 errors: {[str(f) for f in unrelated]}"
        )


class Case4_ReportSectionMissingBlueprint(unittest.TestCase):
    """codex !450 r3 #4 — 某节缺执行蓝图引用块时,error 必须按章节定位。"""

    def test_section_missing_blueprint_block_is_error(self) -> None:
        from validate_template import validate

        # 第 2 节有蓝图,第 1/3 节缺
        rf = (
            "> **关键配置**\n> - **目标对象**: [目标_X_主体]\n\n"
            "# [目标_X_主体] 测试报告\n\n"
            "## 1. 第一节\n内容(无蓝图)\n\n"
            "## 2. 第二节\n> **[执行蓝图]**\n"
            "> - **研究目标**: x\n> - **逻辑链条**: x\n"
            "> - **信息需求**: x\n> - **输出形式**: 段落\n\n"
            "## 3. 第三节\n内容(也无蓝图)\n\n"
            "本报告基于公开信息编制\n"
        )
        payload = {
            "title": "x",
            "primary_category": "x",
            "secondary_category": "x",
            # 合规三段式 + 合规维度 label (codex !450 r3 fixture cleanup)
            "input_form_spec": "需提供: [目标_授信_企业]，可提供: [关注_风险_主题] (默认: 通用)",
            "goal": "作为银行客户经理的预尽调助手，识别风险信号",
            "search_plan": (
                "**[[主体核验] 公开身份]**\n- **数据路由**: 工商\n"
                "- **执行动作**: 法人\n- **验证策略**: 以披露为准\n\n"
                "**[[财务实证] 三年财务]**\n- **数据路由**: 年报\n"
                "- **执行动作**: 营收\n- **验证策略**: 评级最新\n"
            ),
            "report_format": rf,
        }
        findings = validate(payload)
        errors = [f for f in findings if f.severity == "error"]
        # 必须有两条 error 指向第 1 / 第 3 节缺蓝图
        sec1 = [
            f
            for f in errors
            if "执行蓝图" in f.message and ("第 1 节" in f.message or "「第一节」" in f.message)
        ]
        sec3 = [
            f
            for f in errors
            if "执行蓝图" in f.message and ("第 3 节" in f.message or "「第三节」" in f.message)
        ]
        self.assertTrue(sec1, f"未抓到第 1 节缺蓝图;errors: {[str(f) for f in errors]}")
        self.assertTrue(sec3, f"未抓到第 3 节缺蓝图;errors: {[str(f) for f in errors]}")
        # 非 report_format 字段不应被 fixture 污染 (codex !450 r3 NICE)
        unrelated = [f for f in errors if f.field != "report_format"]
        self.assertEqual(
            unrelated, [], f"fixture 污染:非 report_format 报 errors: {[str(f) for f in unrelated]}"
        )


class Case5_ToolNameLeakRegexCoversAllFamilies(unittest.TestCase):
    """codex !450 r3 #5 — search_tool* / crawl_tool* 必须被工具名 lint 拦。"""

    def test_search_tool_company_caught(self) -> None:
        from validate_template import TOOL_NAME_LEAK_RE

        for sample in (
            "调用 search_tool_company 拉公司",
            "用 search_tool 检索",
            "执行 search_tool_disclosure 获取披露",
            "走 crawl_tool_site 抓页",
            "通过 crawl_tool 爬取",
            "用 get_disclosure 拉公告",  # 原有 family,保持工作
            "调 list_companies",
            "find_recent_news",
            # CJK-glued, no spaces — \b 不 fire,旧 regex 漏抓(Pz0sT5 上线泄漏)
            "使用get_cninfo_disclosure_search工具",
            "根据关键词搜索公告：使用get_cninfo_disclosure_search工具。",
            "优先list_companies再深挖",
            "调用search_tool_company查",
        ):
            with self.subTest(sample=sample):
                self.assertRegex(sample, TOOL_NAME_LEAK_RE, f"未抓 {sample!r}")

    def test_legitimate_text_not_falsely_flagged(self) -> None:
        """合规中文文本(无下划线工具名)不应被 leak regex 命中。

        Codex !450 r3 confirmation: `search_tools` 复数形式也属于工具名引用
        (meta 描述里写工具集合也是 R5 leak),应被命中 — 故不在"不应被抓"列表。
        """
        from validate_template import TOOL_NAME_LEAK_RE

        for sample in (
            "通过监管披露与行业数据交叉验证",
            "数据路由: 上市公司公告",
            "司法 / 舆情 / 监管处罚",
            "穿透 [目标_授信_企业] 的公开监管披露",
        ):
            with self.subTest(sample=sample):
                self.assertNotRegex(sample, TOOL_NAME_LEAK_RE, f"误报: {sample!r}")


# Bonus: cue_api task_input client-side lint regression
class Case6_TaskInputClientSideFastFail(unittest.TestCase):
    """codex !450 r3 #2 mirror — `cue_api._normalize_template_payload`
    在 send 前本地拦截违 R9 task_input。"""

    def test_placeholder_text_raises(self) -> None:
        from cue_api import _normalize_template_payload

        with self.assertRaises(ValueError) as cm:
            _normalize_template_payload(
                {"task_input": "请输入企业名称或统一社会信用代码。可选补充..."}
            )
        self.assertIn("R9", str(cm.exception))

    def test_placeholder_variable_raises(self) -> None:
        from cue_api import _normalize_template_payload

        with self.assertRaises(ValueError) as cm:
            _normalize_template_payload({"task_input": "[目标_授信_企业]"})
        self.assertIn("占位", str(cm.exception))

    def test_concrete_subject_passes(self) -> None:
        from cue_api import _normalize_template_payload

        out = _normalize_template_payload({"task_input": "宁德时代"})
        self.assertEqual(out["task_input"], "宁德时代")


class Case7_DimRegexCoversNonChineseLabels(unittest.TestCase):
    """codex !450 r3 #2 — search_plan dim regex must accept English/digit/
    dash labels like `[[ESG-2026]]`, `[[A股]]`, `[[2026]]`."""

    def test_english_dash_digit_labels_match(self) -> None:
        from validate_template import _SEARCH_PLAN_DIM_RE

        for sample in (
            "**[[ESG-2026] ESG事项]**",
            "**[[A股] 披露]**",
            "**[[2026] 年度趋势]**",
            "**[[主体核验] 公开身份信息]**",  # 中文 label 不退化
        ):
            with self.subTest(sample=sample):
                self.assertRegex(sample, _SEARCH_PLAN_DIM_RE)


class Case8_RecommendedTaskHelperRequiresSchedules(unittest.TestCase):
    """codex !450 r3 #1 — update_template_recommended_task 必须本地 raise
    若 schedules 缺失/为空,而不是发到后端拿 422。"""

    def test_missing_schedules_raises(self) -> None:
        from cue_api import update_template_recommended_task

        with self.assertRaises(ValueError) as cm:
            # 注意: 不能真发 HTTP, 但 schedules 校验在 _request 之前
            update_template_recommended_task("tpl_x", schedules=[])
        self.assertIn("schedules", str(cm.exception))

    def test_non_list_schedules_raises(self) -> None:
        from cue_api import update_template_recommended_task

        with self.assertRaises(ValueError):
            update_template_recommended_task("tpl_x", schedules=None)  # type: ignore[arg-type]


class Case9_CronExpressionsTypoRejected(unittest.TestCase):
    """codex !450 r3 #4 — `cron_expressions` (no `task_` prefix) typo 必须
    本地 raise; 否则后端 extra='ignore' 会静默吞掉。"""

    def test_typo_field_raises(self) -> None:
        from cue_api import _normalize_template_payload

        with self.assertRaises(ValueError) as cm:
            _normalize_template_payload(
                {"title": "x", "cron_expressions": ["0 9 * * *"]}
            )
        self.assertIn("cron_expressions", str(cm.exception))

    def test_task_configs_missing_type_raises(self) -> None:
        """codex !450 r3 #3 — task_configs item 缺 type/time 应本地 raise."""
        from cue_api import _normalize_template_payload

        with self.assertRaises(ValueError) as cm:
            _normalize_template_payload(
                {
                    "task_configs": [
                        {"time": "09:00", "date_param": None, "dates": None}
                    ]
                }
            )
        self.assertIn("type", str(cm.exception))


class Case10_TestTemplateDiagnosis(unittest.TestCase):
    """codex r4 finding — test_template.py _diagnose_empty_report 分类正确性.

    +test SSE 长流断连场景的诊断函数,决定要不要走 replay fallback。
    """

    def test_stream_cut_before_reporter(self) -> None:
        """events 只有 coordinator/researcher,reporter 还没 start 就断流。"""
        import json

        from test_template import _diagnose_empty_report

        events = [
            ("start_of_agent", json.dumps({"data": {"agent_name": "coordinator"}})),
            ("message", json.dumps({"data": {"delta": {"content": "x"}}})),
            ("end_of_agent", json.dumps({"data": {"agent_name": "coordinator"}})),
            ("start_of_agent", json.dumps({"data": {"agent_name": "researcher"}})),
            ("message", json.dumps({"data": {"delta": {"content": "y"}}})),
        ]
        d = _diagnose_empty_report(events, elapsed=372.9, timeout=300.0)
        self.assertEqual(d["kind"], "stream_cut_before_reporter")
        self.assertEqual(d["last_agent"], "researcher")
        self.assertFalse(d["reporter_started"])
        self.assertTrue(d["hit_timeout"])

    def test_top_level_agent_name_events_are_supported(self) -> None:
        """Replay SSE uses top-level agent_name; extractor must support it."""
        import json

        from test_template import _diagnose_empty_report, _extract_reporter_content

        events = [
            ("start_of_agent", json.dumps({"agent_name": "reporter"})),
            (
                "message",
                json.dumps(
                    {
                        "agent_name": "reporter",
                        "delta": {"content": "# 淡水泉 尽调报告\n"},
                    }
                ),
            ),
            ("end_of_agent", json.dumps({"agent_name": "reporter"})),
        ]
        report = _extract_reporter_content(events)
        self.assertIn("淡水泉", report)

        d = _diagnose_empty_report(events, elapsed=1.0, timeout=300.0)
        self.assertTrue(d["reporter_started"])
        self.assertTrue(d["reporter_ended"])

    def test_no_agent_events(self) -> None:
        """events 完全无 agent — auth/template_id 错或后端没响应。"""
        import json

        from test_template import _diagnose_empty_report

        events = [
            ("message", json.dumps({"data": {"delta": {"content": "noise"}}})),
        ]
        d = _diagnose_empty_report(events, elapsed=2.0, timeout=300.0)
        self.assertEqual(d["kind"], "no_agent_events")
        self.assertIsNone(d["last_agent"])
        self.assertFalse(d["hit_timeout"])

    def test_reporter_started_no_text(self) -> None:
        """reporter start 看到了但没 message text — 罕见 server-side fail。"""
        import json

        from test_template import _diagnose_empty_report

        events = [
            ("start_of_agent", json.dumps({"data": {"agent_name": "reporter"}})),
            # 没 message events,直接 end
            ("end_of_agent", json.dumps({"data": {"agent_name": "reporter"}})),
        ]
        d = _diagnose_empty_report(events, elapsed=10.0, timeout=300.0)
        self.assertEqual(d["kind"], "reporter_started_no_text")
        self.assertTrue(d["reporter_started"])
        self.assertTrue(d["reporter_ended"])

    def test_extractor_works_without_end_marker(self) -> None:
        """codex r4 关键纠错:end_of_agent 缺失**不会**让 extractor 空 —
        in_reporter 保持 True 直到流结束,后续 message 仍累加。"""
        import json

        from test_template import _extract_reporter_content

        events = [
            ("start_of_agent", json.dumps({"data": {"agent_name": "reporter"}})),
            (
                "message",
                json.dumps({"data": {"delta": {"content": "## 1. 业绩\n"}}}),
            ),
            (
                "message",
                json.dumps({"data": {"delta": {"content": "营收增长 20%\n"}}}),
            ),
            # 没 end_of_agent — 流断在 reporter 中间
        ]
        report = _extract_reporter_content(events)
        # ✓ 即使 end 没到,extractor 仍累加,report 非空
        self.assertIn("业绩", report)
        self.assertIn("营收增长 20%", report)


class Case11_TestTemplateChecks(unittest.TestCase):
    """+test report checks should accept legal-name expansion."""

    def test_title_check_accepts_short_name_expanded_to_legal_name(self) -> None:
        from test_template import _check_title_contains_entity

        report = "# 淡水泉（北京）投资管理有限公司 私募管理人公开尽调底稿\n"
        result = _check_title_contains_entity(report, "淡水泉投资")
        self.assertTrue(result.ok, result.detail)


class Case12_R10ReportTimeFieldValidator(unittest.TestCase):
    """R10 validate_template check: 报告时间 field name + format + placeholder.

    Frontend renders by exact key `报告时间`; wrong variants like 报告生成时间 break
    the FE display. Self-created placeholders like `<由 LLM 填充>` can leak literal
    text into the published report if the reporter LLM ignores them."""

    def _payload_with_rf(self, rf_body: str) -> dict:
        """Build a minimally-valid template payload with a custom report_format."""
        return {
            "title": "T",
            "primary_category": "金融",
            "secondary_category": "预尽调",
            "input_form_spec": "需提供: [目标_测试_企业] (默认: 通用)。",
            "goal": "穿透目标企业的公开监管披露,识别影响首批授信批复的偿债、合规与经营风险。",
            "search_plan": (
                "**[[主体] 公开身份]**\n"
                "- **数据路由**: A\n- **执行动作**: B\n- **验证策略**: C\n\n"
                "**[[财务] 三年财务]**\n"
                "- **数据路由**: A\n- **执行动作**: B\n- **验证策略**: C\n"
            ),
            "report_format": rf_body,
        }

    def _rf_with_time_line(self, time_line: str = "报告时间: YYYY年MM月DD日") -> str:
        return (
            "> **关键配置**\n"
            "> - **目标对象**: [目标_测试_企业]\n"
            "> - **报告类型**: 测试\n"
            "> - **基调设定**: 客观\n"
            "> - **核心命题**: 测试\n\n"
            "# [目标_测试_企业] 测试底稿\n"
            f"{time_line}\n\n"
            "## 1. 节\n\n"
            "> **[执行蓝图]**\n"
            "> - **研究目标**: T\n"
            "> - **逻辑链条**: T\n"
            "> - **信息需求**: T\n"
            "> - **输出形式**: T\n\n"
            "## 2. 节\n\n"
            "> **[执行蓝图]**\n"
            "> - **研究目标**: T\n"
            "> - **逻辑链条**: T\n"
            "> - **信息需求**: T\n"
            "> - **输出形式**: T\n\n"
            "## 3. 节\n\n"
            "> **[执行蓝图]**\n"
            "> - **研究目标**: T\n"
            "> - **逻辑链条**: T\n"
            "> - **信息需求**: T\n"
            "> - **输出形式**: T\n"
        )

    def test_correct_field_passes(self) -> None:
        from validate_template import validate

        payload = self._payload_with_rf(self._rf_with_time_line())
        r10 = [f for f in validate(payload) if "R10" in f.message]
        self.assertEqual(r10, [], f"unexpected R10 findings: {r10}")

    def test_wrong_name_报告生成时间_errors(self) -> None:
        from validate_template import validate

        payload = self._payload_with_rf(
            self._rf_with_time_line("报告生成时间: YYYY年MM月DD日")
        )
        errs = [f for f in validate(payload)
                if f.severity == "error" and "R10" in f.message]
        self.assertTrue(errs, "should error on 报告生成时间")
        self.assertTrue(any("报告生成时间" in f.message for f in errs))

    def test_wrong_name_生成日期_errors(self) -> None:
        from validate_template import validate

        payload = self._payload_with_rf(
            self._rf_with_time_line("生成日期: YYYY年MM月DD日")
        )
        errs = [f for f in validate(payload)
                if f.severity == "error" and "R10" in f.message]
        self.assertTrue(errs, "should error on 生成日期")

    def test_self_created_placeholder_errors(self) -> None:
        from validate_template import validate

        payload = self._payload_with_rf(
            self._rf_with_time_line("报告时间: <由 LLM 填充>")
        )
        errs = [f for f in validate(payload)
                if f.severity == "error" and "R10" in f.message]
        self.assertTrue(errs, "should error on <由 LLM 填充> placeholder")

    def test_curly_brace_placeholder_errors(self) -> None:
        from validate_template import validate

        payload = self._payload_with_rf(
            self._rf_with_time_line("报告时间: {CURRENT_DATE}")
        )
        errs = [f for f in validate(payload)
                if f.severity == "error" and "R10" in f.message]
        self.assertTrue(errs, "should error on {CURRENT_DATE} placeholder")

    def test_missing_time_field_warns_not_errors(self) -> None:
        from validate_template import validate

        rf_no_time = self._rf_with_time_line("").replace("\n\n\n", "\n\n")
        # strip the empty time_line above
        payload = self._payload_with_rf(rf_no_time)
        r10 = [f for f in validate(payload) if "R10" in f.message]
        self.assertEqual(len(r10), 1, f"expected exactly 1 R10 warning: {r10}")
        self.assertEqual(r10[0].severity, "warning")


class Case13_R10ReportTimeRuntimeCheck(unittest.TestCase):
    """+test runtime guard: produced report must have a filled 报告时间 line
    when the template requires one, and must not leak placeholder literals."""

    def test_correct_report_passes(self) -> None:
        from test_template import _check_report_time_filled

        rf = "# X\n报告时间: YYYY年MM月DD日\n\n## 1. ...\n"
        report = "# X\n报告时间: 2026年05月28日\n\n## 1. ...\n"
        result = _check_report_time_filled(rf, report)
        self.assertTrue(result.ok, result.detail)

    def test_placeholder_leak_fails(self) -> None:
        from test_template import _check_report_time_filled

        rf = "# X\n报告时间: YYYY年MM月DD日\n\n"
        report = "# X\n报告时间: <由 LLM 填充>\n\n"
        result = _check_report_time_filled(rf, report)
        self.assertFalse(result.ok, "must catch <由 LLM 填充> literal in report")

    def test_missing_line_when_required_fails(self) -> None:
        from test_template import _check_report_time_filled

        rf = "# X\n报告时间: YYYY年MM月DD日\n\n"
        report = "# X\n\n## 1. ...\n(no report-time line at all)\n"
        result = _check_report_time_filled(rf, report)
        self.assertFalse(result.ok)

    def test_template_no_time_field_skips(self) -> None:
        from test_template import _check_report_time_filled

        rf = "# X\n\n## 1. ...\n"  # no 报告时间 requirement
        report = "# X\n\n## 1. ...\n"
        result = _check_report_time_filled(rf, report)
        self.assertTrue(result.ok, "must pass when template requires no time field")


class Case14_UpgradeSkillHelpers(unittest.TestCase):
    """+upgrade verb helpers (update_skill.py): pure-function unit tests.

    Network and git/subprocess paths are excluded — those are exercised
    end-to-end at agent time, not in stdlib regression. We test the
    pieces that matter: frontmatter parsing, install-mode detection,
    skill-arg resolution, cooldown gating, and silent-check orchestration
    with an injected fetch_fn (no network)."""

    def test_parse_version_from_md_extracts_quoted_version(self) -> None:
        from update_skill import parse_version_from_md
        md = '---\nname: x\nmetadata:\n  version: "0.3.1"\n---\n# body\n'
        self.assertEqual(parse_version_from_md(md), "0.3.1")

    def test_parse_version_from_md_extracts_unquoted_version(self) -> None:
        from update_skill import parse_version_from_md
        md = "---\nname: x\nmetadata:\n  version: 1.2.3\n---\n"
        self.assertEqual(parse_version_from_md(md), "1.2.3")

    def test_parse_version_from_md_missing_returns_none(self) -> None:
        from update_skill import parse_version_from_md
        md = "---\nname: x\n---\n# body\n"
        self.assertIsNone(parse_version_from_md(md))

    def test_parse_version_from_md_no_frontmatter_returns_none(self) -> None:
        from update_skill import parse_version_from_md
        self.assertIsNone(parse_version_from_md("# just a body\nfoo\n"))

    def test_detect_install_mode_git_when_dotgit_in_ancestor(self) -> None:
        import tempfile
        from update_skill import detect_install_mode
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            (tmp_p / ".git").mkdir()
            skill_dir = tmp_p / "cue-buddy"
            skill_dir.mkdir()
            mode, root = detect_install_mode(skill_dir)
            self.assertEqual(mode, "git")
            self.assertEqual(root, tmp_p)

    def test_detect_install_mode_copy_when_no_dotgit(self) -> None:
        import tempfile
        from unittest.mock import patch
        from update_skill import detect_install_mode
        # TMPDIR may itself sit inside a git worktree (e.g. /fast/tmp has a
        # stray .git, or a dev sets TMPDIR into a project dir). Since
        # detect_install_mode walks ancestors looking for .git, a stray
        # ancestor .git would make this return "git" and break the
        # "no .git anywhere → copy" assertion. Force .git ancestor checks
        # to miss so the test is robust regardless of where TMPDIR lives.
        real_exists = Path.exists

        def fake_exists(self):
            if self.name == ".git":
                return False
            return real_exists(self)

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(Path, "exists", fake_exists):
            skill_dir = Path(tmp) / "cue-buddy"
            skill_dir.mkdir()
            mode, root = detect_install_mode(skill_dir)
            self.assertEqual(mode, "copy")
            self.assertIsNone(root)

    def test_resolve_skill_dir_rejects_unknown(self) -> None:
        from update_skill import _resolve_skill_dir
        with self.assertRaises(ValueError):
            _resolve_skill_dir("bogus-skill")

    def test_resolve_skill_dir_accepts_known(self) -> None:
        from update_skill import _resolve_skill_dir
        # Should not raise for both known skills.
        for s in ("cue-buddy", "cue-research"):
            d = _resolve_skill_dir(s)
            self.assertTrue(d.name == s)

    def test_cooldown_expired_when_no_record(self) -> None:
        import tempfile
        from update_skill import _cooldown_expired
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cooldown.json"
            self.assertTrue(_cooldown_expired("cue-buddy", now=1000.0,
                                              cooldown_s=86400, path=p))

    def test_cooldown_not_expired_when_recent(self) -> None:
        import json as _json
        import tempfile
        from update_skill import _cooldown_expired
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cooldown.json"
            p.write_text(_json.dumps({"cue-buddy": 1000.0}))
            # 1 hour later, 24h cooldown → still cooling down.
            self.assertFalse(_cooldown_expired("cue-buddy", now=1000.0 + 3600,
                                                cooldown_s=86400, path=p))

    def test_cooldown_expired_when_old(self) -> None:
        import json as _json
        import tempfile
        from update_skill import _cooldown_expired
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cooldown.json"
            p.write_text(_json.dumps({"cue-buddy": 1000.0}))
            # 25h later → expired.
            self.assertTrue(_cooldown_expired("cue-buddy", now=1000.0 + 25 * 3600,
                                               cooldown_s=86400, path=p))

    def test_silent_check_skips_when_cooldown_fresh(self) -> None:
        """Cooldown gate short-circuits before any network attempt."""
        import json as _json
        import tempfile
        from update_skill import silent_check_for_update
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cooldown.json"
            p.write_text(_json.dumps({"cue-buddy": 1000.0}))
            calls = []
            def boom_fetch(skill):
                calls.append(skill)
                return "9.9.9"
            rc = silent_check_for_update(
                skill="cue-buddy", now=1000.0 + 60,
                cooldown_path=p, fetch_fn=boom_fetch,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(calls, [], "fetch_fn must NOT be called when cooldown is fresh")

    def test_silent_check_writes_cooldown_after_successful_fetch(self) -> None:
        """After a successful version fetch the cooldown timestamp persists."""
        import json as _json
        import tempfile
        from update_skill import silent_check_for_update
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cooldown.json"
            # Inject a fetch that returns the same version as local — so no
            # nudge, but the timestamp should still get written.
            local_md = (Path(__file__).resolve().parents[1] / "SKILL.md")
            from update_skill import parse_version_from_md
            local_v = parse_version_from_md(local_md.read_text(encoding="utf-8"))
            rc = silent_check_for_update(
                skill="cue-buddy", now=2000.0,
                cooldown_path=p, fetch_fn=lambda s: local_v,
            )
            self.assertEqual(rc, 0)
            data = _json.loads(p.read_text())
            self.assertEqual(data.get("cue-buddy"), 2000.0)

    def test_silent_check_does_not_write_cooldown_on_network_failure(self) -> None:
        """If fetch returns None (network down), cooldown stays untouched so
        the next session retries instead of going silent for 24h."""
        import tempfile
        from update_skill import silent_check_for_update
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cooldown.json"
            rc = silent_check_for_update(
                skill="cue-buddy", now=3000.0,
                cooldown_path=p, fetch_fn=lambda s: None,
            )
            self.assertEqual(rc, 0)
            self.assertFalse(p.exists(), "cooldown file must not be written on net failure")

    def test_is_local_behind_strict_semver(self) -> None:
        """Comparator must only fire when local < remote (semver tuple).
        Local-ahead developer cases must NOT trigger nudge."""
        from update_skill import is_local_behind
        # local strictly older → behind
        self.assertTrue(is_local_behind("0.1.0", "0.2.0"))
        self.assertTrue(is_local_behind("0.1.0", "0.1.1"))
        self.assertTrue(is_local_behind("0.1.0", "1.0.0"))
        # same → not behind
        self.assertFalse(is_local_behind("0.2.0", "0.2.0"))
        # local ahead (developer WIP) → must NOT be considered behind
        self.assertFalse(is_local_behind("0.2.0", "0.1.0"))
        self.assertFalse(is_local_behind("1.0.0", "0.99.0"))
        # missing values → False (don't nudge on unknowns)
        self.assertFalse(is_local_behind(None, "0.2.0"))
        self.assertFalse(is_local_behind("0.1.0", None))
        self.assertFalse(is_local_behind(None, None))

    def test_is_local_behind_non_semver_fallback(self) -> None:
        """Non-semver strings can't be tuple-compared; fall back to inequality."""
        from update_skill import is_local_behind
        # both non-semver, differ → conservative: behind
        self.assertTrue(is_local_behind("v1-beta", "v1-rc"))
        # same non-semver → not behind
        self.assertFalse(is_local_behind("v1-beta", "v1-beta"))


class Case15_UpgradeGitBranchGuard(unittest.TestCase):
    """+upgrade git mode must refuse to run unless the user is on the target
    branch and not in detached HEAD. Wrong-branch pull semantics would either
    silently no-op or fail ff-only on diverged history (codex review Block C).
    """

    def _init_repo(self, tmp: Path) -> None:
        """Initialize a tiny git repo with one commit on `main`."""
        import subprocess
        env = {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
               "PATH": os.environ.get("PATH", "")}
        subprocess.run(["git", "init", "-q", "-b", "main", str(tmp)],
                       check=True, env=env)
        (tmp / "file.txt").write_text("hi")
        subprocess.run(["git", "-C", str(tmp), "add", "."],
                       check=True, env=env)
        subprocess.run(["git", "-C", str(tmp), "commit", "-q", "-m", "init"],
                       check=True, env=env)

    def test_current_branch_returns_main_after_init(self) -> None:
        import tempfile
        from update_skill import git_current_branch
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            self._init_repo(tmp_p)
            self.assertEqual(git_current_branch(tmp_p), "main")

    def test_current_branch_returns_none_on_detached_head(self) -> None:
        import tempfile
        import subprocess
        from update_skill import git_current_branch
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            self._init_repo(tmp_p)
            # Detach by checking out the commit SHA directly.
            sha = subprocess.run(
                ["git", "-C", str(tmp_p), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "-C", str(tmp_p), "checkout", "-q", sha],
                check=True,
                env={**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t"},
            )
            self.assertIsNone(git_current_branch(tmp_p))

    def test_current_branch_returns_feature_when_on_feature(self) -> None:
        import tempfile
        import subprocess
        from update_skill import git_current_branch
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            self._init_repo(tmp_p)
            subprocess.run(
                ["git", "-C", str(tmp_p), "checkout", "-q", "-b", "feature/x"],
                check=True,
            )
            self.assertEqual(git_current_branch(tmp_p), "feature/x")


class Case16_NormalizeTemplateId(unittest.TestCase):
    """A bare `<id>` (prefix dropped while copying from chat/notes) must
    still resolve — both humans and agents hit the backend 404 "模板不存
    在" this way. normalize_template_id is called at every template_id
    entry point in cue_api (get/update/frequent/recommended-task) so
    callers never need to pre-normalize. PR#29 only covered research_run's
    CLI; this codifies the cue_api layer coverage."""

    def _fn(self):
        from cue_api import normalize_template_id
        return normalize_template_id

    def test_bare_suffix_gets_prefixed(self):
        self.assertEqual(self._fn()("8qNgr5"), "template_8qNgr5")

    def test_already_prefixed_is_untouched(self):
        self.assertEqual(self._fn()("template_8qNgr5"), "template_8qNgr5")

    def test_none_passes_through(self):
        self.assertIsNone(self._fn()(None))

    def test_double_underscore_id_not_mangled(self):
        # `template__xWp8N` = prefix `template_` + suffix `_xWp8N` (double
        # underscore) — already starts with template_, must stay as-is.
        self.assertEqual(self._fn()("template__xWp8N"), "template__xWp8N")

    def test_bare_double_underscore_suffix_gets_one_prefix(self):
        # Bare `_xWp8N` → `template__xWp8N` (correct: one prefix prepended).
        self.assertEqual(self._fn()("_xWp8N"), "template__xWp8N")

    def test_long_slug_bare_form_gets_prefixed(self):
        self.assertEqual(
            self._fn()("corporate_credit_pre_due_diligence"),
            "template_corporate_credit_pre_due_diligence",
        )

    def test_get_template_normalizes_bare_id_in_url(self):
        from unittest.mock import patch
        import cue_api
        with patch.object(cue_api, "_request", return_value={}) as m:
            cue_api.get_template("8qNgr5")
        m.assert_called_once_with("GET", "/templates/template_8qNgr5")

    def test_update_template_normalizes_bare_id_in_url(self):
        from unittest.mock import patch
        import cue_api
        with patch.object(cue_api, "_request", return_value={"data": {}}) as m:
            cue_api.update_template("fnig0i", {"title": "x"})
        self.assertEqual(m.call_args.args[0], "PUT")
        self.assertEqual(m.call_args.args[1], "/templates/template_fnig0i")

    def test_set_template_frequent_normalizes_bare_id_in_body(self):
        from unittest.mock import patch
        import cue_api
        # frequent endpoint URL has no id; the canonical id rides in body.
        with patch.object(cue_api, "_request", return_value={"data": {}}) as m:
            cue_api.set_template_frequent("Pz0sT5", True)
        self.assertEqual(m.call_args.args[1], "/templates/frequent")
        self.assertEqual(
            m.call_args.kwargs["body"]["template_id"], "template_Pz0sT5"
        )

    def test_update_recommended_task_normalizes_bare_id_in_url(self):
        from unittest.mock import patch
        import cue_api
        with patch.object(cue_api, "_request", return_value={"data": {}}) as m:
            cue_api.update_template_recommended_task(
                "7qiAwz", schedules=[{"type": "daily", "time": "09:00"}]
            )
        self.assertEqual(
            m.call_args.args[1],
            "/templates/template_7qiAwz/recommended-task",
        )


class Case17_ValidateTemplateId(unittest.TestCase):
    """validate_template_id catches a pure-digit suffix (e.g. `142` →
    `template_142`) — the agent grabbed the buddy's numeric DB `id` or a list
    index, not the template_id string. Cue suffixes are base62 (verified
    0/159 buddies have a pure-digit suffix), so this is a guaranteed 404;
    fail fast instead of burning credits. normalize prepends the prefix,
    validate checks the suffix."""

    def _fn(self):
        from cue_api import validate_template_id
        return validate_template_id

    def test_pure_digit_suffix_rejected(self):
        # `142` → normalize → `template_142` → validate rejects.
        self.assertIsNotNone(self._fn()("template_142"))

    def test_bare_pure_digit_rejected(self):
        # bare `142` (pre-normalize) also rejected — suffix is still pure-digit.
        self.assertIsNotNone(self._fn()("142"))

    def test_canonical_id_accepted(self):
        self.assertIsNone(self._fn()("template_fnig0i"))

    def test_double_underscore_id_accepted(self):
        # `template__xWp8N` suffix `_xWp8N` has letters — not pure-digit.
        self.assertIsNone(self._fn()("template__xWp8N"))

    def test_long_slug_accepted(self):
        self.assertIsNone(self._fn()("template_corporate_credit_pre_due_diligence"))

    def test_none_accepted(self):
        self.assertIsNone(self._fn()(None))

    def test_error_message_names_the_id_and_hints_source(self):
        msg = self._fn()("template_142")
        self.assertIn("template_142", msg)
        self.assertIn("template_id", msg)  # hints: use the template_id field


class Case18_ExtractSources(unittest.TestCase):
    """extract_sources pulls citation sources from tool_chunk events so the
    agent can render 【N-M】 markers in the report. tool_call_result.tool_result
    is empty on replay; source detail (tool_name/input/output/urls) lives in
    tool_chunk.chunk = {序号: {type:'mcp', data:{...}}}."""

    def _fn(self):
        from sse_report import extract_sources
        return extract_sources

    def _chunk(self, idx, name, title, inp, out):
        import json
        return "tool_chunk", json.dumps({"chunk": {str(idx): {
            "type": "mcp", "data": {"tool_name": name, "tool_title": title,
                                     "input": inp, "output": out}}}})

    def test_extracts_index_tool_name_urls_preview(self):
        ev = [self._chunk(0, "scan_x", "财报检索", {"query": "资产减值"},
                          '{"rows":[{"source":{"pdf_url":"http://a.pdf"}}]}'),
              self._chunk(2, "get_section", "", {}, '{"stock_code":"002385"}')]
        out = self._fn()(ev)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["index"], 0)
        self.assertEqual(out[0]["tool_name"], "scan_x")
        self.assertEqual(out[0]["tool_title"], "财报检索")
        self.assertIn("http://a.pdf", out[0]["urls"])
        self.assertEqual(out[1]["index"], 2)
        self.assertEqual(out[1]["tool_name"], "get_section")

    def test_sorted_by_index_with_gaps(self):
        ev = [self._chunk(5, "t5", "", {}, ""), self._chunk(0, "t0", "", {}, "")]
        out = self._fn()(ev)
        self.assertEqual([s["index"] for s in out], [0, 5])

    def test_non_tool_chunk_events_ignored(self):
        ev = [("start_of_agent", '{"agent_name":"reporter"}'),
              ("message", '{"delta":{"content":"x"}}')]
        self.assertEqual(self._fn()(ev), [])

    def test_urls_deduped_and_clean(self):
        # output JSON has urls inside quotes; regex must stop at the closing
        # quote so the url isn't followed by JSON noise.
        ev = [self._chunk(0, "t", "", {},
                          '{"a":"http://x.pdf","b":"http://x.pdf","c":"http://y.pdf"}')]
        out = self._fn()(ev)
        self.assertEqual(out[0]["urls"], ["http://x.pdf", "http://y.pdf"])

    def test_empty_or_malformed_ignored(self):
        ev = [("tool_chunk", ""), ("tool_chunk", "{not json"),
              ("tool_chunk", '{"chunk":"not-a-dict"}'),
              ("tool_chunk", '{"chunk":{"not-digit":{}}}')]
        self.assertEqual(self._fn()(ev), [])

    def test_nested_live_shape(self):
        # live chat_stream wraps payload in {"data": {...}}; replay is flat.
        # extract_sources must read chunk through _event_data (like all
        # sibling extractors) or the appendix silently empties on live runs
        # — which PR#40's report_finalized-break made the dominant path.
        import json
        ev = [("tool_chunk", json.dumps({"data": {"chunk": {"0": {
            "type": "mcp", "data": {"tool_name": "t", "tool_title": "",
            "input": {}, "output": '{"url":"http://a.pdf"}'}}}}}))]
        out = self._fn()(ev)
        self.assertEqual(len(out), 1, "nested live shape must resolve via _event_data")
        self.assertEqual(out[0]["tool_name"], "t")
        self.assertIn("http://a.pdf", out[0]["urls"])

    def test_urls_strips_trailing_punctuation(self):
        # prose output (not JSON string) leaks trailing punctuation into the
        # regex match; rstrip cleans it so links aren't broken.
        ev = [self._chunk(0, "t", "", {}, "see http://a.pdf, and http://b.pdf)")]
        out = self._fn()(ev)
        self.assertEqual(out[0]["urls"], ["http://a.pdf", "http://b.pdf"])

    def test_urls_keeps_balanced_parens(self):
        # Wikipedia-style parenthesized paths legitimately end in ) — only
        # strip unbalanced closers, else Foo_(bar) → Foo_(bar (broken link).
        # get_wikipedia_revision is in the tool set, so this matters.
        ev = [self._chunk(0, "t", "", {},
                          '{"url":"http://en.wikipedia.org/wiki/Foo_(bar)"}')]
        out = self._fn()(ev)
        self.assertEqual(out[0]["urls"], ["http://en.wikipedia.org/wiki/Foo_(bar)"])

    def test_extracts_rows_from_scan_output(self):
        # M-level: scan-class output has rows[M] = {company, title, summary,
        # source.pdf_url, page_range}. 【N-M】 maps to rows[M] precisely.
        import json
        out = json.dumps({"rows": [
            {"company": "002385", "title": "商誉减值", "summary": "大北农...",
             "source": {"pdf_url": "http://a.pdf"}, "page_range": [10, 20]},
            {"company": "600089", "title": "存货跌价", "summary": "特变电工...",
             "source": {"pdf_url": "http://b.pdf"}, "page_range": [30, 40]},
        ]})
        ev = [self._chunk(0, "scan_x", "财报检索", {"query": "资产减值"}, out)]
        s = self._fn()(ev)
        self.assertEqual(len(s[0]["rows"]), 2)
        r0 = s[0]["rows"][0]
        self.assertEqual(r0["m"], 0)
        self.assertEqual(r0["company"], "002385")
        self.assertEqual(r0["pdf_url"], "http://a.pdf")
        self.assertEqual(r0["page_range"], [10, 20])
        self.assertIn("大北农", r0["summary"])
        self.assertEqual(s[0]["rows"][1]["m"], 1)

    def test_rows_empty_for_truncated_output(self):
        # get_section output is truncated (115871→8046 chars) → json.loads
        # fails → rows=[] (N-level fallback, not a crash).
        ev = [self._chunk(0, "get_section", "", {},
                          '{"stock_code":"002385","summary":"...[已截断]')]
        s = self._fn()(ev)
        self.assertEqual(s[0]["rows"], [])

    def test_rows_empty_for_no_rows_output(self):
        ev = [self._chunk(0, "yearly_income", "", {}, "No valid data loaded")]
        s = self._fn()(ev)
        self.assertEqual(s[0]["rows"], [])


if __name__ == "__main__":
    # Unbuffered + verbose for skill author workflow.
    unittest.main(verbosity=2)
