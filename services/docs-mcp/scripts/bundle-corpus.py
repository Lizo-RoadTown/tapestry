#!/usr/bin/env python
"""Copy the Tapestry docs corpus into docs_mcp/_corpus/ so the installed package
is self-contained — no DOCS_ROOT env var needed at runtime.

Run before `pip install` / `python -m build` so the wheel ships with the
corpus included.

  python services/docs-mcp/scripts/bundle-corpus.py

The script walks apps/docs-site/src/content/docs/, mirrors the directory
tree under docs_mcp/_corpus/, and copies every .md / .mdx file verbatim.
Bundled files are gitignored — they regenerate on every bundle run.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_ROOT = REPO_ROOT / "apps" / "docs-site" / "src" / "content" / "docs"
DEST_ROOT = REPO_ROOT / "services" / "docs-mcp" / "docs_mcp" / "_corpus"


def main() -> int:
    if not SRC_ROOT.is_dir():
        print(f"FAIL: docs source not found at {SRC_ROOT}")
        return 1

    if DEST_ROOT.exists():
        shutil.rmtree(DEST_ROOT)
    DEST_ROOT.mkdir(parents=True)

    count = 0
    for src in sorted(SRC_ROOT.rglob("*")):
        if not src.is_file():
            continue
        if src.suffix not in (".md", ".mdx"):
            continue
        rel = src.relative_to(SRC_ROOT)
        dst = DEST_ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        count += 1

    print(f"bundled {count} docs into {DEST_ROOT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
