#!/usr/bin/env python3
"""
Architecture diff — compares two snapshots, surfaces deltas, pulls git log.

migration_destination: tapestry/packages/cli/architecture-snapshot/

Reads the two most-recent .json snapshots from docs/architecture-snapshots/
(or paths supplied via --prev / --current), computes structured diffs,
appends git log between their SHAs, and outputs both a JSON + markdown report.

DEV-TOOLING. No LLM, no network. Same inputs always produce same output.

Companion to the canonical architecture_snapshot.py in this same directory.
Operates on the multi-manifest snapshot shape: render / node / python / mcp
/ auth / inventory, each with their own list-of-items structure.

Usage:
    python architecture_diff.py
    python architecture_diff.py --repo-root /path/to/repo
    python architecture_diff.py --prev <path> --current <path>

CANONICAL HOME: tapestry/integrations/claude-code/tapestry-patterns/scripts/ (this file). Lifted 2026-06-22 from claude-skills-marketplace/plugins/liz-patterns/scripts/
Consuming projects should call this via a thin wrapper, not copy the body.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _git_log(repo_root: Path, prev_sha: str, current_sha: str, paths: list[str]) -> list[dict]:
    """Return list of {sha, subject, files} for commits between two SHAs
    that touched any of the given paths."""
    if not prev_sha or prev_sha == "unknown" or not current_sha or current_sha == "unknown":
        return []
    if prev_sha == current_sha:
        return []
    try:
        result = subprocess.run(
            ["git", "log", "--pretty=format:%H|||%s", f"{prev_sha}..{current_sha}", "--", *paths],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
    out = []
    for line in result.stdout.splitlines():
        if "|||" not in line:
            continue
        sha, subject = line.split("|||", 1)
        files_result = subprocess.run(
            ["git", "show", "--name-only", "--pretty=format:", sha],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        files = [f.strip() for f in files_result.stdout.splitlines() if f.strip()]
        out.append({"sha": sha[:8], "subject": subject, "files": files})
    return out


# ---------------------------------------------------------------------------
# Per-section diff functions — all driven by the multi-manifest snapshot shape
# ---------------------------------------------------------------------------

def diff_render(prev: dict, current: dict) -> list[str]:
    if not (prev.get("present") and current.get("present")):
        if current.get("present") and not prev.get("present"):
            return ["NEW: render.yaml introduced"]
        if prev.get("present") and not current.get("present"):
            return ["REMOVED: render.yaml deleted"]
        return []
    changes = []
    prev_svcs = {s["name"]: s for s in prev.get("services") or []}
    curr_svcs = {s["name"]: s for s in current.get("services") or []}
    for name in sorted(set(prev_svcs) | set(curr_svcs)):
        if name not in prev_svcs:
            changes.append(f"NEW service: `{name}`")
        elif name not in curr_svcs:
            changes.append(f"REMOVED service: `{name}`")
        else:
            p, c = prev_svcs[name], curr_svcs[name]
            if p.get("plan") != c.get("plan"):
                changes.append(f"`{name}` plan: {p.get('plan')} → {c.get('plan')}")
            if p.get("env_var_keys") != c.get("env_var_keys"):
                added = set(c.get("env_var_keys") or []) - set(p.get("env_var_keys") or [])
                removed = set(p.get("env_var_keys") or []) - set(c.get("env_var_keys") or [])
                if added:
                    changes.append(f"`{name}` env vars added: " + ", ".join(f"`{k}`" for k in sorted(added)))
                if removed:
                    changes.append(f"`{name}` env vars removed: " + ", ".join(f"`{k}`" for k in sorted(removed)))
            if (p.get("disk") or {}) != (c.get("disk") or {}):
                changes.append(f"`{name}` disk changed: {p.get('disk')} → {c.get('disk')}")
    prev_dbs = {d["name"]: d for d in prev.get("databases") or []}
    curr_dbs = {d["name"]: d for d in current.get("databases") or []}
    for name in sorted(set(prev_dbs) | set(curr_dbs)):
        if name not in prev_dbs:
            changes.append(f"NEW database: `{name}`")
        elif name not in curr_dbs:
            changes.append(f"REMOVED database: `{name}`")
    return changes


def diff_node(prev: dict, current: dict) -> list[str]:
    if not (prev.get("present") and current.get("present")):
        if current.get("present") and not prev.get("present"):
            return ["NEW: package.json(s) introduced"]
        if prev.get("present") and not current.get("present"):
            return ["REMOVED: all package.json deleted"]
        return []
    changes = []
    prev_mans = {m["path"]: m for m in prev.get("manifests") or []}
    curr_mans = {m["path"]: m for m in current.get("manifests") or []}
    for path in sorted(set(prev_mans) | set(curr_mans)):
        if path not in prev_mans:
            changes.append(f"NEW package.json: `{path}`")
            continue
        if path not in curr_mans:
            changes.append(f"REMOVED package.json: `{path}`")
            continue
        prev_deps = prev_mans[path].get("key_dependencies") or {}
        curr_deps = curr_mans[path].get("key_dependencies") or {}
        for k in sorted(set(prev_deps) | set(curr_deps)):
            if k not in prev_deps:
                changes.append(f"`{path}`: NEW key dep `{k}` = `{curr_deps[k]}`")
            elif k not in curr_deps:
                changes.append(f"`{path}`: REMOVED key dep `{k}` (was `{prev_deps[k]}`)")
            elif prev_deps[k] != curr_deps[k]:
                changes.append(f"`{path}`: `{k}` `{prev_deps[k]}` → `{curr_deps[k]}`")
        if prev_mans[path].get("total_dependency_count") != curr_mans[path].get("total_dependency_count"):
            changes.append(
                f"`{path}`: total deps {prev_mans[path].get('total_dependency_count')} "
                f"→ {curr_mans[path].get('total_dependency_count')}"
            )
    return changes


def diff_python(prev: dict, current: dict) -> list[str]:
    if not (prev.get("present") and current.get("present")):
        if current.get("present") and not prev.get("present"):
            return ["NEW: Python manifests introduced"]
        if prev.get("present") and not current.get("present"):
            return ["REMOVED: all Python manifests deleted"]
        return []
    changes = []
    prev_mans = {m["path"]: m for m in prev.get("manifests") or []}
    curr_mans = {m["path"]: m for m in current.get("manifests") or []}
    for path in sorted(set(prev_mans) | set(curr_mans)):
        if path not in prev_mans:
            changes.append(f"NEW manifest: `{path}` ({curr_mans[path].get('package_count')} packages)")
            continue
        if path not in curr_mans:
            changes.append(f"REMOVED manifest: `{path}`")
            continue
        prev_pkgs = {p["name"]: p["constraint"] for p in prev_mans[path].get("packages") or []}
        curr_pkgs = {p["name"]: p["constraint"] for p in curr_mans[path].get("packages") or []}
        for name in sorted(set(prev_pkgs) | set(curr_pkgs)):
            if name not in prev_pkgs:
                changes.append(f"`{path}`: NEW `{name}` `{curr_pkgs[name]}`")
            elif name not in curr_pkgs:
                changes.append(f"`{path}`: REMOVED `{name}` (was `{prev_pkgs[name]}`)")
            elif prev_pkgs[name] != curr_pkgs[name]:
                changes.append(f"`{path}`: `{name}` `{prev_pkgs[name]}` → `{curr_pkgs[name]}`")
    return changes


def diff_mcp(prev: dict, current: dict) -> list[str]:
    if not (prev.get("present") and current.get("present")):
        if current.get("present") and not prev.get("present"):
            return ["NEW: .mcp.json introduced"]
        if prev.get("present") and not current.get("present"):
            return ["REMOVED: .mcp.json deleted"]
        return []
    changes = []
    prev_servers = {s["name"]: s for s in prev.get("servers") or []}
    curr_servers = {s["name"]: s for s in current.get("servers") or []}
    for name in sorted(set(prev_servers) | set(curr_servers)):
        if name not in prev_servers:
            changes.append(f"NEW MCP server: `{name}`")
        elif name not in curr_servers:
            changes.append(f"REMOVED MCP server: `{name}`")
        else:
            p, c = prev_servers[name], curr_servers[name]
            if p.get("url") != c.get("url"):
                changes.append(f"`{name}` url changed")
            if p.get("command") != c.get("command"):
                changes.append(f"`{name}` command changed: `{p.get('command')}` → `{c.get('command')}`")
    return changes


def diff_auth(prev: dict, current: dict) -> list[str]:
    """Auth section is now a list-of-files (multi-manifest shape)."""
    if not (prev.get("present") and current.get("present")):
        if current.get("present") and not prev.get("present"):
            return ["NEW: auth file(s) introduced"]
        if prev.get("present") and not current.get("present"):
            return ["REMOVED: all auth files deleted"]
        return []
    changes = []
    prev_files = {f["path"]: f for f in prev.get("files") or []}
    curr_files = {f["path"]: f for f in current.get("files") or []}
    flags = ["uses_drizzle", "uses_supabase", "uses_prisma", "uses_workos", "uses_clerk"]
    for path in sorted(set(prev_files) | set(curr_files)):
        if path not in prev_files:
            changes.append(f"NEW auth file: `{path}`")
            continue
        if path not in curr_files:
            changes.append(f"REMOVED auth file: `{path}`")
            continue
        p, c = prev_files[path], curr_files[path]
        for flag in flags:
            if p.get(flag) != c.get(flag):
                changes.append(f"`{path}`: {flag} changed: {p.get(flag)} → {c.get(flag)}")
        if set(p.get("providers") or []) != set(c.get("providers") or []):
            added = set(c.get("providers") or []) - set(p.get("providers") or [])
            removed = set(p.get("providers") or []) - set(c.get("providers") or [])
            if added:
                changes.append(f"`{path}`: providers added: " + ", ".join(f"`{x}`" for x in sorted(added)))
            if removed:
                changes.append(f"`{path}`: providers removed: " + ", ".join(f"`{x}`" for x in sorted(removed)))
    return changes


def diff_inventory(prev: dict, current: dict) -> list[str]:
    """Surface NEW or REMOVED top-level dirs (load-bearing for research-shape repos)."""
    if not (prev.get("present") and current.get("present")):
        return []
    prev_dirs = {d["name"] for d in prev.get("directories") or []}
    curr_dirs = {d["name"] for d in current.get("directories") or []}
    changes = []
    for name in sorted(curr_dirs - prev_dirs):
        changes.append(f"NEW top-level directory: `{name}/`")
    for name in sorted(prev_dirs - curr_dirs):
        changes.append(f"REMOVED top-level directory: `{name}/`")
    return changes


def diff_shape(prev: dict, current: dict) -> list[str]:
    p = prev.get("shape")
    c = current.get("shape")
    if p and c and p != c:
        return [f"Repo shape changed: `{p}` → `{c}`"]
    return []


# ---------------------------------------------------------------------------
# Snapshot discovery + rendering
# ---------------------------------------------------------------------------

def find_two_latest(snapshot_dir: Path) -> tuple[Path | None, Path | None]:
    files = sorted(snapshot_dir.glob("*-snapshot.json"))
    if len(files) >= 2:
        return files[-2], files[-1]
    if len(files) == 1:
        return None, files[-1]
    return None, None


def _git_paths_from_snapshot(snapshot: dict) -> list[str]:
    """Build the path-list passed to `git log` based on what the snapshot saw —
    no hardcoded web/ or platform/ assumptions."""
    paths = ["render.yaml", ".mcp.json"]
    for m in (snapshot.get("node") or {}).get("manifests") or []:
        paths.append(m.get("path"))
    for m in (snapshot.get("python") or {}).get("manifests") or []:
        paths.append(m.get("path"))
    for f in (snapshot.get("auth") or {}).get("files") or []:
        paths.append(f.get("path"))
    return [p for p in paths if p]


def render_markdown(diff: dict) -> str:
    lines = [f"# Architecture diff — {diff['current_timestamp']}", ""]
    if not diff.get("prev_timestamp"):
        lines.append("**First snapshot — no prior to compare against.**")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"**Comparing:** `{diff['prev_timestamp']}` → `{diff['current_timestamp']}`")
    lines.append(f"**Git range:** `{diff['prev_sha']}..{diff['current_sha']}`")
    lines.append(f"**Repo shape:** `{diff.get('current_shape', 'unknown')}`")
    lines.append("")

    sections = [
        ("Shape", diff["changes"].get("shape") or []),
        ("Render (backend hosting)", diff["changes"].get("render") or []),
        ("Node packages", diff["changes"].get("node") or []),
        ("Python dependencies", diff["changes"].get("python") or []),
        ("MCP servers", diff["changes"].get("mcp") or []),
        ("Auth wiring", diff["changes"].get("auth") or []),
        ("Top-level inventory", diff["changes"].get("inventory") or []),
    ]
    any_changes = False
    for title, items in sections:
        if items:
            any_changes = True
            lines.append(f"## {title}")
            lines.append("")
            for c in items:
                lines.append(f"- {c}")
            lines.append("")

    if not any_changes:
        lines.append("**No structural changes detected between snapshots.**")
        lines.append("")

    commits = diff.get("commits") or []
    if commits:
        lines.append(f"## Commits in range ({len(commits)})")
        lines.append("")
        for c in commits:
            lines.append(f"- `{c['sha']}` — {c['subject']}")
            if c["files"]:
                shown = ", ".join(f"`{f}`" for f in c["files"][:5])
                more = f" (+{len(c['files'])-5} more)" if len(c["files"]) > 5 else ""
                lines.append(f"  - files: {shown}{more}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Diff two architecture snapshots.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Path to repo. Default: cwd. Never script-location-based.",
    )
    parser.add_argument(
        "--snapshot-dir",
        default=Path("docs/architecture-snapshots"),
        type=Path,
        help="Snapshot dir relative to repo_root. Default: docs/architecture-snapshots",
    )
    parser.add_argument("--prev", type=Path, help="Path to previous snapshot.json (overrides auto)")
    parser.add_argument("--current", type=Path, help="Path to current snapshot.json (overrides auto)")
    args = parser.parse_args()

    repo_root = (args.repo_root or Path.cwd()).resolve()
    if not repo_root.exists():
        print(f"error: repo_root does not exist: {repo_root}", file=sys.stderr)
        return 1

    snapshot_dir = (repo_root / args.snapshot_dir).resolve()
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    if args.prev or args.current:
        prev_path = args.prev
        curr_path = args.current
    else:
        prev_path, curr_path = find_two_latest(snapshot_dir)

    if not curr_path:
        print(f"no snapshots found in {snapshot_dir}", file=sys.stderr)
        return 2

    current = json.loads(curr_path.read_text(encoding="utf-8"))
    prev = json.loads(prev_path.read_text(encoding="utf-8")) if prev_path else {}

    current_ts = current.get("timestamp", "unknown")
    prev_ts = prev.get("timestamp") if prev else None
    current_sha = current.get("git_sha", "unknown")
    prev_sha = prev.get("git_sha") if prev else None

    if prev:
        changes = {
            "shape": diff_shape(prev, current),
            "render": diff_render(prev.get("render", {}), current.get("render", {})),
            "node": diff_node(prev.get("node", {}), current.get("node", {})),
            "python": diff_python(prev.get("python", {}), current.get("python", {})),
            "mcp": diff_mcp(prev.get("mcp", {}), current.get("mcp", {})),
            "auth": diff_auth(prev.get("auth", {}), current.get("auth", {})),
            "inventory": diff_inventory(prev.get("inventory", {}), current.get("inventory", {})),
        }
    else:
        changes = {}

    commits = []
    if prev_sha:
        commits = _git_log(repo_root, prev_sha, current_sha, _git_paths_from_snapshot(current))

    diff = {
        "current_timestamp": current_ts,
        "prev_timestamp": prev_ts,
        "current_sha": current_sha,
        "prev_sha": prev_sha,
        "current_shape": current.get("shape"),
        "changes": changes,
        "commits": commits,
    }

    def _display(p: Path) -> str:
        try:
            return str(p.relative_to(repo_root))
        except ValueError:
            return str(p)

    base_name = curr_path.stem.replace("-snapshot", "-diff")
    json_path = snapshot_dir / f"{base_name}.json"
    md_path = snapshot_dir / f"{base_name}.md"
    json_path.write_text(json.dumps(diff, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(diff), encoding="utf-8")
    print(f"wrote {_display(json_path)}")
    print(f"wrote {_display(md_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
