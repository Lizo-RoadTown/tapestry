#!/usr/bin/env python3
"""Flag a PR that changes runtime but adds no `docs/changelog/` entry.

Part of the change trail (docs/changelog/README.md). ADVISORY: the workflow that
runs this (.github/workflows/changelog-check.yml) is NOT a required merge gate.
It surfaces a missing entry in code review; humans own merge.

Rule: if the diff against the base touches any RUNTIME prefix but adds no file
under `docs/changelog/`, exit 1 with guidance. Opt out with `[skip changelog]`
in the latest commit's SUBJECT line (first line), or by genuinely adding an
entry. (Subject-only, not the whole message, so prose that merely mentions the
marker — like this docstring — doesn't accidentally trip the opt-out.)

Base ref: env CHANGELOG_BASE_REF (default `origin/main`). Diff uses the
merge-base (three-dot) so only the PR's own changes count. If the base can't be
resolved (e.g. a shallow checkout with no base fetched), the check no-ops rather
than false-alarming.

Run from the repo root:

    python scripts/check_changelog.py
"""
from __future__ import annotations

import os
import subprocess
import sys

# Paths whose change warrants a change-trail entry. scripts/ and .github/ are
# intentionally excluded — dev-tooling, not runtime (per the discipline rule).
RUNTIME_PREFIXES = (
    "services/",
    "engine/",
    "infra/migrations/",
    "apps/",
    "packages/",
    "integrations/",
)
CHANGELOG_PREFIX = "docs/changelog/"
SKIP_MARKER = "[skip changelog]"


def _run(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(args, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "")


def _changed_files(base_ref: str) -> list[str] | None:
    """Return the PR's changed files, or None if the base can't be resolved."""
    rc, _ = _run(["git", "rev-parse", "--verify", "--quiet", base_ref])
    if rc != 0:
        return None
    rc, out = _run(["git", "diff", "--name-only", f"{base_ref}...HEAD"])
    if rc != 0:
        return None
    return [line.strip() for line in out.splitlines() if line.strip()]


def _latest_commit_subject() -> str:
    """The first line of the latest commit only — where an intentional
    `[skip changelog]` marker goes. Scanning the full body would let any prose
    that merely mentions the marker trip the opt-out."""
    _, out = _run(["git", "log", "-1", "--format=%s"])
    return out


def main() -> int:
    base_ref = os.environ.get("CHANGELOG_BASE_REF", "origin/main")

    if SKIP_MARKER in _latest_commit_subject():
        print(f"changelog check: '{SKIP_MARKER}' present in the commit subject — skipping.")
        return 0

    changed = _changed_files(base_ref)
    if changed is None:
        print(
            f"changelog check: could not resolve base ref '{base_ref}'; "
            "skipping (no false alarm on a shallow/detached checkout)."
        )
        return 0

    touched_runtime = sorted(
        f for f in changed if f.startswith(RUNTIME_PREFIXES)
    )
    added_entry = any(f.startswith(CHANGELOG_PREFIX) for f in changed)

    if touched_runtime and not added_entry:
        print(
            "changelog check: this PR changes runtime but adds no "
            "docs/changelog/ entry.\n\n"
            "Runtime files touched:",
            file=sys.stderr,
        )
        for f in touched_runtime[:20]:
            print(f"  - {f}", file=sys.stderr)
        if len(touched_runtime) > 20:
            print(f"  … and {len(touched_runtime) - 20} more", file=sys.stderr)
        print(
            "\nAdd a docs/changelog/YYYY-MM-DD-<slug>.md entry (use the "
            "tapestry-patterns:changelog-entry skill), or put "
            f"'{SKIP_MARKER}' in the commit subject (first line) if no entry is "
            "warranted. This check is advisory — it does not block merge.",
            file=sys.stderr,
        )
        return 1

    if touched_runtime:
        print("changelog check: runtime change has a docs/changelog/ entry. OK.")
    else:
        print("changelog check: no runtime files touched. OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
