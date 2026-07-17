#!/usr/bin/env python3
"""backfill_projects.py — register the projects that exist in memory tags
but not in the Project Registry, and normalize tag drift.

Two phases, both idempotent:

  Phase 1 — Register missing projects via POST /projects (REST). 409s
  (already registered) are treated as success. Per Pattern B (umbrella +
  sub-tags) for IME4020: register only the umbrella `ime4020-hub`; the
  -dev and -app sub-tags stay as memory-write conventions, not Registry
  rows.

  Phase 2 — Normalize tag drift in the records table:
    - `make_skills` (underscore) -> `make-skills` (hyphen)  [12 memories]
    - `sde-extraction-dev`        -> `sde-extraction`        [3 memories]
    - `ime4020-hub` (umbrella) preserved; `ime4020-hub-dev` and
      `ime4020-hub-app` preserved as sub-tags
    Phase 2 hits Postgres directly via psycopg + RLS-scoped UPDATEs.

Usage:

    # Dry-run: show what would happen, change nothing
    python scripts/backfill_projects.py --dry-run

    # Run for real (prompts y/n before destructive Phase 2)
    python scripts/backfill_projects.py

Reads LOOM_DB_URL + LOOM_DB_URL_EXTERNAL from env / .env. Uses external
when running locally, internal when running inside a Render service.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional


REGISTRY_URL = "https://loom-project-registry.onrender.com"
SELF_HOST_TENANT_ID = "1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8"
REPO_ROOT = Path(__file__).resolve().parent.parent


# Projects to register. Pattern B = one umbrella row per repo; sub-tags
# (-dev / -app for IME4020) are memory-tagging conventions, not separate
# Registry rows. See docs/architecture/project-scoping-pattern-b.md.
PROJECTS_TO_REGISTER = [
    {
        "slug": "the-loom",
        "name": "the-loom",
        "description": "Personal AI substrate: project intelligence + observability + memory platform.",
        "kind": "dev",
    },
    {
        "slug": "make-skills",
        "name": "Make_Skills",
        "description": "Agent platform engine: runtime, skill compiler, memory MCP, tenant scoping. Splitting into engine + humancensys.com (consumer).",
        "kind": "dev",
    },
    {
        "slug": "sde-extraction",
        "name": "SDE Extraction",
        "description": "Document / structured-data extraction project.",
        "kind": "dev",
    },
    {
        "slug": "claude-skills-marketplace",
        "name": "Claude Skills Marketplace",
        "description": "Public Claude Code plugin marketplace.",
        "kind": "dev",
    },
    {
        "slug": "ime4020-hub",
        "name": "IME 4020W Hub",
        "description": "In-class course hub for IME 4020W. Single repo hosts two instances via Pattern B sub-tags: ime4020-hub-dev (developer-facing) and ime4020-hub-app (student-facing embedded agent).",
        "kind": "dev",
    },
    {
        "slug": "classroom-hub-starter",
        "name": "Classroom Hub Starter",
        "description": "Template repo for course hubs. Derives course-specific hubs (e.g. ime4020-hub).",
        "kind": "dev",
    },
]

# Phase 2 tag normalizations: (old_tag, new_tag, expected_affected_memories)
TAG_NORMALIZATIONS = [
    ("make_skills", "make-skills", 12),
    ("sde-extraction-dev", "sde-extraction", 3),
]


def _load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


def _warm(url: str, max_wait: float = 90.0) -> None:
    """Render free-tier cold-start warmup."""
    deadline = time.time() + max_wait
    attempt = 0
    health = url.rstrip("/") + "/health"
    while time.time() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url=health, method="GET"), timeout=15
            ) as resp:
                if resp.status == 200:
                    if attempt > 1:
                        print(f"  Registry warm (attempt {attempt}).")
                    return
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, ConnectionError, OSError):
            pass
        if attempt == 1:
            print(f"  Cold-starting Registry; waiting up to {int(max_wait)}s...")
        time.sleep(5)


def _register_one(project: dict, dry_run: bool) -> tuple[str, Optional[str]]:
    """POST /projects. Returns (status, uuid_or_none).
    Status: 'created' | 'exists' | 'error'."""
    if dry_run:
        return ("would-create", None)
    body = json.dumps(project).encode("utf-8")
    req = urllib.request.Request(
        url=REGISTRY_URL.rstrip("/") + "/projects",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            row = json.loads(resp.read().decode("utf-8"))
            return ("created", row.get("id"))
    except urllib.error.HTTPError as e:
        body_str = e.read().decode("utf-8", errors="replace")[:300]
        if e.code == 409:
            return ("exists", None)
        return ("error", f"HTTP {e.code}: {body_str}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return ("error", str(e))


def phase1_register(dry_run: bool) -> int:
    """Phase 1 — register the 6 missing projects."""
    print("=" * 70)
    print("Phase 1 — Project Registry backfill")
    print("=" * 70)
    print()
    print(f"Pattern B: umbrella row per repo. {len(PROJECTS_TO_REGISTER)} to register.")
    print()

    if not dry_run:
        print("Warming Project Registry (Render free tier)...")
        _warm(REGISTRY_URL)

    created = 0
    exists = 0
    errored = 0
    for p in PROJECTS_TO_REGISTER:
        status, detail = _register_one(p, dry_run)
        marker = {
            "created": "  [OK]    created      ",
            "exists":  "  [SKIP]  exists       ",
            "would-create": "  [DRY]   would create ",
            "error":   "  [ERR]   ERROR        ",
        }.get(status, f"  ?       {status}")
        print(f"{marker} {p['slug']:<30} {detail or ''}")
        if status == "created":
            created += 1
        elif status == "exists":
            exists += 1
        elif status == "error":
            errored += 1

    print()
    if dry_run:
        print(f"  (dry-run) Would attempt {len(PROJECTS_TO_REGISTER)} POSTs.")
    else:
        print(f"  created: {created}, already-existed: {exists}, errored: {errored}")
    return errored


def phase2_normalize(dry_run: bool) -> int:
    """Phase 2 — normalize drifted tags in records.project_tags via UPDATE."""
    print()
    print("=" * 70)
    print("Phase 2 — Tag normalization")
    print("=" * 70)
    print()

    try:
        import psycopg
    except ImportError:
        print("psycopg not installed. Skipping Phase 2.", file=sys.stderr)
        return 1

    dsn = os.environ.get("LOOM_DB_URL") or os.environ.get("LOOM_DB_URL_EXTERNAL")
    if not dsn:
        print("LOOM_DB_URL / LOOM_DB_URL_EXTERNAL unset; skipping Phase 2.", file=sys.stderr)
        return 1
    # Render external URL needs sslmode
    if "render.com" in dsn and "sslmode" not in dsn:
        dsn = dsn + ("&" if "?" in dsn else "?") + "sslmode=require"

    print(f"Connecting to Postgres...")
    print(f"Normalizations:")
    for old, new, expected in TAG_NORMALIZATIONS:
        print(f"  '{old}' -> '{new}'  (expected ~{expected} memories)")
    print()

    if not dry_run:
        print("This UPDATEs records.project_tags directly. Type 'yes' to continue: ", end="", flush=True)
        confirm = sys.stdin.readline().strip().lower()
        if confirm != "yes":
            print("Aborted.")
            return 1

    affected_total = 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (SELF_HOST_TENANT_ID,))
            for old, new, expected in TAG_NORMALIZATIONS:
                # array_replace handles the per-row update; only touches rows
                # that actually contain the old tag.
                if dry_run:
                    cur.execute(
                        "SELECT count(*) FROM records WHERE %s = ANY(project_tags)",
                        (old,),
                    )
                    count = cur.fetchone()[0]
                    print(f"  (dry-run) would update {count} memories: '{old}' -> '{new}'")
                    affected_total += count
                else:
                    cur.execute(
                        "UPDATE records SET project_tags = array_replace(project_tags, %s, %s) "
                        "WHERE %s = ANY(project_tags)",
                        (old, new, old),
                    )
                    affected = cur.rowcount
                    print(f"  [OK]    updated {affected} memories: '{old}' -> '{new}'")
                    affected_total += affected
        if not dry_run:
            conn.commit()

    print()
    if dry_run:
        print(f"  (dry-run) Total memories that would change: {affected_total}")
    else:
        print(f"  Total memories updated: {affected_total}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="Show what would happen, change nothing.")
    p.add_argument("--phase", choices=["1", "2", "both"], default="both",
                   help="Run only Phase 1 (registry) or Phase 2 (tag normalization). Default: both.")
    args = p.parse_args()

    _load_dotenv(REPO_ROOT / ".env")

    err = 0
    if args.phase in ("1", "both"):
        err += phase1_register(args.dry_run)
    if args.phase in ("2", "both"):
        err += phase2_normalize(args.dry_run)

    print()
    if args.dry_run:
        print("Dry-run complete. Re-run without --dry-run to apply.")
    elif err:
        print(f"Completed with {err} error(s) — review output above.")
    else:
        print("Backfill complete.")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
