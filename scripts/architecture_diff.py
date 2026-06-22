#!/usr/bin/env python3
"""Thin wrapper -> canonical liz-patterns architecture-snapshot script.

Body lives in claude-skills-marketplace/plugins/liz-patterns/scripts/.
Per `feedback_one_pattern_one_canonical_home_not_per_repo_copies_2026_06_13`
and Tapestry MANIFESTO Pillar 1: one name, one home, available everywhere.

Dispatches by THIS file's name -- architecture_snapshot.py wrapper looks up
architecture_snapshot.py canonical; same for architecture_diff.py.

Until the loom-discipline plugin invokes the canonical directly, this
wrapper is the per-repo bridge so existing callers (CI, hooks, manual
invocation) keep working.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

THIS_SCRIPT = Path(__file__).name
REPO_ROOT = Path(__file__).resolve().parent.parent


def _candidates() -> list[Path]:
    """Where to look for the canonical scripts directory, in priority order."""
    out: list[Path] = []
    if env := os.environ.get("LIZ_PATTERNS_SCRIPTS"):
        out.append(Path(env))
    out.append(REPO_ROOT.parent / "claude-skills-marketplace" / "plugins" / "liz-patterns" / "scripts")
    home = Path.home()
    out.extend([
        home / "claude-skills-marketplace" / "plugins" / "liz-patterns" / "scripts",
        Path("C:/Users/Liz/claude-skills-marketplace/plugins/liz-patterns/scripts"),
        home / ".claude" / "plugins" / "marketplaces" / "lizo-skills" / "plugins" / "liz-patterns" / "scripts",
    ])
    return out


def main() -> int:
    for cdir in _candidates():
        canonical = cdir / THIS_SCRIPT
        if canonical.exists():
            args = list(sys.argv[1:])
            if not any(a == "--repo-root" or a.startswith("--repo-root=") for a in args):
                args = ["--repo-root", str(REPO_ROOT)] + args
            return subprocess.call([sys.executable, str(canonical)] + args)
    sys.stderr.write(
        f"error: canonical {THIS_SCRIPT} not found.\n"
        f"Install: /plugin install liz-patterns@lizo-skills\n"
        f"Or set LIZ_PATTERNS_SCRIPTS to the scripts directory.\n"
    )
    return 127


if __name__ == "__main__":
    sys.exit(main())
