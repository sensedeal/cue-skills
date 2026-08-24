#!/usr/bin/env python3
"""cue-data-mcp skill regression — stdlib only."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_DIR = _HERE.parent
_SKILL_MD = _SKILL_DIR / "SKILL.md"
_SKILL_ZH_MD = _SKILL_DIR / "SKILL.zh-CN.md"
_SETUP_MD = _SKILL_DIR / "references" / "setup.md"


def _required_text(case: unittest.TestCase, path: Path) -> str:
    case.assertTrue(path.is_file(), f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def _frontmatter(case: unittest.TestCase, text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    case.assertIsNotNone(m, "SKILL.md missing frontmatter")
    return m.group(1)


class CueDataMcpSkillRegression(unittest.TestCase):
    """Guard the thin instruction layer of the cue-data-mcp skill."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.md = _required_text(cls, _SKILL_MD)
        cls.zh = _required_text(cls, _SKILL_ZH_MD)
        cls.setup = _required_text(cls, _SETUP_MD)
        cls.fm = _frontmatter(cls, cls.md)
        cls.fm_zh = _frontmatter(cls, cls.zh)

    def test_frontmatter_identity_and_version(self) -> None:
        self.assertRegex(self.fm, re.compile(r'^\s*name:\s*cue-data-mcp$', re.M))
        self.assertRegex(
            self.fm,
            re.compile(r'^\s*version:\s*"0\.3\.6"$', re.M),
        )
        self.assertIn('envOptional: ["CUE_API_KEY"]', self.fm)
        self.assertRegex(
            self.fm_zh,
            re.compile(r'^\s*version:\s*"0\.3\.6"$', re.M),
        )

    def test_description_uses_trigger_form(self) -> None:
        description = re.search(r'^\s*description:\s*"([^"]+)"$', self.fm, re.M)
        self.assertIsNotNone(description)
        self.assertTrue(description.group(1).startswith("Use when "))

    def test_skill_remains_thin(self) -> None:
        # 577 words at authoring; keep the same tight guard as the omni-reader skill
        self.assertLess(len(self.md.split()), 900, "SKILL.md is no longer thin")

    def test_discovery_via_anonymous_catalog(self) -> None:
        self.assertIn("GET https://cuecue.cn/api/mcp-catalog", self.md)
        self.assertIn("anonymous, no key required", self.md)
        self.assertIn("`external_status`", self.md)
        self.assertIn("`routing`", self.md)

    def test_connection_contract_is_live_not_hardcoded(self) -> None:
        # routing must come from the catalog DTO; no concrete group endpoints may be baked
        self.assertIn("Use the live domain's `routing` verbatim", self.md)
        self.assertIn("`tools/list`", self.md)
        self.assertIn("Never hardcode tool names", self.md)
        self.assertIn("406", self.md)
        # only the <group> placeholder form may appear, never a real group path
        self.assertNotRegex(self.md, re.compile(r"mcp\.cuecue\.cn/api/[a-z_]+/mcp"))

    def test_scope_boundary_excludes_omni_reader(self) -> None:
        self.assertIn("15 data domains", self.md)
        self.assertIn("`omni-reader`", self.md)
        self.assertIn("cue-omni-reader", self.md)

    def test_key_handling_preserves_the_security_boundary(self) -> None:
        self.assertRegex(
            self.md,
            re.compile(r"Never paste the API key into chat.*generated JSON", re.S),
        )
        self.assertIn("secret facility", self.md)
        self.assertIn("rotate it before continuing", self.md)

    def test_catalog_is_the_only_source_of_truth(self) -> None:
        self.assertRegex(
            self.md,
            re.compile(r"The catalog is the only source of truth", re.I),
        )
        self.assertIn("Never reuse a stale connection string", self.md)

    def test_free_credits_section_matches_current_standard(self) -> None:
        self.assertIn("0.625 credits per data call", self.md)
        self.assertIn("16 data queries per day", self.md)
        self.assertIn("https://cuecue.cn/hub/api-key", self.md)
        self.assertIn("report the live value", self.md)

    def test_zh_translation_parity(self) -> None:
        self.assertIn("完整中文翻译", self.zh)
        self.assertIn("https://cuecue.cn/api/mcp-catalog", self.zh)
        self.assertIn("0.625 积分", self.zh)
        self.assertIn("cue-omni-reader", self.zh)
        self.assertIn("hub/api-key", self.zh)

    def test_setup_reference_has_client_and_raw_paths(self) -> None:
        self.assertIn("Catalog endpoint", self.setup)
        self.assertIn("`CUE_API_KEY`", self.setup)
        # MCP client config shape
        self.assertIn("mcpServers", self.setup)
        self.assertIn("streamable-http", self.setup)
        # raw JSON-RPC path for agents without an MCP client
        self.assertIn("tools/list", self.setup)
        self.assertIn("tools/call", self.setup)
        self.assertIn("$CUE_API_KEY", self.setup)
        # troubleshooting table covers the 406/401 pitfalls
        self.assertIn("406", self.setup)
        self.assertIn("401", self.setup)
        # key rule repeats in setup
        self.assertIn("rotate it before continuing", self.setup)


if __name__ == "__main__":
    unittest.main()
