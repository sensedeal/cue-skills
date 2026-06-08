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
)
from sse_report import (  # noqa: E402
    extract_reporter_content,
    diagnose_empty_report,
)


def build_payload(
    query: str,
    template_id: str | None,
    conversation_id: str,
    mimic: dict | None = None,
) -> dict:
    """Minimal /api/chat/stream payload.

    need_* all False: non-interactive run — don't let the backend interrupt
    the stream to wait on a clarification form / 仿写 confirmation. In
    particular need_confirm=False makes mimic one-shot: the backend
    auto-generates the style template from the sample and proceeds, with no
    template-review round-trip (which would break background execution).
    Buddy run → include template_id. Free-form → omit it (deepresearch_team).
    mimic → {"url": ...} or {"file_hash": ...} (free-form only; see main()).
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
    return payload


def run(
    query: str,
    template_id: str | None,
    conversation_id: str,
    timeout: float,
    mimic: dict | None = None,
) -> tuple[str, str]:
    """Run one chat_stream; on empty live report fall back to replay.

    Returns (report, conv_id). report == "" means retrieval failed (the
    caller prints the diagnosis and exits non-zero).
    """
    payload = build_payload(query, template_id, conversation_id, mimic)
    conv_id = payload["conversation_id"]
    print(f"[cue-research] conv_id={conv_id}, posting chat...", flush=True)

    t0 = time.time()
    events: list[tuple[str, str]] = []
    try:
        for event, data in chat_stream(payload, max_seconds=timeout):
            events.append((event, data))
            if time.time() - t0 > timeout:
                sys.stderr.write("[cue-research] timeout watching SSE\n")
                break
    except CueAPIError as e:
        # 4xx/5xx (auth / template_id) — replay can't save these.
        sys.stderr.write(f"[cue-research] chat_stream failed: {e}\n")
        sys.stderr.write(f"        → {e.user_hint()}\n")
        return "", conv_id
    except (OSError, ValueError) as e:
        # Network blip / SSE parse error: keep the partial events and let the
        # diagnose+replay path below still try to recover.
        sys.stderr.write(
            f"[cue-research] stream raised {type(e).__name__}: {e}; "
            f"events so far={len(events)}, will try replay fallback\n"
        )

    elapsed = time.time() - t0
    print(f"[cue-research] stream done in {elapsed:.1f}s, events={len(events)}", flush=True)

    report = extract_reporter_content(events)
    if report:
        return report, conv_id

    # Empty live report — the long-run NORM. Diagnose, then replay-primary.
    diag = diagnose_empty_report(events, elapsed, timeout)
    print(
        f"[cue-research] empty live report → kind={diag['kind']}, "
        f"last_agent={diag['last_agent']!r}, reporter_started={diag['reporter_started']}, "
        f"messages={diag['message_event_count']}, hit_timeout={diag['hit_timeout']}",
        flush=True,
    )
    if diag["kind"] == "stream_cut_before_reporter":
        print(f"[cue-research] retrieving via replay {conv_id} (no credit cost)…", flush=True)
        try:
            replay_events = [(ev, d) for ev, d in replay(conv_id, max_seconds=timeout)]
        except CueAPIError as e:
            sys.stderr.write(
                f"[cue-research] replay failed: {e}\n"
                f"        → server may not have finished; wait a bit and run: "
                f"cue_api.py replay {conv_id}\n"
            )
            return "", conv_id
        report = extract_reporter_content(replay_events)
        if report:
            print(f"[cue-research] ✓ recovered via replay: {len(report)} chars", flush=True)
            return report, conv_id
        sys.stderr.write(
            "[cue-research] replay also empty — server-side reporter may have "
            "failed. Check cuecue.cn web for this conversation_id.\n"
        )
    elif diag["kind"] == "no_agent_events":
        sys.stderr.write(
            "[cue-research] no agent events — likely API auth / template_id "
            "problem (not a long-stream issue). Check args + key.\n"
        )
    else:  # reporter_started_no_text
        sys.stderr.write(
            "[cue-research] reporter started but emitted no text. Server-side "
            "reporter likely failed; check cuecue.cn web replay.\n"
        )
    return "", conv_id


def main(argv: list[str] | None = None) -> int:
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
    args = p.parse_args(argv)

    # Mimic constraints (Phase 1 scope): one-shot, free-form only.
    if args.mimic_url and args.mimic_file:
        sys.stderr.write("[cue-research] --mimic-url 与 --mimic-file 互斥,二选一\n")
        return 2
    if (args.mimic_url or args.mimic_file) and args.template_id:
        # Backend prioritizes template_id over mimic, so mimic would silently
        # no-op. Refuse rather than mislead. mimic = free-form styling only.
        sys.stderr.write(
            "[cue-research] 仿写仅用于自由式(不带 --template-id):"
            "搭子已有 report_format,与仿写冲突\n"
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
            sys.stderr.write(f"[cue-research] 样本上传失败: {e}\n        → {e.user_hint()}\n")
            return 1
        except SystemExit:
            return 2
        mimic = {"file_hash": file_hash}
        print(f"[cue-research] ✓ 样本已上传 file_hash={file_hash[:12]}…", flush=True)

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

    report, conv_id = run(args.query, args.template_id, conv_id, args.timeout, mimic)
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
    header = (
        f"<!-- cue-research run | conv_id={conv_id} | "
        f"{'template=' + args.template_id if args.template_id else 'free-form'}"
        f"{mimic_note} | {time.strftime('%Y-%m-%d %H:%M')} -->\n\n"
    )
    out_path.write_text(header + report, encoding="utf-8")
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
