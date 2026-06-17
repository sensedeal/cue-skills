import os

from gen_scene_skills import existing_scene_dirs, plan_changes, scene_dir_name


def test_scene_dir_name_uses_skill_frontmatter_slug():
    md = '---\nname: cue-credit-diligence\nscene: "信贷尽调"\n---\n# x'
    assert scene_dir_name(md) == "cue-credit-diligence"


def test_plan_changes_add_update_delete():
    # existing on disk: {a, b}; live scenes now: {b, c} → write {b,c}, delete a
    existing = {"cue-a", "cue-b"}
    live = {"cue-b", "cue-c"}
    add, delete = plan_changes(live, existing)
    assert add == {"cue-b", "cue-c"} and delete == {"cue-a"}


def test_existing_scene_dirs_ignores_stray_files(tmp_path):
    # only scene subdirs count — a stray README.md must NOT be seen as a retired
    # scene (else plan_changes would mark it for rmtree).
    (tmp_path / "cue-equity-research").mkdir()
    (tmp_path / "cue-credit-diligence").mkdir()
    (tmp_path / "README.md").write_text("# index")
    found = existing_scene_dirs(str(tmp_path))
    assert found == {"cue-equity-research", "cue-credit-diligence"}
    assert "README.md" not in found
    # and the full plan never deletes the README
    _, delete = plan_changes(found, found)
    assert "README.md" not in delete


def test_existing_scene_dirs_missing_base_is_empty():
    assert existing_scene_dirs("/nonexistent/path/xyz") == set()
