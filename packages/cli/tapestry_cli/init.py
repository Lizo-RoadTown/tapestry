"""tapestry init — onboard the current directory as a Tapestry consuming project.

The implementation behind `tapestry init` (the `loom` alias still dispatches
here). Stdlib-only so it runs equally from PowerShell / bash / zsh on
Windows / macOS / Linux without extra installs. No dependency on any other
repo (the old the-loom coupling was removed).

What it does:

  1. Pre-check: confirm you're in a directory that looks like a project
     (has .git, or has files, or you pass --force).
  2. Register the project with the Project Registry (GET by-slug is
     idempotent; POST /projects otherwise). Set --registry-url or
     TAPESTRY_REGISTRY_URL. Self-host: no Bearer token; the server falls
     back to SELF_HOST_TENANT_ID.
  3. Create .env with LOOM_PROJECT_ID=<slug> (the master scope gate for the
     tapestry-discipline hooks) + OTel vars sourced from the environment.
  4. Wire the loom-memory MCP server into .mcp.json (with the auth header).
  5. Initialize .project-intelligence/ (project-context.json carries the
     registry UUID the observer needs).
  6. Seed the project skeleton: CLAUDE.md (inlines CORE DIRECTIVE 1),
     .gitignore, docs/ (architecture-snapshots/, architecture/, adr/), and
     skills/. All writes are idempotent — nothing existing is overwritten.

What it does NOT do:
  - Does NOT create a GitHub repo (use `gh repo create`).
  - Does NOT install the Claude Code plugins (see the printed next-steps).
  - Does NOT seed architecture-snapshot scripts — the tapestry-discipline
    hook runs the canonical tapestry-patterns scripts directly.

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


# OpenTelemetry vars propagated into a new project's .env. Sourced from the
# current process environment (never from a the-loom checkout — that dependency
# was removed). Only ENDPOINT + HEADERS actually gate telemetry export; the rest
# are metadata.
_OTEL_KEYS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_PROTOCOL",
    "OTEL_EXPORTER_OTLP_HEADERS",
    "OTEL_RESOURCE_ATTRIBUTES",
    "OTEL_SERVICE_NAME",
)


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


def _git_remote_url(project_dir: Path) -> Optional[str]:
    """Return project_dir's `origin` remote URL, or None if it's not a git repo or
    has no origin. Best-effort; never raises."""
    import subprocess
    try:
        r = subprocess.run(
            ["git", "-C", str(project_dir), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
        url = (r.stdout or "").strip()
        return url if r.returncode == 0 and url else None
    except Exception:  # noqa: BLE001
        return None


def _register_repo(
    registry_url: str,
    project_id: str,
    url: str,
    token: Optional[str],
    default_branch: str = "main",
    timeout: float = 30.0,
) -> bool:
    """POST /projects/{id}/repos so the self-observer can discover and scan this
    repo. Returns True if registered now or already present (409). Never raises —
    the project is already registered, so a repo-registration failure must not
    abort init."""
    # The deployed registry's RepoCreate requires project_id IN THE BODY (as well
    # as the path); send both so this works against the currently-deployed service.
    body = json.dumps(
        {"project_id": project_id, "url": url, "default_branch": default_branch}
    ).encode("utf-8")
    endpoint = registry_url.rstrip("/") + f"/projects/{project_id}/repos"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url=endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        return e.code == 409  # already registered under this project — fine
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return False


def _write_env_file(project_dir: Path, slug: str) -> None:
    """Create .env with LOOM_PROJECT_ID + OTel propagation. Does NOT overwrite.

    LOOM_PROJECT_ID is the master scope gate — the tapestry-discipline hooks
    only fire for a project when it is set. OTel values are sourced from the
    current process environment when present; otherwise commented placeholders
    are written so the operator can fill them in. No dependency on a the-loom
    checkout (removed).
    """
    env_path = project_dir / ".env"
    if env_path.exists():
        print(f"  WARN: {env_path} already exists; not overwriting.")
        print(f"        Add LOOM_PROJECT_ID={slug} manually if missing.")
        return

    lines = [
        "# .env for this Tapestry consuming project.",
        "# Generated by `tapestry init` — review before using. Gitignore me.",
        "",
        f"LOOM_PROJECT_ID={slug}",
        "",
        "# OpenTelemetry export — sourced from your environment at init time so",
        "# this project's hook events flow to the same stack, tagged with the",
        "# project_id above. Unset vars are written as commented placeholders.",
    ]
    found_any = False
    for key in _OTEL_KEYS:
        value = os.environ.get(key)
        if value:
            lines.append(f"{key}={value}")
            found_any = True
        else:
            lines.append(f"# {key}=")
    lines.append("")
    env_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {env_path}")
    if not found_any:
        print("  NOTE: no OTEL_* vars found in the environment; wrote commented")
        print("        placeholders. Set them in .env (or export them) to enable")
        print("        telemetry.")


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
    # Mode-agnostic auth header: references the shared-secret env var by name.
    # When TAPESTRY_MEMORY_API_KEY is unset the client sends "Bearer " (empty),
    # which the memory server treats as anonymous — so this config is valid both
    # before the credential exists and after, and needs no change at flip time.
    loom_memory_entry = {
        "type": "http",
        "url": LOOM_MEMORY_MCP_URL,
        "headers": {"Authorization": "Bearer ${TAPESTRY_MEMORY_API_KEY}"},
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


_CLAUDE_MD_TEMPLATE = """# Working in {name}

Project context for Claude Code. Loaded into every conversation. Keep it tight.

<!-- Seeded by `tapestry init`. Edit freely — a starting skeleton, not a contract. -->

## What this project is

{description}

<!-- One or two plain sentences: what this repo is for and what "done" looks
     like. Describe what *is*, not what it *isn't*. -->

## Tapestry integration (seeded via `tapestry init`)

- **Project slug / `LOOM_PROJECT_ID`:** `{slug}` (in gitignored `.env`) — this is
  the scope gate that turns the tapestry-discipline hooks on for this repo, and
  it tags memory + telemetry to this project.
- **loom-memory MCP** is wired in `.mcp.json`.
- The `tapestry-discipline` + `tapestry-patterns` plugins apply here when enabled.

### CORE DIRECTIVE 1 — loom-memory access is mandatory

Every session MUST have the `loom-memory` MCP server reachable (`memory_read`,
`memory_write`, `memory_recall`, `memory_search`, `memory_list`, `memory_delete`).
If it is unavailable, or SessionStart reports a concrete-rule violation, **halt
substantive work and report to the operator** — do not proceed silently on
in-session context alone.

## How to work here

- **PROBE before asserting.** Read the actual file/source before claiming how
  something works; cite `file:line`.
- **Recall memory** at the start of substantive work; **write memory** when the
  operator teaches you something durable or corrects course.
- **Your own skills live in `skills/`** — see `skills/README.md`. Capture a
  repeated workflow there instead of re-deriving it.
- **Decisions worth preserving** go in `docs/adr/`; architecture notes in
  `docs/architecture/`.

## Tone — no marketing voice

Describe what *is*, not what it *isn't*. Plain, direct, descriptive. Applies to
docs, commit messages, PR bodies, and error messages.
"""

_GITIGNORE_LINES = [
    "# Secrets / env — never commit. init writes .env with telemetry credentials.",
    ".env",
    ".env.local",
    "*.env",
    "!.env.example",
    "",
    "# Python",
    "__pycache__/",
    "*.py[cod]",
    ".pytest_cache/",
    ".venv/",
    "",
    "# OS / editor junk",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*~",
    "*.swp",
    "",
    "# Node (if this project grows a JS toolchain)",
    "node_modules/",
    "",
    "# Per-machine Claude Code state",
    ".claude/logs/",
    ".claude/settings.local.json",
    "",
    "# MCP config — references a secret env var by name; per-machine, not committed",
    ".mcp.json",
    "",
    "# Architecture snapshots — auto-written by the tapestry-discipline SessionStart",
    "# hook every session. Local feedback, not repo history. .gitkeep preserves the dir.",
    "docs/architecture-snapshots/*",
    "!docs/architecture-snapshots/.gitkeep",
]

_DOCS_ARCHITECTURE_README = """# Architecture

Human-authored notes on how this project is put together — the shape of the
system, the main components, and how they fit. Start with a single overview file
and add focused notes as the design settles. Describe what *is*; keep it current.

Machine-generated architecture *snapshots* live in `../architecture-snapshots/`
(written by the tapestry-discipline hook each session) — those are feedback, not
authored docs. This directory is for the durable, human-authored picture.
"""

_DOCS_ADR_README = """# Decision records (ADRs)

One file per decision: `NNNN-short-slug.md`, sequential numbering.

## When to record a decision

- A choice that affects multiple parts of the project
- A choice that reverses an earlier one
- A naming or boundary decision worth preserving for a future agent reading this repo

## Template

    # NNNN — <short-slug>

    **Date:** YYYY-MM-DD
    **Status:** Proposed / Accepted / Superseded by NNNN
    **Decision by:** <who approved + when>

    ## Context
    Why this decision is being made; the current situation and the pressure.

    ## Decision
    The decision itself, plainly stated.

    ## Consequences
    What this makes easier, what it makes harder, what it locks in or rules out.

    ## Related
    Linked memory writes (loom-memory keys), PRs, prior decisions.
"""

_SKILLS_README = """# skills/

Your own skills, scoped to this project. A skill is a short, reusable procedure
you (or Claude) can invoke by name instead of re-deriving it each time.

## Layout

    skills/
      <skill-name>/
        SKILL.md     # frontmatter (name, description) + the procedure

One directory per skill. Keep each SKILL.md tight and action-oriented.

## Where skills live — three homes, don't confuse them

- **`skills/` (here)** — skills specific to *this* project, authored by hand.
- **`.project-intelligence/local-skills/`** — skill *candidates* the agency
  optimizer emits automatically during use. Raw material, not curated.
- **`tapestry-patterns` plugin** — canonical patterns reused across *all*
  projects, one name / one home. If a skill here proves useful everywhere,
  promote it to the plugin rather than copying it into other repos.

## The skills-audit / upskilling loop

1. **Notice friction** — a workflow you repeat, or a correction made twice.
2. **Capture it** as a skill here, or as a candidate in `.project-intelligence/`.
3. **Audit at session end** — the upskilling report surfaces promotion candidates.
4. **Promote** the winners to the `tapestry-patterns` plugin; retire the ones
   that stopped earning use.

This is how a project gets sharper over time instead of re-deriving the same
procedures every session.
"""


def _write_if_absent(path: Path, content: str) -> None:
    """Write content to path only if it doesn't already exist (idempotent)."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path}")


def _write_project_skeleton(
    project_dir: Path, slug: str, name: str, description: str
) -> None:
    """Seed the full project skeleton: CLAUDE.md, .gitignore, docs/ tree, skills/.

    Every write is idempotent (never clobbers an existing file). None of these
    contain secrets. See docs/plans/2026-08-20-seed-and-hook-fix-plan.md.
    """
    # CLAUDE.md — inlines CORE DIRECTIVE 1 (a fresh repo has no CORE_DIRECTIVES.md).
    _write_if_absent(
        project_dir / "CLAUDE.md",
        _CLAUDE_MD_TEMPLATE.format(
            slug=slug, name=name, description=description or "_(describe this project)_"
        ),
    )

    # .gitignore — create if absent, else append any missing lines (no dupes).
    gi_path = project_dir / ".gitignore"
    if not gi_path.exists():
        gi_path.write_text("\n".join(_GITIGNORE_LINES) + "\n", encoding="utf-8")
        print(f"  wrote {gi_path}")
    else:
        existing = gi_path.read_text(encoding="utf-8")
        existing_set = {ln.strip() for ln in existing.splitlines()}
        to_add = [
            ln for ln in _GITIGNORE_LINES
            if ln and not ln.startswith("#") and ln not in existing_set
        ]
        if to_add:
            sep = "" if existing.endswith("\n") else "\n"
            gi_path.write_text(
                existing + sep + "\n# Added by `tapestry init`\n"
                + "\n".join(to_add) + "\n",
                encoding="utf-8",
            )
            print(f"  appended {len(to_add)} lines to {gi_path}")

    # docs/ tree.
    _write_if_absent(
        project_dir / "docs" / "architecture-snapshots" / ".gitkeep", ""
    )
    _write_if_absent(
        project_dir / "docs" / "architecture" / "README.md", _DOCS_ARCHITECTURE_README
    )
    _write_if_absent(project_dir / "docs" / "adr" / "README.md", _DOCS_ADR_README)

    # skills/ home (new convention — a place for this project's own skills).
    _write_if_absent(project_dir / "skills" / "README.md", _SKILLS_README)


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

    print(f"==> tapestry init")
    print(f"    project dir:  {project_dir}")
    print(f"    slug:         {args.slug}")
    print(f"    name:         {name}")
    print(f"    description:  {args.description or '(none)'}")
    print(f"    kind:         {args.kind}")
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

    print(f"--> [1/6] Check Project Registry for existing slug '{args.slug}'...")
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
        print(f"--> [2/6] Register '{args.slug}' with the Project Registry...")
        try:
            row = _register_project(
                args.registry_url, args.slug, name, args.description, args.kind, args.token,
            )
        except RuntimeError as e:
            print(f"error: registry registration failed: {e}", file=sys.stderr)
            return 1
        project_uuid = row.get("id")
        print(f"  registered. UUID: {project_uuid}")

    # Guard: the observer requires a real 36-char UUID in project-context.json.
    # If registration didn't return one, refuse to seed an invalid project
    # rather than write "unknown" (which the observer silently rejects).
    if not project_uuid:
        print("error: the Project Registry did not return a project UUID; cannot",
              file=sys.stderr)
        print("       seed a valid .project-intelligence/project-context.json.",
              file=sys.stderr)
        print(f"       Check --registry-url ({args.registry_url}) and registry health,",
              file=sys.stderr)
        print("       then re-run. No local files were written.", file=sys.stderr)
        return 1

    # Register the project's git repo so the self-observer can discover and scan
    # it (GET /projects/{id}/repos is how the observer finds targets). Best-effort:
    # the project is already registered above, so a missing remote or a failed POST
    # must not abort local setup.
    print(f"--> Register the project's git repo (so the self-observer can scan it)...")
    repo_url = _git_remote_url(project_dir)
    if repo_url:
        if _register_repo(args.registry_url, project_uuid, repo_url, args.token):
            print(f"  repo registered: {repo_url}")
        else:
            print(f"  WARN: could not register repo {repo_url}; register it later via "
                  f"POST {args.registry_url.rstrip('/')}/projects/{project_uuid}/repos")
    else:
        print("  NOTE: no git 'origin' remote found — skipping repo registration. "
              "Add a remote and re-run (or register it later) so the self-observer "
              "can discover this repo.")

    print(f"--> [3/6] Create .env in {project_dir} (LOOM_PROJECT_ID + OTel from env)...")
    _write_env_file(project_dir, args.slug)

    print(f"--> [4/6] Wire loom-memory MCP server (concrete-rule Layer 5)...")
    _write_mcp_config(project_dir)

    print(f"--> [5/6] Initialize .project-intelligence/...")
    _write_project_intelligence(project_dir, args.slug, project_uuid, name)

    print(f"--> [6/6] Seed project skeleton (CLAUDE.md, .gitignore, docs/, skills/)...")
    _write_project_skeleton(project_dir, args.slug, name, args.description)

    print()
    print(f"==> Done.")
    print(f"    Project '{args.slug}' is registered and seeded.")
    print(f"    UUID: {project_uuid}")
    print()
    print(f"Next steps:")
    print(f"  1. If you don't already have the tapestry plugins installed:")
    print(f"       /plugin marketplace add Lizo-RoadTown/tapestry")
    print(f"       /plugin install tapestry-discipline@tapestry")
    print(f"       /plugin install tapestry-patterns@tapestry")
    print(f"  2. Start a Claude Code session here. The SessionStart hook auto-recalls")
    print(f"     relevant memories and writes architecture snapshots to")
    print(f"     docs/architecture-snapshots/.")
    print(f"  3. To enable telemetry, set the OTEL_* vars in .env (or export them);")
    print(f"     hook events then flow tagged with project_id={args.slug}.")
    return 0
