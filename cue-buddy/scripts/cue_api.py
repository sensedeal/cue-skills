#!/usr/bin/env python3
"""Minimal HTTP client for the Cue production API.

Stdlib only (urllib + json + os) — no third-party deps, runs anywhere
with Python 3.10+. Designed to be invoked by agent skills, not as a
general-purpose SDK.

Reads credentials from (in order):
  1. CUE_API_KEY env var
  2. ~/.cue/config.json   {"api_key": "sk...", "base": "https://..."}
  3. CUE_API_BASE env var overrides the base if set

Public functions:
  - load_config()                      : (api_key, base) or raises
  - get_templates()                    : list user templates
  - get_template(template_id)          : full template JSON
  - create_template(payload)           : returns the new template
  - update_template(template_id, p)    : returns the updated template
  - set_template_frequent(id, bool)    : toggle workbench "frequent" pin
                                         (this is the `+frequent` primitive)
  - search_templates(keyword, ...)     : keyword search over templates
  - rewrite(input, device_type)        : POST /api/rewrite — apply rewrite_prompt
                                         (privacy masking + public-source constraint)
  - generate_template(conv_id, req)    : streams the generated 4 fields
                                         (uses seed: bypass when conv_id
                                         is empty or starts with "seed:")
  - chat_stream(payload, on_event)     : posts to /api/chat/stream and
                                         streams SSE events to callback
  - replay(conv_id, on_event)          : reads /api/replay/<id> SSE stream

CLI usage (smoke test from a shell):
    python3 cue_api.py whoami
    python3 cue_api.py list
    python3 cue_api.py get <template_id>
    python3 cue_api.py create <payload.json>
    python3 cue_api.py update <template_id> <payload.json>
    python3 cue_api.py {frequent|unfrequent} <template_id>
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterator


CONFIG_PATH = Path.home() / ".cue" / "config.json"
DEFAULT_BASE = "https://cuecue.cn/api"
API_KEY_PAGE = "https://cuecue.cn/api-key"


class CueAPIError(Exception):
    """Wraps any non-2xx response with status + decoded detail."""

    def __init__(self, status: int, detail: str, path: str):
        super().__init__(f"{path} → HTTP {status}: {detail}")
        self.status = status
        self.detail = detail
        self.path = path

    def user_hint(self) -> str:
        """Render a non-technical actionable hint based on the HTTP status.

        Used by the agent / CLI to translate raw API errors into
        next-step guidance for the business user.
        """
        if self.status == 0:
            # codex r6: transport-layer failure (URLError → no HTTP response).
            # 区分 sandbox/proxy/offline 三个常见原因给方向。
            return (
                "网络不可达 — 无法连到 Cue API。请检查:\n"
                "    1) CUE_API_BASE 拼写 (默认 https://cuecue.cn/api)\n"
                "    2) 网络/VPN/代理设置 (HTTP_PROXY/HTTPS_PROXY env)\n"
                "    3) agent sandbox 是否禁用了出站 (常见于 Codex/Gemini\n"
                "       受限 mode);用 --sandbox danger-full-access 等开放设置"
            )
        if self.status == 401:
            return (
                "API key 无效或已过期。"
                f"请到 {API_KEY_PAGE} 重新创建一个 sk-... 开头的 key，"
                "并 `export CUE_API_KEY=sk...` 或更新 ~/.cue/config.json."
            )
        if self.status == 402:
            return (
                "Cue 余额不足。请到 cuecue.cn 充值后再试。"
                "本次调用没有产生消耗。"
            )
        if self.status == 403:
            return (
                "权限不足：当前 API key 对应的账号无法访问该资源（可能是"
                "模板属于其他用户，或权限被收回）。"
            )
        if self.status == 404:
            return "资源不存在（template_id 错了？或已被删除）。"
        if self.status == 429:
            return (
                "调用过于频繁，被服务端限流。请等 30 秒后再试；"
                "若反复出现，请联系 Cue 支持。"
            )
        if 500 <= self.status < 600:
            return (
                "Cue 服务端临时故障（{self.status}）。稍候再试；"
                "若持续，请到 cuecue.cn 反馈错误码 + path={self.path}."
            ).replace("{self.status}", str(self.status)).replace(
                "{self.path}", self.path
            )
        return f"未预期的错误 HTTP {self.status}: {self.detail[:200]}"


# ---------------------------------------------------------------------------
# Credential & config loading
# ---------------------------------------------------------------------------


def load_config() -> tuple[str, str]:
    """Return (api_key, base_url) or raise SystemExit with a helpful hint."""
    api_key = os.environ.get("CUE_API_KEY", "").strip()
    base = os.environ.get("CUE_API_BASE", "").strip()

    if not api_key and CONFIG_PATH.exists():
        try:
            blob = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            api_key = api_key or blob.get("api_key", "").strip()
            base = base or blob.get("base", "").strip()
        except Exception:
            pass

    base = base or DEFAULT_BASE

    if not api_key:
        sys.stderr.write(
            "\n[cue-buddy] 缺少 API key。\n"
            f"  → 去 {API_KEY_PAGE} 创建一个 sk-prefixed key\n"
            "  → 然后 export CUE_API_KEY=sk... (或写入 ~/.cue/config.json)\n\n"
        )
        raise SystemExit(2)

    return api_key, base


# ---------------------------------------------------------------------------
# Low-level HTTP
# ---------------------------------------------------------------------------


def _request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    stream: bool = False,
    timeout: float = 30.0,
) -> Any:
    """Issue one HTTP request. Returns parsed JSON, OR if stream=True a
    response handle for SSE iteration."""
    api_key, base = load_config()
    url = base.rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    if stream:
        req.add_header("Accept", "text/event-stream")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        # 4xx/5xx — server replied with HTTP error. Decode body for actionable detail.
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(err_body)
                detail = (
                    parsed.get("detail")
                    if isinstance(parsed.get("detail"), str)
                    else json.dumps(parsed, ensure_ascii=False)
                )
            except Exception:
                detail = err_body[:400]
        except Exception:
            detail = "(no body)"
        raise CueAPIError(e.code, detail, path) from e
    except urllib.error.URLError as e:
        # codex r6 finding: connection refused / DNS fail / sandbox-blocked /
        # offline / TLS error 这种 transport-layer 失败之前 propagate 出
        # CueAPIError 范围,CLI 外层 except 兜不住,user 看到 raw traceback。
        # 包装成 CueAPIError(status=0) 表示"无 HTTP response"。user_hint()
        # 有专门 status=0 分支给 actionable 提示(检查网络 / proxy / base URL)。
        reason = getattr(e, "reason", e)
        raise CueAPIError(
            0, f"network unreachable: {reason}", path
        ) from e

    if stream:
        return resp

    raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else None


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------


def get_templates(mode: str = "is_me", include_system: bool = False) -> list[dict]:
    """List the calling user's templates.

    Args:
        mode: per Cue API docs — one of all / unread / timer / is_frequent
              / is_me / is_update. Default 'is_me' shows only what the
              user themself created (no system clutter), which is what a
              business-expert author usually wants.
        include_system: whether to include system templates.

    Returns the list of template dicts. Server returns a PaginatedResponse
    shape; we unwrap data.items.
    """
    params = urllib.parse.urlencode(
        {"mode": mode, "include_system": "true" if include_system else "false"}
    )
    data = _request("GET", f"/templates?{params}")
    if isinstance(data, dict):
        payload = data.get("data")
        if isinstance(payload, dict):
            return payload.get("items") or []
        return data.get("templates") or []
    if isinstance(data, list):
        return data
    return []


def get_template(template_id: str) -> dict:
    """Fetch one full template."""
    data = _request("GET", f"/templates/{template_id}")
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        return data["data"]
    return data or {}


def search_templates(
    keyword: str,
    include_system: bool = True,
    page: int = 1,
    page_size: int = 20,
) -> list[dict]:
    """POST /api/templates/search — keyword search over templates.

    Backend (cubemanus src/api/routes/template.py:753) accepts a
    TemplateShareRequest with `keyword` (str, stripped server-side),
    `include_system` (bool), and pagination. The underlying SQL only
    matches title + primary_category + secondary_category
    (service/template.py:1823-1825), NOT goal/input — so callers
    (e.g. cue-research) should treat results as low-confidence candidates,
    try a few keyword variants, and never auto-select.

    Returns the unwrapped items list (matches get_templates' convention).
    """
    body = {
        "keyword": keyword,
        "include_system": include_system,
        "page": page,
        "page_size": page_size,
    }
    data = _request("POST", "/templates/search", body=body)
    if isinstance(data, dict):
        payload = data.get("data")
        if isinstance(payload, dict):
            return payload.get("items") or []
        return data.get("items") or []
    if isinstance(data, list):
        return data
    return []


# 后端 schema 字段(`src/api/schemas/template.py` CreateTemplateRequest /
# UpdateTemplateRequest / CreateRecommendedTaskRequest)只支持 schedules,
# DB 列 task_cron_expressions / task_configs 是 server-internal。client
# 不应外发这两个 key。下面 _SCHEDULE_KEY_SET 用于 outbound payload 清理。
_SCHEDULE_KEYS_TO_STRIP = ("task_cron_expressions", "task_configs")

# 与 validate_template R9 同源 token 集合(避免漂移)。
# 在 import 失败时(脚本单独 invoke 不带 sys.path)用本地副本兜底。
try:
    from validate_template import (  # type: ignore[import-not-found]
        _TASK_INPUT_GUIDE_TOKENS,
        _TASK_INPUT_PLACEHOLDER_RE,
    )
except ImportError:  # pragma: no cover - guard against partial install
    import re as _re

    _TASK_INPUT_GUIDE_TOKENS = (
        "请输入", "请提供", "可选补充", "可提供", "可选填",
        "默认:", "默认：", "企业名称", "公司名称", "主体名称",
        "统一社会信用代码", "示例", "例如", "如:", "如：",
        "占位", "placeholder",
    )
    _TASK_INPUT_PLACEHOLDER_RE = _re.compile(
        r"[\[<][^\]\n>]*(?:[一-鿿]_[一-鿿]|名称|主体|代码|变量|占位|placeholder|请)[^\]\n>]*[\]>]"
    )


def _normalize_template_payload(payload: dict) -> dict:
    """Reshape client-supplied payload to match the public API schema.

    Operations:

    1. **Reject typo'd field names** (early fail): ``cron_expressions``
       (no ``task_`` prefix) is a common typo — backend default Pydantic
       config ignores unknown fields, so it would silently no-op.
    2. **Legacy task_configs → schedules**: older seed scripts populate
       ``task_configs: [{"type", "time", "date_param", "dates", "name"}]``
       directly to the DB. The public API only accepts ``schedules`` of
       the same {type/time/date_param/dates} shape (no ``name``). When
       ``task_configs`` is present without ``schedules``, derive
       ``schedules`` from it. Each item must carry ``type`` + ``time``
       (backend ScheduleConfig marks them required); items missing
       either raise — silently sending None would 422 from server.
    3. **Strip server-internal keys**: outbound payload must not carry
       ``task_cron_expressions`` / ``task_configs`` (DB-column shape,
       not API contract).
    4. **task_input safety**: collect *all* R9 violations (引导词 + 占位
       variable) and raise once with the full list — short-circuit would
       force buddy authors to fix-and-retry one error at a time.

    Returns a *new* dict; ``payload`` is not mutated.
    """
    out = dict(payload)

    # (1) typo'd field names → raise (codex !450 r3 nit: backend's default
    # extra='ignore' would swallow these silently)
    if "cron_expressions" in out:
        raise ValueError(
            "unsupported field 'cron_expressions' — did you mean 'schedules' "
            "(public API) or 'task_cron_expressions' (DB internal, never "
            "outbound)?"
        )

    # (2) legacy task_configs → schedules (only when caller didn't already
    # supply schedules — schedules wins if both are present)
    if "task_configs" in out and "schedules" not in out:
        raw_configs = out.get("task_configs")
        if isinstance(raw_configs, list) and raw_configs:
            schedules: list[dict] = []
            for i, c in enumerate(raw_configs):
                if not isinstance(c, dict):
                    raise ValueError(
                        f"task_configs[{i}] must be a dict, got {type(c).__name__}"
                    )
                # ScheduleConfig.type / time are required str (no default).
                # date_param / dates are optional → may be None.
                missing = [k for k in ("type", "time") if not c.get(k)]
                if missing:
                    raise ValueError(
                        f"task_configs[{i}] missing required field(s) "
                        f"{missing}; ScheduleConfig.type and .time are "
                        f"required str"
                    )
                schedules.append(
                    {
                        "type": c.get("type"),
                        "time": c.get("time"),
                        "date_param": c.get("date_param"),
                        "dates": c.get("dates"),
                    }
                )
            if schedules:
                out["schedules"] = schedules

    # (3) strip server-internal keys regardless of (2) outcome
    for k in _SCHEDULE_KEYS_TO_STRIP:
        out.pop(k, None)

    # (4) task_input client-side fast-fail — collect all R9 violations
    # then raise once (was short-circuit before codex !450 r3 nit).
    task_input = out.get("task_input")
    if isinstance(task_input, str) and task_input:
        violations: list[str] = []
        hits = [tok for tok in _TASK_INPUT_GUIDE_TOKENS if tok in task_input]
        if hits:
            violations.append(f"含 R9 引导词 {hits}")
        if _TASK_INPUT_PLACEHOLDER_RE.search(task_input):
            violations.append("含 `<...>` / `[...]` 形式占位变量")
        if violations:
            raise ValueError(
                f"task_input 违反 R9「可执行」({'; '.join(violations)}) — "
                f"task_input 必须是已 resolve 的具体值(如企业名/主体名)。"
                f"引导文案应放 input_form_spec;参见 references/hard-rules.md#r9。"
                f"当前值: {task_input!r}"
            )

    return out


def create_template(payload: dict) -> dict:
    """Create a new user-owned template.

    Payload schema (mirrors ``CreateTemplateRequest`` in cubemanus
    ``src/api/schemas/template.py``):

      Required:
        source_conversation_id  - use "seed:<slug>:v1" for synthetic
      Identity (all optional):
        title, primary_category, secondary_category
      LLM-consumed (validate_template enforces shape):
        input_form_spec, goal, search_plan, report_format
      Recommended-task (all optional):
        task_input  - directly-executable concrete value (a single
          company/subject name pre-resolved by the buddy author),
          NOT a placeholder/guidance string and NOT a `<...>` / `[...]`
          variable. Single line, ≤ 30 chars. See R9.
        schedules   - list[{type, time, date_param, dates}],
          min_length=1 (server schema rejects empty/null array)

    Legacy convenience: if ``task_configs`` (DB-column shape) is supplied
    without ``schedules``, this function derives ``schedules`` from it
    transparently. Outbound payload never carries
    ``task_cron_expressions`` / ``task_configs`` (server-internal).

    See references/template-fields-spec.md §5 and hard-rules.md R9.

    Raises:
        ValueError: when ``task_input`` violates R9 「可执行」 client-side
            (avoids burning an API round-trip on obviously-broken input).
    """
    body = _normalize_template_payload(payload)
    data = _request("POST", "/templates", body=body)
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    return data or {}


def update_template(template_id: str, payload: dict) -> dict:
    """Modify an existing user template (partial update supported).

    Same payload shape as :func:`create_template`; only fields present
    are updated. ``task_cron_expressions`` / ``task_configs`` are
    stripped before send (server-internal); legacy ``task_configs``
    triggers automatic ``schedules`` derivation.

    Backend PUT /api/templates/{id} requires at least one regular
    template field (title / input_form_spec / goal / search_plan /
    report_format / categories) in the request. For pure recommended-
    task updates use :func:`update_template_recommended_task` against
    the dedicated /recommended-task endpoint instead.

    Raises:
        ValueError: when ``task_input`` violates R9 「可执行」.
        CueAPIError: 400 if caller sends ONLY task_input/schedules
            without a regular template field (cubemanus contract).
    """
    body = _normalize_template_payload(payload)
    # PUT contract sanity: backend (template.py:598-599) rejects 400 if
    # caller didn't include any regular template field. Surface this
    # earlier with a clearer message before the API round-trip.
    _REGULAR_FIELDS = {
        "title",
        "primary_category",
        "secondary_category",
        "input_form_spec",
        "goal",
        "search_plan",
        "report_format",
    }
    if not (set(body.keys()) & _REGULAR_FIELDS):
        raise ValueError(
            "update_template payload 缺少普通模板字段(title / input_form_spec / "
            "goal / search_plan / report_format / ...);后端 PUT /api/templates/"
            "{id} 不允许仅更新 task_input/schedules。改用 "
            "update_template_recommended_task() 走 /recommended-task 端点。"
        )
    data = _request("PUT", f"/templates/{template_id}", body=body)
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    return data or {}


def update_template_recommended_task(
    template_id: str,
    schedules: list,
    task_input: str | None = None,
) -> dict:
    """Update the recommended-task config on an existing template.

    Backend endpoint: POST /api/templates/{template_id}/recommended-task
    (``CreateRecommendedTaskRequest`` schema). Use this for pure
    schedule/task_input updates; :func:`update_template` PUT requires a
    regular template field.

    Args:
        template_id: target template
        schedules: list[{type, time, date_param, dates}], **required**,
            min_length=1. Backend ``CreateRecommendedTaskRequest.schedules``
            is marked required (``Field(..., min_length=1)``); omitting
            would 422 anyway, so we surface that as a local ValueError.
        task_input: directly-executable subject (R9 client-side checked).
            None=omit field (server keeps existing value).
    """
    if not isinstance(schedules, list) or len(schedules) < 1:
        raise ValueError(
            "update_template_recommended_task requires schedules with ≥1 item; "
            "backend CreateRecommendedTaskRequest.schedules is required "
            "(Field(..., min_length=1))."
        )
    body: dict = {"schedules": schedules}
    if task_input is not None:
        body["task_input"] = task_input
    # Run task_input lint + schedule-item shape check via the normalizer.
    body = _normalize_template_payload(body)
    data = _request(
        "POST", f"/templates/{template_id}/recommended-task", body=body
    )
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    return data or {}


def capabilities(
    *,
    fields: str | None = None,
    q: str | None = None,
    category: str | None = None,
    max_triggers: int | None = None,
    if_none_match: str | None = None,
    timeout: float = 30.0,
) -> dict | None:
    """GET /api/tools/capabilities — researcher surface inventory.

    Backend: cubemanus tool_capabilities API (docs/tool_capabilities_api_2026_05_20.md).

    Args:
        fields: ``summary`` / ``default`` / ``debug``. Omit to use server-side
            auto-summary (bare GET returns empty ``tools[]``; ``q`` or
            ``category`` flips to ``default``; explicit ``fields=default``
            without filters does the full ~300KB inventory dump).
        q: Substring search (≤ 256 chars). Case-insensitive.
        category: Single-category filter (e.g. ``disclosure_cn``).
        max_triggers: Cap per-tool and per-category sample triggers (1..64;
            default 8 server-side).
        if_none_match: Optional ETag from a previous call. Server returns
            304 when the underlying capability state is unchanged.
        timeout: HTTP timeout.

    Returns:
        Parsed JSON payload (the response dict with an added ``_etag`` key
        for client caching). ``None`` when ``if_none_match`` matches and
        the server returned 304 — caller should reuse cached payload.

    Raises:
        CueAPIError: 4xx / 5xx with structured detail.
    """
    api_key, base = load_config()
    params = []
    if fields is not None:
        params.append(("fields", fields))
    if q is not None:
        params.append(("q", q))
    if category is not None:
        params.append(("category", category))
    if max_triggers is not None:
        params.append(("max_triggers", str(max_triggers)))
    qs = urllib.parse.urlencode(params) if params else ""
    # base 已带 /api 前缀 (DEFAULT_BASE = https://cuecue.cn/api);其余 helper
    # 也都是 base + "/templates/..." / "/chat/..." 这种形态,不重复 /api。
    url = base.rstrip("/") + "/tools/capabilities"
    if qs:
        url = f"{url}?{qs}"

    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "application/json")
    if if_none_match:
        req.add_header("If-None-Match", if_none_match)

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 304:
            # Conditional GET success: caller's cache is still valid.
            return None
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(err_body)
                detail = (
                    parsed.get("detail")
                    if isinstance(parsed.get("detail"), str)
                    else json.dumps(parsed, ensure_ascii=False)
                )
            except Exception:
                detail = err_body[:400]
        except Exception:
            detail = "(no body)"
        raise CueAPIError(e.code, detail, "/api/tools/capabilities") from e
    except urllib.error.URLError as e:
        # 跟 _request() 同款 transport-layer error 包装,让 capabilities() 也走
        # CueAPIError(status=0) 路径而非 raw traceback (codex r6)
        reason = getattr(e, "reason", e)
        raise CueAPIError(
            0, f"network unreachable: {reason}", "/api/tools/capabilities"
        ) from e

    raw = resp.read().decode("utf-8")
    payload = json.loads(raw)
    # ETag echoed back as `_etag` so callers can pass it on next call
    # without juggling response headers themselves.
    etag = resp.headers.get("ETag")
    if etag:
        payload["_etag"] = etag
    return payload


def set_template_frequent(template_id: str, is_frequent: bool = True) -> dict:
    """Toggle the 'frequent' flag on a template — this is what surfaces
    the template on the user's Cue workbench "常用" (frequent) shortcuts.

    Maps to the `+frequent` verb in the cue-buddy skill. Cue has no
    cross-user publishing primitive at the API level; "frequent" simply
    means "pin this to my own workbench 常用 area for quick access."
    """
    body = {"template_id": template_id, "is_frequent": is_frequent}
    data = _request("POST", "/templates/frequent", body=body)
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    return data or {}


def rewrite(input: str, device_type: str = "cli") -> dict:
    """POST /api/rewrite — apply rewrite_prompt to a raw user query.

    Backend: cubemanus src/api/routes/rewrite.py:22 → rewrite_service
    .generate_rewrite_with_profile (src/service/rewrite_service.py:108)
    applies src/prompts/rewrite_prompt.py with the caller's USER_PROFILE.

    Returns the unwrapped RewriteData dict (matches set_template_frequent's
    `data["data"]` unwrap convention). Keys: `thinking`, `user_confirmation`
    (a confirm string to show the user), `task_node` (intent_tag,
    agent_persona, target_subject, search_methodology), `rewritten_mandate`
    (the structured mandate to send to /chat/stream), and `safety_flag`
    (pii_masked list, risk_category). Per backend
    `src/api/schemas/rewrite.py:RewriteData` the field is `thinking`,
    NOT `_thinking` (rewrite_prompt.py's template-string nomenclature drifted
    from the actual response schema).

    Used by cue-research's free-form path so privacy masking + public-source
    constraint + intent amplification apply — chat_stream itself does NOT
    invoke rewrite_prompt (only this endpoint does).

    `device_type` is a Header, not a body field (see rewrite.py:24).
    """
    api_key, base = load_config()
    url = base.rstrip("/") + "/rewrite"
    data = json.dumps({"input": input}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("device_type", device_type)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(err_body)
                detail = parsed.get("detail") if isinstance(parsed.get("detail"), str) else json.dumps(parsed, ensure_ascii=False)
            except Exception:
                detail = err_body[:400]
        except Exception:
            detail = "(no body)"
        raise CueAPIError(e.code, detail, "/api/rewrite") from e
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        raise CueAPIError(0, f"network unreachable: {reason}", "/api/rewrite") from e
    raw = resp.read().decode("utf-8")
    payload = json.loads(raw) if raw else {}
    # Backend wraps in DataResponse(data=RewriteData(...)) — unwrap so the
    # caller gets {thinking, user_confirmation, task_node, rewritten_mandate,
    # safety_flag} directly. See cubemanus src/api/routes/rewrite.py:85.
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload or {}


# ---------------------------------------------------------------------------
# Generation & live conversation (P2)
# ---------------------------------------------------------------------------


def generate_template(
    conversation_id: str,
    user_requirement: str,
    on_chunk: Callable[[str], None] | None = None,
) -> str:
    """Stream `/api/generate_template`. Returns the full JSON string.

    Uses the seed: bypass on the backend when `conversation_id` starts
    with "seed:" — passes only `user_requirement` to the LLM (no chat
    history required).
    """
    body = {
        "conversation_id": conversation_id,
        "user_requirement": user_requirement,
    }
    resp = _request("POST", "/generate_template", body=body, stream=True, timeout=120)
    buf = []
    for line in resp:
        text = line.decode("utf-8", errors="replace")
        if text.startswith("data:"):
            chunk = text[5:].lstrip() if text.startswith("data: ") else text[5:]
            chunk = chunk.rstrip("\n")
            buf.append(chunk)
            if on_chunk:
                on_chunk(chunk)
    return "".join(buf)


def chat_stream(
    payload: dict,
    on_event: Callable[[str, str], None] | None = None,
    max_seconds: float = 1200.0,
) -> Iterator[tuple[str, str]]:
    """Post to /api/chat/stream and iterate (event, data) tuples.

    payload must include messages, conversation_id, chat_id,
    workflow_id, template_id, need_* flags.
    """
    resp = _request("POST", "/chat/stream", body=payload, stream=True, timeout=max_seconds)
    event = ""
    for raw in resp:
        line = raw.decode("utf-8", errors="replace").rstrip("\n")
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data = line[5:].lstrip() if line.startswith("data: ") else line[5:]
            if on_event:
                on_event(event, data)
            yield event, data
        elif not line:
            event = ""


def replay(
    conversation_id: str,
    on_event: Callable[[str, str], None] | None = None,
    max_seconds: float = 1200.0,
) -> Iterator[tuple[str, str]]:
    """Read /api/replay/<conv> SSE stream until status=completed or
    max_seconds elapses."""
    resp = _request(
        "GET",
        f"/replay/{conversation_id}",
        stream=True,
        timeout=max_seconds,
    )
    event = ""
    for raw in resp:
        line = raw.decode("utf-8", errors="replace").rstrip("\n")
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data = line[5:].lstrip() if line.startswith("data: ") else line[5:]
            if on_event:
                on_event(event, data)
            yield event, data
        elif not line:
            event = ""


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


def _print_template_brief(t: dict) -> None:
    tid = t.get("template_id") or t.get("id") or "?"
    title = t.get("title") or "(no title)"
    cat = f"{t.get('primary_category', '?')}/{t.get('secondary_category', '?')}"
    intro = (t.get("input_form_spec") or "").replace("\n", " ")[:60]
    print(f"  {tid}  {title}  [{cat}]")
    print(f"    intro: {intro}")


def _cli() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 0
    cmd = sys.argv[1]
    try:
        if cmd == "whoami":
            key, base = load_config()
            print(f"base: {base}")
            print(f"key:  {key[:8]}...{key[-4:]}")
            templates = get_templates()
            print(f"templates accessible: {len(templates)}")
            return 0
        if cmd == "list":
            for t in get_templates():
                _print_template_brief(t)
            return 0
        if cmd == "get":
            if len(sys.argv) < 3:
                print("usage: cue_api.py get <template_id>")
                return 2
            print(json.dumps(get_template(sys.argv[2]), ensure_ascii=False, indent=2))
            return 0
        if cmd == "capabilities":
            # +capabilities CLI:GET /api/tools/capabilities researcher 端点
            # 用法:
            #   cue_api.py capabilities               # bare GET, auto-summary
            #   cue_api.py capabilities q=公告        # 按关键词过滤
            #   cue_api.py capabilities category=disclosure_cn
            #   cue_api.py capabilities fields=default  # 全量 inventory dump
            #   cue_api.py capabilities q=公告 max_triggers=3
            kwargs: dict = {}
            for arg in sys.argv[2:]:
                if "=" not in arg:
                    sys.stderr.write(
                        f"[capabilities] unexpected arg {arg!r}; "
                        f"use k=v form: q=<term> / category=<label> / "
                        f"fields=<summary|default|debug> / max_triggers=<int>\n"
                    )
                    return 2
                k, v = arg.split("=", 1)
                if k == "max_triggers":
                    kwargs[k] = int(v)
                elif k in ("fields", "q", "category"):
                    kwargs[k] = v
                else:
                    sys.stderr.write(f"[capabilities] unknown key {k!r}\n")
                    return 2
            payload = capabilities(**kwargs)
            if payload is None:
                print("[capabilities] 304 Not Modified (cache hit)")
                return 0
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if cmd in ("frequent", "unfrequent"):
            if len(sys.argv) < 3:
                print("usage: cue_api.py {frequent|unfrequent} <template_id>")
                return 2
            res = set_template_frequent(sys.argv[2], is_frequent=(cmd == "frequent"))
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0
        if cmd == "create":
            if len(sys.argv) < 3:
                print("usage: cue_api.py create <payload.json>")
                print("  payload must include: source_conversation_id + the 4 LLM fields")
                return 2
            payload_path = sys.argv[2]
            payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
            if not payload.get("source_conversation_id"):
                sys.stderr.write(
                    "[create] payload missing source_conversation_id; "
                    "use 'seed:<slug>:v1' for synthetic\n"
                )
                return 2
            res = create_template(payload)
            tid = res.get("template_id") or res.get("id") or "?"
            print(f"[create] created template_id={tid}")
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0
        if cmd == "update":
            if len(sys.argv) < 4:
                print("usage: cue_api.py update <template_id> <payload.json>")
                print("  payload may include any subset of the 4 LLM fields + meta")
                return 2
            template_id = sys.argv[2]
            payload_path = sys.argv[3]
            payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
            res = update_template(template_id, payload)
            print(f"[update] updated template_id={template_id}")
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0
        if cmd == "replay":
            # codex r5 finding: test_template.py fallback hint 写 'cue_api.py
            # replay <conv_id>' 但本 CLI 没这个 subcommand,user 跑出 unknown cmd。
            # 加 replay 子命令:重 emit conversation SSE 流到 stdout
            # (无 credit cost, backend resume=0 default)。
            #
            # 用法:
            #   cue_api.py replay <conversation_id>
            #   cue_api.py replay <conversation_id> --timeout 600
            #   cue_api.py replay <conversation_id> --report-only  # 只打 reporter 内容
            if len(sys.argv) < 3:
                print(
                    "usage: cue_api.py replay <conversation_id> "
                    "[--timeout <s>] [--report-only]"
                )
                return 2
            conv_id = sys.argv[2]
            rest = sys.argv[3:]
            timeout = 600.0  # replay 是 DB 重放（报告已跑完），很快，无需对齐实时 60min 上限
            report_only = False
            i = 0
            while i < len(rest):
                arg = rest[i]
                if arg == "--timeout" and i + 1 < len(rest):
                    timeout = float(rest[i + 1])
                    i += 2
                elif arg == "--report-only":
                    report_only = True
                    i += 1
                else:
                    print(f"[replay] unknown arg: {arg!r}")
                    return 2

            in_reporter = False
            report_pieces: list[str] = []
            event_count = 0
            for event, data in replay(conv_id, max_seconds=timeout):
                event_count += 1
                if report_only:
                    try:
                        payload = json.loads(data) if data else {}
                    except json.JSONDecodeError:
                        continue
                    event_data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
                    agent = payload.get("agent_name") or event_data.get("agent_name", "")
                    if event == "start_of_agent" and agent == "reporter":
                        in_reporter = True
                    elif event == "end_of_agent" and agent == "reporter":
                        in_reporter = False
                    elif in_reporter and event == "message":
                        delta = event_data.get("delta") or {}
                        text = delta.get("content") or ""
                        if text:
                            report_pieces.append(text)
                else:
                    print(f"event: {event}")
                    print(f"data: {data}")
                    print()
            if report_only:
                report = "".join(report_pieces)
                if report:
                    print(report)
                else:
                    sys.stderr.write(
                        f"[replay] no reporter content captured "
                        f"(events={event_count}); server-side may have failed\n"
                    )
                    return 1
            else:
                sys.stderr.write(f"[replay] {event_count} events read\n")
            return 0
        print(f"unknown cmd: {cmd}")
        print(__doc__)
        return 2
    except CueAPIError as e:
        sys.stderr.write(f"[error] {e}\n")
        hint = e.user_hint()
        if hint:
            sys.stderr.write(f"        → {hint}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
