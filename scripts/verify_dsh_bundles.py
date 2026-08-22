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
import re
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
    """Doc-consistency: every bundle has a README; the dsh/ index covers them."""
    errors: list[str] = []
    index = DSH_DIR / "README.md"
    index_text = index.read_text(encoding="utf-8") if index.exists() else ""

    for bundle in bundles:
        if not (bundle / "README.md").exists():
            errors.append(f"{bundle.name}: bundle has no README.md (a distributable needs docs)")

    for bundle in bundles:
        # the index table links each bundle by its folder name, e.g. [name](name)
        if bundle.name not in index_text:
            errors.append(f"{bundle.name}: not listed in {index.name} (add it to the bundles table)")

    return errors


def main() -> int:
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
    if all_errors:
        print("DSH bundle validation FAILED:", file=sys.stderr)
        for e in all_errors:
            print("  - " + e, file=sys.stderr)
        return 1
    print(f"All {len(bundles)} DSH bundle(s) OK (structure + docs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
