#!/usr/bin/env python3
"""Tests for paths.py - the single writable-root resolver.

Stdlib only. Covers the consolidation invariants:
  - cue_root() caches across calls
  - $CUE_HOME pins the root (and overrides ~/.cue)
  - writability fallback chain (CUE_HOME -> ~/.cue -> cwd -> temp)
  - cue_config_dir() is deterministic and does NOT fall back to cwd/temp
  - cue_subdir() creates only the asked-for subdir
  - probe_writable() distinguishes writable from read-only

Usage:
    python3 scripts/test_paths.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import paths  # noqa: E402


class TestProbeWritable(unittest.TestCase):
    def test_writable_dir(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(paths.probe_writable(Path(d)))

    def test_unwritable_dir(self) -> None:
        # A path whose parent we cannot create -> probe fails. Use a
        # guaranteed-non-creatable nested path under a non-existent root
        # by patching mkdir to raise. Simplest portable: a read-only parent.
        with tempfile.TemporaryDirectory() as d:
            ro = Path(d) / "ro"
            ro.mkdir()
            ro.chmod(0o500)  # r-x for owner: cannot create files inside
            try:
                # On some CI runners we run as root, which bypasses mode bits.
                # If root, probe may still succeed; only assert when non-root.
                if os.geteuid() != 0:
                    self.assertFalse(paths.probe_writable(ro))
            finally:
                ro.chmod(0o700)  # restore so cleanup works


class TestCueRootCaching(unittest.TestCase):
    def setUp(self) -> None:
        paths._reset_cache()

    def tearDown(self) -> None:
        paths._reset_cache()

    def test_cached_after_first_call(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CUE_HOME": d}):
                first = paths.cue_root()
                second = paths.cue_root()
                self.assertEqual(first, second)
                # Env change after caching must NOT change the cached root.
                os.environ["CUE_HOME"] = "/nonexistent/elsewhere"
                self.assertEqual(paths.cue_root(), first)

    def test_reset_cache_picks_up_env_change(self) -> None:
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            with mock.patch.dict(os.environ, {"CUE_HOME": d1}):
                self.assertEqual(paths.cue_root(), Path(d1))
            paths._reset_cache()
            with mock.patch.dict(os.environ, {"CUE_HOME": d2}):
                self.assertEqual(paths.cue_root(), Path(d2))


class TestCueHomeOverride(unittest.TestCase):
    """CUE_HOME wins over ~/.cue when it is writable."""

    def setUp(self) -> None:
        paths._reset_cache()

    def tearDown(self) -> None:
        paths._reset_cache()

    def test_cue_home_chosen_when_writable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CUE_HOME": d}):
                self.assertEqual(paths.cue_root(), Path(d))

    def test_cue_home_skipped_when_unwritable(self) -> None:
        # CUE_HOME points somewhere non-writable -> resolver falls through to
        # the next writable candidate (cwd/.cue or temp), NOT the bad CUE_HOME.
        with tempfile.TemporaryDirectory() as good:
            bad = Path(good) / "blocked"
            bad.mkdir()
            bad.chmod(0o500)
            try:
                with mock.patch.dict(os.environ, {"CUE_HOME": str(bad)}):
                    if os.geteuid() != 0:
                        root = paths.cue_root()
                        self.assertNotEqual(root, bad)
            finally:
                bad.chmod(0o700)


class TestCueConfigDirDeterministic(unittest.TestCase):
    """config dir must NOT use the writability fallback - the key isn't in cwd."""

    def test_cue_home_when_set(self) -> None:
        with mock.patch.dict(os.environ, {"CUE_HOME": "/explicit/cue"}):
            self.assertEqual(paths.cue_config_dir(), Path("/explicit/cue"))

    def test_default_home(self) -> None:
        env = os.environ.pop("CUE_HOME", None)
        try:
            self.assertEqual(paths.cue_config_dir(), Path.home() / ".cue")
        finally:
            if env is not None:
                os.environ["CUE_HOME"] = env


class TestCueSubdir(unittest.TestCase):
    def setUp(self) -> None:
        paths._reset_cache()

    def tearDown(self) -> None:
        paths._reset_cache()

    def test_creates_asked_subdir_under_root(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CUE_HOME": d}):
                reports = paths.cue_subdir("reports")
                self.assertEqual(reports, Path(d) / "reports")
                self.assertTrue(reports.is_dir())

    def test_other_subdirs_not_sprouted(self) -> None:
        # Asking for "reports" must not also create runs/logs/backups/...
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CUE_HOME": d}):
                paths.cue_subdir("reports")
                self.assertTrue((Path(d) / "reports").is_dir())
                for other in ("runs", "logs", "backups", "proposals", "tmp"):
                    self.assertFalse(
                        (Path(d) / other).exists(),
                        f"{other} should not be created until asked",
                    )


class TestCueSubdirValidation(unittest.TestCase):
    """cue_subdir must reject names that could escape the root."""

    def setUp(self) -> None:
        paths._reset_cache()

    def tearDown(self) -> None:
        paths._reset_cache()

    def test_rejects_non_whitelist(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CUE_HOME": d}):
                with self.assertRaises(ValueError):
                    paths.cue_subdir("evil")

    def test_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CUE_HOME": d}):
                with self.assertRaises(ValueError):
                    paths.cue_subdir("../outside")

    def test_rejects_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CUE_HOME": d}):
                with self.assertRaises(ValueError):
                    paths.cue_subdir("/etc")

    def test_tmp_is_whitelisted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CUE_HOME": d}):
                tmp = paths.cue_subdir("tmp")
                self.assertEqual(tmp, Path(d) / "tmp")
                self.assertTrue(tmp.is_dir())


class TestCueRootNoWritable(unittest.TestCase):
    """When NO candidate is writable, cue_root() must raise (not return a
    silently-unwritable path that would make `cue_api.py root` exit 0)."""

    def setUp(self) -> None:
        paths._reset_cache()

    def tearDown(self) -> None:
        paths._reset_cache()

    def test_raises_when_nothing_writable(self) -> None:
        with mock.patch.object(paths, "probe_writable", return_value=False):
            with self.assertRaises(paths.CueNoWritableRootError):
                paths.cue_root()


class TestCueFile(unittest.TestCase):
    def setUp(self) -> None:
        paths._reset_cache()

    def tearDown(self) -> None:
        paths._reset_cache()

    def test_under_root_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CUE_HOME": d}):
                f = paths.cue_file("last-update-check.json")
                self.assertEqual(f, Path(d) / "last-update-check.json")
                self.assertFalse(f.exists())  # path only; file not created


if __name__ == "__main__":
    unittest.main(verbosity=2)
