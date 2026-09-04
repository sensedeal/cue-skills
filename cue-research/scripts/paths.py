#!/usr/bin/env python3
"""Single writable root for all cue-skills runtime files.

Why this exists: cue-skills used to scatter runtime files across four write
roots (``~/cue-reports/``, ``~/.cue/``, agent cwd, ``/tmp/``), each hardcoded
in a different script. That meant the agent needed write authorization to
every one of them, and ``/tmp/`` broke on Windows (no such dir) while ``~/``
broke in sandboxes that mount the home root read-only.

This module gives every script ONE resolved root. The agent writes to exactly
one location - whichever candidate probes writable first:

    1. ``$CUE_HOME``        (explicit pin; set this to relocate everything.
                             If set but NOT writable, we warn and fall through
                             rather than silently misroute - see cue_root.)
    2. ``~/.cue``           (default; also where ``config.json`` lives)
    3. ``<cwd>/.cue``       (sandbox blocked home root)
    4. ``$TMPDIR/cue``      (last resort; portable via tempfile)

Stdlib only. Importable by ``cue-research/scripts/research_run.py`` via the
same sys.path bootstrap it already uses for ``cue_api``.

Two distinct concepts, do not conflate:
  - ``cue_config_dir()`` : WHERE config.json + cooldowns live. Deterministic
    (CUE_HOME or ~/.cue). The user put their key here; we only READ config, so
    writability is irrelevant - never fall back to cwd/temp for config.
    Cooldowns are best-effort tiny state and ride along here (they fail
    gracefully if ~/.cue isn't writable; see SKILL.md "读写失败则本会话不再弹").
  - ``cue_root()``        : WHERE must-write runtime files (reports/logs/runs/
    backups/proposals) go. Writability-resolved via the candidate chain above.
    Raises CueNoWritableRootError if NOTHING is writable - we do NOT silently
    return an unwritable path (that would make `cue_api.py root` lie with
    exit 0 and let the agent burn credits into a black hole).

Public API:
  - cue_root()            -> Path  (resolve + mkdir + cache the write root)
  - cue_subdir(name)      -> Path  (e.g. cue_subdir("reports"); mkdir on demand)
  - cue_file(name)        -> Path  (a file directly under the root, e.g. a
                                    runtime-written json; root ensured but
                                    file not. NOT for cooldowns - see caveat)
  - cue_config_dir()      -> Path  (deterministic config home; no probe)
  - probe_writable(path)  -> bool  (mkdir + write + unlink test)
  - CueNoWritableRootError        raised by cue_root() when no candidate writes
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Subdirs lazily created under the root. Each holds one category of artifact
# so a single root stays organized instead of a flat dump. ``tmp`` is in the
# allow-list because SKILL.md tells the agent to put +create/+update payloads
# under <root>/tmp/ (and cue_subdir rejects anything not whitelisted, to
# prevent path-traversal escapes like cue_subdir("../outside")).
_SUBDIRS = ("reports", "runs", "logs", "backups", "proposals", "tmp")


class CueNoWritableRootError(RuntimeError):
    """No candidate root was writable. Raised by cue_root() so callers fail
    loudly (e.g. `cue_api.py root` exits non-zero) instead of silently
    returning an unwritable path."""


# Module-level cache. cue_root() does real I/O (probe + mkdir); cache it so
# repeated calls in one process are free. Tests reset via _reset_cache().
_ROOT: Path | None = None


def _reset_cache() -> None:
    """Test hook: forget the cached root so env changes take effect."""
    global _ROOT
    _ROOT = None


def probe_writable(path: Path) -> bool:
    """True if ``path`` can be created (if missing) AND a file written+deleted.

    mkdir(parents=True, exist_ok=True) alone is NOT a sufficient check: some
    sandboxes mount a parent read-only yet let mkdir succeed, failing only on
    the actual write. Mirrors the old ``.wtest`` probe in research_run.py.

    Uses a PID-suffixed probe filename so two processes probing the same
    candidate dir concurrently don't race on unlink (a fixed name let one
    process unlink the other's probe -> false "not writable" -> divergent
    roots)."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".cue-wtest-{os.getpid()}"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True
    except (PermissionError, OSError):
        return False


def cue_config_dir() -> Path:
    """Where ``config.json`` + cooldowns live - deterministic, NOT writability
    fallback. ``$CUE_HOME`` if set, else ``~/.cue``."""
    env = os.environ.get("CUE_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cue"


def _candidates() -> list[Path]:
    """Ordered candidate roots, deduped (by resolved string) preserving order."""
    raw: list[Path] = []
    env = os.environ.get("CUE_HOME", "").strip()
    if env:
        raw.append(Path(env).expanduser())
    raw.append(Path.home() / ".cue")
    raw.append(Path.cwd() / ".cue")
    raw.append(Path(tempfile.gettempdir()) / "cue")
    seen: set[str] = set()
    out: list[Path] = []
    for c in raw:
        try:
            key = str(c.resolve())
        except OSError:
            key = str(c)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def cue_root() -> Path:
    """Resolve the single writable root, create it, cache it.

    First candidate (see _candidates) that probes writable wins. If CUE_HOME
    was explicitly set but its candidate is NOT writable, warn to stderr
    before falling through (don't silently ignore an explicit pin). If NOTHING
    is writable, raise CueNoWritableRootError - callers (notably `cue_api.py
    root`) turn this into a non-zero exit so the agent doesn't proceed into a
    guaranteed-failure run. Quiet otherwise: callers print the root themselves.
    """
    global _ROOT
    if _ROOT is not None:
        return _ROOT
    candidates = _candidates()
    cue_home_set = bool(os.environ.get("CUE_HOME", "").strip())
    for cand in candidates:
        if probe_writable(cand):
            _ROOT = cand
            if cue_home_set and cand != candidates[0]:
                # CUE_HOME was set but unwritable; we fell through to a
                # different root. Surface this so the user's explicit pin
                # isn't silently ignored.
                sys.stderr.write(
                    f"[cue] ⚠️ CUE_HOME={os.environ['CUE_HOME']!r} 不可写,"
                    f"回落到 {cand}\n"
                )
            return _ROOT
    raise CueNoWritableRootError(
        "无可写根候选(试过 CUE_HOME / ~/.cue / <cwd>/.cue / temp)。"
        "设 CUE_HOME 指向一个可写目录,或放开 agent 对其中之一的写权限。"
    )


def cue_subdir(name: str) -> Path:
    """A whitelisted subdir under the root, created on demand (e.g. ``reports``).

    Only the subdir actually needed is created - calling cue_root() for a
    read-only verb (``whoami``) must not sprout empty reports/runs/logs dirs.
    ``name`` is validated against _SUBDIRS and must be a bare single segment
    (no separators, no absolute paths, no ``..``) to prevent escapes like
    cue_subdir("../outside") or cue_subdir("/etc")."""
    if name not in _SUBDIRS:
        raise ValueError(
            f"non-standard subdir {name!r}; allowed: {', '.join(_SUBDIRS)}"
        )
    if os.sep in name or "/" in name or name.startswith(".") or Path(name).is_absolute():
        raise ValueError(f"unsafe subdir name {name!r}")
    d = cue_root() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def cue_file(name: str) -> Path:
    """A file path directly under the root (e.g. a runtime-written json).

    Ensures the root dir exists but does NOT create the file. NOTE: cooldowns
    (last-update-check / last-community-invite) and config do NOT use this -
    they live in the deterministic config dir (cue_config_dir()), because they
    are best-effort state that must not follow the writability fallback (which
    could move them to cwd/temp on a per-run basis). Use this only for runtime
    artifacts that genuinely belong under the resolved write root.
    """
    root = cue_root()
    return root / name
