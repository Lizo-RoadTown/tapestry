#!/usr/bin/env python3
"""
Layer 8 of the concrete-rule pattern: fleet audit script.

Walks every project Liz works in and reports whether each concrete rule
documented in docs/CORE_DIRECTIVES.md holds. A rule that's violated in any
project is a Layer 4 (defense-in-depth) breach — the plugin level (Layer 3)
still covers it for now, but the project-level redundancy is missing.

Currently audits:

  Directive 1 — loom-memory MCP access
    Layer 4 check: does every project's .mcp.json have a loom-memory entry?

Run from the-loom repo root:

    python scripts/audit_concrete_rules.py
    python scripts/audit_concrete_rules.py --fix    # auto-add missing entries

Exit code 0 = all rules hold across the fleet. Non-zero = violations found.

Future directives extend the AUDITS list with their own check function.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable, NamedTuple


# Default project paths to audit. Adjust if Liz's projects move on disk.
DEFAULT_HOME = Path.home()
DEFAULT_PROJECTS = [
    DEFAULT_HOME / "the-loom",
    DEFAULT_HOME / "Make_Skills",
    DEFAULT_HOME / "Summer 2026 Hub",
    DEFAULT_HOME / "SDE_Extraction",
    DEFAULT_HOME / "claude-skills-marketplace",
    DEFAULT_HOME / "classroom-hub-starter",
    DEFAULT_HOME / "humancensys-app",
]

# Env-override precedence for Tapestry migration (PR-prep-2b 2026-06-19):
#   1. TAPESTRY_MEMORY_MCP_URL: Tapestry-aware full URL; highest precedence
#   2. LOOM_MEMORY_MCP_URL: pre-Tapestry full URL
#   3. TAPESTRY_MEMORY_URL: Tapestry-aware bare base; /mcp/memory/ composed
#   4. LOOM_MEMORY_URL: pre-Tapestry bare base; /mcp/memory/ composed
#   5. Hardcoded default — the-loom's Render deployment
LOOM_MEMORY_URL = os.environ.get(
    "TAPESTRY_MEMORY_MCP_URL",
    os.environ.get(
        "LOOM_MEMORY_MCP_URL",
        f"{os.environ.get('TAPESTRY_MEMORY_URL', os.environ.get('LOOM_MEMORY_URL', 'https://loom-agent-context.onrender.com')).rstrip('/')}/mcp/memory/",
    ),
)


class AuditResult(NamedTuple):
    project: Path
    directive: str
    layer: str
    status: str  # "ok" | "violation" | "fixed" | "not-applicable"
    detail: str


def _check_loom_memory_in_mcp_json(project: Path, fix: bool) -> AuditResult:
    """Directive 1, Layer 4: does this project's .mcp.json have loom-memory?"""
    mcp_path = project / ".mcp.json"

    if not mcp_path.exists():
        if not fix:
            return AuditResult(
                project, "Directive 1", "Layer 4",
                "violation",
                ".mcp.json missing entirely — Layer 3 (plugin) is the only memory access path",
            )
        # Create fresh
        config = {"mcpServers": {"loom-memory": {"type": "http", "url": LOOM_MEMORY_URL}}}
        mcp_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        return AuditResult(
            project, "Directive 1", "Layer 4",
            "fixed", f"created {mcp_path} with loom-memory wired",
        )

    try:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return AuditResult(
            project, "Directive 1", "Layer 4",
            "violation", f"{mcp_path} is invalid JSON: {e}",
        )

    servers = data.get("mcpServers") or {}
    if "loom-memory" not in servers:
        if not fix:
            return AuditResult(
                project, "Directive 1", "Layer 4",
                "violation",
                f"{mcp_path} exists but loom-memory entry missing",
            )
        servers["loom-memory"] = {"type": "http", "url": LOOM_MEMORY_URL}
        data["mcpServers"] = servers
        mcp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return AuditResult(
            project, "Directive 1", "Layer 4",
            "fixed", f"merged loom-memory entry into {mcp_path}",
        )

    actual_url = servers["loom-memory"].get("url", "")
    if actual_url != LOOM_MEMORY_URL:
        return AuditResult(
            project, "Directive 1", "Layer 4",
            "violation",
            f"loom-memory present but URL drifted: '{actual_url}' (expected '{LOOM_MEMORY_URL}')",
        )

    return AuditResult(
        project, "Directive 1", "Layer 4",
        "ok", "loom-memory entry present + URL matches canonical",
    )


# Registry: (name, check_function). Add entries here for future directives.
AUDITS: list[tuple[str, Callable[[Path, bool], AuditResult]]] = [
    ("Directive 1 / Layer 4 — loom-memory in .mcp.json", _check_loom_memory_in_mcp_json),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix violations where possible (creates/merges .mcp.json).")
    parser.add_argument("--project", action="append", default=None,
                        help="Add a specific project path to audit. Repeatable.")
    args = parser.parse_args()

    projects = [Path(p) for p in (args.project or [])] or DEFAULT_PROJECTS
    projects = [p for p in projects if p.exists()]

    print("=" * 76)
    print(f"Concrete-rule fleet audit ({'FIX MODE' if args.fix else 'REPORT ONLY'})")
    print(f"Projects: {len(projects)}")
    print("=" * 76)
    print()

    violations = 0
    fixed = 0
    for project in projects:
        print(f"[{project.name}]")
        for audit_name, check in AUDITS:
            result = check(project, args.fix)
            marker = {
                "ok": "  [OK]      ",
                "violation": "  [VIOLATION] ",
                "fixed": "  [FIXED]   ",
                "not-applicable": "  [N/A]     ",
            }.get(result.status, "  [?]       ")
            print(f"{marker}{audit_name}")
            print(f"           {result.detail}")
            if result.status == "violation":
                violations += 1
            elif result.status == "fixed":
                fixed += 1
        print()

    print("=" * 76)
    if violations == 0 and fixed == 0:
        print("All concrete rules hold across the fleet.")
        return 0
    if args.fix:
        print(f"Fixed: {fixed}. Remaining violations: {violations}.")
        if violations:
            print("(Some violations couldn't be auto-fixed — review manually.)")
        return 0 if violations == 0 else 1
    print(f"VIOLATIONS: {violations}. Re-run with --fix to auto-correct where possible.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
