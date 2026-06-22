#!/usr/bin/env python3
"""Audit a repository for common documentation gaps.

Usage:
    python audit_docs.py [path]

Checks for:
    - Top-level README.md
    - License file
    - docs/ folder organized by Diátaxis types (tutorials/, how-to/, reference/, explanation/)
    - ADR folder (docs/adr/)
    - Markdown files that may mix Diátaxis types

Exit code 0 if no issues, 1 if any.
"""

from __future__ import annotations

import sys
from pathlib import Path


DIATAXIS_DIRS = {"tutorials", "how-to", "reference", "explanation"}
LICENSE_NAMES = {"LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"}


def check_readme(root: Path) -> list[str]:
    issues = []
    readme = root / "README.md"
    if not readme.exists():
        issues.append("Missing README.md at repo root")
        return issues

    content = readme.read_text(encoding="utf-8", errors="replace")
    if len(content) < 200:
        issues.append("README.md is very short (<200 chars) — likely incomplete")
    if "##" not in content:
        issues.append("README.md has no section headers — likely missing structure")
    return issues


def check_license(root: Path) -> list[str]:
    for name in LICENSE_NAMES:
        if (root / name).exists():
            return []
    return ["No license file found at repo root"]


def check_docs_folder(root: Path) -> list[str]:
    docs = root / "docs"
    if not docs.exists():
        return ["No docs/ folder — consider organizing documentation by Diátaxis type"]

    found_types = {d.name.lower() for d in docs.iterdir() if d.is_dir()}
    missing = DIATAXIS_DIRS - found_types
    issues = []
    if missing == DIATAXIS_DIRS:
        issues.append(
            "docs/ exists but no Diátaxis-style subfolders found "
            f"(expected one of: {', '.join(sorted(DIATAXIS_DIRS))})"
        )
    elif missing:
        issues.append(
            f"docs/ is missing Diátaxis types: {', '.join(sorted(missing))}"
        )
    return issues


def check_adr(root: Path) -> list[str]:
    adr_paths = [root / "docs" / "adr", root / "adr", root / "doc" / "adr"]
    if any(p.exists() for p in adr_paths):
        return []
    return ["No ADR folder found (consider docs/adr/ for architectural decisions)"]


def find_mixed_type_docs(root: Path) -> list[str]:
    """Heuristic: look for files whose headings suggest mixed Diátaxis types."""
    issues = []
    docs = root / "docs"
    if not docs.exists():
        return issues

    type_signals = {
        "tutorial": {"step 1", "let's start", "you'll learn", "first, "},
        "reference": {"## api", "parameters:", "returns:", "## options"},
        "explanation": {"## why", "## background", "## rationale"},
    }

    for md in docs.rglob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        hits = {
            kind for kind, signals in type_signals.items()
            if any(sig in text for sig in signals)
        }
        if len(hits) >= 2:
            rel = md.relative_to(root)
            issues.append(f"{rel}: appears to mix types ({', '.join(sorted(hits))})")
    return issues


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        return 2

    print(f"Auditing {root}\n")
    all_issues: list[tuple[str, list[str]]] = [
        ("README", check_readme(root)),
        ("License", check_license(root)),
        ("Docs folder", check_docs_folder(root)),
        ("ADRs", check_adr(root)),
        ("Mixed-type docs", find_mixed_type_docs(root)),
    ]

    total = 0
    for section, issues in all_issues:
        if not issues:
            print(f"[OK] {section}")
            continue
        print(f"[!!] {section}")
        for issue in issues:
            print(f"     - {issue}")
            total += 1

    print()
    if total == 0:
        print("No issues found.")
        return 0
    print(f"{total} issue(s) found.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
