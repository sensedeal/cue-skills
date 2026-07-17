#!/usr/bin/env python3
"""+upgrade verb — check for skill updates and (optionally) pull them.

Named `+upgrade` (not `+update`) because `+update <template_id>` already
means "modify an existing template" in cue-buddy's verb table — this one
is about upgrading the skill files themselves.

User-triggered explicit `+upgrade`. Also exposes a `--silent-check` mode
that the agent invokes once at session start: with a 24h cooldown it
checks the remote SKILL.md version and prints a single-line nudge ONLY
when the local install is behind. Never prompts, never auto-pulls.

Two install modes handled:
  - git clone of the cue-skills repo → `git pull --ff-only`
  - copy of one skill subdir into ~/.claude/skills/ → manual instructions

Stdlib only. Read-only checks except the final `git pull` (gated on user
confirmation).

Usage:
  python3 cue-buddy/scripts/update_skill.py [--skill cue-buddy|cue-research]
                                            [--yes] [--dry-run]
                                            [--check-only] [--silent-check]

  --skill         which skill (default: cue-buddy)
  --yes / -y      skip confirmation prompt
  --dry-run       show diff but do not pull
  --check-only    compare versions only; no diff, no pull
  --silent-check  session-start mode: 24h-cooldown silent version check;
                  print one line to stderr if behind, else exit silently.
                  Never prompts; agent calls this at session start.

Exit codes:
  0  up-to-date OR update applied OR silent-check finished silently
  1  user cancelled / local modifications blocked pull
  2  config / arg / network error
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE))
from paths import cue_config_dir  # noqa: E402 - sibling; cooldown lives in config dir
_KNOWN_SKILLS = ("cue-buddy", "cue-research")
_DEFAULT_BRANCH = "main"
_RAW_SKILL_URL = (
    "https://raw.githubusercontent.com/sensedeal/cue-skills/"
    "{branch}/{skill}/SKILL.md"
)
_GITHUB_REPO_URL = "https://github.com/sensedeal/cue-skills"

# Cooldown file: stores per-skill timestamp of last silent-check (seconds since
# epoch). Lives in the config dir ($CUE_HOME or ~/.cue) - deterministic, no
# writability probe at import, and honors an existing cooldown file so a
# relocate via CUE_HOME doesn't reset the 24h timer. Writes are best-effort.
_COOLDOWN_PATH = cue_config_dir() / "last-update-check.json"
# Legacy location (pre-CUE_HOME). Consulted on read so a relocate via CUE_HOME
# doesn't reset the 24h timer for a skill whose timestamp still lives here.
_LEGACY_COOLDOWN_PATH = Path.home() / ".cue" / "last-update-check.json"
_COOLDOWN_SECONDS = 24 * 3600  # 24h between silent checks


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


_VERSION_RE = re.compile(r"(?m)^\s*version\s*:\s*[\"']?([^\s\"']+)[\"']?\s*$")


def _semver_tuple(v: str) -> tuple | None:
    """Parse `X.Y.Z` into a tuple for comparison. None on parse failure."""
    try:
        return tuple(int(p) for p in v.split("."))
    except (ValueError, AttributeError):
        return None


def is_local_behind(local_v: str | None, remote_v: str | None) -> bool:
    """True iff local version is STRICTLY OLDER than remote (semver tuple).

    Returns False on: same version, missing versions, parse-failure, or
    local ahead of remote (developer with unmerged work — don't nudge them
    to 'upgrade' to an older release).
    """
    if not local_v or not remote_v or local_v == remote_v:
        return False
    lt, rt = _semver_tuple(local_v), _semver_tuple(remote_v)
    if lt is None or rt is None:
        # Non-semver versions (e.g. git tags / weird strings) — be
        # conservative: nudge if they differ, since we can't compare.
        return local_v != remote_v
    return lt < rt


def parse_version_from_md(md: str) -> str | None:
    """Extract `metadata.version` from a SKILL.md's YAML frontmatter.

    Looks at the first `---\\n...\\n---` block; returns None if not found.
    """
    m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if not m:
        return None
    fm = m.group(1)
    vm = _VERSION_RE.search(fm)
    return vm.group(1) if vm else None


# ---------------------------------------------------------------------------
# Install-mode detection
# ---------------------------------------------------------------------------


def detect_install_mode(skill_dir: Path) -> tuple[str, Path | None]:
    """Return (mode, repo_root). mode ∈ {git, copy}.

    Walks up from skill_dir looking for a `.git` entry. If found, the
    parent dir is the repo root and `git pull` will work. Otherwise the
    skill was likely installed via `cp -r` and we can't auto-pull.
    """
    for ancestor in [skill_dir] + list(skill_dir.parents):
        if (ancestor / ".git").exists():
            return "git", ancestor
    return "copy", None


# ---------------------------------------------------------------------------
# Remote version fetch (GitHub raw)
# ---------------------------------------------------------------------------


def fetch_remote_version(
    skill: str,
    branch: str = _DEFAULT_BRANCH,
    timeout: float = 15.0,
) -> str | None:
    """Fetch the remote SKILL.md from GitHub raw and parse its version.

    Returns None on network error (caller handles gracefully).
    """
    url = _RAW_SKILL_URL.format(branch=branch, skill=skill)
    req = urllib.request.Request(url, headers={"Accept": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    return parse_version_from_md(body)


# ---------------------------------------------------------------------------
# Cooldown (for --silent-check)
# ---------------------------------------------------------------------------


def _load_cooldown(path: Path = _COOLDOWN_PATH) -> dict:
    """Read the cooldown JSON. Missing/corrupt → empty dict (never raise)."""
    def _read(p: Path) -> dict:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    data = _read(path)
    # If `path` is the relocated ($CUE_HOME) cooldown, also consult the legacy
    # ~/.cue cooldown so a relocate doesn't reset the 24h timer for a skill
    # whose timestamp still lives at the legacy path (honors existing). Take
    # the MAX timestamp per skill (not primary-wins): the later of the two is
    # the truth - a stale expired entry in one file must not override a newer
    # still-cooling entry in the other.
    if path != _LEGACY_COOLDOWN_PATH:
        for k, v in _read(_LEGACY_COOLDOWN_PATH).items():
            if not isinstance(v, (int, float)):
                continue
            cur = data.get(k)
            if not isinstance(cur, (int, float)) or v > cur:
                data[k] = v
    return data


def _save_cooldown(data: dict, path: Path = _COOLDOWN_PATH) -> None:
    """Best-effort write. Never raise (silent-check must not break sessions)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def _cooldown_expired(skill: str, now: float, cooldown_s: int = _COOLDOWN_SECONDS,
                     path: Path = _COOLDOWN_PATH) -> bool:
    """True if it's been ≥ cooldown_s seconds since the last silent-check
    for this skill (or there's no record yet)."""
    data = _load_cooldown(path)
    last = data.get(skill)
    if not isinstance(last, (int, float)):
        return True
    return (now - last) >= cooldown_s


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command capturing stdout/stderr. Never raises."""
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def git_local_status(repo_root: Path) -> str:
    """Return `git status --porcelain` output (empty = clean)."""
    return _git(["status", "--porcelain"], repo_root).stdout.strip()


def git_current_branch(repo_root: Path) -> str | None:
    """Return the currently-checked-out branch name, or None if detached HEAD.

    Used to refuse `+upgrade` unless the user is on the target branch — pulling
    `origin/main` into a feature branch would either silently no-op (when
    feature branch already contains main) or fail ff-only on diverged history.
    Either way the user mental model "+upgrade installs the latest from
    GitHub" doesn't match reality, so we refuse with a clear message.
    """
    res = _git(["symbolic-ref", "--short", "HEAD"], repo_root)
    if res.returncode != 0:
        return None  # detached HEAD
    name = res.stdout.strip()
    return name or None


def git_fetch(repo_root: Path, branch: str = _DEFAULT_BRANCH) -> tuple[bool, str]:
    """Run `git fetch origin <branch>`. Return (ok, stderr-on-failure)."""
    res = _git(["fetch", "origin", branch], repo_root)
    return (res.returncode == 0, res.stderr.strip())


def git_log_ahead(repo_root: Path, branch: str = _DEFAULT_BRANCH) -> list[str]:
    """Return `git log --oneline HEAD..origin/<branch>` as lines.

    Empty list means local HEAD is at-or-ahead of origin/<branch>.
    """
    res = _git(["log", "--oneline", f"HEAD..origin/{branch}"], repo_root)
    if res.returncode != 0:
        return []
    return [ln for ln in res.stdout.splitlines() if ln.strip()]


def git_pull_ff(repo_root: Path, branch: str = _DEFAULT_BRANCH) -> tuple[bool, str]:
    """Run `git pull --ff-only origin <branch>`. Return (ok, stderr-on-failure)."""
    res = _git(["pull", "--ff-only", "origin", branch], repo_root)
    return (res.returncode == 0, (res.stderr or res.stdout).strip())


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _resolve_skill_dir(skill: str) -> Path:
    if skill not in _KNOWN_SKILLS:
        raise ValueError(
            f"unknown skill {skill!r}; choose from {_KNOWN_SKILLS}"
        )
    return _REPO_ROOT / skill


def _print_session_cache_note() -> None:
    print(
        "\nℹ️ 已 load 的 SKILL.md 可能是 session 缓存——多数 agent(Claude Code / "
        "Codex CLI / Gemini CLI 等)需要**重启 agent 或重 load SKILL.md** 才会读到新版;"
        "少数 agent 支持文件变更自动 reload。不确定就重启一下最稳妥。"
    )


def silent_check_for_update(
    skill: str = "cue-buddy",
    branch: str = _DEFAULT_BRANCH,
    cooldown_s: int = _COOLDOWN_SECONDS,
    cooldown_path: Path = _COOLDOWN_PATH,
    now: float | None = None,
    fetch_fn=None,
) -> int:
    """Session-start silent check. Prints ONE line to stderr iff behind.

    Behaviour:
      - If cooldown not expired → return 0 silently.
      - Else attempt to fetch remote SKILL.md version (short timeout).
      - On network failure: return 0 silently, DO NOT update cooldown
        (so the next session will retry — don't hide outages forever).
      - On success: update cooldown timestamp regardless of behind/equal.
      - If local version ≠ remote version: print one-line nudge.

    Args (mostly for testing — production should call with defaults):
      cooldown_path / now / fetch_fn allow injection.

    Never raises. Always returns 0 (silent-check must not break sessions).
    """
    if now is None:
        now = time.time()
    if fetch_fn is None:
        fetch_fn = lambda s, b=branch: fetch_remote_version(s, b, timeout=5.0)

    if not _cooldown_expired(skill, now, cooldown_s, cooldown_path):
        return 0

    try:
        skill_dir = _resolve_skill_dir(skill)
    except ValueError:
        return 0  # silent on bad skill arg

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return 0

    try:
        local_v = parse_version_from_md(skill_md.read_text(encoding="utf-8"))
    except Exception:
        return 0

    try:
        remote_v = fetch_fn(skill)
    except Exception:
        return 0
    if remote_v is None:
        # Network failure — leave cooldown alone, retry next session.
        return 0

    # Update cooldown timestamp now that we got a result.
    data = _load_cooldown(cooldown_path)
    data[skill] = now
    _save_cooldown(data, cooldown_path)

    if is_local_behind(local_v, remote_v):
        sys.stderr.write(
            f"ℹ️  cue-skills/{skill} 有新版可用: {local_v} → {remote_v}。"
            f"运行 +upgrade 升级。\n"
        )
    return 0


def run_upgrade(
    skill: str = "cue-buddy",
    branch: str = _DEFAULT_BRANCH,
    yes: bool = False,
    dry_run: bool = False,
    check_only: bool = False,
    stdin=None,
) -> int:
    """Explicit `+upgrade` orchestration. See module docstring for CLI."""
    if stdin is None:
        stdin = sys.stdin

    try:
        skill_dir = _resolve_skill_dir(skill)
    except ValueError as e:
        sys.stderr.write(f"[+upgrade] {e}\n")
        return 2

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        sys.stderr.write(
            f"[+upgrade] {skill_md} not found — is this a real cue-skills install?\n"
        )
        return 2

    local_v = parse_version_from_md(skill_md.read_text(encoding="utf-8"))
    print(f"[+upgrade] skill: {skill}")
    print(f"           local version: {local_v or '(missing)'}")

    # 1. Fetch remote version
    remote_v = fetch_remote_version(skill, branch)
    if remote_v is None:
        sys.stderr.write(
            "[+upgrade] 无法从 GitHub 拉取最新 SKILL.md。可能是:\n"
            "           1) 网络不可达 / 被代理拦截\n"
            "           2) GitHub raw 临时故障\n"
            "           3) 仓库或分支名不对(默认 sensedeal/cue-skills@main)\n"
        )
        return 2
    print(f"           remote version (origin/{branch}): {remote_v}")

    # 2. Detect install mode
    mode, repo_root = detect_install_mode(skill_dir)
    print(
        f"           install mode: {mode}"
        + (f" (repo at {repo_root})" if repo_root else "")
    )

    if check_only:
        if local_v == remote_v:
            print(
                "\n[+upgrade] metadata.version 一致;若需精确对比 git 提交差异,"
                "去 git mode 跑(或在 GitHub 看)。"
            )
        else:
            print(f"\n[+upgrade] 有新版可用: {local_v} → {remote_v}")
        return 0

    # 3a. git mode — fetch + log + pull (with local-modification guard)
    if mode == "git":
        assert repo_root is not None

        # Refuse if user is on a non-target branch or detached HEAD. Pulling
        # origin/main into a feature branch either silently no-ops (feature
        # already contains main) or fails ff-only on diverged history; either
        # way the user mental model "+upgrade fetches the latest" breaks.
        current = git_current_branch(repo_root)
        if current is None:
            sys.stderr.write(
                f"[+upgrade] HEAD 处于 detached 状态(无 branch)。+upgrade 需要在 "
                f"`{branch}` 分支上跑。请先 `git checkout {branch}` 再重试。\n"
            )
            return 1
        if current != branch:
            sys.stderr.write(
                f"[+upgrade] 当前在分支 `{current}`,但 +upgrade 只升级 `{branch}`。"
                f"请先 `git checkout {branch}` 再重试(或在 feature 分支上手动 "
                f"`git rebase {branch}`/`git merge {branch}`,看你的工作流)。\n"
            )
            return 1

        print(f"\n[+upgrade] git fetch origin {branch} …")
        ok, err = git_fetch(repo_root, branch)
        if not ok:
            sys.stderr.write(f"[+upgrade] git fetch failed: {err}\n")
            return 2

        ahead = git_log_ahead(repo_root, branch)
        if not ahead:
            print(
                "\n[+upgrade] 已是最新(本地 HEAD 与 origin/" + branch + " 一致)。"
            )
            return 0

        print(f"\n[+upgrade] origin/{branch} 比本地新 {len(ahead)} 个提交:")
        for line in ahead[:20]:
            print(f"           {line}")
        if len(ahead) > 20:
            print(f"           ... 还有 {len(ahead) - 20} 个未列")

        dirty = git_local_status(repo_root)
        if dirty:
            sys.stderr.write(
                "\n⚠️ 本地有未提交改动,拒绝 fast-forward(防止丢失你的工作):\n"
            )
            for line in dirty.splitlines()[:10]:
                sys.stderr.write(f"           {line}\n")
            sys.stderr.write(
                "\n请先 `git stash` 或 `git commit` 你的改动,然后重跑 +upgrade。\n"
            )
            return 1

        if dry_run:
            print("\n[+upgrade] --dry-run: 不执行 git pull。")
            return 0

        if not yes:
            sys.stderr.write(
                "\n确认拉取这些提交?\n"
                "  1. 拉取(git pull --ff-only)\n"
                "  2. 取消\n"
                "请输入 [1/2]: "
            )
            sys.stderr.flush()
            try:
                choice = stdin.readline().strip().lower()
            except Exception:
                choice = ""
            if choice not in ("1", "y", "yes"):
                print("[+upgrade] 取消。")
                return 1

        print(f"\n[+upgrade] git pull --ff-only origin {branch} …")
        ok, msg = git_pull_ff(repo_root, branch)
        if not ok:
            sys.stderr.write(f"[+upgrade] git pull 失败:\n{msg}\n")
            return 2
        print(msg or "(no output)")
        print("\n[+upgrade] ✓ 升级成功。")
        _print_session_cache_note()
        return 0

    # 3b. copy mode — manual instructions
    print("\n[+upgrade] 此 skill 是 copy 装的(无 .git),无法自动 pull。")
    if local_v == remote_v:
        print(
            "           metadata.version 一致;如需 GitHub main 上的最新提交,需手动:"
        )
    else:
        print(f"           有新版可用: {local_v} → {remote_v}。手动更新方式:")
    print(
        "\n⚠️  以下命令会**覆盖** {skill_dir} 下的任何本地手工改动。先 diff/备份,"
        "再执行覆盖那一步。Cue 不会替你保留 ad-hoc edits。".format(skill_dir=skill_dir)
    )
    print(
        f"""
  # 方式 A — 重新 clone 整个 repo,先 diff 备份再覆盖
  tmp=$(mktemp -d)   # portable (Linux/macOS/git-bash); avoids Windows-less /tmp
  git clone --depth=1 {_GITHUB_REPO_URL}.git "$tmp/cue-skills"
  diff -ru {skill_dir} "$tmp/cue-skills/{skill}/" > "$tmp/{skill}.local-diff" || true
  # ⬇️ 这一步覆盖(可改成 `cp -R -i` 加交互确认,或先看上面 diff):
  cp -R "$tmp/cue-skills/{skill}/"* {skill_dir}/

  # 方式 B — 下载最新 SKILL.md 单文件(只更新单个文件,不动 scripts/)
  curl -L {_RAW_SKILL_URL.format(branch=branch, skill=skill)} -o {skill_md}
"""
    )
    _print_session_cache_note()
    return 1  # not actually updated; user must act


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="update_skill.py",
        description=(
            "Check for cue-skills updates (silent or explicit) and "
            "optionally pull them. User-triggered for full upgrade."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:", 1)[-1] if __doc__ else "",
    )
    p.add_argument(
        "--skill", default="cue-buddy", choices=list(_KNOWN_SKILLS),
        help="which skill to check (default: cue-buddy)",
    )
    p.add_argument("--branch", default=_DEFAULT_BRANCH, help=argparse.SUPPRESS)
    p.add_argument("--yes", "-y", action="store_true",
                   help="skip confirmation prompt")
    p.add_argument("--dry-run", action="store_true",
                   help="show diff but do not pull")
    p.add_argument("--check-only", action="store_true",
                   help="compare versions only; no diff, no pull")
    p.add_argument("--silent-check", action="store_true",
                   help="session-start mode: 24h-cooldown silent check; "
                   "one-line nudge if behind, else silent")
    args = p.parse_args(argv)

    if args.silent_check:
        return silent_check_for_update(skill=args.skill, branch=args.branch)
    return run_upgrade(
        skill=args.skill,
        branch=args.branch,
        yes=args.yes,
        dry_run=args.dry_run,
        check_only=args.check_only,
    )


if __name__ == "__main__":
    raise SystemExit(_cli())
