#!/usr/bin/env python3
"""Shared SSE→report helpers extracted from test_template.py.

Used by both buddy (+test) and cue-research (any chat_stream consumer).
Stdlib only. No behavior change from the originals — the test_template
regression suite (test_skill_regression.py) is the contract.
"""

from __future__ import annotations

import json
import re


def _agent_name(payload: dict) -> str:
    nested = payload.get("data")
    if not isinstance(nested, dict):
        nested = {}
    return payload.get("agent_name") or nested.get("agent_name", "")


def _event_data(payload: dict) -> dict:
    nested = payload.get("data")
    return nested if isinstance(nested, dict) else payload


def extract_reporter_content(events: list[tuple[str, str]]) -> str:
    """Accumulate text emitted while inside reporter's start/end window."""
    in_reporter = False
    pieces: list[str] = []
    for event, data in events:
        if not data:
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        if event == "start_of_agent" and _agent_name(payload) == "reporter":
            in_reporter = True
            continue
        if event == "end_of_agent" and _agent_name(payload) == "reporter":
            in_reporter = False
            continue
        if in_reporter and event == "message":
            delta = _event_data(payload).get("delta") or {}
            text = delta.get("content") or ""
            if text:
                pieces.append(text)
    return "".join(pieces)


def diagnose_empty_report(
    events: list[tuple[str, str]],
    elapsed: float,
    timeout: float,
) -> dict:
    """Classify why extract_reporter_content returned empty. See spec for kinds."""
    last_agent: str | None = None
    reporter_started = False
    reporter_ended = False
    message_count = 0
    for event, data in events:
        if not data:
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        if event == "start_of_agent":
            ag = _agent_name(payload)
            if ag:
                last_agent = ag
            if ag == "reporter":
                reporter_started = True
        elif event == "end_of_agent" and _agent_name(payload) == "reporter":
            reporter_ended = True
        elif event == "message":
            message_count += 1
    hit_timeout = elapsed >= (timeout - 5.0)
    if not last_agent:
        kind = "no_agent_events"
    elif not reporter_started:
        kind = "stream_cut_before_reporter"
    else:
        kind = "reporter_started_no_text"
    return {
        "kind": kind,
        "last_agent": last_agent,
        "reporter_started": reporter_started,
        "reporter_ended": reporter_ended,
        "message_event_count": message_count,
        "hit_timeout": hit_timeout,
    }


def extract_tool_calls(events: list[tuple[str, str]]) -> list[dict]:
    """Reconstruct per-tool-call dict (name, input, result preview, agent)."""
    calls: dict[str, dict] = {}
    order: list[str] = []
    current_agent = ""
    for event, data in events:
        if not data:
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        d = _event_data(payload)
        if event == "start_of_agent":
            current_agent = _agent_name(payload)
        if event == "tool_call":
            tid = d.get("tool_call_id") or f"_anon_{len(order)}"
            inp = d.get("tool_input") or d.get("tool_plain_input") or {}
            calls[tid] = {
                "tool_name": d.get("tool_name", "?"),
                "tool_title": d.get("tool_title", ""),
                "input": inp,
                "result": None,
                "agent": current_agent,
            }
            order.append(tid)
        elif event == "tool_call_result":
            tid = d.get("tool_call_id")
            if tid in calls:
                calls[tid]["result"] = d.get("tool_result", "")
    return [calls[tid] for tid in order]


def extract_sources(events: list[tuple[str, str]]) -> list[dict]:
    """Citation sources from tool_chunk events, for rendering 【N-M】 markers.

    tool_chunk events carry the source detail (tool_call_result.tool_result
    is empty on replay). chunk field is {序号: {type:'mcp', data:{tool_name,
    tool_title, input, output}}}; output holds source links (e.g.
    rows[M].source.pdf_url). 【N-M】 in the report maps N→序号, M→output row.

    Reads chunk through _event_data — live chat_stream payloads are nested
    {"data":{...}} while replay is flat, and PR#40's report_finalized-break
    makes run() complete on the live (nested) path.

    Returns list sorted by 序号: [{index, tool_name, tool_title, input,
    urls, rows, output_preview}]. urls via regex (clean for JSON-string
    output; trailing punctuation stripped, balanced parens kept). rows:
    [{m, company, title, pdf_url, summary, page_range}] parsed from
    output.rows when present (scan-class tools) for 【N-M】→rows[M] precise
    mapping; [] when output is truncated/non-JSON (get_section) → N-level.
    """
    sources: dict[str, dict] = {}
    for event, data in events:
        if event != "tool_chunk" or not data:
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        chunk = _event_data(payload).get("chunk", {})
        if not isinstance(chunk, dict):
            continue
        for k, v in chunk.items():
            # isascii() guards int(k): '²'.isdigit() is True but int('²') raises.
            if not (isinstance(k, str) and k.isascii() and k.isdigit()):
                continue
            d = v.get("data", v) if isinstance(v, dict) else {}
            if not isinstance(d, dict):
                continue
            out = str(d.get("output", "") or "")
            urls = []
            for u in re.findall(r"https?://[^\"\s\\]+", out):
                u = u.rstrip(",;\"'")
                # strip trailing ) ] } only when unbalanced — Wikipedia-style
                # parenthesized paths (Foo_(bar)) legitimately end in ).
                for closer, opener in ((")", "("), ("]", "["), ("}", "{")):
                    while u.endswith(closer) and u.count(opener) < u.count(closer):
                        u = u[:-1]
                if u and u not in urls:
                    urls.append(u)
            # M-level: parse output rows for 【N-M】→rows[M] precise mapping.
            # get_section output is truncated (json.loads fails) → rows=[] (N-level).
            rows_out = []
            try:
                o = json.loads(out) if out.strip() else None
                if isinstance(o, dict) and isinstance(o.get("rows"), list):
                    for m, r in enumerate(o["rows"]):
                        if not isinstance(r, dict):
                            continue
                        src = r.get("source") if isinstance(r.get("source"), dict) else {}
                        rows_out.append({
                            "m": m,
                            "company": str(r.get("company", "") or ""),
                            "title": str(r.get("title", "") or ""),
                            "pdf_url": src.get("pdf_url", "") or "",
                            "summary": str(r.get("summary", "") or ""),
                            "page_range": r.get("page_range", ""),
                        })
            except (json.JSONDecodeError, ValueError):
                pass  # truncated/non-JSON output → N-level fallback
            sources[k] = {
                "index": int(k),
                "tool_name": d.get("tool_name", "") or "",
                "tool_title": d.get("tool_title", "") or "",
                "input": d.get("input", {}),
                "urls": urls,
                "rows": rows_out,
                "output_preview": out[:200],
            }
    return [sources[k] for k in sorted(sources, key=lambda x: int(x))]


def extract_agent_timeline(events: list[tuple[str, str]]) -> list[dict]:
    """Return per-agent (name, execution_time_s). One entry per end_of_agent event."""
    timeline: list[dict] = []
    for event, data in events:
        if event != "end_of_agent" or not data:
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        d = _event_data(payload)
        timeline.append({"agent": d.get("agent_name", "?"), "execution_time": d.get("execution_time", 0)})
    return timeline


def summarize_tool_input(inp) -> str:
    """Render tool_input as a short single-line summary for the run.md table."""
    if isinstance(inp, dict):
        for k in ("query", "keyword", "entity", "company_name", "params"):
            if k in inp and inp[k]:
                v = str(inp[k]).replace("\n", " ")
                return f"{k}={v[:80]}"
        for k, v in inp.items():
            return f"{k}={str(v)[:80]}".replace("\n", " ")
        return "(empty)"
    s = str(inp).replace("\n", " ")
    return s[:120] or "(empty)"


def preview_tool_result(result) -> str:
    """Render tool_result as ≤120 char preview for the run.md table."""
    if result is None:
        return "(no result captured)"
    s = str(result).replace("\n", " ").replace("|", "\\|")
    return s[:120] + ("..." if len(s) > 120 else "")
