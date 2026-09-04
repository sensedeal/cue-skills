#!/usr/bin/env python3
"""cue-omni-reader skill regression — stdlib only."""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_DIR = _HERE.parent
_REPO_ROOT = _SKILL_DIR.parent
_SKILL_MD = _SKILL_DIR / "SKILL.md"
_SKILL_ZH_MD = _SKILL_DIR / "SKILL.zh-CN.md"
_README_MD = _SKILL_DIR / "README.md"
_README_ZH_MD = _SKILL_DIR / "README.zh-CN.md"
_SETUP_MD = _SKILL_DIR / "references" / "setup.md"
_COMPAT_MD = _SKILL_DIR / "references" / "compatibility.md"
_REPORTS_DIR = _SKILL_DIR / "docs" / "verification-reports"
_BRIDGE_AUDIT_MD = _REPORTS_DIR / "2026-08-08-bridge-cli-audit.md"
_CONTENT_ONLY_REPORT_MD = _REPORTS_DIR / "2026-08-11-content-only-compat.md"
_EXPECTED_SKILL_VERSION = "0.5.0"
_EXPECTED_BRIDGE_VERSION = "1.7.1"
_CURRENT_PUBLICATION_REPORT = "2026-09-04-bridge-1.7.1-published.md"
_STANDALONE_IIIS = re.compile(r"(?<![A-Za-z0-9])iiis(?![A-Za-z0-9])", re.I)
_ACCOUNT_OR_CREDIT_BALANCE = re.compile(
    r"(?<![A-Za-z0-9_])(?:\*\*|__|`)?\s*"
    r"(?P<balance_key_quote>[\"']?)"
    r"(?:account[\s_-]*balance|credit[\s_-]*balance"
    r"|remaining[\s_-]*credits|credits[\s_-]*remaining)"
    r"(?P=balance_key_quote)\s*(?:\*\*|__|`)?\s*"
    r"(?::|=|\bis\b|\bwas\b|\bwere\b|\bof\b|\|)\s*"
    r"(?!\[redacted\]|<redacted>|\$\{)"
    r"(?:\*\*|__|`)?\s*"
    r"[+\-−]?\s*(?:\(\s*)?[+\-−]?\s*"
    r"(?:(?P<balance_prefix_quote>[\"']?)"
    r"(?:USD|EUR|GBP|CNY|RMB|JPY|CAD|AUD|HKD|[$€£¥])"
    r"(?P=balance_prefix_quote)\s*)?"
    r"[+\-−]?\s*(?P<balance_value_quote>[\"']?)"
    r"[+\-−]?\s*(?:\(\s*)?[+\-−]?\s*"
    r"(?:(?:USD|EUR|GBP|CNY|RMB|JPY|CAD|AUD|HKD"
    r"|[$€£¥])\s*)?[+\-−]?\s*\d[\d,]*(?:\.\d+)?"
    r"(?:\s*(?:USD|EUR|GBP|CNY|RMB|JPY|CAD|AUD|HKD"
    r"|[$€£¥]))?(?:\s*\))?"
    r"(?P=balance_value_quote)"
    r"(?:\s*(?P<balance_suffix_quote>[\"']?)"
    r"(?:USD|EUR|GBP|CNY|RMB|JPY|CAD|AUD|HKD|[$€£¥])"
    r"(?P=balance_suffix_quote))?(?:\s*\))?"
    r"\s*(?:\*\*|__|`)?(?![\d.])",
    re.I,
)


def _required_text(case: unittest.TestCase, path: Path) -> str:
    case.assertTrue(path.is_file(), f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def _bridge_pin(text: str) -> str:
    """The audited Bridge spec pin in a reference doc, e.g. @cueai/omni-reader-mcp@1.4.0."""
    match = re.search(r"@cueai/omni-reader-mcp@\d+\.\d+\.\d+", text)
    if not match:
        raise AssertionError("no @cueai/omni-reader-mcp@X.Y.Z pin found")
    return match.group(0)


def _release_evidence_documents() -> tuple[Path, ...]:
    documents = {
        *_REPORTS_DIR.glob("*.md"),
        _COMPAT_MD,
    }
    return tuple(sorted(documents, key=str))


def _codex_evidence_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    codex_section_level: int | None = None

    def flush() -> None:
        if not current:
            return
        block = "\n".join(current)
        if codex_section_level is not None or re.search(
            r"\bCodex(?: CLI)?\b",
            block,
            re.I,
        ):
            blocks.append(block)
        current.clear()

    for line in text.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading:
            flush()
            level = len(heading.group(1))
            if codex_section_level is not None and level <= codex_section_level:
                codex_section_level = None
            if re.search(r"\bCodex(?: CLI)?\b", heading.group(2), re.I):
                codex_section_level = level
            continue
        if not line.strip():
            flush()
            continue
        if line.startswith("|"):
            flush()
            if codex_section_level is not None or re.search(
                r"\bCodex(?: CLI)?\b",
                line,
                re.I,
            ):
                blocks.append(line)
            continue
        if re.match(r"^\s*(?:[-*]|\d+\.)\s+", line):
            flush()
            current.append(line)
            continue
        current.append(line)
    flush()
    return blocks


def _codex_evidence_issues(text: str) -> list[str]:
    forbidden_claim = re.compile(
        r"(?<!not )(?<!never )(?<!not been )(?<!n't been )"
        r"\bnatively discovered\b"
        r"|(?<!not )(?<!never )(?<!not been )(?<!n't been )"
        r"\bnatively loaded\b"
        r"|\bnative[- ]loading\b"
        r"(?:(?!\bnot\b|\bnever\b|\bunverified\b).){0,80}"
        r"\b(?:verified|observed|demonstrated|passed|succeeded|occurred|successful|confirmed|worked)\b"
        r"|\bnative(?:[- ]project)?[- ]discovery\b"
        r"(?:(?!\bnot\b|\bnever\b|\bunverified\b).){0,80}"
        r"\b(?:verified|observed|demonstrated|passed|succeeded|occurred|successful|confirmed|worked)\b"
        r"|\bproject discovery(?:/| and )loading\b"
        r"(?:(?!\bnot\b|\bnever\b|\bunverified\b).){0,80}"
        r"\b(?:verified|observed|demonstrated|passed|succeeded|occurred|successful|confirmed|worked)\b"
        r"|\bdiscovery/loading (?:run|check|path)\b"
        r"|\b(?:Codex(?: CLI)?|native|project[- ]skill) "
        r"(?:project[- ])?(?:skill[- ])?"
        r"(?:discovery|loading|selection|activation)"
        r"(?:(?:/| and )(?:discovery|loading|selection|activation))*\b"
        r"(?:(?!\bnot\b|\bnever\b|\bunverified\b).){0,80}"
        r"\b(?:verified|observed|demonstrated|passed|succeeded|occurred|successful|confirmed|worked)\b"
        r"|(?<!no )\b(?:the )?activation[- ]tool(?: use)? "
        r"(?:was|is|has been) (?:used|called|invoked|observed|verified)\b"
        r"|\bclient activation (?:was|is|has been) "
        r"(?:observed|verified|demonstrated|recorded)\b"
        r"|\b(?:skill|client) activation (?:succeeded|occurred)\b"
        r"|\b(?:the )?(?:project[- ])?skill was "
        r"(?:(?:successfully|automatically) )?"
        r"(?:discovered|selected|loaded|activated)\b"
        r"|\bCodex(?: CLI)? (?:automatically )?"
        r"(?:discovered|selected|loaded|activated) "
        r"(?:the )?(?:project )?skill\b"
        r"|\bCodex(?: CLI)? (?:found|located) "
        r"(?:the )?(?:project )?skill(?: file)?\b"
        r"|\bCodex(?: CLI)? (?:found|located|selected)\b"
        r"[^\n]{0,160}\bSKILL\.md\b"
        r"|\bCodex(?: CLI)? used an ephemeral project copy\b"
        r"|\b(?:the )?(?:official )?package was copied\b"
        r"[^\n]{0,160}\bephemeral\b[^\n]{0,80}\bproject\b"
        r"|\bCodex(?: CLI)? was (?:prompted|asked|told|instructed)\b"
        r"[^\n]{0,120}\bskill\b"
        r"|\b(?:the )?prompt (?:explicitly )?"
        r"(?:asked|requested|told|instructed)\b"
        r"[^\n]{0,160}\b(?:Codex|skill)\b"
        r"|\b(?:the )?(?:project )?(?:skill|package) was "
        r"(?:copied|placed|staged|installed|mounted|symlinked|written)\b"
        r"[^\n]{0,160}\.agents/skills/"
        r"|\bephemeral\b[^\n]{0,120}\.agents/skills/"
        r"[^\n]{0,120}\b(?:workspace|project)\b"
        r"[^\n]{0,80}\b(?:contained|included|held|provided)\b"
        r"[^\n]{0,80}\bskill\b"
        r"|`activate_skill`|`Skill` activation",
        re.I,
    )
    exact_skill_file = ".agents/skills/cue-omni-reader/SKILL.md"
    exact_skill_path = re.escape(f"`{exact_skill_file}`")
    agents_path = re.compile(
        r"(?<![A-Za-z0-9_/-])"
        r"(\.agents/[A-Za-z0-9_./-]+)",
        re.I,
    )
    observation = re.compile(
        r"\b(?:observed|JSONL|recorded|showed|read|reading|opened|opening|inspected|accessed)\b",
        re.I,
    )
    path_claim = re.compile(
        r"(?:(?<!no )(?<!not )(?<!never )\b"
        r"(?:copied|placed|staged|installed|mounted|symlinked|wrote|"
        r"prepared|provisioned|configured|found|located|selected|loaded|"
        r"activated|discovered)\b"
        r"[^\n]{0,200}\.agents/skills/[A-Za-z0-9._-]+/SKILL\.md"
        r"|\.agents/skills/[A-Za-z0-9._-]+/SKILL\.md"
        r"[^\n]{0,160}\b(?:was|is|has been) (?:successfully )?"
        r"(?:copied|placed|staged|installed|mounted|symlinked|written|"
        r"prepared|provisioned|configured|found|located|selected|loaded|"
        r"activated|discovered)\b"
        r"|(?<!no )\bsetup\b[^\n]{0,200}"
        r"\.agents/skills/[A-Za-z0-9._-]+/SKILL\.md)",
        re.I,
    )
    observed_read = re.compile(
        rf"\bJSONL\b.*\bread(?:ing)?\b.*{exact_skill_path}",
        re.I | re.S,
    )
    blocks = _codex_evidence_blocks(text)
    issues = [
        f"Codex evidence overclaim: {block}"
        for block in blocks
        if forbidden_claim.search(block)
    ]
    agents_path_blocks = [
        paragraph
        for paragraph in re.split(r"\n\s*\n", text)
        if agents_path.search(paragraph)
    ]
    issues.extend(
        f"Codex evidence overclaim: {paragraph}"
        for paragraph in agents_path_blocks
        if path_claim.search(paragraph)
    )
    issues.extend(
        f"Codex evidence overclaim: standalone .agents path: {paragraph}"
        for paragraph in agents_path_blocks
        if exact_skill_file in {
            path.rstrip(".") for path in agents_path.findall(paragraph)
        }
        and not observed_read.search(paragraph)
    )
    relevant_evidence = bool(
        issues
        or agents_path_blocks
        or any(
            observation.search(block)
            and ("JSONL" in block or re.search(r"SKILL\.md", block, re.I))
            for block in blocks
        )
    )
    if not relevant_evidence:
        return []

    path_blocks = [*blocks, *agents_path_blocks]
    for block in dict.fromkeys(path_blocks):
        observed_paths = re.findall(r"`([^`\n]*SKILL\.md)`", block, re.I)
        observed_paths.extend(agents_path.findall(block))
        normalized_paths = [path.rstrip(".") for path in observed_paths]
        if any(path != exact_skill_file for path in normalized_paths):
            issues.append("unexpected Codex skill read path")
            break
    if not any(observed_read.search(block) for block in blocks):
        issues.append("missing exact observed Codex read")
    return issues


def _frontmatter(case: unittest.TestCase, markdown: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", markdown, re.S)
    case.assertIsNotNone(match, "SKILL.md missing YAML frontmatter")
    return match.group(1)


def _decode_shipped_text(
    case: unittest.TestCase,
    relative: str,
    data: bytes,
) -> str:
    case.assertNotIn(b"\0", data, f"binary file is not allowed: {relative}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        case.fail(f"non-UTF-8 file is not allowed: {relative}")


def _shipped_text_files(
    case: unittest.TestCase,
    root: Path,
) -> dict[str, str]:
    shipped: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        shipped[relative] = _decode_shipped_text(
            case,
            relative,
            path.read_bytes(),
        )
    return shipped


def _release_sensitive_text_files(
    case: unittest.TestCase,
) -> dict[Path, str]:
    shipped = _shipped_text_files(case, _SKILL_DIR)
    return {
        _SKILL_DIR / relative: text for relative, text in shipped.items()
    }


def _assert_exact_layout(
    case: unittest.TestCase,
    shipped: dict[str, str],
    expected: set[str],
) -> None:
    case.assertEqual(set(shipped), expected)


def _assert_no_account_or_credit_balance(
    case: unittest.TestCase,
    text: str,
) -> None:
    case.assertIsNone(
        _ACCOUNT_OR_CREDIT_BALANCE.search(text),
        "account or credit balance unexpectedly found in release evidence",
    )


def _assert_no_sensitive_content(
    case: unittest.TestCase,
    text: str,
) -> None:
    patterns = (
        (
            "AWS access key",
            re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        ),
        (
            "GitHub token",
            re.compile(
                r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}"
                r"|github_pat_[A-Za-z0-9_]{20,})\b",
            ),
        ),
        (
            "OpenAI-style key",
            re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b", re.I),
        ),
        (
            "assigned secret",
            re.compile(
                r"(?<![A-Z0-9_])(?P<secret_key_quote>[\"']?)"
                r"[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)"
                r"(?P=secret_key_quote)\s*[:=]\s*"
                r"(?!\$\{|\[redacted\]|<)"
                r"(?P<secret_value_quote>[\"']?)"
                r"(?:Bearer\s+)?[A-Za-z0-9._~+/=-]{16,}"
                r"(?P=secret_value_quote)(?![A-Za-z0-9._~+/=-])",
                re.I,
            ),
        ),
        (
            "Bearer credential",
            re.compile(
                r"\bBearer\s+(?!\$\{|\[redacted\])"
                r"[A-Za-z0-9._~+/=-]{16,}",
                re.I,
            ),
        ),
        (
            "macOS personal path",
            re.compile(r"/Users/[A-Za-z0-9._-]+/"),
        ),
        (
            "Linux home path",
            re.compile(r"/home/[A-Za-z0-9._-]+/"),
        ),
        (
            "root home path",
            re.compile(r"/root(?:/|\\)"),
        ),
        (
            "Windows user path",
            re.compile(
                r"C:[\\/]+Users[\\/]+[A-Za-z0-9._-]+[\\/]",
                re.I,
            ),
        ),
        (
            "Windows UNC user path",
            re.compile(
                r"\\\\[^\\/\s]+\\Users\\[A-Za-z0-9._-]+\\",
                re.I,
            ),
        ),
        (
            "private IPv4 address",
            re.compile(
                r"\b(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)"
                r"(?:\d{1,3}\.){1,2}\d{1,3}\b",
            ),
        ),
        (
            "account or credit balance",
            _ACCOUNT_OR_CREDIT_BALANCE,
        ),
        (
            "full operation or result ID",
            re.compile(
                r"(?<![A-Za-z0-9_])(?P<key_quote>[\"']?)"
                r"(?:operation|result)(?:_id)?(?P=key_quote)\s*[:=]\s*"
                r"(?P<value_quote>[\"']?)[A-Za-z0-9-]{20,}"
                r"(?P=value_quote)(?![A-Za-z0-9_])",
                re.I,
            ),
        ),
    )
    for label, pattern in patterns:
        case.assertIsNone(pattern.search(text), f"found {label}")
    case.assertNotIn("mcp" + "__", text)
    case.assertNotRegex(text, r"CUE_API_KEY\s*(?:\|\||\?\?)\s*['\"]")


class TestSkillMd(unittest.TestCase):
    def setUp(self) -> None:
        self.md = _required_text(self, _SKILL_MD)
        self.fm = _frontmatter(self, self.md)

    def test_frontmatter_is_portable_and_trigger_focused(self) -> None:
        top_level = set(re.findall(r"^([a-z][a-z-]*):", self.fm, re.M))
        self.assertEqual(
            top_level,
            {"name", "description", "license", "metadata"},
        )
        self.assertRegex(self.fm, re.compile(r"^name: cue-omni-reader$", re.M))
        description = re.search(
            r'^description:\s*"([^"]+)"$', self.fm, re.M
        )
        self.assertIsNotNone(description)
        self.assertTrue(description.group(1).startswith("Use when "))
        for workflow_word in ("install", "poll", "retry", "discard", "setup"):
            self.assertNotIn(workflow_word, description.group(1).lower())
        self.assertRegex(
            self.fm,
            re.compile(
                rf'^\s*version:\s*"{re.escape(_EXPECTED_SKILL_VERSION)}"$',
                re.M,
            ),
        )
        self.assertIn('bins: ["node"]', self.fm)
        self.assertIn('envOptional: ["CUE_API_KEY"]', self.fm)

    def test_skill_is_thin_and_uses_official_tools(self) -> None:
        self.assertIn("MCP package and active tool schemas are authoritative", self.md)
        for tool in (
            "`parse`",
            "`get_parse_status`",
            "`cancel_parse`",
            "`read_result`",
            "`read_outline`",
            "`discard_result`",
            "`save_result`",
        ):
            self.assertIn(tool, self.md)
        self.assertNotIn("mcp" + "__", self.md)
        # 1000: unified parse/error guidance sits below this; preserve a tight guard.
        self.assertLess(len(self.md.split()), 1000, "SKILL.md is no longer thin")

    def test_source_handling_preserves_the_security_boundary(self) -> None:
        self.assertIn("Only HTTP(S) strings are URLs", self.md)
        self.assertIn("Pass the user's source string directly to `parse`", self.md)
        self.assertRegex(self.md, re.compile(r"Do not pre-read.*base64", re.S))
        self.assertIn("`file://`", self.md)
        self.assertIn("public temporary upload", self.md)

    def test_parse_is_the_only_first_call_and_continuations_are_automatic(self) -> None:
        self.assertIn(
            "Use `parse` as the only first call for both HTTP(S) URLs and local paths",
            self.md,
        )
        self.assertIn(
            "do not ask the user to choose a local, remote, upload, or URL mode",
            self.md,
        )
        self.assertIn(
            "Choose continuation tools from the structured result",
            self.md,
        )
        self.assertIn(
            "never present the tool list as a menu for the user",
            self.md,
        )

    def test_text_output_retains_textual_structure(self) -> None:
        self.assertIn(
            "Text output is Markdown and may retain headings, lists, GFM tables, or raw HTML tables",
            self.md,
        )
        self.assertIn(
            "it lacks grounding/layout sidecars, not all structure",
            self.md,
        )
        self.assertIn(
            "An empty outline means no recognized headings, not that the text has no structure",
            self.md,
        )

    def test_bootstrap_requires_confirmation_and_minimum_root(self) -> None:
        self.assertRegex(
            self.md,
            r"Before installing the Bridge or expanding an allowed root, obtain user confirmation",
        )
        self.assertIn("minimum required directory", self.md)
        self.assertIn("references/setup.md", self.md)
        self.assertIn("`doctor`", self.md)
        self.assertRegex(self.md, re.compile(r"reload|restart", re.I))
        self.assertRegex(self.md, re.compile(r"never ask.*API key.*chat", re.I))
        self.assertRegex(
            self.md,
            re.compile(
                r"already inside an allowed root.*do not ask for another confirmation",
                re.I | re.S,
            ),
        )

    def test_parse_strategy_obeys_the_active_schema(self) -> None:
        self.assertIn("Obey the active `parse` schema", self.md)
        self.assertRegex(
            self.md,
            re.compile(r"schema exposes `wait`.*`wait: false`", re.S),
        )
        self.assertIn("source-only Bridge", self.md)
        self.assertRegex(self.md, re.compile(r"long media|large document", re.I))
        self.assertRegex(
            self.md,
            re.compile(r"Do not race.*synchronous.*asynchronous", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(r"ambiguous timeout.*confirmation", re.I | re.S),
        )

    def test_operation_lifecycle_is_recoverable(self) -> None:
        self.assertIn("save the `operation_id`", self.md)
        self.assertRegex(
            self.md,
            re.compile(r"recover.*existing operation.*before resubmitting", re.I),
        )
        for state in (
            "`processing`",
            "`completed`",
            "`cleanup_pending`",
            "`failed`",
            "`canceled`",
            "`expired`",
        ):
            self.assertIn(state, self.md)
        self.assertRegex(
            self.md,
            re.compile(r"user asks to stop.*`cancel_parse`", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(r"cannot promise.*charges", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(r"tool-level error.*not.*MCP disconnection", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(
                r"state not recognized.*preserve.*operation.*do not resubmit"
                r".*claim.*completion.*cancellation.*billing.*cleanup",
                re.I | re.S,
            ),
        )

    def test_artifact_is_fully_consumed_then_discarded(self) -> None:
        self.assertIn("`result.kind=artifact`", self.md)
        self.assertIn("`next_cursor`", self.md)
        self.assertRegex(
            self.md,
            re.compile(r"preview.*not.*complete", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(r"original task.*`discard_result`", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(r"claim deletion only after.*confirmed", re.I | re.S),
        )

    def test_result_delivery_decision_table_is_explicit(self) -> None:
        for line in (
            "Answer directly → inline when present; otherwise `read_result`",
            "Find one section → `read_outline` → `read_result(cursor)`",
            "Read all content → `read_result` until no `next_cursor`",
            "Deliver a file → `save_result`",
        ):
            self.assertIn(line, self.md)
        self.assertIn('`result_delivery="artifact"`', self.md)
        for use_case in ("saving", "section navigation", "multiple documents", "strict context control"):
            self.assertIn(use_case, self.md)
        self.assertRegex(
            self.md,
            re.compile(r"`read_outline`.*does not require.*`save_result`", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(r"bounded concurrent independent `parse` calls", re.I),
        )

    def test_unknown_client_capabilities_have_safe_fallbacks(self) -> None:
        for capability in ("Tasks unknown", "Roots unknown", "Host timeout unknown", "Cwd/workspace unknown"):
            self.assertIn(capability, self.md)
        self.assertRegex(self.md, re.compile(r"Tasks unknown.*ordinary `parse`.*`get_parse_status`", re.S))
        self.assertRegex(self.md, re.compile(r"Roots unknown.*process cwd.*explicit roots", re.I | re.S))
        self.assertRegex(self.md, re.compile(r"Host timeout unknown.*20-second status wait", re.S))
        self.assertRegex(self.md, re.compile(r"Cwd/workspace unknown.*do not widen", re.I | re.S))

    def test_same_source_reuse_is_scoped_to_recoverable_or_retained_records(self) -> None:
        self.assertRegex(
            self.md,
            re.compile(
                r"Same-source retries.*reuse only.*recoverable.*retained-completed records",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            self.md,
            re.compile(
                r"failed.*canceled.*expired.*out-of-window.*may create.*bill.*new operation",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            self.md,
            re.compile(
                r"reusable record.*`auto`→`artifact`.*without a second operation",
                re.I | re.S,
            ),
        )
        self.assertNotIn(
            "A same-source, same-representation retry reuses the durable identity",
            self.md,
        )

    def test_content_only_fallback_preserves_state_and_document_bytes(self) -> None:
        self.assertRegex(
            self.md,
            re.compile(
                r"structuredContent.*when available.*content\[\]\.text",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            self.md,
            re.compile(
                r"completed inline.*exact Markdown.*non-inline.*compact JSON",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            self.md,
            re.compile(r"append only.*`result\.text`", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(r"never append.*JSON wrapper", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(r"generic success.*not.*completed result", re.I | re.S),
        )

    def test_summary_uses_the_complete_assembled_result(self) -> None:
        self.assertRegex(
            self.md,
            re.compile(r"summary.*assemble.*complete result.*first", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(r"parse only.*complete Markdown.*offer.*summary", re.I | re.S),
        )
        self.assertRegex(
            self.md,
            re.compile(r"do not truncate", re.I),
        )

    def test_billing_errors_and_original_task_remain_truthful(self) -> None:
        self.assertRegex(self.md, re.compile(r"Report.*billing facts", re.I))
        self.assertRegex(
            self.md,
            re.compile(r"retry only when.*retryable", re.I | re.S),
        )
        self.assertIn("Continue the user's original task after parsing", self.md)


class TestReferences(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = _required_text(self, _SKILL_MD)
        self.skill_zh = _required_text(self, _SKILL_ZH_MD)
        self.readme = _required_text(self, _README_MD)
        self.readme_zh = _required_text(self, _README_ZH_MD)
        self.setup = _required_text(self, _SETUP_MD)
        self.compat = _required_text(self, _COMPAT_MD)

    def test_network_diagnostics_are_stage_aware_and_do_not_publish_internal_names(
        self,
    ) -> None:
        doctor = (
            f"npx -y @cueai/omni-reader-mcp@{_EXPECTED_BRIDGE_VERSION} doctor --json"
        )
        english = (self.skill, self.readme)
        chinese = (self.skill_zh, self.readme_zh)
        active_documents = (*english, *chinese, self.setup, self.compat)

        for document in (*english, *chinese):
            self.assertIn("CUBE_UNAVAILABLE", document)
            self.assertIn("CUBE_PROTOCOL_ERROR", document)
            self.assertIn(doctor, document)
        for document in english:
            self.assertIn("secure upload stage", document)
        for document in chinese:
            self.assertIn("安全上传阶段", document)
        for document in active_documents:
            self.assertNotRegex(document, _STANDALONE_IIIS)
            self.assertNotIn("cubefile.ai.iiis.co", document)

    def test_bridge_upgrade_guidance_avoids_a_circular_reinstall(self) -> None:
        for document in (self.skill, self.readme):
            self.assertIn("BRIDGE_UPGRADE_REQUIRED", document)
            self.assertIn("install the latest published", document.lower())
            self.assertRegex(
                document,
                re.compile(
                    r"already running the latest published release.*do not reinstall or retry"
                    r".*doctor --json.*service operator.*Bridge admission",
                    re.I | re.S,
                ),
            )
        for document in (self.skill_zh, self.readme_zh):
            self.assertIn("BRIDGE_UPGRADE_REQUIRED", document)
            self.assertIn("安装最新已发布版本", document)
            self.assertRegex(
                document,
                re.compile(
                    r"已经运行最新已发布版本.*不要重新安装或重试"
                    r".*doctor --json.*服务运维方.*Bridge admission",
                    re.S,
                ),
            )

    def test_unified_parse_guidance_and_error_semantics_are_bilingual(self) -> None:
        english = (self.skill, self.readme)
        chinese = (self.skill_zh, self.readme_zh)

        for document in english:
            self.assertIn(
                "Use `parse` as the only first call for both HTTP(S) URLs and local paths",
                document,
            )
            self.assertIn(
                "Choose continuation tools from the structured result",
                document,
            )
            self.assertIn(
                "Text output is Markdown and may retain headings, lists, GFM tables, or raw HTML tables",
                document,
            )
            self.assertIn(
                "An empty outline means no recognized headings, not that the text has no structure",
                document,
            )
            self.assertIn("OMNI_NOT_ENTITLED", document)
            self.assertIn("DIRECT_UPLOAD_DISABLED", document)
            self.assertIn("DIRECT_UPLOAD_UNAVAILABLE", document)
            self.assertIn("DETAIL_CAPABILITIES_UNAVAILABLE", document)
            self.assertIn("UNSUPPORTED_DETAIL", document)
            self.assertIn("HTTP 403 is the account-entitlement signal", document)
            self.assertIn("not that the account is disabled or text-only", document)
            self.assertIn("do not retry unchanged", document)

        for document in chinese:
            self.assertIn("`parse` 是 HTTP(S) URL 与本地路径唯一的首次调用", document)
            self.assertIn("根据结构化结果选择后续工具", document)
            self.assertIn("文本输出是 Markdown", document)
            self.assertIn("GFM 表格或原始 HTML 表格", document)
            self.assertIn("空 outline 只表示没有识别到标题", document)
            self.assertIn("OMNI_NOT_ENTITLED", document)
            self.assertIn("DIRECT_UPLOAD_DISABLED", document)
            self.assertIn("DIRECT_UPLOAD_UNAVAILABLE", document)
            self.assertIn("DETAIL_CAPABILITIES_UNAVAILABLE", document)
            self.assertIn("UNSUPPORTED_DETAIL", document)
            self.assertIn("HTTP 403 才是账号 entitlement 信号", document)
            self.assertIn("不表示账号被禁用或账号只能使用 text", document)
            self.assertIn("不要原样重试", document)

    def test_physical_tool_sets_are_fixed_but_not_user_modes(self) -> None:
        self.assertIn(
            "Remote-only exposes exactly `parse`, `get_parse_status`, and `cancel_parse`",
            self.skill,
        )
        self.assertIn(
            "Bridge exposes the same three plus `read_result`, `read_outline`, `discard_result`, and `save_result`",
            self.skill,
        )
        self.assertIn(
            "Only `parse` is a first call; the other six are continuation and lifecycle primitives",
            self.skill,
        )
        self.assertNotIn("## Public tools", self.skill)
        self.assertNotIn("## Public tools (seven)", self.readme)
        self.assertIn(
            "仅远端表面恰好暴露 `parse`、`get_parse_status`、`cancel_parse`",
            self.skill_zh,
        )
        self.assertIn(
            "Bridge 暴露同样三个工具，再加 `read_result`、`read_outline`、`discard_result`、`save_result`",
            self.skill_zh,
        )
        self.assertIn("只有 `parse` 是首次调用", self.skill_zh)
        self.assertNotIn("## 公共工具", self.skill_zh)
        self.assertNotIn("## 公共工具（七个）", self.readme_zh)

    def test_doctor_limits_its_claim_to_control_configuration_facts(self) -> None:
        english = (self.readme, self.setup)
        chinese = (self.readme_zh,)
        for document in (*english, *chinese):
            self.assertNotIn("endpoint compatibility", document)
            self.assertNotIn("端点兼容性", document)
            self.assertNotIn("endpoint and compatibility facts", document)
            self.assertNotIn("端点与兼容性事实", document)
        for document in english:
            self.assertIn(
                "only authenticated Cube control/configuration facts",
                document,
            )
            self.assertIn("The granted data plane is not probed", document)
            self.assertIn(
                "only a real local-file parse validates the route end-to-end",
                document,
            )
        for document in chinese:
            self.assertIn("仅检查已鉴权的 Cube 控制面/配置事实", document)
            self.assertIn("不会探测已授权数据平面", document)
            self.assertIn("只有真实本地文件 parse 才能端到端验证该路由", document)

    def test_active_documents_pin_the_exact_current_bridge(self) -> None:
        pin = f"@cueai/omni-reader-mcp@{_EXPECTED_BRIDGE_VERSION}"
        for document in (
            self.skill,
            self.skill_zh,
            self.readme,
            self.readme_zh,
            self.setup,
        ):
            pins = re.findall(r"@cueai/omni-reader-mcp@\d+\.\d+\.\d+", document)
            self.assertTrue(pins, "active document has no Bridge package pin")
            self.assertEqual(
                set(pins),
                {pin},
                "every active Bridge package reference must use the current audited pin",
            )

    def test_english_and_chinese_result_guidance_is_semantically_aligned(self) -> None:
        english = (
            "Answer directly → inline when present; otherwise `read_result`",
            "Find one section → `read_outline` → `read_result(cursor)`",
            "Read all content → `read_result` until no `next_cursor`",
            "Deliver a file → `save_result`",
        )
        chinese = (
            "直接回答 → 有 inline 就直接用；否则 `read_result`",
            "定位一个章节 → `read_outline` → `read_result(cursor)`",
            "读取全部内容 → 反复 `read_result`，直到没有 `next_cursor`",
            "交付文件 → `save_result`",
        )
        for line in english:
            self.assertIn(line, self.skill)
        for line in chinese:
            self.assertIn(line, self.skill_zh)
        for token in (
            '`result_delivery="artifact"`',
            "read_outline",
            "save_result",
            "multiple documents",
            "bounded concurrent independent `parse` calls",
            "Tasks unknown",
            "Roots unknown",
            "Host timeout unknown",
            "Cwd/workspace unknown",
        ):
            self.assertIn(token, self.skill)
        for token in (
            '`result_delivery="artifact"`',
            "read_outline",
            "save_result",
            "多份文档",
            "有界并发的独立 `parse` 调用",
            "Tasks 未知",
            "Roots 未知",
            "宿主超时未知",
            "cwd/workspace 关系未知",
        ):
            self.assertIn(token, self.skill_zh)

    def test_english_and_chinese_retry_reuse_boundaries_are_aligned(self) -> None:
        for token in (
            "Same-source retries reuse only",
            "recoverable",
            "retained-completed records",
            "failed",
            "canceled",
            "expired",
            "out-of-window",
            "may create and bill a new operation",
        ):
            self.assertIn(token, self.skill)
        for token in (
            "同来源重试只复用",
            "可恢复",
            "仍保留的已完成记录",
            "失败",
            "已取消",
            "已过期",
            "超出交付窗口",
            "可能新建 operation 并计费",
        ):
            self.assertIn(token, self.skill_zh)

    def test_active_guidance_has_no_copied_rate_conversions(self) -> None:
        active = "\n".join((self.skill, self.skill_zh, self.readme, self.readme_zh, self.setup))
        for copied in (
            "150 pages",
            "150 页",
            "30 minutes of audio",
            "30 分钟音频",
            "4 minutes of video",
            "4 分钟视频",
            "67 credits / 1,000",
        ):
            self.assertNotIn(copied, active)

    def test_readmes_do_not_hardcode_the_regression_count(self) -> None:
        self.assertNotRegex(self.readme, r"#\s*\d+\s+skill regression tests")
        self.assertNotRegex(self.readme_zh, r"#\s*\d+\s*个 skill 回归测试")

    def test_setup_pins_the_audited_bridge_and_node(self) -> None:
        pin = f"@cueai/omni-reader-mcp@{_EXPECTED_BRIDGE_VERSION}"
        self.assertEqual(_bridge_pin(self.setup), pin)
        self.assertIn("Node.js 20.12", self.setup)
        self.assertIn(f"npx -y {pin} setup", self.setup)
        self.assertIn(f"npx -y {pin} doctor --json", self.setup)
        self.assertIn(f"npx -y {pin} uninstall --yes --json", self.setup)
        self.assertRegex(
            self.setup,
            re.compile(r"never.*implicit `latest`", re.I),
        )

    def test_setup_documents_exact_trusted_uninstall_entries(self) -> None:
        expected = (
            "Uninstall removes a normal trusted 1.7.0 or 1.7.1 Bridge entry; it "
            "also removes the exact broken bare-npx Windows entry written by 1.5.1 "
            "and restores a matching trusted URL-only entry when available."
        )
        self.assertIn(expected, self.setup)
        self.assertNotIn(
            "Uninstall removes a normal trusted 1.5.5 or 1.6.0 Bridge entry",
            self.setup,
        )

    def test_setup_documents_safe_client_and_root_behavior(self) -> None:
        for client in ("Hermes", "Cursor", "Claude Desktop", "Other"):
            self.assertIn(client, self.setup)
        self.assertIn("minimum required directory", self.setup)
        self.assertIn("macOS/Linux", self.setup)
        self.assertIn("Windows", self.setup)
        self.assertRegex(self.setup, re.compile(r"reload|restart", re.I))
        self.assertRegex(
            self.setup,
            re.compile(r"do not invent.*configuration path", re.I | re.S),
        )
        self.assertRegex(
            self.setup,
            re.compile(r"do not paste.*API key", re.I | re.S),
        )

    def test_bridge_cli_claims_have_package_source_evidence(self) -> None:
        audit = _required_text(self, _BRIDGE_AUDIT_MD)
        compat = _required_text(self, _CONTENT_ONLY_REPORT_MD)
        self.assertIn("2026-08-08-bridge-cli-audit.md", self.setup)
        self.assertIn("2026-08-11-content-only-compat.md", self.setup)
        self.assertIn("package-source", audit)
        self.assertIn("@cueai/omni-reader-mcp@1.1.2", audit)
        self.assertRegex(
            audit,
            re.compile(r"`--allowed-root`.*replace.*`--add-root`.*append", re.I | re.S),
        )
        self.assertRegex(
            audit,
            re.compile(r"matching trusted backup.*restore", re.I | re.S),
        )
        self.assertRegex(
            audit,
            re.compile(r"no live.*configuration write.*Omni", re.I | re.S),
        )
        self.assertIn("@cueai/omni-reader-mcp@1.1.3", compat)
        self.assertIn("content[].text", compat)
        self.assertIn("291", compat)
        self.assertRegex(
            compat,
            re.compile(r"no production parse.*no Omni credits", re.I | re.S),
        )

    def test_versions_match_across_skill_setup_and_current_reports(self) -> None:
        skill_version = re.search(
            r'^\s*version:\s*"([^"]+)"$',
            _frontmatter(self, self.skill),
            re.M,
        ).group(1)
        skill_zh_version = re.search(
            r'^\s*version:\s*"([^"]+)"$',
            _frontmatter(self, self.skill_zh),
            re.M,
        ).group(1)
        bridge_version = re.search(
            r"@cueai/omni-reader-mcp@(\d+\.\d+\.\d+)",
            self.setup,
        ).group(1)
        self.assertEqual(skill_version, _EXPECTED_SKILL_VERSION)
        self.assertEqual(skill_zh_version, _EXPECTED_SKILL_VERSION)
        self.assertEqual(bridge_version, _EXPECTED_BRIDGE_VERSION)
        self.assertIn(f"Skill version: `{skill_version}`", self.compat)
        self.assertIn(f"Bridge version: `{bridge_version}`", self.compat)

        for name in (
            "2026-08-08-claude-code.md",
            "2026-08-08-codex-cli.md",
            "2026-08-08-gemini-cli.md",
            "2026-08-08-hermes.md",
            "2026-08-08-skill-pressure.md",
            "2026-08-08-workbuddy.md",
        ):
            report = _required_text(self, _REPORTS_DIR / name)
            self.assertIn("v0.1.0", report, f"historical skill version changed in {name}")

        for name in (
            "2026-08-08-bridge-cli-audit.md",
            "2026-08-08-claude-code.md",
            "2026-08-08-codex-cli.md",
            "2026-08-08-gemini-cli.md",
            "2026-08-08-hermes.md",
            "2026-08-08-skill-pressure.md",
        ):
            report = _required_text(self, _REPORTS_DIR / name)
            self.assertIn("1.1.2", report, f"historical Bridge version changed in {name}")

        current = _required_text(self, _REPORTS_DIR / _CURRENT_PUBLICATION_REPORT)
        self.assertIn(f"v{skill_version}", current)
        self.assertIn(bridge_version, current)

        for name in ("2026-08-18-bridge-1.3.1-published.md", "2026-08-18-bridge-1.3.2-published.md"):
            report = _required_text(self, _REPORTS_DIR / name)
            self.assertIn("v0.4.0", report)
            self.assertNotIn("v0.5.0", report)

    def test_current_publication_report_records_verified_1_7_1_release(self) -> None:
        current = _required_text(self, _REPORTS_DIR / _CURRENT_PUBLICATION_REPORT)
        report_index = _required_text(self, _REPORTS_DIR / "README.md")
        for fact in (
            "833237f883f15745ecbcc92b2469c308d96d4b12",
            "42d146fbc2858a25f94737fec41c2b72d8325df5",
            "4eb180caf17ace090bcd1344cfa29204809da95c",
            "8db1dd7b8fb5707bb7591c7178c7424064594e8deb32902074236fc72694536f",
            "sha512-WH0x1mRvfmpbYbcFAepoXJj544Ln3Pkjppy9IV8ju+mUpfQq/ayk9uGMUsYShs9EnRySJX6MbITbN2eE42F+bQ==",
            "registry tarball byte-identical",
            "64 files",
            "versions=[\"1.5.5\",\"1.6.0\",\"1.7.0\",\"1.7.1\"]",
            "BRIDGE_UPGRADE_REQUIRED",
            "already running the latest published release",
            "do not reinstall or retry",
            "doctor --json",
            "Bridge admission",
            "no production parse or billing call",
            "no reset, backfill, or replay",
            "native WorkBuddy skill loading remains unverified",
            "cue-skill publication remains owner-gated",
        ):
            self.assertIn(fact, current)
        self.assertIn(_CURRENT_PUBLICATION_REPORT, report_index)

    def test_compatibility_evidence_is_scoped(self) -> None:
        self.assertIn("Evidence date: 2026-08-11", self.compat)
        for client in (
            "Claude Code",
            "Codex CLI",
            "Gemini CLI",
            "Hermes",
            "WorkBuddy",
        ):
            self.assertIn(client, self.compat)
        self.assertIn("simulated", self.compat)
        self.assertIn("live", self.compat)
        self.assertIn("Skill loading evidence", self.compat)
        self.assertRegex(
            self.compat,
            re.compile(
                r"Claude Code.*native.*`Skill`.*simulated verified",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            self.compat,
            re.compile(
                r"Codex CLI.*JSONL.*read.*`\.agents/skills/.*SKILL\.md`"
                r".*simulated verified",
                re.I | re.S,
            ),
        )
        self.assertIn(
            "root-expansion only; install/doctor bootstrap unverified",
            self.compat,
        )
        self.assertRegex(
            self.compat,
            re.compile(
                r"Gemini CLI.*native.*`activate_skill`.*simulated verified",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            self.compat,
            re.compile(
                r"Hermes.*native.*`hermes chat`.*`--skills`.*simulated verified",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            self.compat,
            re.compile(r"WorkBuddy.*native.*unverified", re.I | re.S),
        )
        self.assertRegex(
            self.compat,
            re.compile(
                r"`hermes -z --skills`.*bypass.*preload",
                re.I | re.S,
            ),
        )
        self.assertIn(
            "01a1037d1e6d7b6eb96a786ef282c3aea4818194",
            self.compat,
        )
        self.assertRegex(
            self.compat,
            re.compile(
                r"v0\.20\.0.*implementation defect.*not.*general.*contract",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            self.compat,
            re.compile(
                r"WorkBuddy.*source[- ]artifact.*official.*unverified",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            self.compat,
            re.compile(r"not.*hostname rule", re.I | re.S),
        )
        self.assertRegex(
            self.compat,
            re.compile(r"active schema.*wait", re.I | re.S),
        )
        self.assertRegex(
            self.compat,
            re.compile(r"release.*blocked", re.I | re.S),
        )

    def test_native_loading_reports_are_client_specific(self) -> None:
        claude = _required_text(
            self,
            _REPORTS_DIR / "2026-08-08-claude-code.md",
        )
        codex = _required_text(
            self,
            _REPORTS_DIR / "2026-08-08-codex-cli.md",
        )
        gemini = _required_text(
            self,
            _REPORTS_DIR / "2026-08-08-gemini-cli.md",
        )
        hermes = _required_text(
            self,
            _REPORTS_DIR / "2026-08-08-hermes.md",
        )
        pressure = _required_text(
            self,
            _REPORTS_DIR / "2026-08-08-skill-pressure.md",
        )
        workbuddy = _required_text(
            self,
            _REPORTS_DIR / "2026-08-08-workbuddy.md",
        )
        self.assertIn("Claude Code v2.1.223", claude)
        self.assertRegex(
            claude,
            re.compile(
                r"native.*`.claude/skills/cue-omni-reader/`"
                r".*one.*`Skill`.*`cue-omni-reader`",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            claude,
            re.compile(
                r"explicit instruction.*activate.*relevant.*discovered skill",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            claude,
            re.compile(
                r"unprompted automatic triggering.*remain unverified",
                re.I | re.S,
            ),
        )
        self.assertIn("Codex CLI v0.146.0", codex)
        self.assertIn(
            "`.agents/skills/cue-omni-reader/SKILL.md`",
            codex,
        )
        self.assertRegex(
            codex,
            re.compile(
                r"read-only.*JSONL.*reading.*"
                r"`\.agents/skills/cue-omni-reader/SKILL\.md`",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            codex,
            re.compile(
                r"does not establish discovery, loading, selection, activation, "
                r"response behavior, or how Codex reached the file",
                re.I,
            ),
        )
        self.assertNotRegex(
            codex,
            re.compile(r"project copy|copied.*\.agents/skills|prompt explicitly requested", re.I),
        )
        self.assertNotRegex(
            codex,
            re.compile(r"final response.*(?:parse|polling|retrieval|cleanup)", re.I | re.S),
        )
        self.assertNotIn("before producing the simulated workflow", codex)
        self.assertIn("The four instruction-text behavior checks passed.", codex)
        self.assertIn(
            "No response-behavior pass is attributed to the file-read observation.",
            codex,
        )
        self.assertNotRegex(codex, re.compile(r"natively discovered", re.I))
        self.assertNotIn("`activate_skill`", codex)
        self.assertNotIn("| Native activation |", codex)
        self.assertRegex(
            pressure,
            re.compile(
                r"R11 client-native path evidence.*Claude Code.*Codex CLI"
                r".*Gemini CLI.*Hermes",
                re.I | re.S,
            ),
        )
        self.assertRegex(
            gemini,
            re.compile(
                r"native.*project.*`activate_skill`.*count.*1.*success.*1",
                re.I | re.S,
            ),
        )
        self.assertIn("| Native activation |", gemini)
        self.assertRegex(
            hermes,
            re.compile(
                r"native.*`hermes chat`.*`--skills cue-omni-reader`.*passed",
                re.I | re.S,
            ),
        )
        self.assertIn("| Native preload |", hermes)
        self.assertNotIn("| Native activation |", hermes)
        self.assertRegex(
            hermes,
            re.compile(r"user-selected explicit preload", re.I),
        )
        self.assertRegex(
            hermes,
            re.compile(
                r"discovery and automatic activation were not exercised",
                re.I,
            ),
        )
        self.assertRegex(
            workbuddy,
            re.compile(
                r"exact.*official v0\.1\.0.*not.*natively loaded",
                re.I | re.S,
            ),
        )
        self.assertIn("| R11 client-native path evidence |", pressure)
        self.assertNotIn("| R11 native activation |", pressure)
        self.assertRegex(
            hermes,
            re.compile(
                r"`hermes -z --skills`.*bypass.*preload",
                re.I | re.S,
            ),
        )
        self.assertIn(
            "01a1037d1e6d7b6eb96a786ef282c3aea4818194",
            hermes,
        )
        for evidence in (
            "`hermes --version`",
            "`git -C <install-directory-reported-above> rev-parse HEAD`",
            "`git -C <install-directory-reported-above> remote get-url origin`",
            "`git -C <install-directory-reported-above> blame -L 12541,12550 HEAD -- hermes_cli/main.py`",
            "`git -C <install-directory-reported-above> blame -L 18101,18146 HEAD -- cli.py`",
            "https://github.com/NousResearch/hermes-agent.git",
        ):
            self.assertIn(evidence, hermes)
        self.assertIn(
            "Persistent installation, unprompted automatic triggering, and live Omni behavior remain unverified on every client.",
            self.compat,
        )
        self.assertRegex(
            pressure,
            re.compile(
                r"Persistent installation.*unprompted automatic triggering"
                r".*remain unverified",
                re.I | re.S,
            ),
        )
        for report in (claude, codex, gemini, hermes):
            self.assertRegex(
                report,
                re.compile(r"no production parse.*no Omni credits", re.I | re.S),
            )

    def test_codex_evidence_never_exceeds_observed_skill_file_read(self) -> None:
        documents = _release_evidence_documents()
        expected = {
            *_REPORTS_DIR.glob("*.md"),
            _COMPAT_MD,
        }
        self.assertEqual(set(documents), expected)
        for path in documents:
            text = _required_text(self, path)
            self.assertEqual(
                _codex_evidence_issues(text),
                [],
                f"invalid Codex evidence in {path}",
            )

    def test_codex_evidence_guard_rejects_multiline_and_wrong_path_claims(self) -> None:
        valid_read = (
            "- Codex CLI: JSONL recorded Codex reading "
            "`.agents/skills/cue-omni-reader/SKILL.md` before answering."
        )
        positive_overclaims = (
            "Native loading and discovery were verified for this run.",
            "Native discovery was verified for this run.",
            "The activation tool was used for this run.",
            "Codex activation-tool use was observed for this run.",
            "Codex natively loaded the project skill.",
            "Client activation was observed for this run.",
            "Skill activation succeeded.",
            "The project skill was discovered.",
            "Codex loaded the skill automatically.",
            "The project skill was selected.",
            "The skill was activated before answering.",
            "Codex discovery/loading/selection/activation passed.",
            "Project skill loading succeeded.",
            "Native activation was verified.",
            "Codex CLI skill discovery and activation succeeded.",
            "Codex skill discovery was successful.",
            "Project skill activation was confirmed.",
            "Native project discovery worked.",
            "Codex project discovery worked.",
            "Codex project loading was successful.",
            "Codex project skill was successfully loaded.",
            "Project-skill activation worked.",
            "Codex skill-selection worked.",
            "Codex found the skill file.",
            "Codex located the project skill.",
            "Codex selected `.agents/skills/cue-omni-reader/SKILL.md`.",
            "Codex used an ephemeral project copy.",
            "The official package was copied into an ephemeral `.agents/skills/` project for Codex.",
            "Codex was prompted to use the relevant project skill.",
            "The prompt asked Codex to select the project skill.",
            "The skill was placed at `.agents/skills/cue-omni-reader/SKILL.md` for Codex.",
            "The project skill was staged under `.agents/skills/` for Codex.",
            "An ephemeral `.agents/skills/` workspace contained the skill for Codex.",
        )
        for claim in positive_overclaims:
            with self.subTest(claim=claim):
                multiline_overclaim = valid_read + "\n  " + claim
                self.assertTrue(
                    any(
                        "overclaim" in issue
                        for issue in _codex_evidence_issues(multiline_overclaim)
                    )
                )

        negative_boundaries = (
            "Client activation remains unverified.",
            "The read does not establish a client activation event.",
            "No activation tool use was observed.",
            "Codex has not been natively loaded.",
            "Skill activation did not occur.",
            "The project skill was not discovered.",
            "Codex did not load the skill automatically.",
            "The project skill was not selected.",
            "The skill was not activated before answering.",
            "Codex discovery/loading/selection/activation did not pass.",
            "Project skill loading did not succeed.",
            "Native activation was not verified.",
            "Codex was not natively discovered.",
            "Codex was never natively discovered.",
            "Codex skill loading was never verified.",
            "Codex discovery/loading/selection/activation never passed.",
            "Codex skill discovery was not successful.",
            "Project skill activation was not confirmed.",
            "Native project discovery did not work.",
            "Codex project discovery did not work.",
            "Codex project loading was not successful.",
            "Codex project skill was not successfully loaded.",
            "Project-skill activation did not work.",
            "Codex skill-selection did not work.",
            "Codex did not find the skill file.",
            "Codex did not locate the project skill.",
            "Codex did not select `.agents/skills/cue-omni-reader/SKILL.md`.",
            "Codex was not prompted to use the project skill.",
            "The prompt did not ask Codex to select the project skill.",
            "The skill was not placed at `.agents/skills/cue-omni-reader/SKILL.md` for Codex.",
            "No project-copy or package-placement setup evidence is claimed for Codex.",
        )
        for boundary in negative_boundaries:
            with self.subTest(boundary=boundary):
                self.assertEqual(
                    _codex_evidence_issues(valid_read + "\n  " + boundary),
                    [],
                )

        heading_scoped_overclaim = (
            valid_read
            + "\n\n## Codex CLI\n\nNative discovery was verified."
        )
        self.assertTrue(
            any(
                "overclaim" in issue
                for issue in _codex_evidence_issues(heading_scoped_overclaim)
            )
        )

        wrong_path = (
            "- Codex CLI: JSONL recorded Codex reading "
            "`.agents/skills/unrelated/SKILL.md` before answering."
        )
        self.assertIn(
            "missing exact observed Codex read",
            _codex_evidence_issues(wrong_path),
        )

        cross_section_path = (
            wrong_path
            + "\n\n## Gemini CLI\n\n"
            + "Observed `.agents/skills/cue-omni-reader/SKILL.md`."
        )
        self.assertIn(
            "missing exact observed Codex read",
            _codex_evidence_issues(cross_section_path),
        )

        conflicting_read_path = (
            valid_read
            + "\n\n## Codex CLI alternate evidence\n\n"
            + "JSONL recorded Codex reading "
            + "`.agents/skills/unrelated/SKILL.md`."
        )
        self.assertIn(
            "unexpected Codex skill read path",
            _codex_evidence_issues(conflicting_read_path),
        )

        heading_scoped_conflict = (
            valid_read
            + "\n\n## Codex CLI alternate evidence\n\n"
            + "JSONL recorded reading "
            + "`.agents/skills/unrelated/SKILL.md`."
        )
        self.assertIn(
            "unexpected Codex skill read path",
            _codex_evidence_issues(heading_scoped_conflict),
        )

        for observation in (
            "JSONL recorded Codex opening",
            "JSONL showed Codex inspected",
            "JSONL showed Codex accessed",
        ):
            with self.subTest(observation=observation):
                alternate_verb_conflict = (
                    valid_read
                    + "\n\n## Codex CLI alternate evidence\n\n"
                    + observation
                    + " `.agents/skills/unrelated/SKILL.md`."
                )
                self.assertIn(
                    "unexpected Codex skill read path",
                    _codex_evidence_issues(alternate_verb_conflict),
                )

        heading_scoped_valid = (
            "## Codex CLI observed evidence\n\n"
            "JSONL recorded reading "
            "`.agents/skills/cue-omni-reader/SKILL.md`."
        )
        self.assertEqual(_codex_evidence_issues(heading_scoped_valid), [])

        report_cross_section_path = (
            "# Codex CLI verification\n\n"
            "## Observed evidence\n\n"
            "JSONL recorded Codex reading "
            "`.agents/skills/unrelated/SKILL.md`.\n\n"
            "## Appendix\n\n"
            "Exact package path: "
            "`.agents/skills/cue-omni-reader/SKILL.md`."
        )
        self.assertIn(
            "missing exact observed Codex read",
            _codex_evidence_issues(report_cross_section_path),
        )

        generic_section_conflict = (
            valid_read
            + "\n\n## Other evidence\n\n"
            + "Observed `.agents/skills/unrelated/SKILL.md`."
        )
        self.assertIn(
            "unexpected Codex skill read path",
            _codex_evidence_issues(generic_section_conflict),
        )

        for alternate_path in (
            ".agents/skills/unrelated/SKILL.md",
            "[project skill](.agents/skills/unrelated/SKILL.md)",
            ".agents/config.toml",
            "[project policy](.agents/rules/review.md)",
        ):
            with self.subTest(alternate_path=alternate_path):
                plain_or_link_conflict = (
                    valid_read
                    + "\n\n## Other evidence\n\nObserved "
                    + alternate_path
                    + "."
                )
                self.assertIn(
                    "unexpected Codex skill read path",
                    _codex_evidence_issues(plain_or_link_conflict),
                )
                self.assertIn(
                    "unexpected Codex skill read path",
                    _codex_evidence_issues(alternate_path),
                )

        for exact_path_claim in (
            "Copied `.agents/skills/cue-omni-reader/SKILL.md` into the project.",
            "Found [the skill](.agents/skills/cue-omni-reader/SKILL.md).",
            "`.agents/skills/cue-omni-reader/SKILL.md` was selected.",
            "Prepared `.agents/skills/cue-omni-reader/SKILL.md` for Codex.",
            "Project setup used `.agents/skills/cue-omni-reader/SKILL.md`.",
        ):
            with self.subTest(exact_path_claim=exact_path_claim):
                issues = _codex_evidence_issues(
                    valid_read + "\n\n## Other evidence\n\n" + exact_path_claim
                )
                self.assertTrue(any("overclaim" in issue for issue in issues))

        standalone_exact_path = _codex_evidence_issues(
            valid_read
            + "\n\nThe exact `.agents/skills/cue-omni-reader/SKILL.md` "
            + "path was not selected or loaded by a verified client mechanism."
        )
        self.assertTrue(
            any("overclaim" in issue for issue in standalone_exact_path)
        )
        self.assertEqual(
            _codex_evidence_issues(
                valid_read
                + "\n\nThe file was not selected or loaded by a verified "
                + "client mechanism. No project setup is established by the "
                + "observed read."
            ),
            [],
        )

    def test_public_reports_record_actual_client_evidence_paths(self) -> None:
        pressure = _required_text(
            self,
            _REPORTS_DIR / "2026-08-08-skill-pressure.md",
        )
        for document in (self.compat, pressure):
            for client in (
                "Claude Code",
                "Codex CLI",
                "Gemini CLI",
                "Hermes",
                "WorkBuddy",
            ):
                self.assertIn(client, document)
        self.assertRegex(
            pressure,
            re.compile(
                r"Claude Code.*Codex CLI.*Gemini CLI.*Hermes.*WorkBuddy",
                re.I | re.S,
            ),
        )


class TestRepositoryIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = _required_text(self, _SKILL_MD)
        self.readme = _required_text(self, _REPO_ROOT / "README.md")
        self.readme_zh = _required_text(self, _REPO_ROOT / "README.zh-CN.md")
        self.workflow = _required_text(
            self, _REPO_ROOT / ".github" / "workflows" / "skill-regression.yml"
        )

    def test_version_matches_both_catalogs(self) -> None:
        version = re.search(
            r'^\s*version:\s*"([^"]+)"$', self.skill, re.M
        ).group(1)
        english = re.search(
            r"cue-omni-reader.*?\| v(\d+\.\d+\.\d+) \|",
            self.readme,
        )
        chinese = re.search(
            r"cue-omni-reader.*?\| v(\d+\.\d+\.\d+) \|",
            self.readme_zh,
        )
        self.assertIsNotNone(english)
        self.assertIsNotNone(chinese)
        self.assertEqual(version, _EXPECTED_SKILL_VERSION)
        self.assertEqual(version, english.group(1))
        self.assertEqual(version, chinese.group(1))

    def test_catalogs_state_the_thin_official_boundary(self) -> None:
        for catalog in (self.readme, self.readme_zh):
            self.assertIn("cue-omni-reader", catalog)
            self.assertRegex(catalog, r"official MCP|官方 MCP")
            self.assertRegex(catalog, r"no custom parser|不含自定义解析")

    def test_ci_matrix_runs_the_new_skill_on_both_python_versions(self) -> None:
        self.assertIn(
            "skill: [cue-buddy, cue-research, cue-omni-reader, cue-data-mcp]",
            self.workflow,
        )
        self.assertIn('python-version: ["3.12", "3.13"]', self.workflow)

    def test_dsh_bundle_pins_bridge_1_7_1_without_bumping_the_guard(self) -> None:
        bundle = _REPO_ROOT / "dsh" / "cue-omni-reader"
        package = json.loads(_required_text(self, bundle / "package.json"))
        guard = json.loads(
            _required_text(
                self,
                _REPO_ROOT / "dsh" / "cue-omni-reader-guard" / "package.json",
            )
        )
        self.assertEqual(package["version"], "0.1.5")
        self.assertEqual(guard["version"], "0.1.4")

        documents = (
            bundle / "cordis.patch.yml",
            bundle / "README.md",
            bundle / "README.zh-CN.md",
            _REPO_ROOT / "dsh" / "usage.md",
            _REPO_ROOT / "dsh" / "usage.zh-CN.md",
        )
        pins = []
        for document in documents:
            pins.extend(
                re.findall(
                    r"@cueai/omni-reader-mcp@\d+\.\d+\.\d+",
                    _required_text(self, document),
                )
            )
        self.assertEqual(len(pins), 7)
        self.assertEqual(set(pins), {"@cueai/omni-reader-mcp@1.7.1"})


class TestSecurityAndLayout(unittest.TestCase):
    def test_sensitive_content_detector_covers_common_formats(self) -> None:
        sensitive_samples = (
            "AKIA" + "A" * 16,
            "ASIA" + "A" * 16,
            "ghp_" + "a" * 36,
            "gho_" + "a" * 36,
            "ghs_" + "a" * 36,
            "github_" + "pat_" + "a" * 40,
            "sk-" + "proj-" + "a" * 40,
            "SERVICE_TOKEN=" + "a" * 32,
            '"CUE_API_KEY": "' + "a" * 32 + '"',
            "'SERVICE_TOKEN'='" + "b" * 32 + "'",
            "Bearer " + "a" * 32,
            "/Users/" + "alice/private.pdf",
            "/home/" + "alice/private.pdf",
            "/" + "root/private.pdf",
            "C:" + "\\Users\\alice\\private.pdf",
            "\\\\" + "server\\Users\\alice\\private.pdf",
            "192." + "168.1.23",
            "operation_id=" + "a" * 24,
            "result_id: " + "a" * 24,
            '"operation_id": "' + "a" * 24 + '"',
            "result_id='" + "b" * 24 + "'",
            "account " + "balance: " + "123.45",
            "credit " + "balance: USD " + "12.50",
            "credit " + "balance: -" + "12.50 USD",
            '"credit_' + 'balance": "-12.50 USD"',
            "account " + 'balance: USD "12.50"',
            "credit " + "balance: EUR '-4.25'",
            "account " + 'balance: $ "12.50"',
            "credit " + 'balance: "12.50" €',
            "credit " + 'balance: -"12.50 USD"',
            "account " + 'balance: +"$12.50"',
            "account " + 'balance: "USD" 12.50',
            "account " + 'balance: "$" 12.50',
            "credit " + 'balance: USD -"12.50"',
            "account " + "balance: −$" + "12.50",
            "account " + "balance: ($" + "12.50)",
            "account " + "balance: -(USD 12.50)",
            "account " + "balance: +(12.50 USD)",
            "account " + 'balance: "($12.50)"',
            "account " + 'balance: "−USD 12.50"',
            "account " + "balance was $12.50",
            "credit " + "balance of ($12.50)",
            "account " + 'balance was "-($12.50)"',
            "credit " + "balance of +(12.50 USD)",
            "remaining " + 'credits were "($12.50)"',
            "Credit " + "balance: **$12.50**",
            "| Credit " + "balance | **($12.50)** |",
            "account " + "balance: `$12.50`",
            "**Credit " + "balance**: **($12.50)**",
            "| **Account " + "balance** | `USD 12.50` |",
            "| account " + "balance | -$12.50 |",
            "account " + "balance: -" + "25",
            "remaining " + "credits = " + "42",
            '"credits_' + 'remaining": ' + "99",
            "mcp" + "__omni__parse",
        )
        for sample in sensitive_samples:
            with self.subTest(sample=sample[:12]):
                with self.assertRaises(AssertionError):
                    _assert_no_sensitive_content(self, sample)

        _assert_no_sensitive_content(
            self,
            "CUE_API_KEY ${CUE_API_KEY} Bearer ${CUE_API_KEY} result_id "
            "account balance: [redacted] remaining credits: ${CREDITS}",
        )

    def test_shipped_text_reader_rejects_binary(self) -> None:
        with self.assertRaises(AssertionError):
            _decode_shipped_text(self, "payload.bin", b"binary\0payload")

    def test_exact_layout_gate_rejects_unexpected_file(self) -> None:
        shipped = {"SKILL.md": "", "runtime-driver.py": ""}
        with self.assertRaises(AssertionError):
            _assert_exact_layout(self, shipped, {"SKILL.md"})

    def test_shipped_layout_is_exact_and_text_only(self) -> None:
        expected = {
            "SKILL.md",
            "SKILL.zh-CN.md",
            "README.md",
            "README.zh-CN.md",
            "docs/verification-reports/2026-08-08-baseline-pressure.md",
            "docs/verification-reports/2026-08-08-bridge-cli-audit.md",
            "docs/verification-reports/2026-08-08-claude-code.md",
            "docs/verification-reports/2026-08-08-codex-cli.md",
            "docs/verification-reports/2026-08-08-gemini-cli.md",
            "docs/verification-reports/2026-08-08-hermes.md",
            "docs/verification-reports/2026-08-08-skill-pressure.md",
            "docs/verification-reports/2026-08-08-workbuddy.md",
            "docs/verification-reports/2026-08-11-content-only-compat.md",
            "docs/verification-reports/2026-08-13-bridge-1.1.3-published.md",
            "docs/verification-reports/2026-08-14-bridge-1.2.0-published.md",
            "docs/verification-reports/2026-08-14-bridge-1.2.1-published.md",
            "docs/verification-reports/2026-08-15-bridge-1.2.2-published.md",
            "docs/verification-reports/2026-08-17-bridge-1.3.0-published.md",
            "docs/verification-reports/2026-08-18-bridge-1.3.1-published.md",
            "docs/verification-reports/2026-08-18-bridge-1.3.2-published.md",
            "docs/verification-reports/2026-08-18-bridge-1.3.3-published.md",
            "docs/verification-reports/2026-08-19-bridge-1.4.1-published.md",
            "docs/verification-reports/2026-08-26-bridge-1.5.5-published.md",
            "docs/verification-reports/2026-08-30-bridge-1.6.0-published.md",
            "docs/verification-reports/2026-09-04-bridge-1.7.1-published.md",
            "docs/verification-reports/README.md",
            "references/compatibility.md",
            "references/setup.md",
            "scripts/sync_bridge_pin.py",
            "scripts/test_skill_regression.py",
        }
        shipped = _shipped_text_files(self, _SKILL_DIR)
        _assert_exact_layout(self, shipped, expected)

    def test_no_runtime_driver_or_nested_release_archive(self) -> None:
        scripts = sorted(
            p.name for p in (_SKILL_DIR / "scripts").iterdir() if p.is_file()
        )
        self.assertEqual(scripts, ["sync_bridge_pin.py", "test_skill_regression.py"])
        archives = [
            p for p in _SKILL_DIR.rglob("*")
            if p.is_file() and p.suffix.lower() in {".zip", ".tgz", ".tar", ".gz"}
        ]
        self.assertEqual(archives, [])

    def test_shipped_files_contain_no_secret_or_personal_path(self) -> None:
        release_files = _release_sensitive_text_files(self)
        shipped = _shipped_text_files(self, _SKILL_DIR)
        self.assertTrue(
            {_SKILL_DIR / relative for relative in shipped}.issubset(release_files)
        )
        _assert_no_sensitive_content(self, "\n".join(shipped.values()))
        public_text = "\n".join(release_files.values())
        _assert_no_account_or_credit_balance(self, public_text)
        for internal_narrative in (
            "embedded " + "credential",
            "leaked a " + "credential",
            "personal skill " + "artifact",
            "user's earlier WorkBuddy " + "session",
            "encrypted file " + "fallback",
            "custom-driver bootstrap rejected by " + "audit",
        ):
            self.assertNotIn(internal_narrative, public_text)
        self.assertFalse(
            (_REPO_ROOT / "docs" / "superpowers").exists(),
            "internal implementation plans must not ship to the public repository",
        )

    def test_baseline_report_exists(self) -> None:
        report = _REPORTS_DIR / "2026-08-08-baseline-pressure.md"
        text = _required_text(self, report)
        self.assertIn("Skill loaded:** no", text)
        self.assertIn("simulated", text)
        self.assertRegex(text, r"R[1-9]|Scenario")


if __name__ == "__main__":
    sys.exit(0 if unittest.main(verbosity=2, exit=False).result.wasSuccessful() else 1)
