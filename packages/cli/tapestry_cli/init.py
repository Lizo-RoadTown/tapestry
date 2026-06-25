"""loom init — onboard the current directory as a loom consuming project.

The implementation behind `loom init` (and the legacy `scripts/loom_init.py`
shim). Stdlib-only so it runs equally from PowerShell / bash / zsh on
Windows / macOS / Linux without extra installs.

What it does (mirrors `docs/howto/onboard-a-project.md` Part 1, steps 2-5):

  1. Pre-check: confirm you're in a directory that looks like a project
     (has .git, or has files, or you pass --force).
  2. Pre-check: confirm the slug isn't already registered for your
     tenant (GET /projects/by-slug/<slug>). Idempotent on rerun.
  3. POST to your project-registry deployment's /projects endpoint to
     register the project (set --registry-url or TAPESTRY_REGISTRY_URL).
     Self-host mode: no Bearer token needed; server falls back to
     SELF_HOST_TENANT_ID.
  4. Create .env in the current dir with OTel credentials copied from
     the-loom's .env (so hook events flow to Grafana tagged with this
     new project_id) + LOOM_PROJECT_ID=<slug>.
  5. Create .project-intelligence/ folder per the platform-data-model.
  6. Print confirmation + next-steps.

What it does NOT do:
  - Does NOT create a GitHub repo (use `gh repo create` or the
    PowerShell scaffolder for that).
  - Does NOT install the tapestry-discipline Claude Code plugin.
  - Does NOT install skills (Phase 5 SDK install-path future work).
  - Does NOT touch .gitignore (warns if .env not gitignored).

Dual-mode:
  - Self-host (default): no --token, server falls back to SELF_HOST_TENANT_ID.
  - Hosted-multitenant: pass --token <jwt>; sent as Bearer to the Registry.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional


# No personal deployment baked in. Point this at YOUR backend with
# --registry-url or the TAPESTRY_REGISTRY_URL env var.
DEFAULT_REGISTRY_URL = os.environ.get(
    "TAPESTRY_REGISTRY_URL", "https://your-project-registry.example.com"
)


def _read_loom_env(loom_repo: Path) -> dict[str, str]:
    """Read the-loom's .env to pull OTel credentials for propagation."""
    env_path = loom_repo / ".env"
    out: dict[str, str] = {}
    if not env_path.is_file():
        return out
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key:
                out[key] = value
    except OSError:
        pass
    return out


def _gitignore_has_env(project_dir: Path) -> bool:
    gi = project_dir / ".gitignore"
    if not gi.is_file():
        return False
    try:
        for line in gi.read_text(encoding="utf-8").splitlines():
            if line.strip() == ".env":
                return True
    except OSError:
        pass
    return False


def _warm_registry(registry_url: str, max_wait: float = 90.0) -> None:
    """Render free-tier services cold-start. Wait for /health up to max_wait."""
    url = registry_url.rstrip("/") + "/health"
    deadline = time.time() + max_wait
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url=url, method="GET"), timeout=15
            ) as resp:
                if resp.status == 200:
                    if attempt > 1:
                        print(f"  Registry warmed up (attempt {attempt}).")
                    return
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, ConnectionError, OSError):
            pass
        if attempt == 1:
            print(f"  Registry cold-starting (Render free tier); waiting up to {int(max_wait)}s...")
        time.sleep(5)
    print(f"  WARN: Registry /health didn't respond within {int(max_wait)}s; proceeding anyway.")


def _check_registry(
    registry_url: str, slug: str, token: Optional[str], timeout: float = 60.0,
) -> Optional[dict[str, Any]]:
    """GET /projects/by-slug/<slug>. Returns row, None on 404, raises on other errors."""
    url = registry_url.rstrip("/") + f"/projects/by-slug/{urllib.parse.quote(slug)}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
            return None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Registry GET /by-slug/{slug} returned HTTP {e.code}: {body}")


def _register_project(
    registry_url: str,
    slug: str,
    name: str,
    description: str,
    kind: str,
    token: Optional[str],
    timeout: float = 30.0,
) -> dict[str, Any]:
    """POST /projects. Returns the new row. Raises on non-201."""
    body = json.dumps({
        "slug": slug, "name": name, "description": description, "kind": kind,
    }).encode("utf-8")
    url = registry_url.rstrip("/") + "/projects"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 201:
                raise RuntimeError(f"Registry POST /projects returned HTTP {resp.status}")
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Registry POST /projects returned HTTP {e.code}: {err_body}")


def _write_env_file(project_dir: Path, slug: str, loom_env: dict[str, str]) -> None:
    """Create .env with OTel propagation + LOOM_PROJECT_ID. Does NOT overwrite."""
    env_path = project_dir / ".env"
    if env_path.exists():
        print(f"  WARN: {env_path} already exists; not overwriting.")
        print(f"        Add LOOM_PROJECT_ID={slug} manually if missing.")
        return

    lines = [
        "# .env for this consuming project of the-loom.",
        "# Generated by `loom init` — review before using.",
        "# Gitignore me. (See .gitignore — loom warns if not present.)",
        "",
        f"LOOM_PROJECT_ID={slug}",
        "",
        "# OTel credentials propagated from the-loom/.env so this project's",
        "# hook events flow to the same Grafana Cloud stack, tagged with the",
        "# project_id above.",
    ]
    for key in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_PROTOCOL",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_RESOURCE_ATTRIBUTES",
        "OTEL_SERVICE_NAME",
    ):
        value = loom_env.get(key)
        if value:
            lines.append(f"{key}={value}")
    lines.append("")
    env_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {env_path}")


# Constants for the loom-memory MCP server entry — this is the concrete rule
# every consuming project must satisfy. See skills_private/concrete-rule/SKILL.md
# and docs/CORE_DIRECTIVES.md. Format: Claude Code's .mcp.json schema.
#
# Env-override precedence for Tapestry migration (PR-prep-2b 2026-06-19):
#   1. TAPESTRY_MEMORY_MCP_URL: Tapestry-aware full URL; highest precedence
#   2. LOOM_MEMORY_MCP_URL: pre-Tapestry full URL
#   3. TAPESTRY_MEMORY_URL: Tapestry-aware bare base; /mcp/memory/ composed
#   4. LOOM_MEMORY_URL: pre-Tapestry bare base; /mcp/memory/ composed
#   5. Placeholder — set one of the above to YOUR memory MCP endpoint.
#      No personal deployment is baked in.
LOOM_MEMORY_MCP_URL = os.environ.get(
    "TAPESTRY_MEMORY_MCP_URL",
    os.environ.get(
        "LOOM_MEMORY_MCP_URL",
        f"{os.environ.get('TAPESTRY_MEMORY_URL', os.environ.get('LOOM_MEMORY_URL', 'https://your-memory-host.example.com')).rstrip('/')}/mcp/memory/",
    ),
)
LOOM_MEMORY_SERVER_NAME = "loom-memory"


def _write_mcp_config(project_dir: Path) -> None:
    """Ensure `.mcp.json` exists in project_dir with loom-memory wired in.

    This is **Layer 5** of the concrete-rule defense-in-depth pattern (see
    skills_private/concrete-rule/SKILL.md). Every consuming project MUST
    have loom-memory in its `.mcp.json` so Claude Code sessions can call
    memory_recall / memory_write / memory_read tools regardless of which
    plugins are enabled.

    Idempotent: if `.mcp.json` exists, merges the loom-memory entry into
    its mcpServers block (preserves all existing servers). If it doesn't
    exist, creates a minimal one with just loom-memory.

    The plugin's plugin.json (integrations/claude-code/tapestry-discipline/
    .claude-plugin/plugin.json v0.1.8+) ALSO registers loom-memory at the
    user level — Layer 3 of the concrete rule. Both layers exist so that
    if the plugin is disabled or fails, the project-level config still
    provides memory access.
    """
    mcp_path = project_dir / ".mcp.json"
    loom_memory_entry = {
        "type": "http",
        "url": LOOM_MEMORY_MCP_URL,
    }

    if mcp_path.exists():
        try:
            existing = json.loads(mcp_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  WARN: {mcp_path} exists but couldn't be parsed ({e}).")
            print(f"        Skipping merge. Add loom-memory manually:")
            print(f"          {{\"loom-memory\": {{\"type\": \"http\", \"url\": \"{LOOM_MEMORY_MCP_URL}\"}}}}")
            return

        servers = existing.setdefault("mcpServers", {})
        if LOOM_MEMORY_SERVER_NAME in servers:
            existing_url = servers[LOOM_MEMORY_SERVER_NAME].get("url", "")
            if existing_url == LOOM_MEMORY_MCP_URL:
                print(f"  loom-memory already wired in {mcp_path}")
                return
            print(f"  WARN: {mcp_path} has loom-memory pointing at a different URL:")
            print(f"        existing: {existing_url}")
            print(f"        expected: {LOOM_MEMORY_MCP_URL}")
            print(f"        Leaving as-is. Review and reconcile if needed.")
            return
        servers[LOOM_MEMORY_SERVER_NAME] = loom_memory_entry
        mcp_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        print(f"  merged loom-memory into {mcp_path}")
        return

    # Create fresh
    config = {
        "mcpServers": {
            LOOM_MEMORY_SERVER_NAME: loom_memory_entry,
        }
    }
    mcp_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {mcp_path}")


def _write_project_intelligence(
    project_dir: Path,
    slug: str,
    project_uuid: str,
    project_name: str,
) -> None:
    """Create .project-intelligence/ per the platform-data-model. Idempotent."""
    pi = project_dir / ".project-intelligence"
    pi.mkdir(exist_ok=True)

    agent_profile_path = pi / "agent-profile.json"
    if not agent_profile_path.exists():
        agent_profile_path.write_text(json.dumps({
            "configured_agents": [
                {
                    "kind": "claude-code",
                    "version": "unknown",
                    "capabilities": ["hooks", "mcp", "skills", "plugins"],
                }
            ],
            "generated_by": "tapestry_cli.init",
        }, indent=2), encoding="utf-8")
        print(f"  wrote {agent_profile_path}")

    project_context_path = pi / "project-context.json"
    if not project_context_path.exists():
        project_context_path.write_text(json.dumps({
            "project_id": project_uuid,
            "slug": slug,
            "name": project_name,
            "hostname": socket.gethostname(),
            "registered_via": "tapestry_cli.init",
        }, indent=2), encoding="utf-8")
        print(f"  wrote {project_context_path}")

    observatory_config_path = pi / "observatory-config.json"
    if not observatory_config_path.exists():
        observatory_config_path.write_text(json.dumps({
            "telemetry_destinations": [
                {
                    "kind": "grafana-cloud-otlp",
                    "configured_via": "OTEL_EXPORTER_OTLP_* env vars in .env",
                }
            ],
            "sampling_rules": "default-all",
        }, indent=2), encoding="utf-8")
        print(f"  wrote {observatory_config_path}")

    for sub in ("local-skills", "workflow-candidates", "lessons-learned", "promotion-candidates"):
        d = pi / sub
        d.mkdir(exist_ok=True)
        readme = d / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# {sub}\n\nLocal {sub.replace('-', ' ')} for this project. "
                f"Populated by the agency optimizer during use. See "
                f"docs/proposals/2026-05-25-platform-data-model.md in the-loom "
                f"for the directory contract.\n",
                encoding="utf-8",
            )

    print(f"  initialized {pi}/")


def add_arguments(p: argparse.ArgumentParser) -> None:
    """Attach the init subcommand's args to a parser. Used by cli.py dispatch."""
    p.add_argument("--slug", required=True,
                   help="Project slug (kebab-case, lowercase). Used as LOOM_PROJECT_ID.")
    p.add_argument("--name", default=None,
                   help="Human-readable project name. Defaults to slug.")
    p.add_argument("--description", default="",
                   help="One-sentence project description.")
    p.add_argument("--kind", default="dev", choices=["dev", "archived", "paused"],
                   help="Project lifecycle state (default: dev).")
    p.add_argument("--loom-repo", default=None,
                   help="Path to the-loom repo (defaults to LOOM_REPO env var, "
                        "then $HOME/the-loom or %%USERPROFILE%%/the-loom).")
    p.add_argument("--registry-url", default=DEFAULT_REGISTRY_URL,
                   help=f"Project Registry base URL (default: {DEFAULT_REGISTRY_URL}).")
    p.add_argument("--token", default=None,
                   help="Optional Bearer token (hosted-multitenant mode).")
    p.add_argument("--force", action="store_true",
                   help="Skip the 'looks like a project' pre-check.")


def run(args: argparse.Namespace) -> int:
    """Execute the init flow. Returns POSIX exit code."""
    project_dir = Path.cwd()
    name = args.name or args.slug

    # Locate the-loom repo
    loom_repo_str = args.loom_repo or os.environ.get("LOOM_REPO") or str(Path.home() / "the-loom")
    loom_repo = Path(loom_repo_str).expanduser().resolve()
    if not (loom_repo / "render.yaml").is_file():
        print(f"error: --loom-repo path doesn't look like the-loom (no render.yaml at {loom_repo}).", file=sys.stderr)
        print(f"       Pass --loom-repo /path/to/the-loom explicitly, or set LOOM_REPO env var.", file=sys.stderr)
        return 1

    print(f"==> loom init")
    print(f"    project dir:  {project_dir}")
    print(f"    slug:         {args.slug}")
    print(f"    name:         {name}")
    print(f"    description:  {args.description or '(none)'}")
    print(f"    kind:         {args.kind}")
    print(f"    loom repo:    {loom_repo}")
    print(f"    registry:     {args.registry_url}")
    print(f"    auth:         {'Bearer token (hosted)' if args.token else 'self-host fallback (no token)'}")
    print()

    if not args.force:
        has_git = (project_dir / ".git").exists()
        has_files = any(project_dir.iterdir())
        if not has_git and not has_files:
            print(f"error: {project_dir} doesn't look like a project (no .git, no files).", file=sys.stderr)
            print(f"       Pass --force to override.", file=sys.stderr)
            return 1

    print(f"--> [1/4] Check Project Registry for existing slug '{args.slug}'...")
    _warm_registry(args.registry_url)

    try:
        existing = _check_registry(args.registry_url, args.slug, args.token)
    except RuntimeError as e:
        print(f"error: registry check failed: {e}", file=sys.stderr)
        return 1
    if existing:
        print(f"  IDEMPOTENT: project '{args.slug}' already registered.")
        print(f"  UUID: {existing.get('id')}")
        print(f"  created_at: {existing.get('created_at')}")
        print(f"  Skipping Registry POST; proceeding with local file setup.")
        project_uuid = existing.get("id")
    else:
        print(f"--> [2/4] Register '{args.slug}' with the Project Registry...")
        try:
            row = _register_project(
                args.registry_url, args.slug, name, args.description, args.kind, args.token,
            )
        except RuntimeError as e:
            print(f"error: registry registration failed: {e}", file=sys.stderr)
            return 1
        project_uuid = row.get("id")
        print(f"  registered. UUID: {project_uuid}")

    loom_env = _read_loom_env(loom_repo)
    if not loom_env.get("OTEL_EXPORTER_OTLP_HEADERS"):
        print(f"  WARN: {loom_repo}/.env didn't have OTEL_EXPORTER_OTLP_HEADERS;")
        print(f"        the generated .env won't have telemetry credentials. Fix manually.")

    print(f"--> [3/5] Create .env in {project_dir}...")
    _write_env_file(project_dir, args.slug, loom_env)

    if not _gitignore_has_env(project_dir):
        print(f"  WARN: .gitignore does NOT contain '.env'. Add it to prevent")
        print(f"        committing OTel credentials.")

    print(f"--> [4/5] Wire loom-memory MCP server (concrete-rule Layer 5)...")
    _write_mcp_config(project_dir)

    print(f"--> [5/5] Initialize .project-intelligence/...")
    _write_project_intelligence(project_dir, args.slug, project_uuid or "unknown", name)

    print()
    print(f"==> Done.")
    print(f"    Project '{args.slug}' is now registered with the-loom.")
    print(f"    UUID: {project_uuid}")
    print()
    print(f"Next steps:")
    print(f"  1. If you don't already have the tapestry-discipline plugin installed,")
    print(f"     see docs/howto/onboard-a-project.md Part 2.")
    print(f"  2. Start a Claude Code session in this directory. The SessionStart")
    print(f"     hook (v0.1.7+) will auto-recall relevant memories for this project.")
    print(f"  3. Hook events from this project will flow to Grafana tagged with")
    print(f"     project_id={args.slug}.")
    print(f"  4. If .env doesn't exist or is missing OTel creds, copy from")
    print(f"     {loom_repo}/.env manually.")
    return 0
