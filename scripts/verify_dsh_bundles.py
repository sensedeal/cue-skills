#!/usr/bin/env python3
"""Validate every DSH bundle under ``dsh/<bundle>/``.

A bundle is a package whose ``package.json`` declares ``dsh.bundle.patch``.
For each such directory this check enforces:

  1. ``package.json`` is valid JSON and declares ``dsh.bundle.patch`` (a path).
  2. the referenced patch file exists.
  3. the patch parses (``!!js`` tags stripped) and is a list of loader patch
     entries; every ``insert`` row has ``id``, ``name``, and ``config``.
  4. every row's ``name`` is declared in the package ``dependencies`` /
     ``peerDependencies`` (DSH rule: raw/Web cordis.yml bare plugins must
     appear in the resolver manifest's dependencies).

Stdlib-only except for PyYAML, which is optional (a regex structural check is
the fallback). Exit 0 on success, 1 on any failure.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DSH_DIR = REPO / "dsh"

try:
    import yaml  # type: ignore
    HAVE_YAML = True
except Exception:  # pragma: no cover - fallback path
    HAVE_YAML = False


def strip_js_tag(text: str) -> str:
    """Turn ``!!js <expr>`` into a plain scalar so stdlib YAML can parse."""
    return re.sub(r"!!js\s*", "", text)


def parse_patch(text: str):
    if HAVE_YAML:
        return yaml.safe_load(strip_js_tag(text))
    # Dependency-free fallback: confirm the top level looks like a list whose
    # first block is an `insert` list of rows containing id/name/config.
    if not re.search(r"^\s*-\s*insert\s*:", text, re.M):
        return None
    return "unparsed"


def iter_insert_rows(patch):
    """Yield each row from every ``insert`` list in the patch entries."""
    if patch == "unparsed":
        return
    if not isinstance(patch, list):
        return
    for entry in patch:
        if not isinstance(entry, dict):
            continue
        for row in entry.get("insert", []) or []:
            if isinstance(row, dict):
                yield row


def validate_bundle(bundle: Path) -> list[str]:
    errors: list[str] = []
    pkg_path = bundle / "package.json"
    if not pkg_path.exists():
        return errors  # not a bundle; callers skip

    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    except Exception as e:  # pragma: no cover
        return [f"{bundle.name}/package.json: invalid JSON ({e})"]

    patch_rel = (pkg.get("dsh") or {}).get("bundle", {}).get("patch")
    if not isinstance(patch_rel, str):
        return [f"{bundle.name}/package.json: missing `dsh.bundle.patch` string"]
    patch_path = bundle / patch_rel
    if not patch_path.exists():
        errors.append(f"{bundle.name}: patch path missing: {patch_path.name}")
        return errors

    patch = parse_patch(patch_path.read_text(encoding="utf-8"))
    if patch is None:
        errors.append(f"{bundle.name}/{patch_rel}: could not parse as a patch list")
        return errors

    deps = set((pkg.get("dependencies") or {}).keys()) | set(
        (pkg.get("peerDependencies") or {}).keys()
    )
    rows = list(iter_insert_rows(patch))
    if not rows:
        errors.append(f"{bundle.name}/{patch_rel}: no `insert` rows found")
    for row in rows:
        for k in ("id", "name", "config"):
            if k not in row:
                errors.append(f"{bundle.name}/{patch_rel}: insert row missing `{k}`")
        name = row.get("name")
        pkg_name = pkg.get("name")
        # A bundle may mount a plugin it ships itself (name == pkg name) or a
        # plugin it depends on; anything else must be a declared dependency.
        if name and name not in deps and name != pkg_name:
            errors.append(
                f"{bundle.name}: row plugin `{name}` is not the bundle's own "
                f"package nor declared in dependencies/peerDependencies "
                f"(DSH resolves bare plugins only from the resolver manifest)"
            )

    if errors:
        return errors
    print(
        f"OK {bundle.name}: {len(rows)} insert row(s); patch={patch_rel}; "
        f"deps={sorted(deps)}"
    )
    return []


def validate_docs(bundles: list[Path]) -> list[str]:
    """Doc-consistency: bilingual READMEs and the dsh/ index covers them."""
    errors: list[str] = []
    index = DSH_DIR / "README.md"
    index_text = index.read_text(encoding="utf-8") if index.exists() else ""

    if not (DSH_DIR / "README.zh-CN.md").exists():
        errors.append("dsh/README.zh-CN.md missing (bilingual index required)")
    if (DSH_DIR / "usage.md").exists() and not (DSH_DIR / "usage.zh-CN.md").exists():
        errors.append("dsh/usage.zh-CN.md missing (bilingual usage doc required)")

    for bundle in bundles:
        for fname in ("README.md", "README.zh-CN.md"):
            if not (bundle / fname).exists():
                errors.append(f"{bundle.name}: bundle has no {fname} (bilingual docs required)")

    for bundle in bundles:
        # the index table links each bundle by its folder name, e.g. [name](name)
        if bundle.name not in index_text:
            errors.append(f"{bundle.name}: not listed in {index.name} (add it to the bundles table)")

    return errors


SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


def semver_ok(value) -> bool:
    return isinstance(value, str) and SEMVER_RE.fullmatch(value) is not None


def plugin_entry(pkg: dict):
    """Return a relative plugin entry path if the package ships a plugin module."""
    exports = pkg.get("exports")
    if isinstance(exports, dict) and "." in exports:
        val = exports["."]
        if isinstance(val, dict) and "import" in val:
            return val["import"]
        if isinstance(val, str):
            return val
    main = pkg.get("main")
    return main if isinstance(main, str) else None


def check_publish(bundle: Path) -> list[str]:
    """Pre-publish hygiene: scope, version, npm metadata, and the plugin entry."""
    errors: list[str] = []
    pkg_path = bundle / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))

    name = pkg.get("name")
    if not isinstance(name, str) or "/" not in name or not name.startswith("@"):
        errors.append(f"{bundle.name}/package.json: name must be scoped (e.g. @cueai/dsh-…); got {name!r}")
    else:
        scope = name.split("/")[0]
        allowed = tuple(
            s.strip() for s in os.environ.get("DSH_PUBLISH_SCOPE", "@cueai").split(",") if s.strip()
        )
        if allowed and scope not in allowed:
            errors.append(
                f"{bundle.name}: scope {scope!r} not in allowed publish scopes {allowed} "
                f"(override via DSH_PUBLISH_SCOPE)"
            )

    if not semver_ok(pkg.get("version")):
        errors.append(f"{bundle.name}: version must be valid semver; got {pkg.get('version')!r}")
    for field in ("description", "license"):
        if not pkg.get(field):
            errors.append(f"{bundle.name}: missing npm field `{field}`")

    entry = plugin_entry(pkg)
    if entry:
        ep = bundle / entry
        if not ep.exists():
            errors.append(f"{bundle.name}: plugin entry missing: {entry}")
        else:
            r = subprocess.run(["node", "--check", str(ep)], capture_output=True, text=True)
            if r.returncode != 0:
                errors.append(f"{bundle.name}: plugin entry syntax error ({entry}): {r.stderr.strip()[:160]}")

    return errors


def heading_skeleton(text: str) -> list[tuple[int, str]]:
    """Ordered list of (level, heading-text) for every ATX heading at level 2+.

    The heading TEXT is language-specific, so parity matches on LEVEL + ORDER
    only, but the text is kept for human-readable diagnostics.
    """
    skeleton: list[tuple[int, str]] = []
    for line in text.splitlines():
        m = re.match(r"^(#{2,})(\s+)(.*)$", line)
        if m:
            skeleton.append((len(m.group(1)), m.group(3).strip()))
    return skeleton


def count_fences(text: str) -> int:
    """Count fenced code blocks (leading ``` line per block)."""
    return sum(1 for line in text.splitlines() if line.strip().startswith("```"))


def doc_pairs() -> list[tuple[Path, Path]]:
    """(en, zh) documentation pairs under dsh/ to keep in structural parity."""
    pairs = [
        (DSH_DIR / "README.md", DSH_DIR / "README.zh-CN.md"),
        (DSH_DIR / "usage.md", DSH_DIR / "usage.zh-CN.md"),
    ]
    for bundle in sorted(p for p in DSH_DIR.iterdir() if (p / "package.json").exists()):
        pairs.append((bundle / "README.md", bundle / "README.zh-CN.md"))
    return pairs


def check_translation_parity() -> list[str]:
    """Enforce structural parity between each English/Chinese doc pair.

    Translations differ in wording, so text is never compared. Instead match the
    section skeleton by (level, order) — a heading added/removed/reordered/level
    -changed in only one language is caught — plus the fenced-code-block count.
    """
    errors: list[str] = []
    for en, zh in doc_pairs():
        if not en.exists() or not zh.exists():
            continue  # existence is enforced by validate_docs
        etxt = en.read_text(encoding="utf-8")
        ztxt = zh.read_text(encoding="utf-8")
        rel = en.relative_to(DSH_DIR)
        es, zs = heading_skeleton(etxt), heading_skeleton(ztxt)
        if len(es) != len(zs):
            errors.append(
                f"{rel}: section count differs — EN {len(es)} vs zh {len(zs)} "
                f"(add/translate the section in both languages)"
            )
        else:
            for i, ((elv, et), (zlv, zt)) in enumerate(zip(es, zs)):
                if elv != zlv:
                    errors.append(
                        f"{rel}: section #{i + 1} level differs — "
                        f"EN {'#'*elv} ({et}) vs zh {'#'*zlv} ({zt})"
                    )
        ef, zf = count_fences(etxt), count_fences(ztxt)
        if ef != zf:
            errors.append(
                f"{rel}: fenced-code-block count differs — EN {ef} vs zh {zf}"
            )
    return errors


def main() -> int:
    publish = "--publish-check" in sys.argv
    parity = "--check-translation-parity" in sys.argv
    if not DSH_DIR.exists():
        print(f"(no {DSH_DIR.relative_to(REPO)}/ directory — nothing to verify)")
        return 0
    bundles = sorted(p for p in DSH_DIR.iterdir() if (p / "package.json").exists())
    if not bundles:
        print(f"(no bundles under {DSH_DIR.relative_to(REPO)}/)")
        return 0
    all_errors: list[str] = []
    for bundle in bundles:
        all_errors.extend(validate_bundle(bundle))
    all_errors.extend(validate_docs(bundles))
    if publish:
        for bundle in bundles:
            all_errors.extend(check_publish(bundle))
    if parity:
        all_errors.extend(check_translation_parity())
    if all_errors:
        print("DSH bundle validation FAILED:", file=sys.stderr)
        for e in all_errors:
            print("  - " + e, file=sys.stderr)
        return 1
    checks = ["structure", "docs"]
    if publish:
        checks.append("publish-check")
    if parity:
        checks.append("translation-parity")
    print(f"All {len(bundles)} DSH bundle(s) OK ({' + '.join(checks)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
