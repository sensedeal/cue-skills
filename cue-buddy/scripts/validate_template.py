#!/usr/bin/env python3
"""Client-side spec validator for Cue buddy templates.

Mirrors the Hard Rules from SKILL.md and `references/hard-rules.md`.
Run BEFORE `cue_api.create_template(payload)` to catch issues without
spending LLM credits.

Stdlib only. Returns list[Finding]; non-empty means the template
violates the spec.

Usage:
  # validate a JSON file
  python3 validate_template.py path/to/template.json

  # validate stdin JSON
  cat template.json | python3 validate_template.py -

  # as a library
  from validate_template import validate, Finding
  findings = validate(payload_dict)
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "title",
    "primary_category",
    "secondary_category",
    "input_form_spec",
    "goal",
    "search_plan",
    "report_format",
)

LLM_PROSE_FIELDS = (
    "input_form_spec",
    "goal",
    "search_plan",
    "report_format",
)

# Tool-name prefixes that must never leak into prose. Cue's tool inventory
# follows `<verb>_<noun>` snake case. The verbs below capture the main
# tool families.
FORBIDDEN_TOOL_PREFIXES = ("get_", "list_", "find_", "search_tool", "crawl_tool")

# Regex form of FORBIDDEN_TOOL_PREFIXES. Single source of truth — both
# `_check_no_tool_names` and (optionally) other repos' lints should import
# this to avoid validator/runtime drift (codex !450 r3 Block 5).
# - get_*/list_*/find_*: tool family verbs, snake_case
# - search_tool*/crawl_tool*: tool-naming convention with optional suffix
#   (search_tool_company / crawl_tool_disclosure / etc.)
#
# Boundaries use explicit ASCII-word-char lookarounds, NOT `\b`: in Python 3
# `\w` (hence `\b`) treats CJK as word chars, so `\b` does NOT fire between a
# Chinese char and the ASCII tool name. A CJK-glued leak with no spaces —
# `使用get_cninfo_disclosure_search工具` — slipped past R5 and shipped to prod
# (Pz0sT5, found 2026-06-24). The lookarounds assert the match isn't glued to
# another ASCII identifier char on either side, so CJK-adjacent leaks ARE
# caught, while genuine substrings of a larger ASCII identifier
# (`myget_x` / `get_xBar`) are still NOT flagged.
TOOL_NAME_LEAK_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    r"get_[a-z_]+|"
    r"list_[a-z_]+|"
    r"find_[a-z_]+|"
    r"search_tool[a-z_]*|"
    r"crawl_tool[a-z_]*"
    r")(?![A-Za-z0-9_])"
)

# Decision phrases that turn the buddy into a verdict-maker.
FORBIDDEN_VERDICT_PHRASES = (
    "建议进入",
    "谨慎进入",
    "暂缓进入",
    "是否建议进入",
    "进入尽调建议",
    "建议授信",
    "拒绝授信",
)


@dataclasses.dataclass
class Finding:
    severity: str   # "error" | "warning"
    field: str
    message: str

    def __str__(self) -> str:
        mark = "❌" if self.severity == "error" else "⚠️"
        return f"  {mark} [{self.field}] {self.message}"


# ---------------------------------------------------------------------------
# Field-by-field checks
# ---------------------------------------------------------------------------


def _check_identity(p: dict, out: list[Finding]) -> None:
    for f in ("title", "primary_category", "secondary_category"):
        v = p.get(f)
        if not isinstance(v, str) or not v.strip():
            out.append(Finding("error", f, "缺失或为空"))
    for f in LLM_PROSE_FIELDS:
        v = p.get(f)
        if not isinstance(v, str) or not v.strip():
            out.append(Finding("error", f, "缺失或为空"))


def _check_input_form_spec(intro: str, out: list[Finding]) -> None:
    # Must be single line
    if "\n" in intro.strip("\n"):
        out.append(Finding("error", "input_form_spec", "必须单行，不能含换行"))
    # Must start with 需提供:
    if not (intro.startswith("需提供:") or intro.startswith("需提供：")):
        out.append(Finding("error", "input_form_spec", "必须以 `需提供:` 开头"))
    # Must reference 可提供 + 默认
    if "可提供:" not in intro and "可提供：" not in intro:
        out.append(Finding("error", "input_form_spec", "缺少 `可提供:` 段"))
    if "默认:" not in intro and "默认：" not in intro:
        out.append(Finding("warning", "input_form_spec", "建议带 `(默认: ...)` 兜底值"))
    # Three-segment variable [属性_主体_类型]
    three_seg = re.compile(r"\[[一-鿿]+_[一-鿿]+_[一-鿿]+\]")
    if not three_seg.search(intro):
        out.append(
            Finding(
                "error",
                "input_form_spec",
                "必须至少包含一个三段式变量 [属性_主体_类型]，例如 [目标_授信_企业]",
            )
        )


# title 是搭子在卡片上的「名字」：简洁有力、体现价值。砍虚词，但**别过度简化丢掉区分价值**。
_TITLE_FLUFF = ["情报简报", "与分析", "全量", "细项", "深度解读", "公开资质"]


def _check_title(title: str, out: list[Finding]) -> None:
    """title = 卡片标题/搭子名：~≤8-10 字、价值优先；砍虚词（公开/全量/细项/与分析/简报/
    深度），但保留体现价值的词（如 信披属实 / 需求匹配 / 海外执法），别为短而短。"""
    t = title.strip()
    n = len(t)
    if n > 12:
        out.append(
            Finding(
                "warning",
                "title",
                f"标题 {n} 字偏长：建议精简到 ~8-10 字、价值优先；砍虚词但保留区分价值的词"
                "（别过度简化丢掉价值）",
            )
        )
    fluff = [w for w in _TITLE_FLUFF if w in t]
    if fluff:
        out.append(
            Finding(
                "warning",
                "title",
                f"标题含可删虚词 {fluff}：去掉更简洁；但保留体现价值的词",
            )
        )


# 实现/技术内部词不应出现在 goal —— goal 是搭子在 playbook 卡片上的「简介」，讲
# **解决什么问题 / 给什么价值**，不讲「怎么实现」。怎么做属于 search_plan。
_GOAL_IMPL_LEAK = [
    "LangGraph",
    "循环图",
    "批处理",
    "MECE",
    "pipeline",
    "管道",
    "状态机",
    "工作流",
    "原子建模",
    "全接口",
    "轨道",
    "向量",
    "大模型",
    "prompt",
    "评估模型",
    "估值模型",
    "自适应",
]


def _check_goal(goal: str, out: list[Finding]) -> None:
    """goal 即搭子的简介/卡片文案：要简洁有力、价值优先、不硬码主体、不泄漏实现。
    （怎么做的细节放 search_plan；免责边界放避坑指南 / report_format。）"""
    g = goal.strip()
    n = len(g)
    # 1. 简洁有力：goal 是卡片简介，不是运行手册。
    if n > 200:
        out.append(
            Finding(
                "error",
                "goal",
                f"长度 {n} 过长（>200）：goal 是搭子简介/卡片文案，应简洁有力、价值优先；"
                "把维度与「怎么做」放进 search_plan，不要堆进 goal",
            )
        )
    elif n > 100:
        out.append(
            Finding(
                "warning",
                "goal",
                f"长度 {n} 偏长（>100）：建议收敛到一句价值优先的简介（参考 ~40-80 字）",
            )
        )
    # 2. 不泄漏实现/技术词（讲价值不讲实现）。
    leaks = [w for w in _GOAL_IMPL_LEAK if w.lower() in g.lower()]
    if leaks:
        out.append(
            Finding(
                "error",
                "goal",
                f"出现实现/技术内部词 {leaks[:4]}：goal 讲价值不讲实现，删除这些表述",
            )
        )
    # 3. 免责/边界声明不进 goal（卡片不该被法律尾注占满）。
    if re.search(r"(不替代|不构成|严格不|仅(?:做|提供|基于|在公开)|凡(?:公开|未|无|来源))", g):
        out.append(
            Finding(
                "warning",
                "goal",
                "goal 含免责/边界声明：免责放 search_plan 避坑指南或 report_format，"
                "卡片简介只讲价值",
            )
        )
    # 4. 长「作为…助手」角色前缀：建议价值/解决什么问题开头（角色由 input_form/场景体现）。
    if re.match(r"^作为[^，。]{4,40}助手[，,]", g) and n > 90:
        out.append(
            Finding(
                "warning",
                "goal",
                "以「作为…助手，」长角色前缀 + 长串「怎么做」开头：建议改为价值优先句式",
            )
        )
    # 5. 拒绝编号清单。
    numbered = re.findall(r"^\s*\d+\.\s", g, re.MULTILINE)
    if numbered:
        out.append(
            Finding(
                "error",
                "goal",
                f"必须是简洁有力的简介，不能是编号清单（发现 {len(numbered)} 个编号）",
            )
        )


# Dimension heading: `**[[标签] 维度名]**` (R3 contract).
# Label allows Chinese / English / digits / dashes — buddy authors may use
# `[[ESG-2026]]`, `[[A股]]`, `[[2026]]` etc. (codex !450 r3 broadening).
# Only excludes `]` and newline inside the label to keep block boundaries
# unambiguous. Captures full match + position so we can slice into blocks.
_SEARCH_PLAN_DIM_RE = re.compile(r"\*\*\[\[[^\]\n]+\][^\[\]\n]+\]\*\*")


def _split_search_plan_blocks(sp: str) -> list[tuple[str, int, int]]:
    """Slice search_plan into per-dimension blocks.

    Returns list of ``(heading_text, body_start, body_end)`` where
    ``body`` is the text between this dimension's heading and the next
    (or end of string). Used by R3 block-level checks so a missing
    `**数据路由**` in dimension 3 of 4 is caught precisely instead of
    being masked by global count.
    """
    matches = list(_SEARCH_PLAN_DIM_RE.finditer(sp))
    blocks: list[tuple[str, int, int]] = []
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(sp)
        blocks.append((m.group(0), body_start, body_end))
    return blocks


def _check_search_plan(sp: str, out: list[Finding]) -> None:
    # Source-clustered dimension headings
    blocks = _split_search_plan_blocks(sp)
    dim_count = len(blocks)
    if dim_count < 2:
        out.append(
            Finding(
                "error",
                "search_plan",
                f"必须有 ≥2 个 `**[[标签] 维度名]**` 形式的源聚类维度，当前 {dim_count}",
            )
        )
    if dim_count > 5:
        out.append(
            Finding(
                "warning",
                "search_plan",
                f"维度数 {dim_count} > 5，可能粒度过细",
            )
        )

    # R3 block-level check: each dimension must contain 数据路由/执行动作/
    # 验证策略 三件套. Codex !450 r3 reported global `sp.count(...)` masked
    # per-dimension misses when global count happened to ≥ 2.
    for heading, body_start, body_end in blocks:
        body = sp[body_start:body_end]
        for required in ("**数据路由**", "**执行动作**", "**验证策略**"):
            if required not in body:
                out.append(
                    Finding(
                        "error",
                        "search_plan",
                        f"维度 {heading} 缺 `{required}`",
                    )
                )

    # 信源与数据策略 (kept as document-level warning — these are heuristics)
    for required in ("信源偏好", "避坑指南", "数据裁决逻辑"):
        if required not in sp:
            out.append(
                Finding("warning", "search_plan", f"建议含 `{required}` 段")
            )


# Section heading: `## N. 标题` or `## N、标题` (R4 contract).
# Reject decimal `## 1.1` via negative lookahead — sub-section.
_REPORT_SECTION_HEADING_RE = re.compile(
    r"(?m)^##\s*(\d+)[.、](?!\d)\s*(.+?)\s*$"
)


def _split_report_sections(rf: str) -> list[tuple[int, str, int, int]]:
    """Slice report_format into per-section blocks.

    Returns list of ``(number, title, body_start, body_end)``. Each
    block's body is the text between this section heading and the next
    (or end of string). Used by R4 block-level checks.
    """
    matches = list(_REPORT_SECTION_HEADING_RE.finditer(rf))
    blocks: list[tuple[int, str, int, int]] = []
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(rf)
        blocks.append((int(m.group(1)), m.group(2).strip(), body_start, body_end))
    return blocks


_BLUEPRINT_FIELDS = ("**研究目标**", "**逻辑链条**", "**信息需求**", "**输出形式**")


def _check_report_format(rf: str, out: list[Finding]) -> None:
    # `> **关键配置**` opener
    if "> **关键配置**" not in rf:
        out.append(
            Finding(
                "error",
                "report_format",
                "必须以 `> **关键配置**` 引用块开头（含 目标对象/报告类型/基调设定/核心命题）",
            )
        )
    # Title with variable
    title_m = re.search(r"^#\s+(.+)$", rf, re.MULTILINE)
    if not title_m:
        out.append(Finding("error", "report_format", "缺少 `# <title>` 一级标题"))
    else:
        title = title_m.group(1)
        if not re.search(r"\[[一-鿿]+_[一-鿿]+_[一-鿿]+\]", title):
            out.append(
                Finding(
                    "error",
                    "report_format",
                    f"主标题必须含三段式变量（例如 # [目标_<场景>_主体] ...），当前: {title!r}",
                )
            )

    sections = _split_report_sections(rf)

    if len(sections) < 3:
        out.append(
            Finding(
                "error",
                "report_format",
                f"章节数 {len(sections)} 过少（< 3），结构化报告至少要 3 章",
            )
        )
    # Sequential numbering
    numbers = [n for n, _, _, _ in sections]
    if numbers != list(range(1, len(numbers) + 1)):
        out.append(
            Finding(
                "error",
                "report_format",
                f"章节编号必须从 1 开始连续递增，当前: {numbers}",
            )
        )

    # R4 block-level check: each section block must contain its blueprint
    # quote and the four blueprint fields. Codex !450 r3 reported global
    # `rf.count(...)` masked per-section misses (and missing-marker were
    # warning, not error — but R4 doc + R7 declare 4 件套 mandatory).
    for number, title_text, body_start, body_end in sections:
        body = rf[body_start:body_end]
        if "> **[执行蓝图]**" not in body:
            out.append(
                Finding(
                    "error",
                    "report_format",
                    f"第 {number} 节「{title_text}」缺 `> **[执行蓝图]**` 引用块",
                )
            )
            # No blueprint block → field-level checks would all fire,
            # noisy; skip per-field checks for this section.
            continue
        for field in _BLUEPRINT_FIELDS:
            if field not in body:
                out.append(
                    Finding(
                        "error",
                        "report_format",
                        f"第 {number} 节「{title_text}」蓝图缺 `{field}`",
                    )
                )

    # Output spec must not list specific columns (file-level — column leak
    # pattern is unambiguous, no per-block need)
    output_lines = [ln for ln in rf.splitlines() if "**输出形式**" in ln]
    column_list_pattern = re.compile(r"\([^)]*?/[^)]*?/[^)]*?\)")
    column_leaks = [ln for ln in output_lines if column_list_pattern.search(ln)]
    if column_leaks:
        out.append(
            Finding(
                "error",
                "report_format",
                f"`输出形式` 不要列具体表格列名（应由 reporter prompt 决定），发现 {len(column_leaks)} 处违规",
            )
        )
    # Standard disclaimer
    if "本报告基于公开信息编制" not in rf and "免责声明" not in rf:
        out.append(
            Finding("warning", "report_format", "末尾建议包含标准化免责声明")
        )


# R9 「可执行」机检 (codex !444+ r1 Block A 收紧):
# - 显式引导词 (动作类): 直接禁止
# - 字段名占位词: "企业名称/公司名称/..." 这种 placeholder-style 词
# - 示例标记: "示例/例如/占位/placeholder"
# - 全角/半角冒号都覆盖
_TASK_INPUT_GUIDE_TOKENS = (
    "请输入",
    "请提供",
    "可选补充",
    "可提供",
    "可选填",
    "默认:",
    "默认：",
    "企业名称",
    "公司名称",
    "主体名称",
    "统一社会信用代码",
    "示例",
    "例如",
    "如:",
    "如：",
    "占位",
    "placeholder",
)

# task_input 会原样展示并提交给 agent，不能拿它承载内部编排说明。
# 精确词避免误伤正常业务语言；英文比较时统一 lower-case。
_TASK_INPUT_INTERNAL_TOKENS = (
    "researcher",
    "reporter",
    "coordinator",
    "supervisor",
    "file_retrieval",
    "content_digest",
    "agent=",
    "tool=",
)
_TASK_INPUT_CALL_COUNT_RE = re.compile(
    r"(?:调用|检索|读取|摘要|提炼)\s*(?:至少|不少于|不低于)?\s*\d+\s*次"
    r"|(?:至少|不少于|不低于)\s*\d+\s*次(?:调用|检索|读取|摘要|提炼)"
)

# 占位变量形态 `<目标_X_主体>` / `[属性_主体_类型]` / `<请填写...>`
# 等显式 placeholder syntax,与 input_form_spec 三段式变量同样禁止
# 出现在 task_input(task_input 是要直接 submit 的具体值,变量在前端无渲染)
_TASK_INPUT_PLACEHOLDER_RE = re.compile(
    r"[\[<][^\]\n>]*(?:[一-鿿]_[一-鿿]|名称|主体|代码|变量|占位|placeholder|请)[^\]\n>]*[\]>]"
)


def _check_task_input(payload: dict, out: list[Finding]) -> None:
    """R9: task_input 必须是可直接执行的具体值，不是 placeholder 引导文案。

    task_input 是前端"使用推荐方案"按钮直接 submit 的 agent 输入字符串；
    UI 在 `推荐方案 ({task_input})` 单括号内渲染，过长或含引导词会把
    按钮挤变形 + 跑空。引导文案应放 input_form_spec。

    Severity (与 R9 doc 对齐):
    - 「可执行」违规 (引导词 / 占位 / 多行 / 长度 / 空白) = error
    - 「用户语言」违规 (内部节点/工具/调用次数) = error
    - 「代表性」属设计审视, doc 强调, 本 lint 不机检
    """
    v = payload.get("task_input")
    if v is None or v == "":
        return
    if not isinstance(v, str):
        out.append(Finding("error", "task_input", f"必须是字符串，当前类型 {type(v).__name__}"))
        return
    if not v.strip():
        out.append(
            Finding(
                "error",
                "task_input",
                "不能是空白字符串；不设置请删除该字段或置为空串 ''",
            )
        )
        return
    if "\n" in v:
        out.append(Finding("error", "task_input", "必须单行，不能含换行"))
    if len(v) > 30:
        out.append(
            Finding(
                "error",
                "task_input",
                f"长度 {len(v)} > 30，UI `推荐方案 ({{task_input}})` 单括号易挤变形；"
                f"应是单值（如企业名/主体名），引导文案放 input_form_spec",
            )
        )
    hits = [tok for tok in _TASK_INPUT_GUIDE_TOKENS if tok in v]
    if hits:
        out.append(
            Finding(
                "error",
                "task_input",
                f"含引导词 {hits} — task_input 必须是「可直接执行的具体值」"
                f"（如 buddy author 选定的代表性主体），引导文案应放 input_form_spec",
            )
        )
    lowered = v.lower()
    internal_hits = [tok for tok in _TASK_INPUT_INTERNAL_TOKENS if tok in lowered]
    if internal_hits or _TASK_INPUT_CALL_COUNT_RE.search(v):
        detail = list(internal_hits)
        if _TASK_INPUT_CALL_COUNT_RE.search(v):
            detail.append("内部调用次数")
        out.append(
            Finding(
                "error",
                "task_input",
                f"含内部编排说明 {detail} — task_input 会直接展示并提交，"
                "必须保持真实用户语言；节点/工具/次数/顺序应放模板、runtime 或验收层",
            )
        )
    if _TASK_INPUT_PLACEHOLDER_RE.search(v):
        out.append(
            Finding(
                "error",
                "task_input",
                "含 `<...>` / `[...]` 形式占位变量；task_input 必须是已 resolve 的"
                "具体值（buddy author 在 seed 阶段就该选定主体）。占位变量属"
                "input_form_spec 三段式 [属性_主体_类型]",
            )
        )


def _check_no_tool_names(payload: dict, out: list[Finding]) -> None:
    """R5 enforcement — reuses TOOL_NAME_LEAK_RE (file-level constant).

    Covers all FORBIDDEN_TOOL_PREFIXES families: get_/list_/find_/
    search_tool*/crawl_tool*. Codex !450 r3 reported earlier regex
    missed search_tool*/crawl_tool* despite the constant listing them.
    """
    for f in LLM_PROSE_FIELDS:
        v = payload.get(f, "") or ""
        hits = TOOL_NAME_LEAK_RE.findall(v)
        if hits:
            out.append(
                Finding(
                    "error",
                    f,
                    f"出现 {len(hits)} 个工具名 (e.g. {hits[:3]})，工具名不允许出现在模板文本中",
                )
            )


def _check_no_admission_verdict(payload: dict, out: list[Finding]) -> None:
    text = "\n".join(payload.get(f, "") or "" for f in LLM_PROSE_FIELDS)
    leaks = [p for p in FORBIDDEN_VERDICT_PHRASES if p in text]
    if leaks:
        out.append(
            Finding(
                "error",
                "(any prose)",
                (
                    f"含准入决策语 {leaks} — 搭子是证据收集器，不是决策者；"
                    f"应改写为'风险信号定级'或'关键发现'等描述性语言"
                ),
            )
        )


_THREE_SEG_INNER = r"[一-鿿]+_[一-鿿]+_[一-鿿]+"


def _extract_intro_main_var(intro: str) -> str | None:
    """The 需提供: 后的第一个三段式变量是主变量（标题与关键配置必须复用它）。"""
    m = re.search(r"需提供\s*[:：]\s*\[(" + _THREE_SEG_INNER + r")\]", intro)
    return m.group(1) if m else None


def _extract_title_var(report_format: str) -> str | None:
    m = re.search(
        r"(?m)^#\s+[^\n]*?\[(" + _THREE_SEG_INNER + r")\]",
        report_format,
    )
    return m.group(1) if m else None


def _extract_config_target_var(report_format: str) -> str | None:
    m = re.search(
        r"(?m)^>\s*[-\*]?\s*\*\*目标对象\*\*\s*[:：]\s*\[("
        + _THREE_SEG_INNER
        + r")\]",
        report_format,
    )
    return m.group(1) if m else None


def _check_variable_consistency(payload: dict, out: list[Finding]) -> None:
    """R6: 三段式变量在 input_form_spec / 主标题 / 关键配置·目标对象 三处必须一致.

    前端会用 input_form_spec 里 `需提供:` 的变量值替换标题与关键配置中
    出现的同名变量。三处不一致 → 用户填了输入但报告标题或配置块仍
    显示原始变量名，造成"标题写 [目标_X_企业]，内容讲的是别的"。
    """
    intro = payload.get("input_form_spec") or ""
    rf = payload.get("report_format") or ""
    if not (isinstance(intro, str) and isinstance(rf, str)):
        return

    intro_var = _extract_intro_main_var(intro)
    title_var = _extract_title_var(rf)
    config_var = _extract_config_target_var(rf)

    found = {
        "input_form_spec (需提供)": intro_var,
        "report_format 主标题": title_var,
        "report_format 关键配置·目标对象": config_var,
    }
    present = {loc: var for loc, var in found.items() if var}

    # Only enforce consistency when at least two anchors are present —
    # 单个变量在场无所谓"一致"问题，其它检查会兜底。
    if len(present) < 2:
        return

    unique = set(present.values())
    if len(unique) > 1:
        details = "; ".join(f"{loc}=[{var}]" for loc, var in present.items())
        out.append(
            Finding(
                "error",
                "(variable consistency)",
                (
                    f"R6: 三段式变量必须三处一致 — {details}. "
                    f"前端用 input_form_spec 的'需提供:'变量替换标题与关键配置"
                    f"中的同名变量，名字不同将无法联动渲染."
                ),
            )
        )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def _known_scenes_from_capabilities() -> list[str] | None:
    """Best-effort fetch of the controlled playbook scene vocabulary from
    `GET /api/tools/capabilities` (field `playbook_scenes`). Returns None when
    offline / no key / field absent — so `+validate` stays usable offline and
    never emits a false scene warning. The server is the single source of truth
    for playbook scenes."""
    try:
        import cue_api  # same scripts/ dir; needs a key + network

        # 短超时：这是 best-effort lint，不应因网络挂起拖慢 +validate（codex C）。
        caps = cue_api.capabilities(timeout=3.0)
        scenes = caps.get("playbook_scenes") if isinstance(caps, dict) else None
        if isinstance(scenes, list) and scenes:
            return [str(s) for s in scenes]
    except (Exception, SystemExit):
        # 无 key 时 cue_api.load_config() 抛 SystemExit（非 Exception，必须显式捕获，
        # 否则离线/无 key 跑 +validate 会直接退出码 2 而非跳过场景检查）（codex A）。
        return None
    return None


def _check_scene_vocab(
    payload: dict, out: list[Finding], scenes: list[str] | None
) -> None:
    """[warning] secondary_category 建议复用受控场景词表，让同类搭子在 playbook 聚类。
    仅在拿到词表时检查（offline 不误报）。非受控场景不阻断创建，只是不会进 playbook
    的固定场景（除非积累到浮现阈值）。"""
    if not scenes:
        return
    sc = payload.get("secondary_category")
    if not isinstance(sc, str) or not sc.strip():
        return
    if sc.strip() not in scenes:
        out.append(
            Finding(
                "warning",
                "secondary_category",
                (
                    f"`{sc}` 不在受控场景词表内。要进 playbook 的固定场景，请原样复用其一："
                    f"{ '、'.join(scenes) }；自定义场景仅在积累足够同类搭子后才会自动浮现。"
                ),
            )
        )


# R10: 报告时间字段约定 — 前端解析依赖 `报告时间: YYYY年MM月DD日` 字面。
# 后端 reporter prompt emits this exact key; 前端按这个 key 渲染。
# 变体如 `报告生成时间` / `生成时间` /
# `报告日期` / `生成日期` / `生成时刻` 一律不允许。
_WRONG_TIME_FIELDS = (
    "报告生成时间", "生成时间", "报告日期", "生成日期", "生成时刻",
)
_REPORT_TIME_OK_RE = re.compile(r"(?m)^报告时间\s*[:：]\s*YYYY年MM月DD日\s*$")
_REPORT_TIME_FUZZY_RE = re.compile(r"(?m)^[>\s]*报告时间\s*[:：]")
_BAD_TIME_PLACEHOLDER_RE = re.compile(r"<由\s*LLM\s*填充>|<由\s*reporter\s*填|\{CURRENT_DATE\}")


def _check_report_time_field(rf: str, out: list[Finding]) -> None:
    """R10: report_format 必须含 `报告时间: YYYY年MM月DD日` 字面。

    Three failure modes:
      1. Wrong field name (报告生成时间 / 生成时间 / 报告日期 / 生成日期 / 生成时刻)
         → error. Frontend renders by exact key `报告时间`; variants get dropped
         or rendered as plain text.
      2. Non-standard placeholder (<由 LLM 填充> / <由 reporter 填...> /
         {CURRENT_DATE}) → error. Reporter LLM recognizes literal
         `YYYY年MM月DD日` and fills it from {CURRENT_YEAR}/MONTH/DAY; custom
         placeholders may leak the literal string into the published report.
      3. Missing entirely → warning. Strongly recommended for FE display.
    """
    # (1) wrong variants — error each
    for wrong in _WRONG_TIME_FIELDS:
        if wrong in rf:
            out.append(
                Finding(
                    "error",
                    "report_format",
                    f"R10: 字段名必须是 `报告时间`,不能是 `{wrong}` — 前端按 `报告时间` "
                    f"精确解析,变体会让 FE 识别不到时间行(或渲染成普通正文)。",
                )
            )
    # (2) bad placeholder
    if _BAD_TIME_PLACEHOLDER_RE.search(rf):
        out.append(
            Finding(
                "error",
                "report_format",
                "R10: 不准用 `<由 LLM 填充>` / `<由 reporter 填...>` / `{CURRENT_DATE}` "
                "等自创占位符 — 请写字面 `YYYY年MM月DD日`,reporter LLM 自动识别此 "
                "pattern 并填入北京时间",
            )
        )
    # (3) presence / format
    if _REPORT_TIME_OK_RE.search(rf):
        return  # standard form present, all good
    if _REPORT_TIME_FUZZY_RE.search(rf):
        out.append(
            Finding(
                "error",
                "report_format",
                "R10: `报告时间:` 后面必须是字面 `YYYY年MM月DD日` "
                "(无引用块前缀 `>`、放在主标题正下一行)",
            )
        )
    else:
        out.append(
            Finding(
                "warning",
                "report_format",
                "R10: 建议在主标题下一行加 `报告时间: YYYY年MM月DD日` "
                "(前端依赖此字段渲染报告时间;缺失会显示成空或'未知日期')",
            )
        )


def validate(payload: dict, scenes: list[str] | None = None) -> list[Finding]:
    """Run all checks on a template payload. Return list of findings.

    `scenes`: optional controlled playbook scene vocabulary (for the R-scene
    warning). Pass the list from `+capabilities` (field `playbook_scenes`);
    when None the scene check is skipped (offline-safe)."""
    out: list[Finding] = []
    _check_identity(payload, out)
    if isinstance(payload.get("title"), str):
        _check_title(payload["title"], out)
    if isinstance(payload.get("input_form_spec"), str):
        _check_input_form_spec(payload["input_form_spec"], out)
    if isinstance(payload.get("goal"), str):
        _check_goal(payload["goal"], out)
    if isinstance(payload.get("search_plan"), str):
        _check_search_plan(payload["search_plan"], out)
    if isinstance(payload.get("report_format"), str):
        _check_report_format(payload["report_format"], out)
        _check_report_time_field(payload["report_format"], out)
    _check_no_tool_names(payload, out)
    _check_no_admission_verdict(payload, out)
    _check_variable_consistency(payload, out)
    _check_task_input(payload, out)
    _check_scene_vocab(payload, out, scenes)
    return out


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="validate_template.py",
        description=(
            "Lint a Cue buddy template JSON against the 7 hard rules + R9 "
            "(see ../references/hard-rules.md). Exit 0 if valid (warnings "
            "allowed) or 1 if any error-level finding."
        ),
        epilog=(
            "Examples:\n"
            "  python3 validate_template.py path/to/template.json\n"
            "  cat template.json | python3 validate_template.py -\n"
            "  python3 -c 'from validate_template import validate; print(validate(payload))'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "src",
        nargs="?",
        help="Path to a JSON template file, or '-' to read from stdin",
    )
    args = parser.parse_args()

    if args.src is None:
        parser.print_help()
        return 0
    src = args.src
    if src == "-":
        payload = json.loads(sys.stdin.read())
    else:
        payload = json.loads(Path(src).read_text(encoding="utf-8"))

    # 受控场景词表：best-effort 从 capabilities 拉（offline/无 key 时为 None → 跳过场景检查）
    findings = validate(payload, scenes=_known_scenes_from_capabilities())
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    print(f"\nvalidate: {payload.get('template_id') or payload.get('title') or '(unnamed)'}")
    print(f"  errors:   {len(errors)}")
    print(f"  warnings: {len(warnings)}")
    print()
    for f in findings:
        print(f)
    print()
    if errors:
        print("→ 校验未通过。请按上述错误改后再 +create。")
        return 1
    if warnings:
        print("→ 校验通过(含建议优化项)。可 +create，但建议先看下 warnings。")
        return 0
    print("→ 校验完全通过。可 +create。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
