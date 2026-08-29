#!/usr/bin/env python3
"""Assert each plugin's marketplace version matches its own plugin.json version.

Guards against silent drift between `.claude-plugin/marketplace.json` (the catalog
Claude Code reads to decide what `/plugin update` offers) and each plugin's own
`<source>/.claude-plugin/plugin.json` manifest. The two version fields must be
identical; nothing else in the repo checks this, so a bump to one without the
other drifts silently onto main (as happened for tapestry-patterns 0.1.2 vs 0.1.3).

Run from the repo root:

    python scripts/check_plugin_versions.py

Exit 0 if every plugin is aligned; exit 1 with a report if any drifts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def main() -> int:
    try:
        catalog = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read {MARKETPLACE}: {e}", file=sys.stderr)
        return 1

    mismatches: list[str] = []
    checked = 0
    for plugin in catalog.get("plugins", []):
        name = plugin.get("name", "<unnamed>")
        catalog_version = plugin.get("version")
        source = (plugin.get("source") or "").lstrip("./")
        if not source:
            mismatches.append(f"{name}: no `source` field in marketplace.json")
            continue
        manifest_path = REPO_ROOT / source / ".claude-plugin" / "plugin.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            rel = manifest_path.relative_to(REPO_ROOT) if manifest_path.is_absolute() else manifest_path
            mismatches.append(f"{name}: cannot read {rel}: {e}")
            continue
        manifest_version = manifest.get("version")
        checked += 1
        if catalog_version != manifest_version:
            mismatches.append(
                f"{name}: marketplace.json={catalog_version} != "
                f"{source}/.claude-plugin/plugin.json={manifest_version}"
            )
        else:
            print(f"  OK  {name}: {catalog_version}")

    if mismatches:
        print("\nPlugin version drift detected:", file=sys.stderr)
        for m in mismatches:
            print(f"  MISMATCH  {m}", file=sys.stderr)
        print(
            "\nFix: make the plugin's own .claude-plugin/plugin.json `version` match "
            "its marketplace.json `version` (they must be identical). The bump should "
            "ride with the commit that changes the plugin.",
            file=sys.stderr,
        )
        return 1

    print(f"\nAll {checked} plugin versions aligned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
