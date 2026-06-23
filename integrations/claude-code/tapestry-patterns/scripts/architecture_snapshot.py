#!/usr/bin/env python3
"""
Architecture snapshot — deterministic, shape-agnostic extractor.

migration_destination: tapestry/packages/cli/architecture-snapshot/

Reads structural state from any consuming project + emits two artifacts:

  1. <timestamp>-snapshot.json — machine-readable for diff
  2. <timestamp>-snapshot.md   — human-readable with a Mermaid diagram

Auto-detects (no per-repo hardcoded paths):
  - render.yaml          (services, env-var KEYS only, disks, databases)
  - .mcp.json            (MCP servers)
  - ANY requirements*.txt under root (excluding vendor/generated dirs)
  - ANY package.json under root (interesting deps + scripts; excluding vendor)
  - ANY pyproject.toml under root
  - ANY auth.ts / auth.config.ts / lib/auth.ts (Auth.js-shape patterns)
  - Top-level directory inventory (for research-shape / docs-only repos
    that don't have package.json / requirements.txt)

This is DEV-TOOLING. Pure static parsing — no LLM, no network calls, no
token cost. Deterministic: same inputs always produce same outputs.

Usage:
    python architecture_snapshot.py
    python architecture_snapshot.py --repo-root /path/to/repo
    python architecture_snapshot.py --output-dir docs/architecture-snapshots
    python architecture_snapshot.py --json-only

CANONICAL HOME: tapestry/integrations/claude-code/tapestry-patterns/scripts/ (this file). Lifted 2026-06-22 from claude-skills-marketplace/plugins/liz-patterns/scripts/
Per `feedback_one_pattern_one_canonical_home_not_per_repo_copies_2026_06_13`,
consuming projects should NOT contain a copy of this script's body. They
should contain a thin wrapper that invokes the canonical version (see
scripts/architecture_snapshot_wrapper.py for the template).

Until the tapestry-discipline plugin is updated to invoke the canonical
script directly (Loom-agent's pending fix), each consuming project ships
the wrapper as a transient bridge.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("missing dependency: PyYAML. install via 'pip install PyYAML'", file=sys.stderr)
    sys.exit(1)


_EXCLUDED_DIR_PARTS = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__",
    "site-packages", ".mypy_cache", ".pytest_cache", ".tox", "build",
    "dist", ".next", ".turbo", ".vercel", "vendor", "_upstream",
    "anthropics-skills", "deprecated", "docs/_archive", ".serena",
    ".project-intelligence",
}


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _is_excluded(rel_path: Path) -> bool:
    parts = rel_path.parts
    for part in parts[:-1]:
        if part in _EXCLUDED_DIR_PARTS:
            return True
    return False


def _git_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


# ---------------------------------------------------------------------------
# render.yaml
# ---------------------------------------------------------------------------

def parse_render_yaml(repo_root: Path) -> dict:
    """Extract services, env var KEYS (never values), disks, databases."""
    path = repo_root / "render.yaml"
    raw = _read_text(path)
    if raw is None:
        return {"present": False}
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        return {"present": True, "parse_error": str(e)}

    services = []
    for svc in data.get("services") or []:
        env_keys = sorted([e.get("key") for e in svc.get("envVars") or [] if e.get("key")])
        disk = svc.get("disk") or {}
        services.append({
            "name": svc.get("name"),
            "type": svc.get("type"),
            "runtime": svc.get("runtime"),
            "plan": svc.get("plan"),
            "region": svc.get("region"),
            "auto_deploy": svc.get("autoDeploy"),
            "previews": (svc.get("previews") or {}).get("generation"),
            "health_check": svc.get("healthCheckPath"),
            "env_var_keys": env_keys,
            "disk": {
                "name": disk.get("name"),
                "mount_path": disk.get("mountPath"),
                "size_gb": disk.get("sizeGB"),
            } if disk else None,
        })

    databases = []
    for db in data.get("databases") or []:
        databases.append({
            "name": db.get("name"),
            "plan": db.get("plan"),
            "database_name": db.get("databaseName"),
            "region": db.get("region"),
        })

    return {"present": True, "services": services, "databases": databases}


# ---------------------------------------------------------------------------
# package.json — auto-discover all package.json files
# ---------------------------------------------------------------------------

_INTERESTING_NODE_DEPS = {
    # Frameworks
    "next", "react", "react-dom", "vue", "svelte", "vite", "remix",
    # Auth
    "next-auth", "@auth/drizzle-adapter", "@auth/prisma-adapter",
    "@supabase/supabase-js", "@clerk/nextjs", "@workos-inc/node",
    # DB / ORM
    "drizzle-orm", "pg", "@prisma/client", "mongodb", "mongoose",
    # UI
    "tailwindcss", "@tailwindcss/postcss", "shadcn-ui",
    # State / motion
    "xstate", "@xstate/react", "motion", "zustand", "redux",
    # Docs
    "fumadocs-core", "fumadocs-ui", "nextra",
    # Build tooling
    "typescript", "esbuild", "webpack",
}


def parse_node_packages(repo_root: Path) -> dict:
    """Discover every package.json under repo_root + extract interesting deps."""
    manifests = []
    for path in repo_root.rglob("package.json"):
        rel = path.relative_to(repo_root)
        if _is_excluded(rel):
            continue
        raw = _read_text(path)
        if raw is None:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            manifests.append({
                "path": rel.as_posix(),
                "parse_error": str(e),
            })
            continue
        deps = data.get("dependencies") or {}
        dev_deps = data.get("devDependencies") or {}
        all_deps = {**deps, **dev_deps}
        pinned_interesting = {k: v for k, v in all_deps.items() if k in _INTERESTING_NODE_DEPS}
        manifests.append({
            "path": rel.as_posix(),
            "name": data.get("name"),
            "version": data.get("version"),
            "scripts": list((data.get("scripts") or {}).keys()),
            "key_dependencies": pinned_interesting,
            "total_dependency_count": len(deps),
            "total_dev_dependency_count": len(dev_deps),
        })
    if not manifests:
        return {"present": False}
    manifests.sort(key=lambda m: m["path"])
    return {
        "present": True,
        "manifests": manifests,
        "total_manifest_count": len(manifests),
    }


# ---------------------------------------------------------------------------
# requirements*.txt + pyproject.toml — Python dep auto-discovery
# ---------------------------------------------------------------------------

def _parse_requirements_lines(raw: str) -> list[dict]:
    packages = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"([a-zA-Z0-9_.\-\[\]]+)\s*([><=!~]+\s*[\d.]+.*)?", line)
        if m:
            packages.append({"name": m.group(1).lower(), "constraint": (m.group(2) or "").strip()})
    return packages


def parse_python_dependencies(repo_root: Path) -> dict:
    """Discover every requirements*.txt + pyproject.toml under root."""
    manifests = []
    total_packages = 0

    for path in repo_root.rglob("requirements*.txt"):
        rel = path.relative_to(repo_root)
        if _is_excluded(rel):
            continue
        raw = _read_text(path)
        if raw is None:
            continue
        packages = sorted(_parse_requirements_lines(raw), key=lambda p: p["name"])
        manifests.append({
            "path": rel.as_posix(),
            "kind": "requirements.txt",
            "package_count": len(packages),
            "packages": packages,
        })
        total_packages += len(packages)

    for path in repo_root.rglob("pyproject.toml"):
        rel = path.relative_to(repo_root)
        if _is_excluded(rel):
            continue
        raw = _read_text(path)
        if raw is None:
            continue
        # Lightweight extraction: just count deps and capture project name.
        # Full TOML parse is optional; we surface presence + a hint.
        name_match = re.search(r'^\s*name\s*=\s*"([^"]+)"', raw, re.MULTILINE)
        deps_block = re.search(r"\bdependencies\s*=\s*\[(.*?)\]", raw, re.DOTALL)
        pkg_count = 0
        if deps_block:
            pkg_count = len(re.findall(r'"[^"]+"', deps_block.group(1)))
        manifests.append({
            "path": rel.as_posix(),
            "kind": "pyproject.toml",
            "project_name": name_match.group(1) if name_match else None,
            "package_count": pkg_count,
            "packages": [],  # full extraction deferred — toml parser not in stdlib for 3.10
        })
        total_packages += pkg_count

    if not manifests:
        return {"present": False}
    manifests.sort(key=lambda m: m["path"])
    return {
        "present": True,
        "manifests": manifests,
        "total_manifest_count": len(manifests),
        "total_package_count": total_packages,
    }


# ---------------------------------------------------------------------------
# .mcp.json
# ---------------------------------------------------------------------------

def parse_mcp_config(repo_root: Path) -> dict:
    """Extract MCP servers and their command/url shapes."""
    path = repo_root / ".mcp.json"
    raw = _read_text(path)
    if raw is None:
        return {"present": False}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"present": True, "parse_error": str(e)}

    servers = []
    for name, cfg in (data.get("mcpServers") or {}).items():
        servers.append({
            "name": name,
            "shape": "command" if cfg.get("command") else ("url" if cfg.get("url") else "unknown"),
            "command": cfg.get("command"),
            "args_count": len(cfg.get("args") or []),
            "url": cfg.get("url"),
        })
    return {"present": True, "servers": servers}


# ---------------------------------------------------------------------------
# Auth — auto-discover auth.ts / auth.config.ts patterns
# ---------------------------------------------------------------------------

_AUTH_FILE_PATTERNS = ["auth.ts", "auth.config.ts"]


def parse_auth_setup(repo_root: Path) -> dict:
    """Auto-discover auth wiring files anywhere in the repo."""
    matches = []
    for pattern in _AUTH_FILE_PATTERNS:
        for path in repo_root.rglob(pattern):
            rel = path.relative_to(repo_root)
            if _is_excluded(rel):
                continue
            raw = _read_text(path)
            if raw is None:
                continue
            adapters = re.findall(r"from\s+[\"']@auth/([a-zA-Z\-]+)-adapter[\"']", raw)
            providers = re.findall(r"import\s+\w+\s+from\s+[\"']next-auth/providers/(\w+)[\"']", raw)
            db_imports = re.findall(r"from\s+[\"']([^\"']*db[^\"']*)[\"']", raw)
            matches.append({
                "path": rel.as_posix(),
                "adapters": adapters,
                "providers": providers,
                "uses_drizzle": "DrizzleAdapter" in raw,
                "uses_supabase": "@supabase" in raw or "createServerClient" in raw,
                "uses_prisma": "PrismaAdapter" in raw,
                "uses_workos": "WorkOS" in raw or "workos" in raw.lower(),
                "uses_clerk": "Clerk" in raw or "@clerk" in raw,
                "db_imports": db_imports,
            })
    if not matches:
        return {"present": False}
    matches.sort(key=lambda m: m["path"])
    return {"present": True, "files": matches}


# ---------------------------------------------------------------------------
# Top-level directory inventory (research-shape fallback)
# ---------------------------------------------------------------------------

def parse_top_level_inventory(repo_root: Path) -> dict:
    """Inventory top-level dirs + notable files. Useful for research-shape
    repos that don't have package.json / requirements.txt to anchor a snapshot.

    Captures: dir names (only, no recursion), file count per dir, presence of
    .project-intelligence/, .mcp.json, render.yaml, CLAUDE.md, ARCHITECTURE.md.
    """
    dirs = []
    notable_files = []
    notable_targets = {
        ".project-intelligence", ".mcp.json", "render.yaml",
        "CLAUDE.md", "AGENTS.md", "ARCHITECTURE.md", "README.md",
        ".env.template", "vite.config.js", "next.config.js",
        "supabase",
    }
    try:
        for entry in sorted(repo_root.iterdir()):
            if entry.name.startswith("."):
                if entry.name in notable_targets:
                    notable_files.append({"name": entry.name, "type": "dir" if entry.is_dir() else "file"})
                continue
            if entry.is_dir():
                if entry.name in _EXCLUDED_DIR_PARTS:
                    continue
                # Count files at depth 1 only (cheap)
                try:
                    file_count = sum(1 for f in entry.iterdir() if f.is_file())
                    subdir_count = sum(1 for d in entry.iterdir() if d.is_dir())
                except (OSError, PermissionError):
                    file_count = 0
                    subdir_count = 0
                dirs.append({
                    "name": entry.name,
                    "file_count_depth_1": file_count,
                    "subdir_count": subdir_count,
                })
            elif entry.name in notable_targets:
                notable_files.append({"name": entry.name, "type": "file"})
    except (OSError, PermissionError):
        return {"present": False, "error": "could not iterate repo_root"}

    return {
        "present": True,
        "directories": dirs,
        "notable_files": notable_files,
    }


# ---------------------------------------------------------------------------
# Repo-shape classification
# ---------------------------------------------------------------------------

def classify_repo_shape(snapshot: dict) -> str:
    """Classify what kind of repo this is based on what was detected.

    Returns one of: 'engine', 'web-app', 'multi-service', 'research', 'docs-only', 'mixed'.
    Pure heuristic — used to drive the markdown's narrative + the mermaid diagram.
    """
    has_render = (snapshot.get("render") or {}).get("present")
    has_node = (snapshot.get("node") or {}).get("present")
    has_python = (snapshot.get("python") or {}).get("present")
    py_manifest_count = (snapshot.get("python") or {}).get("total_manifest_count", 0) or 0
    node_manifest_count = (snapshot.get("node") or {}).get("total_manifest_count", 0) or 0

    if not (has_render or has_node or has_python):
        return "docs-only"
    if has_node and not has_python:
        return "web-app"
    if has_python and not has_node:
        if py_manifest_count >= 3:
            return "multi-service"
        return "engine"
    if has_node and has_python:
        return "mixed"
    return "mixed"


# ---------------------------------------------------------------------------
# Mermaid renderer — driven by what was detected, NOT hardcoded
# ---------------------------------------------------------------------------

def render_mermaid(snapshot: dict) -> str:
    render_block = snapshot.get("render") or {}
    node_block = snapshot.get("node") or {}
    auth_block = snapshot.get("auth") or {}
    mcp_block = snapshot.get("mcp") or {}
    shape = snapshot.get("shape", "unknown")

    lines = ["```mermaid", "graph TB", ""]
    has_user_edge = False

    # Render-deployed backend services
    if render_block.get("present"):
        services = render_block.get("services") or []
        databases = render_block.get("databases") or []
        if services or databases:
            lines.append('    subgraph Render["Render"]')
            for svc in services:
                label = f"{svc.get('name','?')}<br/>{svc.get('runtime','?')} · plan: {svc.get('plan','?')}"
                if svc.get("disk"):
                    d = svc["disk"]
                    label += f"<br/>disk: {d.get('mount_path')} ({d.get('size_gb')}GB)"
                key = "svc_" + (svc.get("name", "x").replace("-", "_"))
                lines.append(f'        {key}["{label}"]')
            for db in databases:
                label = f"{db.get('name','?')}<br/>Postgres · {db.get('plan','?')}"
                key = "db_" + (db.get("name", "db").replace("-", "_"))
                lines.append(f"        {key}[({label})]")
            lines.append("    end")
            lines.append("")

    # Node frontends (auto-detected, NOT hardcoded to Vercel/humancensys)
    if node_block.get("present"):
        for m in node_block.get("manifests") or []:
            mpath = m.get("path", "?")
            mname = m.get("name") or mpath.replace("/", "_")
            mkey = "node_" + re.sub(r"[^a-zA-Z0-9_]", "_", mpath)
            deps = m.get("key_dependencies") or {}
            tag = mname
            if "next" in deps:
                tag += f"<br/>Next.js {deps['next']}"
            elif "vite" in deps:
                tag += f"<br/>Vite {deps['vite']}"
            elif "react" in deps:
                tag += f"<br/>React {deps['react']}"
            lines.append(f'    {mkey}["{tag}<br/>{mpath}"]')
        lines.append("")

    # MCP layer
    servers = mcp_block.get("servers") or []
    if servers:
        lines.append('    subgraph MCP["MCP servers (.mcp.json)"]')
        for s in servers:
            shape_s = s.get("shape", "?")
            target = s.get("url") or s.get("command") or "?"
            key = "mcp_" + re.sub(r"[^a-zA-Z0-9_]", "_", s.get("name") or "x")
            lines.append(f'        {key}["{s.get("name")}<br/>{shape_s}: {str(target)[:48]}"]')
        lines.append("    end")
        lines.append("")

    lines.append("```")
    if shape == "research" or shape == "docs-only":
        lines.append("")
        lines.append(f"_(Diagram is sparse — repo shape detected as: **{shape}**. "
                     "Top-level inventory section below carries the load-bearing structure.)_")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def render_markdown(snapshot: dict) -> str:
    ts = snapshot["timestamp"]
    sha = snapshot["git_sha"]
    shape = snapshot.get("shape", "unknown")

    out = [f"# Architecture snapshot — {ts}", ""]
    out.append(f"**Git SHA:** `{sha}`")
    out.append(f"**Repo shape (auto-detected):** `{shape}`")
    out.append(f"**Generated by:** canonical `architecture_snapshot.py` in `tapestry-patterns` plugin")
    out.append("")
    out.append("Deterministic + shape-agnostic. For prose narrative and diagnosis, see the")
    out.append("matching `-narrative.md` (produced by the architecture-analyst agent).")
    out.append("")

    out.append("## Diagram")
    out.append("")
    out.append(render_mermaid(snapshot))
    out.append("")

    # Render
    render_block = snapshot.get("render") or {}
    if render_block.get("present"):
        out.append("## Render (backend hosting)")
        out.append("")
        for svc in render_block.get("services") or []:
            out.append(f"### Service: `{svc.get('name')}`")
            out.append(f"- Runtime: {svc.get('runtime')}, plan: {svc.get('plan')}, region: {svc.get('region')}")
            if svc.get("disk"):
                d = svc["disk"]
                out.append(f"- Persistent disk: `{d.get('mount_path')}` ({d.get('size_gb')} GB)")
            out.append(f"- Auto-deploy: {svc.get('auto_deploy')}, previews: {svc.get('previews')}")
            out.append(f"- Env var keys ({len(svc.get('env_var_keys') or [])}): " + ", ".join(f"`{k}`" for k in svc.get("env_var_keys") or []))
            out.append("")
        for db in render_block.get("databases") or []:
            out.append(f"### Database: `{db.get('name')}`")
            out.append(f"- Plan: {db.get('plan')}, database name: `{db.get('database_name')}`, region: {db.get('region')}")
            out.append("")

    # Node packages
    node_block = snapshot.get("node") or {}
    if node_block.get("present"):
        out.append(f"## Node packages ({node_block.get('total_manifest_count')} package.json)")
        out.append("")
        for m in node_block.get("manifests") or []:
            out.append(f"### `{m.get('path')}` — {m.get('name','?')} v{m.get('version','?')}")
            if m.get("parse_error"):
                out.append(f"- Parse error: `{m['parse_error']}`")
                continue
            out.append(f"- Scripts: " + ", ".join(f"`{s}`" for s in m.get("scripts") or []))
            out.append(f"- Total deps: {m.get('total_dependency_count')}, devDeps: {m.get('total_dev_dependency_count')}")
            kd = m.get("key_dependencies") or {}
            if kd:
                out.append(f"- Key pinned versions:")
                for k, v in kd.items():
                    out.append(f"  - `{k}`: `{v}`")
            out.append("")

    # Python
    py_block = snapshot.get("python") or {}
    if py_block.get("present"):
        out.append(f"## Python dependencies ({py_block.get('total_manifest_count')} manifests, {py_block.get('total_package_count')} packages)")
        out.append("")
        for m in py_block.get("manifests") or []:
            out.append(f"### `{m.get('path')}` ({m.get('kind')}, {m.get('package_count')} packages)")
            for pkg in m.get("packages") or []:
                c = pkg.get("constraint") or ""
                suffix = f" {c}" if c else ""
                out.append(f"- `{pkg.get('name')}{suffix}`")
            out.append("")

    # Auth (auto-discovered)
    auth_block = snapshot.get("auth") or {}
    if auth_block.get("present"):
        out.append(f"## Auth wiring ({len(auth_block.get('files') or [])} files)")
        out.append("")
        for f in auth_block.get("files") or []:
            out.append(f"### `{f.get('path')}`")
            for flag in ("uses_drizzle", "uses_supabase", "uses_prisma", "uses_workos", "uses_clerk"):
                if f.get(flag):
                    out.append(f"- {flag.replace('uses_', '').capitalize()}: yes")
            if f.get("providers"):
                out.append(f"- Providers: " + ", ".join(f"`{p}`" for p in f["providers"]))
            if f.get("adapters"):
                out.append(f"- Adapters: " + ", ".join(f"`@auth/{a}-adapter`" for a in f["adapters"]))
            out.append("")

    # MCP
    mcp_block = snapshot.get("mcp") or {}
    if mcp_block.get("present"):
        out.append("## MCP servers (`.mcp.json`)")
        out.append("")
        for s in mcp_block.get("servers") or []:
            label = s.get("name")
            if s.get("shape") == "command":
                out.append(f"- `{label}` — command: `{s.get('command')}` (args: {s.get('args_count')})")
            elif s.get("shape") == "url":
                out.append(f"- `{label}` — url: `{s.get('url')}`")
        out.append("")

    # Top-level inventory (always shown for research-shape / docs-only;
    # also useful as context for engine/multi-service repos)
    inv_block = snapshot.get("inventory") or {}
    if inv_block.get("present"):
        out.append("## Top-level inventory")
        out.append("")
        dirs = inv_block.get("directories") or []
        if dirs:
            out.append("### Directories (depth-1)")
            out.append("")
            out.append("| Directory | Files (depth 1) | Subdirs |")
            out.append("|---|---:|---:|")
            for d in dirs:
                out.append(f"| `{d['name']}/` | {d['file_count_depth_1']} | {d['subdir_count']} |")
            out.append("")
        notable = inv_block.get("notable_files") or []
        if notable:
            out.append("### Notable root files")
            out.append("")
            for n in notable:
                out.append(f"- `{n['name']}` ({n['type']})")
            out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an architecture snapshot.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Path to repo to snapshot. Default: cwd. Overrides any default-from-script-location behavior.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/architecture-snapshots"),
        help="Where to write snapshot files (relative to repo_root). Default: docs/architecture-snapshots",
    )
    parser.add_argument("--json-only", action="store_true", help="Skip the .md output.")
    args = parser.parse_args()

    # Repo root resolution: explicit arg > cwd. Never fall back to script location.
    repo_root = (args.repo_root or Path.cwd()).resolve()
    if not repo_root.exists():
        print(f"error: repo_root does not exist: {repo_root}", file=sys.stderr)
        return 1

    out_dir = (repo_root / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d-%H%M")

    snapshot = {
        "timestamp": now.isoformat(),
        "git_sha": _git_sha(repo_root),
        "repo_root": str(repo_root),
        "render": parse_render_yaml(repo_root),
        "node": parse_node_packages(repo_root),
        "python": parse_python_dependencies(repo_root),
        "mcp": parse_mcp_config(repo_root),
        "auth": parse_auth_setup(repo_root),
        "inventory": parse_top_level_inventory(repo_root),
    }
    snapshot["shape"] = classify_repo_shape(snapshot)

    def _display(p: Path) -> str:
        try:
            return str(p.relative_to(repo_root))
        except ValueError:
            return str(p)

    json_path = out_dir / f"{timestamp}-snapshot.json"
    json_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {_display(json_path)}")

    if not args.json_only:
        md_path = out_dir / f"{timestamp}-snapshot.md"
        md_path.write_text(render_markdown(snapshot), encoding="utf-8")
        print(f"wrote {_display(md_path)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
