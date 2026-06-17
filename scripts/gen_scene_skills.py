"""从 /api/playbook 生成每场景的 SKILL.md 到 cue-skills/playbook/<slug>/。

单一生成源在 Cue 后端端点（GET /api/playbook/scenes/<scene>/skill）——本脚本只
fetch + 写文件 + 删退场，不复制渲染逻辑。运行时查 live 设计 → 搭子变动无需重跑,
仅场景集合变化才增删文件。仓分离,故走 HTTP（不能直接 import 后端代码）。

用法: python3 gen_scene_skills.py [--api-base https://cuecue.cn] [--apply]
默认 dry-run（只打印 diff）；--apply 才写盘。
"""
import argparse
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
    existing = (
        set(os.listdir(REPO_PLAYBOOK_DIR)) if os.path.isdir(REPO_PLAYBOOK_DIR) else set()
    )
    add, delete = plan_changes(live, existing)
    print(
        f"live scenes: {len(live)} | 写/更新: {sorted(add)} | 删除(退场): {sorted(delete)}"
    )
    if not args.apply:
        print("(dry-run；加 --apply 写盘)")
        return 0
    for d, md in skills.items():
        path = os.path.join(REPO_PLAYBOOK_DIR, d)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(md)
    for d in delete:
        shutil.rmtree(os.path.join(REPO_PLAYBOOK_DIR, d), ignore_errors=True)
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
