#!/usr/bin/env python3
"""cue-omni-reader skill regression — stdlib only."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_DIR = _HERE.parent
_REPO_ROOT = _SKILL_DIR.parent
_SKILL_MD = _SKILL_DIR / "SKILL.md"
_SETUP_MD = _SKILL_DIR / "references" / "setup.md"
_COMPAT_MD = _SKILL_DIR / "references" / "compatibility.md"
_REPORTS_DIR = _SKILL_DIR / "docs" / "verification-reports"
_BRIDGE_AUDIT_MD = _REPORTS_DIR / "2026-08-08-bridge-cli-audit.md"
_CONTENT_ONLY_REPORT_MD = _REPORTS_DIR / "2026-08-11-content-only-compat.md"
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
            re.compile(r'^\s*version:\s*"0\.1\.1"$', re.M),
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
            "`discard_result`",
        ):
            self.assertIn(tool, self.md)
        self.assertNotIn("mcp" + "__", self.md)
        self.assertLess(len(self.md.split()), 800, "SKILL.md is no longer thin")

    def test_source_handling_preserves_the_security_boundary(self) -> None:
        self.assertIn("Only HTTP(S) strings are URLs", self.md)
        self.assertIn("Pass the user's source string directly to `parse`", self.md)
        self.assertRegex(self.md, re.compile(r"Do not pre-read.*base64", re.S))
        self.assertIn("`file://`", self.md)
        self.assertIn("public temporary upload", self.md)

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
        self.setup = _required_text(self, _SETUP_MD)
        self.compat = _required_text(self, _COMPAT_MD)

    def test_setup_pins_the_audited_bridge_and_node(self) -> None:
        self.assertIn("@cueai/omni-reader-mcp@1.2.2", self.setup)
        self.assertIn("Node.js 20.12", self.setup)
        self.assertIn("npx -y @cueai/omni-reader-mcp@1.2.2 setup", self.setup)
        self.assertIn("npx -y @cueai/omni-reader-mcp@1.2.2 doctor --json", self.setup)
        self.assertIn(
            "npx -y @cueai/omni-reader-mcp@1.2.2 uninstall --yes --json",
            self.setup,
        )
        self.assertRegex(
            self.setup,
            re.compile(r"never.*implicit `latest`", re.I),
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
        skill = _required_text(self, _SKILL_MD)
        skill_version = re.search(
            r'^\s*version:\s*"([^"]+)"$',
            _frontmatter(self, skill),
            re.M,
        ).group(1)
        bridge_version = re.search(
            r"@cueai/omni-reader-mcp@(\d+\.\d+\.\d+)",
            self.setup,
        ).group(1)
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

        current = _required_text(self, _REPORTS_DIR / "2026-08-15-bridge-1.2.2-published.md")
        self.assertIn(f"v{skill_version}", current)
        self.assertIn(bridge_version, current)

    def test_compatibility_is_versioned_and_evidence_scoped(self) -> None:
        self.assertIn("Skill version: `0.1.1`", self.compat)
        self.assertIn("Bridge version: `1.2.2`", self.compat)
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
        self.assertEqual(version, english.group(1))
        self.assertEqual(version, chinese.group(1))

    def test_catalogs_state_the_thin_official_boundary(self) -> None:
        for catalog in (self.readme, self.readme_zh):
            self.assertIn("cue-omni-reader", catalog)
            self.assertRegex(catalog, r"official MCP|官方 MCP")
            self.assertRegex(catalog, r"no custom parser|不含自定义解析")

    def test_ci_matrix_runs_the_new_skill_on_both_python_versions(self) -> None:
        self.assertIn(
            "skill: [cue-buddy, cue-research, cue-omni-reader]",
            self.workflow,
        )
        self.assertIn('python-version: ["3.12", "3.13"]', self.workflow)


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
            "docs/verification-reports/README.md",
            "references/compatibility.md",
            "references/setup.md",
            "scripts/test_skill_regression.py",
        }
        shipped = _shipped_text_files(self, _SKILL_DIR)
        _assert_exact_layout(self, shipped, expected)

    def test_no_runtime_driver_or_nested_release_archive(self) -> None:
        scripts = sorted(
            p.name for p in (_SKILL_DIR / "scripts").iterdir() if p.is_file()
        )
        self.assertEqual(scripts, ["test_skill_regression.py"])
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
