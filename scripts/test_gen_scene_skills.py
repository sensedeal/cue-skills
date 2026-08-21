"""Regression for gen_scene_skills.py — playbook scene-skill generator.

Stdlib unittest (same style as every <skill>/scripts/test_skill_regression.py),
so CI can run it with plain `python3 scripts/test_gen_scene_skills.py`.
No pytest fixtures (tmp_path) — a bare-python run must not be a silent no-op.
"""

import os
import tempfile
import unittest

from gen_scene_skills import existing_scene_dirs, plan_changes, scene_dir_name


class SceneDirNameTest(unittest.TestCase):
    def test_uses_skill_frontmatter_slug(self):
        md = '---\nname: cue-credit-diligence\nscene: "信贷尽调"\n---\n# x'
        self.assertEqual(scene_dir_name(md), "cue-credit-diligence")


class PlanChangesTest(unittest.TestCase):
    def test_add_update_delete(self):
        # existing on disk: {a, b}; live scenes now: {b, c} → write {b,c}, delete a
        existing = {"cue-a", "cue-b"}
        live = {"cue-b", "cue-c"}
        add, delete = plan_changes(live, existing)
        self.assertEqual(add, {"cue-b", "cue-c"})
        self.assertEqual(delete, {"cue-a"})


class ExistingSceneDirsTest(unittest.TestCase):
    def test_ignores_stray_files(self):
        # only scene subdirs count — a stray README.md must NOT be seen as a retired
        # scene (else plan_changes would mark it for rmtree).
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, "cue-equity-research"))
            os.mkdir(os.path.join(tmp, "cue-credit-diligence"))
            with open(os.path.join(tmp, "README.md"), "w") as fh:
                fh.write("# index")
            found = existing_scene_dirs(tmp)
            self.assertEqual(found, {"cue-equity-research", "cue-credit-diligence"})
            self.assertNotIn("README.md", found)
            # and the full plan never deletes the README
            _, delete = plan_changes(found, found)
            self.assertNotIn("README.md", delete)

    def test_missing_base_is_empty(self):
        self.assertEqual(existing_scene_dirs("/nonexistent/path/xyz"), set())


if __name__ == "__main__":
    unittest.main()
