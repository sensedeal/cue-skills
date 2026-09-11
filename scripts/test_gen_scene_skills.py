"""Regression for gen_scene_skills.py — playbook scene-skill generator.

Stdlib unittest (same style as every <skill>/scripts/test_skill_regression.py),
so CI can run it with plain `python3 scripts/test_gen_scene_skills.py`.
No pytest fixtures (tmp_path) — a bare-python run must not be a silent no-op.
"""

import os
import tempfile
import unittest

from gen_scene_skills import REPO_PLAYBOOK_DIR, diff_snapshots, existing_scene_dirs
from gen_scene_skills import normalize_skill_md, plan_changes, scene_dir_name

# The upstream copy normalize_skill_md patches away. These are the *literal*
# strings GET /api/playbook/scenes/<scene>/skill still emits (observed
# 2026-09-11, all 22 scenes). If the backend is ever updated, the replacements
# silently no-op — PlaybookSnapshotsCleanTest is what catches that, by
# asserting the invariant on the written files rather than on the input.
STALE_GRANT = "新账号送免费积分（注册 50 + 每天 10），可先免费试。"
STALE_DEPS = "否则克隆开源仓（含 cue-research + cue-buddy 全套依赖）"
STALE_MARKERS = ("注册 50 + 每天 10", "cue-research + cue-buddy 全套依赖")


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


class NormalizeSkillMdTest(unittest.TestCase):
    def test_rewrites_signup_grant_copy(self):
        out = normalize_skill_md(f"## 前置\n- {STALE_GRANT}\n- tail\n")
        self.assertIn("注册 500 + 每天 10", out)
        self.assertNotIn(STALE_GRANT, out)
        # the rest of the document is untouched
        self.assertTrue(out.startswith("## 前置\n- "), out)
        self.assertTrue(out.endswith("\n- tail\n"), out)

    def test_rewrites_dependency_copy(self):
        out = normalize_skill_md(f"- {STALE_DEPS}，**有则更新、无则克隆**：\n")
        self.assertIn("拿到自包含的 cue-research runner", out)
        self.assertNotIn(STALE_DEPS, out)
        # the clause after the patched span survives
        self.assertIn("**有则更新、无则克隆**", out)

    def test_idempotent(self):
        # --apply is run every closure round, so a second pass must be a no-op
        # (otherwise every regeneration would produce a spurious diff).
        src = f"- {STALE_GRANT}\n- {STALE_DEPS}\n"
        once = normalize_skill_md(src)
        self.assertEqual(normalize_skill_md(once), once)

    def test_leaves_unrelated_copy_alone(self):
        src = (
            "- 若你已安装 `cue-skills`（或本 skill 来自整包发布）→ 直接用其中的 "
            "`cue-research/scripts/research_run.py`，**跳过本节**。\n"
            "- 跑深度研究**消耗 credits**；只覆盖公开数据，不替代尽调/法律/核保。\n"
        )
        self.assertEqual(normalize_skill_md(src), src)


class DiffSnapshotsTest(unittest.TestCase):
    """diff_snapshots 是 dry-run 的实质：告诉收口轮次"这次会动哪些文件"。"""

    def _write(self, base, name, body):
        os.makedirs(os.path.join(base, name), exist_ok=True)
        with open(os.path.join(base, name, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write(body)

    def test_new_changed_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "cue-same", "same body\n")
            self._write(tmp, "cue-old", "old body\n")
            skills = {
                "cue-same": "same body\n",  # 与磁盘一致
                "cue-old": "new body\n",  # 已变化
                "cue-fresh": "brand new\n",  # 磁盘上没有
            }
            diffs = diff_snapshots(skills, tmp)
            self.assertEqual(diffs["cue-same"][0], "unchanged")
            self.assertEqual(diffs["cue-old"][0], "changed")
            self.assertEqual(diffs["cue-fresh"][0], "new")
            # 只有 changed 带 diff 正文，且确实包含增删两行
            self.assertIn("-old body", diffs["cue-old"][1])
            self.assertIn("+new body", diffs["cue-old"][1])
            self.assertEqual(diffs["cue-same"][1], "")
            self.assertEqual(diffs["cue-fresh"][1], "")

    def test_detects_change_that_normalize_already_applied(self):
        # 磁盘上已是 normalize 后的产物 → 必须判 unchanged（--apply 幂等的前提）
        with tempfile.TemporaryDirectory() as tmp:
            normalized = normalize_skill_md(f"- {STALE_GRANT}\n- {STALE_DEPS}\n")
            self._write(tmp, "cue-scene", normalized)
            diffs = diff_snapshots({"cue-scene": f"- {STALE_GRANT}\n- {STALE_DEPS}\n"}, tmp)
            self.assertEqual(diffs["cue-scene"][0], "unchanged")


class PlaybookSnapshotsCleanTest(unittest.TestCase):
    """No committed scene snapshot may carry the pre-#105/#107/#111 copy.

    This is the guard with teeth: it asserts on the *written files*, so it still
    fails if normalize_skill_md silently degrades (e.g. the backend rewrote the
    prose and the literals no longer match) as long as the stale strings land on
    disk through any path.
    """

    def test_no_stale_markers_in_committed_snapshots(self):
        snapshots = []
        for d in sorted(os.listdir(REPO_PLAYBOOK_DIR)):
            p = os.path.join(REPO_PLAYBOOK_DIR, d, "SKILL.md")
            if os.path.isfile(p):
                snapshots.append(p)
        self.assertTrue(snapshots, f"no SKILL.md found under {REPO_PLAYBOOK_DIR}")
        for p in snapshots:
            with open(p, encoding="utf-8") as fh:
                body = fh.read()
            for marker in STALE_MARKERS:
                self.assertNotIn(
                    marker,
                    body,
                    f"{os.path.relpath(p, REPO_PLAYBOOK_DIR)} still carries '{marker}' "
                    f"— regenerate via scripts/gen_scene_skills.py --apply",
                )


if __name__ == "__main__":
    unittest.main()
