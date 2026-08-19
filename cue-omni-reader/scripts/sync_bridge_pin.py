#!/usr/bin/env python3
"""Sync the audited Bridge version pin across cue-omni-reader references.

Usage: python3 scripts/sync_bridge_pin.py <version>

The skill keeps an exact audited pin (never an implicit `latest`), but the pin
is maintained by one command instead of hand-editing several files per Bridge
release. After the new version is published to npm, run this from the repo
root; it rewrites every pin in references/setup.md and the version line in
references/compatibility.md, then verifies the npm registry actually carries
the new version so a stale or un-published bump fails fast.

The regression test (test_skill_regression.py) reads the pin dynamically from
setup.md, so it follows automatically -- the only per-release human steps are
the prose evidence entry in compatibility.md, the SKILL.md tool-surface prose
(if the tool list changed), the skill's own version bump, and the publication
report.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_DIR = _HERE.parent
_SETUP_MD = _SKILL_DIR / "references" / "setup.md"
_COMPAT_MD = _SKILL_DIR / "references" / "compatibility.md"

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_PIN = re.compile(r"@cueai/omni-reader-mcp@\d+\.\d+\.\d+")
_COMPAT_VERSION_LINE = re.compile(r"^- Bridge version: `\d+\.\d+\.\d+`$", re.M)


def registry_latest() -> str | None:
    """Query npm's dist-tags.latest for the Bridge; None on any failure."""
    try:
        result = subprocess.run(
            ["npm", "view", "@cueai/omni-reader-mcp", "dist-tags.latest", "--json"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        value = json.loads(result.stdout)
        if isinstance(value, str) and _SEMVER.match(value):
            return value
        return None
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return None


def sync(version: str) -> None:
    if not _SEMVER.match(version):
        sys.exit(f"error: {version!r} is not a numeric semver")

    published = registry_latest()
    if published is None:
        sys.exit(
            "error: could not confirm the new version on the npm registry "
            "(network, or registry.latest mismatch). Publish @cueai/omni-reader-mcp "
            f"as {version} first, then re-run."
        )
    if published != version:
        sys.exit(
            f"error: npm dist-tags.latest is {published}, not {version}. The pin "
            "must match the published latest -- publish first, then re-run."
        )

    setup = _SETUP_MD.read_text(encoding="utf-8")
    pins = _PIN.findall(setup)
    if not pins:
        sys.exit(f"error: no Bridge pin found in {_SETUP_MD.name}")
    old = _PIN.search(pins[0]).group(0)  # e.g. "@cueai/omni-reader-mcp@1.3.3"
    old_version = old.rsplit("@", 1)[1]
    if old_version == version:
        print(f"setup.md already pinned at {version}; nothing to rewrite")
    else:
        rewritten = _PIN.sub(f"@cueai/omni-reader-mcp@{version}", setup)
        _SETUP_MD.write_text(rewritten, encoding="utf-8")
        print(f"setup.md: {len(pins)} pin(s) {old_version} -> {version}")

    compat = _COMPAT_MD.read_text(encoding="utf-8")
    if _COMPAT_VERSION_LINE.search(compat):
        rewritten = _COMPAT_VERSION_LINE.sub(f"- Bridge version: `{version}`", compat)
        _COMPAT_MD.write_text(rewritten, encoding="utf-8")
        print(f"compatibility.md: Bridge version line {old_version} -> {version}")
    else:
        print("compatibility.md: no version line matched (expected '- Bridge version: `x.y.z`'); left unchanged")

    print(
        "\nRemaining per-release human steps (not automatable):\n"
        "1. compatibility.md prose: append the new release's evidence entry\n"
        "2. SKILL.md tool-surface prose: update only if the public tool list changed\n"
        "3. SKILL.md frontmatter version + README catalog version: bump the skill's own version\n"
        "4. docs/verification-reports/: write the publication report for the new version\n"
        "5. run: python3 scripts/test_skill_regression.py\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="new Bridge version to pin, e.g. 1.4.0")
    args = parser.parse_args()
    sync(args.version)


if __name__ == "__main__":
    main()
