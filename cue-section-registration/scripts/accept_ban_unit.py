#!/usr/bin/env python3
"""Offline acceptance: ban-window + section replace helpers used by emit_and_merge."""
import importlib.util
import sys
from pathlib import Path

p = Path(__file__).resolve().parent / "emit_and_merge.py"
spec = importlib.util.spec_from_file_location("emit_and_merge", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Affirmative hit must fail
bad = "该管理人合规良好，建议通过。"
hits = mod.affirmative_ban_check(bad) if hasattr(mod, "affirmative_ban_check") else mod.affirmative_hits(bad)
assert hits, "expected ban hits on overclaim prose"

# Negation window must pass
ok = "不得写成合规良好或准入通过。"
hits2 = mod.affirmative_ban_check(ok) if hasattr(mod, "affirmative_ban_check") else mod.affirmative_hits(ok)
assert not hits2, f"negation window should clear hits, got {hits2}"

# Section replace keeps later heading
ms = "# T\n\n## 登记与合规\n\nold\n\n## 产品清单\n\nkeep\n"
new = "## 登记与合规\n\nnew\n"
out = mod.replace_section(ms, new)
assert "## 产品清单" in out and "keep" in out and "new" in out and "old" not in out

print("ACCEPT_BAN_UNIT_OK")
