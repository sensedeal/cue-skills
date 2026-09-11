"""从 /api/playbook 生成每场景的 SKILL.md 到 cue-skills/playbook/<slug>/。

单一生成源在 Cue 后端端点（GET /api/playbook/scenes/<scene>/skill）——本脚本只
fetch + 写文件 + 删退场，不复制渲染逻辑。运行时查 live 设计 → 搭子变动无需重跑,
仅场景集合变化才增删文件。仓分离,故走 HTTP（不能直接 import 后端代码）。

用法: python3 gen_scene_skills.py [--api-base https://cuecue.cn] [--apply]
默认 dry-run（打印每个场景的 unified diff + 新增/退场）；--apply 才写盘。
"""
import argparse
import difflib
import json
import os
import re
import shutil
import sys
import urllib.request
from urllib.parse import quote

REPO_PLAYBOOK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "playbook"
)


def _get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def scene_dir_name(skill_md: str) -> str:
    """从生成的 SKILL.md frontmatter 取 name (= cue-<slug>) 作目录名。"""
    m = re.search(r"^name:\s*(\S+)\s*$", skill_md, re.M)
    if not m:
        raise ValueError("skill md missing frontmatter name")
    return m.group(1)


def plan_changes(live_dirs: set, existing_dirs: set):
    """返回 (要新增/更新的 dir 名集合, 要删除的 dir 名集合)。"""
    return live_dirs, existing_dirs - live_dirs


def existing_scene_dirs(base: str) -> set:
    """base 下的场景子目录集合——只算目录，忽略 README.md 等散文件
    （否则它们会被当成退场场景，进入 plan_changes 的删除集被 rmtree）。"""
    if not os.path.isdir(base):
        return set()
    return {d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))}



def normalize_skill_md(md: str) -> str:
    """Patch known-stale strings until the Cue backend skill template is updated.

    Source of truth for scene SKILL.md is GET /api/playbook/scenes/<scene>/skill.
    These replacements keep regenerated snapshots aligned with repo docs (#105/#107/#111)
    when the backend still emits older copy.
    """
    md = md.replace(
        "新账号送免费积分（注册 50 + 每天 10），可先免费试。",
        "新账号赠送积分（注册 500 + 每天 10），可先用赠送额度试。",
    )
    md = md.replace(
        "否则克隆开源仓（含 cue-research + cue-buddy 全套依赖）",
        "否则克隆开源仓（拿到自包含的 cue-research runner；整仓克隆最省事）",
    )
    return md


def diff_snapshots(skills: dict, base: str) -> dict:
    """{dir_name: (status, unified_diff)} — 对比 live(normalize 后) vs 磁盘快照。

    status ∈ {"new", "changed", "unchanged"}。只覆盖 live 场景；退场场景由
    plan_changes 的 delete 集负责。dry-run 用它回答"这次刷新到底会动哪些文件"
    ——--apply 是幂等的，无 diff 的场景 git 不动，故该集合可先看后写。
    """
    out = {}
    for d, md in sorted(skills.items()):
        new = normalize_skill_md(md)
        path = os.path.join(base, d, "SKILL.md")
        if not os.path.exists(path):
            out[d] = ("new", "")
            continue
        with open(path, encoding="utf-8") as f:
            old = f.read()
        if old == new:
            out[d] = ("unchanged", "")
            continue
        out[d] = (
            "changed",
            "".join(
                difflib.unified_diff(
                    old.splitlines(True),
                    new.splitlines(True),
                    f"playbook/{d}/SKILL.md (on disk)",
                    f"playbook/{d}/SKILL.md (live, normalized)",
                )
            ),
        )
    return out


def fetch_scene_skills(api_base: str) -> dict:
    """{dir_name: skill_md} for 每个当前浮现场景。"""
    pb = json.loads(_get(f"{api_base}/api/playbook"))
    data = pb.get("data", pb)
    out = {}
    for s in data.get("scenes", []):
        scene = s["secondary_category"]
        md = _get(f"{api_base}/api/playbook/scenes/{quote(scene)}/skill")
        out[scene_dir_name(md)] = md
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", default="https://cuecue.cn")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    skills = fetch_scene_skills(args.api_base)
    live = set(skills)
    existing = existing_scene_dirs(REPO_PLAYBOOK_DIR)
    add, delete = plan_changes(live, existing)
    print(
        f"live scenes: {len(live)} | 写/更新: {sorted(add)} | 删除(退场): {sorted(delete)}"
    )
    if not args.apply:
        diffs = diff_snapshots(skills, REPO_PLAYBOOK_DIR)
        changed = [d for d, (st, _) in diffs.items() if st != "unchanged"]
        print(f"\n将写/更新 {len(changed)}/{len(diffs)} 个场景:")
        for d in sorted(changed):
            status, text = diffs[d]
            print(f"\n=== {d} ({status}) ===")
            print(text if text else "(新场景，无旧快照)")
        print("\n(dry-run；加 --apply 写盘)")
        return 0
    for d, md in skills.items():
        path = os.path.join(REPO_PLAYBOOK_DIR, d)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(normalize_skill_md(md))
    for d in delete:
        shutil.rmtree(os.path.join(REPO_PLAYBOOK_DIR, d), ignore_errors=True)
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
