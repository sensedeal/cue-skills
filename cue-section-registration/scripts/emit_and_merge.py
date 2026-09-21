#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Emit 登记与合规 section payload from AMAC and merge into minimal 管理人尽调 draft shell.

Host-callable helper for skill cue-section-登记合规.
Never prints CUE_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MCP_URL = "https://mcp.cuecue.cn/api/regulatory_cn/mcp/"
TOOL_NAME = "get_amac_fund_manager"
PROTOCOL_VERSION = "2025-03-26"
DEFAULT_WORKSPACE = Path.home() / "work" / "cue-agent-workspace" / "drafts"
SECTION_HEADING = "## 登记与合规"

FORBIDDEN_PHRASES = [
    "合规良好",
    "合规情况良好",
    "暂无明显合规问题",
    "建议通过",
    "可作为尽调通过的依据",
    "无风险",
    "无处罚",
    "已合规",
    "准入通过",
    "尽调通过",
    "登记合规通过",
]

# Affirmative ban windows: phrase hits inside these are OK (negation / prohibition).
BAN_WINDOW_MARKERS = ("不得", "禁止", "不得据此")


def load_api_key() -> str:
    env = os.environ.get("CUE_API_KEY", "").strip()
    if env:
        return env
    candidates = []
    cue_home = os.environ.get("CUE_HOME")
    if cue_home:
        candidates.append(Path(cue_home) / "config.json")
    candidates.append(Path.home() / ".cue" / "config.json")
    for path in candidates:
        try:
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            key = (data.get("api_key") or data.get("CUE_API_KEY") or "").strip()
            if key:
                return key
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return ""


def _mcp_post(key: str, payload: dict, session_id: Optional[str] = None) -> Tuple[Any, Optional[str]]:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(MCP_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            new_sid = resp.headers.get("Mcp-Session-Id") or session_id
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:400]
        raise SystemExit(
            f"MCP HTTP {e.code} calling {payload.get('method')}: {err_body}"
        ) from None
    except urllib.error.URLError as e:
        raise SystemExit(f"MCP network error: {e}") from None

    # Parse JSON or SSE streamable-http
    result = None
    if raw.lstrip().startswith("{"):
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = None
    if result is None:
        for line in raw.splitlines():
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if not chunk or chunk == "[DONE]":
                    continue
                try:
                    obj = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and ("result" in obj or "error" in obj):
                    result = obj
                    break
    if result is None:
        raise SystemExit(f"MCP unparseable response ({len(raw)} bytes)")
    if "error" in result and result["error"]:
        raise SystemExit(f"MCP error: {result['error']}")
    return result.get("result"), new_sid


def call_amac_fund_manager(key: str, keyword: str) -> Any:
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "cue-section-登记合规", "version": "0.1.0"},
        },
    }
    _, sid = _mcp_post(key, init_payload)
    # optional initialized notification (best-effort)
    try:
        _mcp_post(
            key,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            session_id=sid,
        )
    except SystemExit:
        pass
    call_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": TOOL_NAME,
            "arguments": {"keyword": keyword, "include_detail": True, "limit": 5},
        },
    }
    result, _ = _mcp_post(key, call_payload, session_id=sid)
    if not result:
        raise SystemExit("Empty MCP tools/call result")
    if result.get("isError"):
        raise SystemExit(f"Tool error: {result}")
    content = result.get("content") or []
    texts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            texts.append(block.get("text") or "")
    if not texts:
        # some servers return structuredContent
        if "structuredContent" in result:
            return result["structuredContent"]
        raise SystemExit(f"No text content in tool result: {list(result.keys())}")
    blob = "\n".join(texts).strip()
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return blob


def extract_managers(payload: Any) -> List[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("managers", "data", "items", "results", "list", "records"):
            val = payload.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        # single manager object
        if any(k in payload for k in ("managerName", "registerNo", "id")):
            return [payload]
    return []


def safe_name(name: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\s]+', "", name.strip())
    return s or "未命名"


def _bool_field(row: dict, *keys: str) -> Optional[bool]:
    for k in keys:
        if k in row and row[k] is not None:
            v = row[k]
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                low = v.strip().lower()
                if low in ("true", "yes", "1", "是"):
                    return True
                if low in ("false", "no", "0", "否"):
                    return False
            if isinstance(v, (int, float)):
                return bool(v)
    return None


def _extract_org_tips(row: dict) -> str:
    """Prefer structured 机构提示 from detail.tips; else top-level tip fields."""
    tips_obj = ((row.get("detail") or {}) if isinstance(row.get("detail"), dict) else {}).get("tips") or {}
    if isinstance(tips_obj, dict):
        for key in ("机构提示信息", "机构提示", "提示信息"):
            val = tips_obj.get(key)
            if isinstance(val, list) and val:
                return " / ".join(str(x) for x in val)
            if isinstance(val, str) and val.strip():
                return val.strip()
        for val in tips_obj.values():
            if isinstance(val, list) and val:
                return " / ".join(str(x) for x in val)
            if isinstance(val, str) and val.strip():
                return val.strip()
    tip = row.get("orgTip") or row.get("institutionTip") or row.get("specialTipInfo")
    if tip:
        return str(tip)
    return ""


def build_judgments(row: dict) -> List[str]:
    name = row.get("managerName") or row.get("name") or "（未返回全称）"
    reg_no = row.get("registerNo") or row.get("register_no") or "（未见编号）"
    ptype = (
        row.get("primaryInvestType")
        or row.get("primary_invest_type")
        or row.get("type")
        or "（未见类型）"
    )
    j1 = (
        f"登记身份可写入底稿：协会公开页在册；全称「{name}」；编号 {reg_no}；"
        f"类型为{ptype}。"
    )

    special = _bool_field(
        row, "hasSpecialTips", "has_special_tips", "specialTips", "hasSpecialTip"
    )
    credit = _bool_field(
        row, "hasCreditTips", "has_credit_tips", "creditTips", "hasCreditTip"
    )
    if special is None and credit is None:
        j2 = (
            "公开特殊/诚信提示位：本次返回未见对应字段——仅记「未见」，"
            "不得写成无风险或准入通过。"
        )
    else:
        sp = "True" if special else "False" if special is False else "未见"
        cr = "True" if credit else "False" if credit is False else "未见"
        j2 = (
            f"公开提示位（协会当前页字段）：特殊={sp}，诚信={cr}"
            "——仅公开页字段，不得写成无风险、无处罚或准入通过。"
        )

    # TEMPLATE slot ③: 公开机构提示是否需知会 — never fund_count
    tip = _extract_org_tips(row)
    if tip:
        j3 = f"公开机构提示需知会：{tip}；是否升格另判（不在本节作准入结论）。"
    else:
        j3 = (
            "公开机构提示：本次未见需知会的机构提示摘要；升格与否另判，"
            "本节不作准入结论。"
        )
    return [j1, j2, j3]


def build_boundaries() -> List[str]:
    return [
        "本节不能单独作准入结论",
        "不含处罚全量、产品清单、工商穿透、访谈",
        "禁止用任何短窗处罚空结果写入本节或相邻结论为「无处罚」",
    ]


def build_takeaway() -> Dict[str, Any]:
    return {
        "human": "并进管理人尽调底稿 → 登记与合规",
        "agent": {
            "manuscript": "管理人尽调",
            "block": "登记与合规",
            "merge": "judgments",
            "honor": "boundaries",
        },
    }


def phrase_in_ban_window(text: str, start: int, end: int) -> bool:
    """True if the match [start:end] sits inside a 不得/禁止/不得据此 window."""
    # Look back up to 40 chars for a marker; window extends ~30 chars after marker.
    left = max(0, start - 40)
    prefix = text[left:start]
    for marker in BAN_WINDOW_MARKERS:
        mi = prefix.rfind(marker)
        if mi < 0:
            continue
        # marker relative to full text
        abs_marker = left + mi
        # window: from marker to ~80 chars after, or to sentence end
        window_end = min(len(text), abs_marker + 80)
        if abs_marker <= start < window_end:
            return True
    return False


def affirmative_ban_check(text: str) -> List[str]:
    """Return forbidden phrase hits that are NOT inside negation windows."""
    hits = []
    for phrase in FORBIDDEN_PHRASES:
        start = 0
        while True:
            i = text.find(phrase, start)
            if i < 0:
                break
            if not phrase_in_ban_window(text, i, i + len(phrase)):
                hits.append(phrase)
                break
            start = i + len(phrase)
    return hits


def render_section_md(subject: dict, judgments: List[str], boundaries: List[str], evidence: dict) -> str:
    lines = [
        SECTION_HEADING,
        "",
        f"**主体**：{subject.get('name')} · 登记编号 {subject.get('register_no')} · {subject.get('type')}",
        "",
        "### 判断（≤3）",
        "",
    ]
    for i, j in enumerate(judgments, 1):
        lines.append(f"{i}. {j}")
    lines += ["", "### 边界", ""]
    for b in boundaries:
        lines.append(f"- {b}")
    lines += [
        "",
        "### 带走",
        "",
        "- 并进「管理人尽调 → 登记与合规」",
        "",
        "### 支撑证据（折叠）",
        "",
        f"- 来源：AMAC `{TOOL_NAME}`",
        f"- 法定代表人：{evidence.get('artificial_person', '—')}",
        f"- 在管产品数（公开字段）：{evidence.get('fund_count', '—')}",
        f"- 办公地址（公开）：{evidence.get('office', '—')}",
        "",
    ]
    return "\n".join(lines)


def render_minimal_shell(subject_name: str, section_body: str) -> str:
    header = (
        f"# 管理人尽调 · {subject_name}\n\n"
        "> 最小壳：仅「登记与合规」节由 Cue skill 写入；其余节待填。"
        " 非整本尽调底稿。\n\n"
    )
    later = (
        "## 公开处罚检索\n\n"
        "（待填）\n\n"
        "## 产品清单\n\n"
        "（待填）\n"
    )
    # section_body already starts with ## 登记与合规
    return header + section_body.rstrip() + "\n\n" + later


def replace_section(manuscript: str, new_section: str) -> str:
    """Replace ## 登记与合规 … until next ##  (or EOF)."""
    pattern = re.compile(
        r"^## 登记与合规\s*$.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    new_section = new_section.rstrip() + "\n\n"
    if pattern.search(manuscript):
        return pattern.sub(new_section, manuscript, count=1)
    # heading missing: append before first later slot or at end
    return manuscript.rstrip() + "\n\n" + new_section


def write_sidecar(path: Path, payload: dict, dry_run: bool) -> Path:
    side = path.with_suffix(".json")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if not dry_run:
        side.write_text(text, encoding="utf-8")
    return side


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="emit_and_merge.py",
        description=(
            "Call AMAC get_amac_fund_manager, emit ≤3 登记与合规 judgments, "
            "create or merge into 管理人尽调 draft shell."
        ),
    )
    parser.add_argument("--keyword", required=True, help="管理人关键词，如 重阳投资")
    parser.add_argument(
        "--workspace",
        default=str(DEFAULT_WORKSPACE),
        help=f"Drafts directory (default: {DEFAULT_WORKSPACE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute payload and paths but do not write files",
    )
    args = parser.parse_args(argv)

    key = load_api_key()
    if not key:
        print(
            "ERROR: CUE_API_KEY not found in env or ~/.cue/config.json "
            "(key never printed).",
            file=sys.stderr,
        )
        return 2

    raw = call_amac_fund_manager(key, args.keyword)
    managers = extract_managers(raw)
    if len(managers) == 0:
        print(
            f"DISAMBIGUATION: keyword={args.keyword!r} → 0 manager hits. "
            "Refine keyword or check AMAC spelling; refusing to write judgments.",
            file=sys.stderr,
        )
        return 3
    if len(managers) > 1:
        names = []
        for m in managers[:12]:
            names.append(
                f"{m.get('managerName') or m.get('name') or '?'}|"
                f"{m.get('registerNo') or '?'}"
            )
        print(
            f"DISAMBIGUATION: keyword={args.keyword!r} → {len(managers)} hits. "
            "Refuse to write judgments. Candidates: " + "; ".join(names),
            file=sys.stderr,
        )
        return 3

    row = managers[0]
    subject = {
        "name": row.get("managerName") or row.get("name") or args.keyword,
        "register_no": row.get("registerNo") or row.get("register_no") or "",
        "type": row.get("primaryInvestType") or row.get("type") or "",
    }
    judgments = build_judgments(row)
    if len(judgments) > 3:
        judgments = judgments[:3]
    boundaries = build_boundaries()
    takeaway = build_takeaway()
    evidence = {
        "source": f"AMAC {TOOL_NAME}",
        "keyword": args.keyword,
        "artificial_person": row.get("artificialPersonName") or row.get("artificial_person"),
        "fund_count": row.get("fundCount"),
        "office": row.get("officeAddress") or row.get("office"),
        "amac_id": row.get("id"),
        "url": row.get("url"),
    }

    section_md = render_section_md(subject, judgments, boundaries, evidence)
    ban_hits = affirmative_ban_check(section_md)
    # Also check judgments joined
    ban_hits += [h for h in affirmative_ban_check("\n".join(judgments)) if h not in ban_hits]
    if ban_hits:
        print(
            "ERROR: affirmative ban-check failed (forbidden phrases outside "
            f"不得/禁止/不得据此 windows): {ban_hits}",
            file=sys.stderr,
        )
        return 4

    workspace = Path(os.path.expanduser(args.workspace))
    if not args.dry_run:
        workspace.mkdir(parents=True, exist_ok=True)

    sn = safe_name(subject["name"])
    md_path = workspace / f"管理人尽调-{sn}.md"
    created = not md_path.exists()

    if created:
        manuscript = render_minimal_shell(subject["name"], section_md)
        action = "created"
    else:
        existing = md_path.read_text(encoding="utf-8")
        manuscript = replace_section(existing, section_md)
        action = "merged"

    ban_hits2 = affirmative_ban_check(manuscript)
    # Only fail if NEW section introduced affirmative hits outside windows;
    # still check full manuscript for safety on our section content.
    section_only_hits = affirmative_ban_check(section_md)
    if section_only_hits:
        print(f"ERROR: section ban-check failed: {section_only_hits}", file=sys.stderr)
        return 4

    sidecar_payload = {
        "section": "管理人尽调底稿·登记与合规节",
        "subject": subject,
        "judgments": judgments,
        "boundaries": boundaries,
        "next_sections": ["产品清单节", "公开处罚检索节（长窗）"],
        "takeaway": takeaway,
        "forbidden_phrases": FORBIDDEN_PHRASES,
        "evidence_fold": evidence,
        "meta": {
            "keyword": args.keyword,
            "action": action,
            "skill": "cue-section-登记合规",
            "version": "0.1.0",
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        },
    }

    if not args.dry_run:
        md_path.write_text(manuscript, encoding="utf-8")
    side_path = write_sidecar(md_path, sidecar_payload, args.dry_run)

    print(f"action: {action}{' (dry-run)' if args.dry_run else ''}")
    print(f"md: {md_path}")
    print(f"sidecar: {side_path}")
    print(f"subject: {subject['name']} | {subject['register_no']} | {subject['type']}")
    print("judgments:")
    for i, j in enumerate(judgments, 1):
        print(f"  {i}. {j}")
    print("boundaries:")
    for b in boundaries:
        print(f"  - {b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
