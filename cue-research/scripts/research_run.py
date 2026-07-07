#!/usr/bin/env python3
"""cue-research runner — fire one deep-research run and retrieve the report.

This is a THIN composer over the shared cue-buddy primitives (cue_api +
sse_report). It does NOT duplicate them — it imports them via the documented
sys.path pattern, the same one SKILL.md tells the agent to use. Having one
invocable unit (instead of an agent hand-writing the stream loop from prose)
is what makes two things clean:

  1. Background execution. SKILL.md launches this via Bash with
     run_in_background=true; a deep-research run is 3-15 min (60 min server
     hard cap), so blocking the agent's turn on a live stream is wasteful and
     fragile. Fire-and-retrieve frees the turn; the agent reads --output when
     the background task completes.
  2. replay-as-PRIMARY. Long live client SSE streams routinely drop the
     reporter segment before it arrives (server still finishes + writes DB).
     So an empty live extract is the NORM, not a bug. We extract from the
     live stream, and on empty fall back to replay (same parser, reads the
     full workflow_events from the DB — almost always recovers the report).

The rewrite step (free-form privacy de-identification) stays the AGENT's job
per SKILL.md Hard Rules 3/4 — this runner only runs chat_stream + retrieves.
For a buddy run pass --template-id; for a free-form run pass the already
rewritten mandate as --query with no --template-id.

Usage:
    python3 research_run.py --query "<question or rewritten mandate>" \
        [--template-id ID] [--conversation-id ID] \
        --output ~/cue-reports/2026-06-08-foo.md [--timeout 3600]

Exit codes: 0 = report retrieved + saved; 1 = empty/failed (diagnosis printed).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Same sys.path bootstrap SKILL.md documents: shared primitives live in the
# sibling cue-buddy/scripts (cue-research deliberately keeps no copy of them).
_HERE = Path(__file__).resolve().parent
_BUDDY_SCRIPTS = _HERE.parent.parent / "cue-buddy" / "scripts"
sys.path.insert(0, str(_BUDDY_SCRIPTS))

from cue_api import (  # noqa: E402
    CueAPIError,
    chat_stream,
    load_config,
    replay,
    upload_file,
    upload_material,
)
try:  # noqa: E402 — cue-buddy v0.2.2+ exposes these; fall back for older siblings
    from cue_api import normalize_template_id, validate_template_id
except ImportError:
    def normalize_template_id(template_id: str | None) -> str | None:
        if template_id and not template_id.startswith("template_"):
            return "template_" + template_id
        return template_id
    def validate_template_id(template_id: str | None) -> str | None:
        if not template_id:
            return None
        suffix = template_id[len("template_"):] if template_id.startswith("template_") else template_id
        if suffix.isdigit():
            return f"template_id={template_id}: 纯数字后缀不是 Cue id (用 template_id 字段,非数字 id)"
        return None
from sse_report import (  # noqa: E402
    _agent_name,
    _event_data,
    extract_reporter_content,
    extract_sources,
    diagnose_empty_report,
)


# Empty-live-report diagnoses where the report may still exist in the DB, so a
# (free) replay is worth attempting. no_agent_events is excluded — that's an
# auth/template_id failure with nothing to recover.
REPLAYABLE_EMPTY_KINDS = frozenset(
    {"stream_cut_before_reporter", "reporter_started_no_text"}
)

# Events _emit_progress renders a line for. Gate before json.loads so the
# thousands of message/tool_chunk/start_of_llm deltas per run are skipped
# without parsing.
_PROGRESS_EVENTS = frozenset({"start_of_agent", "tool_call", "report_finalized"})


def _emit_progress(event: str, data: str) -> None:
    """Print a flushed progress line for key SSE events.

    Lets the agent (and user, if reading the backgrounded stdout) see research
    steps as they happen: which agent phase is running (with its
    task_requirement), each tool call, and report finalization. Other event
    types (message / start_of_llm / tool_chunk / ...) are too noisy or are
    report content, so skipped. Lines share the `[cue-research]` prefix and go
    to stdout so the full stream (start → progress → RESULT) reads
    top-to-bottom in one file.
    """
    if event not in _PROGRESS_EVENTS:
        return
    if not data:
        return
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict):
        return
    ed = _event_data(payload)
    if event == "start_of_agent":
        ag = _agent_name(payload) or "?"
        tr = ed.get("task_requirement")
        if tr:
            print(f"[cue-research] ▶ agent={ag} task={tr}", flush=True)
        else:
            print(f"[cue-research] ▶ agent={ag}", flush=True)
    elif event == "tool_call":
        name = ed.get("tool_name") or "?"
        title = ed.get("tool_title") or ""
        if title:
            print(f"[cue-research] 🔧 tool={name} ({title})", flush=True)
        else:
            print(f"[cue-research] 🔧 tool={name}", flush=True)
    elif event == "report_finalized":
        print("[cue-research] ✓ report finalized", flush=True)


def format_sources_section(sources: list[dict]) -> str:
    """Format citation sources as a markdown appendix for the .md report.

    Renders one ### block per source (【N】 tool_name), listing input
    keys + source urls + output preview, so the agent/user can resolve
    【N-M】 markers in the report body against the N-indexed source list.
    Returns "" when no sources — keeps the report unchanged for runs
    that produced no tool_chunk events.
    """
    if not sources:
        return ""
    lines = ["\n\n---\n\n## 数据来源详情\n"]
    for s in sources:
        title = f" ({s['tool_title']})" if s['tool_title'] else ""
        lines.append(f"### 【{s['index']}】{s['tool_name']}{title}")
        inp = s.get("input")
        if isinstance(inp, dict) and inp:
            parts = [f"{k}={str(v)[:40]}" for k, v in list(inp.items())[:3]]
            lines.append(f"- input: {', '.join(parts)}")
        for u in s.get("urls", [])[:5]:
            lines.append(f"- {u}")
        preview = s.get("output_preview", "")
        if preview:
            lines.append(f"- preview: {preview[:150]}…")
        lines.append("")
    return "\n".join(lines)


def build_payload(
    query: str,
    template_id: str | None,
    conversation_id: str,
    mimic: dict | None = None,
    conversation_file_ids: list[str] | None = None,
) -> dict:
    """Minimal /api/chat/stream payload.

    need_* all False: non-interactive run — don't let the backend interrupt
    the stream to wait on a clarification form / 仿写 confirmation. In
    particular need_confirm=False makes mimic one-shot: the backend
    auto-generates the style template from the sample and proceeds, with no
    template-review round-trip (which would break background execution).
    Buddy run → include template_id. Free-form → omit it (deepresearch_team).
    mimic → {"url": ...} or {"file_hash": ...} (free-form only; see main()).
    conversation_file_ids → 素材接地: file_ids from upload_material; the 研究
    agent retrieves their full content via file_retrieval. Orthogonal to
    template_id and mimic — works on both buddy and free-form runs.
    """
    payload: dict = {
        "messages": [{"role": "user", "content": query}],
        "conversation_id": conversation_id,
        "chat_id": conversation_id,  # one chat per run; reuse the conv id
        "need_analysis": False,
        "need_confirm": False,
        "need_underlying": False,
        "need_recommend": False,
    }
    if template_id:
        payload["template_id"] = template_id
    if mimic:
        payload["mimic"] = mimic
    if conversation_file_ids:
        payload["conversation_file_ids"] = conversation_file_ids
    return payload


def run(
    query: str,
    template_id: str | None,
    conversation_id: str,
    timeout: float,
    mimic: dict | None = None,
    conversation_file_ids: list[str] | None = None,
) -> tuple[str, str]:
    """Run one chat_stream; on empty live report fall back to replay.

    Returns (report, conv_id). report == "" means retrieval failed (the
    caller prints the diagnosis and exits non-zero).
    """
    payload = build_payload(
        query, template_id, conversation_id, mimic, conversation_file_ids
    )
    conv_id = payload["conversation_id"]
    print(f"[cue-research] conv_id={conv_id}, posting chat...", flush=True)

    t0 = time.time()
    events: list[tuple[str, str]] = []
    started = False
    try:
        for event, data in chat_stream(payload, max_seconds=timeout):
            if not started:
                started = True
                print(f"[cue-research] STARTED conv_id={conv_id}", flush=True)
            events.append((event, data))
            _emit_progress(event, data)
            if event == "report_finalized":
                # Report is done; the live stream often stays open after this,
                # which would hold the run until the 60min timeout (agent stuck
                # at "已开跑" with the report already in the DB). Break and
                # extract now — reporter's message events are all in `events`
                # by this point, so extract_reporter_content below resolves.
                break
            if time.time() - t0 > timeout:
                print("[cue-research] timeout watching SSE", flush=True)
                break
    except CueAPIError as e:
        # 4xx/5xx (auth / template_id) — replay can't save these.
        # Print to stdout so the agent's stdout-only capture sees the failure
        # (SKILL.md tells it to watch stdout for chat_stream failed).
        print(f"[cue-research] chat_stream failed: {e}", flush=True)
        print(f"[cue-research] → {e.user_hint()}", flush=True)
        return "", [], conv_id
    except (OSError, ValueError) as e:
        # Network blip / SSE parse error: keep the partial events and let the
        # diagnose+replay path below still try to recover.
        print(
            f"[cue-research] stream raised {type(e).__name__}: {e}; "
            f"events so far={len(events)}, will try replay fallback",
            flush=True,
        )

    elapsed = time.time() - t0
    print(f"[cue-research] stream done in {elapsed:.1f}s, events={len(events)}", flush=True)

    report = extract_reporter_content(events)
    if report:
        return report, extract_sources(events), conv_id

    # Empty live report — the long-run NORM. Diagnose, then replay-primary.
    diag = diagnose_empty_report(events, elapsed, timeout)
    print(
        f"[cue-research] empty live report → kind={diag['kind']}, "
        f"last_agent={diag['last_agent']!r}, reporter_started={diag['reporter_started']}, "
        f"messages={diag['message_event_count']}, hit_timeout={diag['hit_timeout']}",
        flush=True,
    )
    if diag["kind"] in REPLAYABLE_EMPTY_KINDS:
        # Both kinds mean the live stream ended without reporter text, but the
        # server may still have finished + persisted to the DB. Replay reads the
        # full workflow_events back (no credit cost), so always attempt it before
        # giving up — for reporter_started_no_text too, not just a clean cut.
        print(f"[cue-research] retrieving via replay {conv_id} (no credit cost)…", flush=True)
        try:
            replay_events = [(ev, d) for ev, d in replay(conv_id, max_seconds=timeout)]
        except CueAPIError as e:
            print(
                f"[cue-research] replay failed: {e}\n"
                f"[cue-research] → server may not have finished; wait a bit and run: "
                f"cue_api.py replay {conv_id}",
                flush=True,
            )
            return "", [], conv_id
        report = extract_reporter_content(replay_events)
        if report:
            print(f"[cue-research] ✓ recovered via replay: {len(report)} chars", flush=True)
            return report, extract_sources(replay_events), conv_id
        print(
            "[cue-research] replay also empty — server-side reporter likely "
            "failed (started but persisted no text). Check cuecue.cn web for "
            "this conversation_id; re-run if it was a transient model failure.",
            flush=True,
        )
    elif diag["kind"] == "no_agent_events":
        print(
            "[cue-research] no agent events — likely API auth / template_id "
            "problem (not a long-stream issue). Check args + key.",
            flush=True,
        )
    return "", [], conv_id


def main(argv: list[str] | None = None) -> int:
    # Tolerate legacy-encoding stdout (e.g. Windows consoles) so the emoji
    # progress markers (▶/🔧/✓) don't UnicodeEncodeError — which would be
    # caught as ValueError and misdiagnosed as a network blip.
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", required=True, help="问题原文,或自由式已 rewrite 的 mandate")
    p.add_argument("--template-id", default=None, help="搭子模板 id;留空=自由式深研")
    p.add_argument(
        "--conversation-id",
        default=None,
        help="复用已有 conversation_id 续跑;留空则新建 cue-research-<rand>",
    )
    p.add_argument(
        "--output",
        default=None,
        help="报告落盘路径(Markdown)。留空默认 ~/cue-reports/<date>-<slug>.md",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=3600.0,
        help="SSE 总超时秒(默认 3600=60min,对齐服务端硬超时;单次深研通常 3-15min)",
    )
    p.add_argument(
        "--mimic-url",
        default=None,
        help="仿写:模仿该网页的写作风格(仅自由式,与 --template-id / --mimic-file 互斥)",
    )
    p.add_argument(
        "--mimic-file",
        default=None,
        help="仿写:模仿本地样本文档的写作风格,先上传换 file_hash(仅自由式,与 --template-id / --mimic-url 互斥)",
    )
    p.add_argument(
        "--material",
        action="append",
        default=None,
        metavar="PATH",
        help="文档接地:把本地文档作为调研素材(可重复多个);研究 agent 经 file_retrieval "
        "全文检索其内容。与 --template-id / --mimic-* 正交,搭子与自由式均可用。",
    )
    args = p.parse_args(argv)
    # Tolerate a bare `<id>` for --template-id (prepend `template_` if missing),
    # so logs, payload, and the empty-run stub all use the resolved id.
    args.template_id = normalize_template_id(args.template_id)
    # Fail fast on a pure-digit suffix (e.g. `142` → `template_142`): the agent
    # grabbed the buddy's numeric DB `id` or a list index, not the template_id
    # string. Cue suffixes are base62 — never pure digits — so this is a
    # guaranteed 404. Don't burn credits on it.
    _bad_id = validate_template_id(args.template_id)
    if _bad_id:
        print(f"[cue-research] ✗ {_bad_id}", flush=True)
        return 2

    # Mimic constraints (Phase 1 scope): one-shot, free-form only.
    if args.mimic_url and args.mimic_file:
        print("[cue-research] --mimic-url 与 --mimic-file 互斥,二选一", flush=True)
        return 2
    if (args.mimic_url or args.mimic_file) and args.template_id:
        # Backend prioritizes template_id over mimic, so mimic would silently
        # no-op. Refuse rather than mislead. mimic = free-form styling only.
        print(
            "[cue-research] 仿写仅用于自由式(不带 --template-id):"
            "搭子已有 report_format,与仿写冲突",
            flush=True,
        )
        return 2

    try:
        load_config()
    except SystemExit:
        return 2

    mimic: dict | None = None
    if args.mimic_url:
        mimic = {"url": args.mimic_url}
    elif args.mimic_file:
        try:
            print(f"[cue-research] 上传仿写样本 {args.mimic_file} …", flush=True)
            file_hash = upload_file(args.mimic_file)
        except CueAPIError as e:
            print(f"[cue-research] 样本上传失败: {e}\n[cue-research] → {e.user_hint()}", flush=True)
            return 1
        except SystemExit:
            return 2
        mimic = {"file_hash": file_hash}
        print(f"[cue-research] ✓ 样本已上传 file_hash={file_hash[:12]}…", flush=True)

    # 素材接地: upload each --material doc to file_id (single-use, fail-fast).
    # Orthogonal to mimic/template — uploaded before the run; bound at chat time
    # via conversation_file_ids so the 研究 agent can file_retrieval the full doc.
    material_file_ids: list[str] = []
    if args.material:
        for mpath in args.material:
            try:
                print(f"[cue-research] 上传素材 {mpath} …", flush=True)
                fid = upload_material(mpath)
            except CueAPIError as e:
                print(
                    f"[cue-research] 素材上传失败 ({mpath}): {e}\n"
                    f"[cue-research] → {e.user_hint()}",
                    flush=True,
                )
                return 1
            except SystemExit:
                return 2
            material_file_ids.append(fid)
            print(f"[cue-research] ✓ 素材已就绪 file_id={fid}", flush=True)

    if args.conversation_id:
        conv_id = args.conversation_id
    else:
        import uuid

        conv_id = f"cue-research-{uuid.uuid4().hex[:12]}"

    # Resolve --output (date-stamped default under ~/cue-reports/).
    if args.output:
        out_path = Path(args.output).expanduser()
    else:
        slug = "".join(
            ch for ch in args.query[:24] if ch.isalnum() or ch in " -_一-鿿"
        ).strip().replace(" ", "-") or "research"
        out_path = Path.home() / "cue-reports" / f"{time.strftime('%Y-%m-%d-%H%M')}-{slug}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report, sources, conv_id = run(
        args.query,
        args.template_id,
        conv_id,
        args.timeout,
        mimic,
        material_file_ids or None,
    )
    if not report:
        # Persist a stub so a backgrounded run always leaves a readable trace.
        out_path.write_text(
            f"# (empty) cue-research run\n\n- conv_id: `{conv_id}`\n"
            f"- query: {args.query}\n- template_id: {args.template_id}\n\n"
            f"报告获取失败,见上方诊断 / cuecue.cn 网页端该 conversation。\n",
            encoding="utf-8",
        )
        print(f"[cue-research] FAILED — stub written → {out_path}", flush=True)
        print(f"[cue-research] RESULT empty conv_id={conv_id} output={out_path}", flush=True)
        return 1

    mimic_note = ""
    if mimic:
        mimic_note = " | mimic=" + ("url" if mimic.get("url") else "file")
    material_note = ""
    if material_file_ids:
        material_note = f" | materials={len(material_file_ids)}"
    header = (
        f"<!-- cue-research run | conv_id={conv_id} | "
        f"{'template=' + args.template_id if args.template_id else 'free-form'}"
        f"{mimic_note}{material_note} | {time.strftime('%Y-%m-%d %H:%M')} -->\n\n"
    )
    out_path.write_text(header + report + format_sources_section(sources), encoding="utf-8")
    print(
        f"[cue-research] ✓ report {len(report)} chars → {out_path}", flush=True
    )
    # Single machine-parseable final line for the agent to key on.
    print(
        f"[cue-research] RESULT ok conv_id={conv_id} chars={len(report)} output={out_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
