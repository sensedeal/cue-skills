#!/usr/bin/env python3
"""+tune verb — use the seed: bypass on /api/generate_template to ask
the LLM to revise an existing template based on a list of issues, then
validate, diff-preview, and (on confirmation) PUT the update.

Usage:
    python3 tune_template.py <template_id> --issues <issues.txt>
    python3 tune_template.py <template_id> --message "把章节 4 拆成 4 和 5"
    cat issues.txt | python3 tune_template.py <template_id> --stdin

Flow:
    1. GET /api/templates/<id>             → current template
    2. Build user_requirement = current_template_json + issues
    3. POST /api/generate_template         → streamed JSON of 4 fields
    4. Local validate (validate_template.validate)
    5. Show diff of (input_form_spec / goal / search_plan / report_format)
    6. Ask confirmation
    7. PUT /api/templates/<id>             → persist

Notes:
    - Consumes Cue credits (typically 1-3 积分 per tune call).
    - The generated draft is **shown to user first**; no auto-PUT.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
from pathlib import Path

# Make sibling modules importable when invoked directly
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from cue_api import (  # noqa: E402
    CueAPIError,
    generate_template,
    get_template,
    load_config,
    normalize_template_id,
    update_template,
    validate_template_id,
)
from validate_template import validate  # noqa: E402


LLM_FIELDS = ("input_form_spec", "goal", "search_plan", "report_format")


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_user_requirement(current: dict, issues: str) -> str:
    """Compose the message sent to /api/generate_template.

    Seed-bypass mode: backend uses ONLY user_requirement (no chat history).
    So we hand it the full current template + the desired fixes.
    """
    # 后端契约改造后已 strict 输出 canonical `input_form_spec` 字段;
    # `introduction` 字段已被 drop。tune script 全量切到 canonical 命名。
    current_form_spec = current.get("input_form_spec") or ""
    return (
        "请基于以下现有模板，按问题清单做最小且必要的修改，"
        "重新生成 input_form_spec / goal / search_plan / report_format 4 个字段。"
        "保持业务语义不变，仅修复指出的问题；"
        "其余部分保持稳定，不要大幅改写。\n\n"
        "【当前模板】\n"
        f"标题: {current.get('title', '')}\n"
        f"分类: {current.get('primary_category', '')} / {current.get('secondary_category', '')}\n\n"
        f"input_form_spec (用户输入表单规范):\n{current_form_spec}\n\n"
        f"goal:\n{current.get('goal', '')}\n\n"
        f"search_plan:\n{current.get('search_plan', '')}\n\n"
        f"report_format:\n{current.get('report_format', '')}\n\n"
        "【问题清单】\n"
        f"{issues}\n\n"
        "【硬约束（违反将被本地校验拒绝）】\n"
        "1. input_form_spec 单行,含三段式变量 [属性_主体_类型],以 `需提供:` 开头\n"
        "2. goal 单段攻击力句式，无编号清单，无'建议进入/谨慎进入/暂缓进入'决策语\n"
        "3. search_plan 按数据源聚类（**[[标签] 维度]** 形式），每维度含 数据路由/执行动作/验证策略\n"
        "4. report_format 主标题含三段式变量，章节连续递增，每章 `> **[执行蓝图]**` 含 4 件套\n"
        "5. 所有字段不出现工具名（get_*/list_*/find_*/search_tool*/crawl_tool*）\n"
    )


# ---------------------------------------------------------------------------
# Streaming + parse
# ---------------------------------------------------------------------------


def call_generate(current: dict, issues: str) -> dict:
    """Returns dict with the 4 LLM fields parsed from the stream.

    Robustness:
    - Strips stray `\\r` injected between SSE token boundaries (seen
      sporadically on /generate_template stream — caused
      `Invalid control character at: line 1 column 4` even when the
      LLM output was semantically valid).
    - Uses ``strict=False`` so embedded literal newlines inside string
      values don't reject the parse.
    """
    conv_id = f"seed:tune:{int(time.time())}"
    req = build_user_requirement(current, issues)
    print("[+tune] streaming generate_template …", file=sys.stderr)
    raw = generate_template(conv_id, req)
    # Strip stray CRs first — see docstring above.
    text = raw.replace("\r", "").strip()
    # Try to find the outermost {...} JSON block
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise RuntimeError(f"could not locate JSON in stream output (head={text[:200]!r})")
    blob = text[start : end + 1]
    return json.loads(blob, strict=False)


# ---------------------------------------------------------------------------
# Format normalization
# ---------------------------------------------------------------------------
#
# LLM-driven `+tune` and `+author` calls produce structurally-correct prose
# but commonly miss specific markdown markers required by the strict
# validator (e.g. `**[[标签] 维度]**` bold-bracket cluster headings,
# `# title` whitespace after the `#`, Chinese numeral sections instead of
# arabic). Each LLM run rejects on those mechanical formatting nits even
# when the *content* is fine — wasting credits to re-prompt.
#
# These normalizers fix mechanical formatting issues in-place after the LLM
# call and before the validator. They never change semantic content (no
# fields are added, dropped, or paraphrased). Opt-out via
# ``--no-normalize`` on the CLI.

_VAR_RE = re.compile(r"\[[一-鿿]+_[一-鿿]+_[一-鿿]+\]")

_CN_TO_ARABIC = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
}


def normalize_search_plan(sp: str) -> str:
    """Convert `### N. [[label] dim]` heading-style cluster markers to the
    validator-required `**[[label] dim]**` bold-bracket form.
    """
    # `### N. [[label] dim]` → `**[[label] dim]**`
    sp = re.sub(
        r"(?m)^#{1,4}\s*\d*\.?\s*\[\[([^\]]+?)\]\s*([^\]]+?)\]\s*$",
        r"**[[\1] \2]**",
        sp,
    )
    return sp


def _extract_first_required_var(input_form_spec: str) -> str:
    m = re.search(
        r"需提供[:：]\s*(\[[一-鿿]+_[一-鿿]+_[一-鿿]+\])", input_form_spec
    )
    return m.group(1) if m else "[目标_主体_类型]"


def normalize_input_form_spec(ifs: str) -> str:
    """Ensure `需提供:` and `可提供:` segments both exist.

    If the LLM emitted only `需提供: [X] (默认: ...)` (no `可提供:`
    segment), wrap defaults into a `可提供:` segment so the validator
    R1 check passes. Never edits the `需提供` variables themselves.
    """
    s = ifs.strip()
    has_keti = ("可提供:" in s) or ("可提供：" in s)
    if has_keti:
        return s
    # Try to split on a trailing `(默认: ...)`
    m = re.search(
        r"^(.*?)\s*[（(]\s*默认[:：]\s*([^）)]+)\s*[）)]\s*(.*)$", s
    )
    if m:
        head, default_val, tail = m.groups()
        suffix = tail.strip() if tail.strip() else "[补充_说明_备注]"
        return f"{head} (可提供: {suffix} (默认: {default_val}))"
    return s + " 可提供: [补充_说明_备注]"


def normalize_report_format(rf: str) -> str:
    """Fix markdown whitespace + section-numbering nits.

    Applies (in order):
    - `^##title` → `## title` (missing space after `#`)
    - `>**[执行蓝图]**` → `> **[执行蓝图]**` (missing space before `**`)
    - `>*` → `> *` (missing space)
    - `> ***x` → `> *   **x` (triple-asterisk artifact)
    - `## 一、xxx` → `## 1. xxx` (Chinese numeral → arabic)
    - Sequential renumber: walk top-level `^## ` headings (numbered or
      unnumbered), assign 1..N in document order. Preserves heading text.
    """
    rf = re.sub(r"(?m)^(#{1,4})([^\s#])", r"\1 \2", rf)
    rf = re.sub(
        r"(?m)^>\s*\*\*\s*\[\s*执行蓝图\s*\]\s*\*\*",
        r"> **[执行蓝图]**",
        rf,
    )
    rf = re.sub(r"(?m)^>\*", r"> *", rf)
    rf = re.sub(r"(?m)^>\s*\*\*\*([^\*])", r"> *   **\1", rf)

    def _cn_repl(m: re.Match) -> str:
        cn = m.group(1)
        return f"## {_CN_TO_ARABIC.get(cn, 0)}. {m.group(2)}"

    rf = re.sub(
        r"(?m)^##\s*([一二三四五六七八九十]+)[、.]\s*(.+?)\s*$",
        _cn_repl,
        rf,
    )

    # Sequential renumber pass — skip sub-sections (`## 1.1 子节`) so they
    # stay untouched; validator's _REPORT_SECTION_HEADING_RE uses the same
    # `(?!\d)` negative lookahead to reject decimal sub-numbering at `##`
    # level. (codex review 2026-05-29 nit)
    lines = rf.split("\n")
    counter = [0]
    _SUB = re.compile(r"^##\s+\d+[.、]\d")

    def _renumber(ln: str) -> str:
        if _SUB.match(ln):
            return ln
        m = re.match(r"^##\s+(?:\d+[.、](?!\d)\s*)?(.+?)\s*$", ln)
        if not m:
            return ln
        counter[0] += 1
        return f"## {counter[0]}. {m.group(1)}"

    out_lines = [_renumber(ln) if re.match(r"^##\s", ln) else ln for ln in lines]
    return "\n".join(out_lines)


def normalize_report_title(rf: str, input_form_spec: str = "") -> str:
    """If the `# title` lacks a 三段式 var placeholder, inject the
    first 需提供 var from input_form_spec (so validator R6 variable
    consistency passes).
    """
    placeholder = _extract_first_required_var(input_form_spec)
    lines = rf.split("\n")
    for i, ln in enumerate(lines):
        if (
            re.match(r"^#\s+(.+)$", ln)
            and not re.match(r"^##", ln)
            and not _VAR_RE.search(ln)
        ):
            title_text = ln.lstrip("# ").strip()
            lines[i] = f"# {placeholder} {title_text}"
            break
    return "\n".join(lines)


def apply_normalization(proposed: dict) -> dict:
    """Apply all in-place fixes to LLM output before validation."""
    if "search_plan" in proposed and isinstance(proposed["search_plan"], str):
        proposed["search_plan"] = normalize_search_plan(proposed["search_plan"])
    if "input_form_spec" in proposed and isinstance(
        proposed["input_form_spec"], str
    ):
        proposed["input_form_spec"] = normalize_input_form_spec(
            proposed["input_form_spec"]
        )
    if "report_format" in proposed and isinstance(
        proposed["report_format"], str
    ):
        proposed["report_format"] = normalize_report_format(
            proposed["report_format"]
        )
        proposed["report_format"] = normalize_report_title(
            proposed["report_format"], proposed.get("input_form_spec", "")
        )
    return proposed


# ---------------------------------------------------------------------------
# Diff rendering
# ---------------------------------------------------------------------------


def render_diff(field: str, old: str, new: str) -> str:
    diff = difflib.unified_diff(
        (old or "").splitlines(keepends=False),
        (new or "").splitlines(keepends=False),
        fromfile=f"{field} (current)",
        tofile=f"{field} (proposed)",
        lineterm="",
        n=2,
    )
    return "\n".join(diff)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("template_id", type=normalize_template_id,
                   help="搭子模板 id (裸 <id> 自动补 template_ 前缀)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--issues", help="path to issues.txt (one bullet per line)")
    g.add_argument("--message", help="single-line issue description")
    g.add_argument("--stdin", action="store_true", help="read issues from stdin")
    p.add_argument("--yes", "-y", action="store_true", help="跳过 credits 确认")
    p.add_argument(
        "--no-normalize",
        action="store_true",
        help="禁用 LLM 输出 format 自动 normalize（默认开启，修复"
        " `### N. [[标签] 维度]` → `**[[标签] 维度]**`、`#title` 缺空格、"
        "中文数字章节、章节编号不连续、`可提供:` 段缺失等机械格式问题）",
    )
    args = p.parse_args(argv)
    _bad_id = validate_template_id(args.template_id)
    if _bad_id:
        print(f"[+tune] ✗ {_bad_id}", flush=True)
        return 2

    try:
        load_config()
    except SystemExit:
        return 2

    if args.issues:
        issues = Path(args.issues).read_text(encoding="utf-8")
    elif args.message:
        issues = args.message
    else:
        issues = sys.stdin.read()
    if not issues.strip():
        sys.stderr.write("[+tune] no issues provided\n")
        return 2

    if not args.yes:
        sys.stderr.write(
            "\n[+tune] 将调用 /api/generate_template 重新生成 4 字段。\n"
            "        实际积分取决于现有模板和问题清单长度（粗略 1-3 起步），"
            "确切费用见 cuecue.cn 工作台。继续？[y/N]: "
        )
        sys.stderr.flush()
        if input().strip().lower() not in ("y", "yes"):
            print("[+tune] cancelled.")
            return 1

    try:
        current = get_template(args.template_id)
    except CueAPIError as e:
        sys.stderr.write(f"[+tune] fetch failed: {e}\n")
        sys.stderr.write(f"        → {e.user_hint()}\n")
        return 1

    try:
        proposed = call_generate(current, issues)
    except (CueAPIError, RuntimeError, json.JSONDecodeError) as e:
        sys.stderr.write(f"[+tune] generate failed: {e}\n")
        return 1

    if not args.no_normalize:
        proposed = apply_normalization(proposed)

    # Merge proposed into a full payload for validation.
    # Backend strict schema emits canonical `input_form_spec`. We keep a
    # short-term `introduction` parse fallback for any stale snapshot that
    # might still surface the old key in the wild, but we do NOT write
    # `introduction` back into merged — that column was dropped in the
    # backend contract phase.
    merged = {**current}
    # Strip any legacy key from inherited `current` so it never gets PUT back.
    merged.pop("introduction", None)
    for k in LLM_FIELDS:
        val = None
        if k == "input_form_spec":
            val = proposed.get("input_form_spec") or proposed.get("introduction")
        else:
            val = proposed.get(k)
        if isinstance(val, str):
            merged[k] = val

    findings = validate(merged)
    err = [f for f in findings if f.severity == "error"]
    warn = [f for f in findings if f.severity == "warning"]
    print(f"\n[+tune] validation: {len(err)} errors, {len(warn)} warnings")
    for f in findings:
        print(" ", f)

    print("\n[+tune] proposed changes (unified diff):")
    for field in LLM_FIELDS:
        old = current.get(field, "")
        new = merged.get(field, "")
        if old == new:
            continue
        print(f"\n--- {field} ---")
        print(render_diff(field, old, new) or "(structurally identical)")

    if err:
        # Save proposal to /tmp so user can inspect & manually fix without
        # the JSON cluttering the terminal.
        proposal_path = Path(
            f"/tmp/cue-buddy-proposal-{args.template_id[-8:]}-"
            f"{time.strftime('%Y%m%d-%H%M%S')}.json"
        )
        proposal_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            "\n[+tune] 提案有 errors,不建议直接 +update。"
            "请按上面 ❌ 列表修改 issues 描述后重跑,"
            "或手工编辑后用 cue_api.py update 提交。"
        )
        print(f"[+tune] 提案已保存 → {proposal_path}")
        print("[+tune] 手工修法: ")
        print(
            f"  1) 编辑 {proposal_path} 修复 errors\n"
            f"  2) python3 scripts/validate_template.py {proposal_path}  "
            f"# 验证修复后是否过\n"
            f"  3) python3 scripts/cue_api.py update {args.template_id} "
            f"{proposal_path}  # 提交"
        )
        return 1

    if not args.yes:
        sys.stderr.write("\n[+tune] 接受此提案并 PUT 更新模板？[y/N]: ")
        sys.stderr.flush()
        if input().strip().lower() not in ("y", "yes"):
            print("[+tune] cancelled — no PUT performed. Draft saved in memory only.")
            return 1

    backup_path = _backup_before_put(args.template_id, current)
    print(f"[+tune] backed up current version → {backup_path}")

    try:
        result = update_template(args.template_id, {k: merged[k] for k in LLM_FIELDS})
    except CueAPIError as e:
        sys.stderr.write(f"[+tune] update failed: {e}\n")
        sys.stderr.write(f"        → {e.user_hint()}\n")
        sys.stderr.write(
            f"[+tune] previous version is preserved at {backup_path} — "
            "restore with `cue_api.py update <id> <backup>` if needed\n"
        )
        return 1
    print(f"[+tune] updated. Server returned: {result.get('template_id') or result.get('id')}")
    print(f"[+tune] rollback available: `cue_api.py update {args.template_id} {backup_path}`")
    return 0


def _backup_before_put(template_id: str, current: dict) -> Path:
    """Save current template snapshot to ~/.cue/backups/ — gives the user
    an undo path since PUT overwrites without server-side history."""
    backups_dir = Path.home() / ".cue" / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in template_id)
    path = backups_dir / f"{safe_id}.{ts}.json"
    # Only keep the LLM-relevant fields + identity to keep the backup
    # restorable directly via `cue_api.py update`. Drop server-side
    # fields (timestamps, ids, etc) that PUT shouldn't see.
    snapshot = {k: current.get(k) for k in LLM_FIELDS if current.get(k) is not None}
    for meta in ("title", "primary_category", "secondary_category"):
        if current.get(meta) is not None:
            snapshot[meta] = current[meta]
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


if __name__ == "__main__":
    raise SystemExit(main())
