"""tapestry deploy — create a Render service for the current repo, from the terminal.

The tedium this removes: every new project means clicking through the Render
dashboard to create a service, connect the GitHub repo, set build/start/plan,
and re-attach the shared env group. This does all of that in one command via
Render's REST API (https://api.render.com/v1), reading a small committed spec.

Stdlib-only (urllib), matching the rest of tapestry-cli — no third-party deps.

What it does:
  1. Load the deploy spec (deploy/render-service.json by default; flags override).
  2. Resolve the repo URL from `git origin` (unless --repo given).
  3. Resolve the Render ownerId (GET /v1/owners), unless --owner-id given.
  4. Idempotency: GET /v1/services?name=<name> — if it already exists, stop.
  5. POST /v1/services with the repo link + branch + autoDeploy + serviceDetails
     (build/start go under serviceDetails.envSpecificDetails) + inline envVars.
  6. Attach an existing env group by name (POST /v1/env-groups/{id}/services/{id}).
  7. Print the new service URL.

Prerequisites (operator, one-time):
  - RENDER_API_KEY in the environment (or --api-key). Generate at:
    Render dashboard -> avatar -> Account Settings -> API Keys.
  - The GitHub<->Render account connection (Render's GitHub App) must already be
    authorized for the repo. That step is dashboard-only; there is no API for it.

Use --dry-run to print the exact request without sending it (needs no API key).

Verified against Render's API reference 2026-09-25:
  - POST /v1/services: top-level type/name/ownerId (required) + repo/branch/
    autoDeploy/rootDir/envVars/serviceDetails. Native build/start live under
    serviceDetails.envSpecificDetails.{buildCommand,startCommand}.
  - GET /v1/services?name=<>&limit=<> and GET /v1/owners?name=<> return arrays of
    {service|owner, cursor} wrapper objects.
  - POST /v1/env-groups/{envGroupId}/services/{serviceId} — no body.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional


DEFAULT_API_URL = os.environ.get("RENDER_API_URL", "https://api.render.com/v1")
DEFAULT_SPEC_PATH = "deploy/render-service.json"

# Friendly aliases -> Render's serviceType enum.
# Only types the payload builder can produce a valid body for are advertised.
# web_service / background_worker / private_service / cron_job all take
# runtime + plan + build/start (healthCheckPath is web-only, gated below).
# static_site is intentionally omitted: it has no start command / runtime /
# plan and needs a publishPath the builder does not produce.
_TYPE_ALIASES = {
    "web": "web_service",
    "cron": "cron_job",
    "worker": "background_worker",
    "private": "private_service",
}
_VALID_TYPES = set(_TYPE_ALIASES.values())


# --------------------------------------------------------------------------
# HTTP (stdlib urllib; same shape as init.py's registry calls)
# --------------------------------------------------------------------------
def _request(
    method: str,
    url: str,
    api_key: str,
    body: Optional[dict] = None,
    timeout: float = 60.0,
) -> Any:
    """Call the Render API. Returns parsed JSON (or None on 204). Raises
    RuntimeError with the response body on any 4xx/5xx."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{method} {url} -> HTTP {e.code}: {detail}") from None


def _git_origin_url(project_dir: Path) -> Optional[str]:
    """Best-effort `origin` remote URL; None if not a git repo / no origin."""
    try:
        r = subprocess.run(
            ["git", "-C", str(project_dir), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
        url = (r.stdout or "").strip()
        return url if r.returncode == 0 and url else None
    except Exception:  # noqa: BLE001
        return None


def _resolve_owner_id(api_key: str, owner_name: Optional[str]) -> str:
    """GET /v1/owners (optionally filtered by name). Returns the single owner's
    id, or raises if zero / ambiguous so the operator picks with --owner-id."""
    url = DEFAULT_API_URL.rstrip("/") + "/owners?limit=100"
    if owner_name:
        url += "&name=" + urllib.parse.quote(owner_name)
    rows = _request("GET", url, api_key) or []
    owners = [row["owner"] for row in rows if "owner" in row]
    if not owners:
        raise RuntimeError(
            "no Render owners returned for this API key"
            + (f" matching name={owner_name!r}" if owner_name else "")
        )
    if len(owners) > 1:
        listing = ", ".join(f"{o['name']} ({o['id']})" for o in owners)
        raise RuntimeError(
            f"multiple Render owners; pass --owner-id to choose one of: {listing}"
        )
    return owners[0]["id"]


def _find_service_by_name(api_key: str, name: str) -> Optional[dict]:
    """GET /v1/services?name=<name> — return the exact-name match, else None."""
    url = (
        DEFAULT_API_URL.rstrip("/")
        + "/services?limit=100&name="
        + urllib.parse.quote(name)
    )
    rows = _request("GET", url, api_key) or []
    for row in rows:
        svc = row.get("service", {})
        if svc.get("name") == name:
            return svc
    return None


def _find_env_group_id(api_key: str, name: str) -> Optional[str]:
    """GET /v1/env-groups?name=<name> — return the exact-name match id, else None.
    Best-effort: returns None (with a caller warning) if the lookup fails."""
    url = (
        DEFAULT_API_URL.rstrip("/")
        + "/env-groups?limit=100&name="
        + urllib.parse.quote(name)
    )
    try:
        rows = _request("GET", url, api_key) or []
    except RuntimeError:
        return None
    for row in rows:
        grp = row.get("envGroup", row)
        if grp.get("name") == name:
            return grp.get("id")
    return None


# --------------------------------------------------------------------------
# Spec + payload
# --------------------------------------------------------------------------
def _load_spec(project_dir: Path, args: argparse.Namespace) -> dict:
    """Merge the on-disk spec (if any) with flag overrides. Flags win."""
    spec: dict[str, Any] = {}
    spec_path = project_dir / args.spec
    if spec_path.is_file():
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            raise RuntimeError(f"could not read spec {spec_path}: {e}")

    # Flag overrides (only when provided).
    for key, val in (
        ("name", args.name),
        ("type", args.type),
        ("plan", args.plan),
        ("region", args.region),
        ("branch", args.branch),
        ("rootDir", args.root),
        ("runtime", args.runtime),
        ("buildCommand", args.build),
        ("startCommand", args.start),
        ("healthCheckPath", args.health_check_path),
        ("schedule", args.schedule),
        ("repo", args.repo),
        ("envGroup", args.env_group),
        ("autoDeploy", args.auto_deploy),
    ):
        if val is not None:
            spec[key] = val

    # Plain env vars from --set KEY=VALUE (merged over spec["envVars"]).
    env_vars = {ev["key"]: ev["value"] for ev in spec.get("envVars", [])}
    for pair in args.set or []:
        if "=" not in pair:
            raise RuntimeError(f"--set expects KEY=VALUE, got {pair!r}")
        k, v = pair.split("=", 1)
        env_vars[k] = v
    spec["_envVars"] = env_vars

    # Secret env var NAMES — values pulled from the local environment at run time.
    spec["_secretNames"] = list(dict.fromkeys(spec.get("secretEnv", []) + (args.secret or [])))
    return spec


def _resolve_env_vars(spec: dict) -> tuple[list[dict], list[str]]:
    """Build the envVars array: plain vars + resolved secrets. Returns
    (envVars, missing_secret_names)."""
    env_vars = [{"key": k, "value": v} for k, v in spec["_envVars"].items()]
    missing: list[str] = []
    for name in spec["_secretNames"]:
        val = os.environ.get(name)
        if val is None:
            missing.append(name)
        else:
            env_vars.append({"key": name, "value": val})
    return env_vars, missing


def _build_service_payload(spec: dict, repo_url: str, owner_id: str) -> dict:
    """Compose the POST /v1/services body from the spec. Native runtimes only
    (build/start under serviceDetails.envSpecificDetails)."""
    raw_type = str(spec.get("type", "web"))
    service_type = _TYPE_ALIASES.get(raw_type, raw_type)
    if service_type not in _VALID_TYPES:
        raise RuntimeError(
            f"invalid service type {raw_type!r}; use one of "
            f"{sorted(_TYPE_ALIASES)} or a Render serviceType."
        )

    runtime = spec.get("runtime", "python")
    build_cmd = spec.get("buildCommand")
    start_cmd = spec.get("startCommand")
    if not build_cmd or not start_cmd:
        raise RuntimeError("spec needs buildCommand and startCommand (native runtime)")

    details: dict[str, Any] = {
        "runtime": runtime,
        "plan": spec.get("plan", "starter"),
        "region": spec.get("region", "oregon"),
        "envSpecificDetails": {
            "buildCommand": build_cmd,
            "startCommand": start_cmd,
        },
    }
    if service_type == "cron_job":
        schedule = spec.get("schedule")
        if not schedule:
            raise RuntimeError("cron service needs a 'schedule' (cron expression)")
        details["schedule"] = schedule
    elif service_type == "web_service":
        # healthCheckPath is web-only; Render rejects it on worker/private.
        if spec.get("healthCheckPath"):
            details["healthCheckPath"] = spec["healthCheckPath"]

    env_vars, _missing = _resolve_env_vars(spec)

    payload: dict[str, Any] = {
        "type": service_type,
        "name": spec["name"],
        "ownerId": owner_id,
        "repo": repo_url,
        "branch": spec.get("branch", "main"),
        "autoDeploy": spec.get("autoDeploy", "yes"),
        "serviceDetails": details,
    }
    if spec.get("rootDir"):
        payload["rootDir"] = spec["rootDir"]
    if env_vars:
        payload["envVars"] = env_vars
    return payload


def _mask_secret_values(payload: dict, secret_names: set[str]) -> dict:
    """Return a deep copy of the payload with every envVar value whose key is a
    declared secret replaced by '***'. Non-secret env var values are kept. Used
    only for --dry-run output so resolved secret values never reach stdout."""
    masked = copy.deepcopy(payload)
    for ev in masked.get("envVars", []):
        if ev.get("key") in secret_names:
            ev["value"] = "***"
    return masked


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--spec", default=DEFAULT_SPEC_PATH,
                   help=f"Deploy spec JSON (default: {DEFAULT_SPEC_PATH}).")
    p.add_argument("--name", default=None, help="Render service name.")
    p.add_argument("--type", default=None,
                   help="Service type: web | cron | worker | private.")
    p.add_argument("--plan", default=None, help="Render plan (e.g. starter, free).")
    p.add_argument("--region", default=None, help="Region (default: oregon).")
    p.add_argument("--branch", default=None, help="Git branch (default: main).")
    p.add_argument("--root", default=None, help="rootDir within the repo.")
    p.add_argument("--runtime", default=None, help="Runtime (default: python).")
    p.add_argument("--build", default=None, help="Build command.")
    p.add_argument("--start", default=None, help="Start command.")
    p.add_argument("--health-check-path", default=None, help="Health check path (web).")
    p.add_argument("--schedule", default=None, help="Cron schedule (cron services).")
    p.add_argument("--repo", default=None, help="Repo URL (default: git origin).")
    p.add_argument("--owner-id", default=None, help="Render owner/workspace id.")
    p.add_argument("--owner-name", default=None, help="Resolve owner id by name.")
    p.add_argument("--env-group", default=None, help="Existing env group to attach.")
    p.add_argument("--auto-deploy", default=None, choices=["yes", "no"],
                   help="Auto-deploy on push (default: yes).")
    p.add_argument("--set", action="append", metavar="KEY=VALUE",
                   help="Plain env var (repeatable).")
    p.add_argument("--secret", action="append", metavar="KEY",
                   help="Secret env var name; value read from your environment (repeatable).")
    p.add_argument("--api-key", default=os.environ.get("RENDER_API_KEY"),
                   help="Render API key (default: RENDER_API_KEY env var).")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the request that WOULD be sent; make no API calls.")


def run(args: argparse.Namespace) -> int:
    project_dir = Path.cwd()

    try:
        spec = _load_spec(project_dir, args)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not spec.get("name"):
        print("error: no service name (set 'name' in the spec or pass --name).",
              file=sys.stderr)
        return 1

    repo_url = spec.get("repo") or _git_origin_url(project_dir)
    if not repo_url:
        print("error: no repo URL (no git 'origin' remote; pass --repo or set it "
              "in the spec).", file=sys.stderr)
        return 1

    print(f"==> tapestry deploy")
    print(f"    service:  {spec['name']} ({_TYPE_ALIASES.get(str(spec.get('type','web')), spec.get('type','web'))})")
    print(f"    repo:     {repo_url}")
    print(f"    branch:   {spec.get('branch', 'main')}")
    print(f"    plan:     {spec.get('plan', 'starter')} / {spec.get('region', 'oregon')}")
    if spec.get("envGroup"):
        print(f"    env grp:  {spec['envGroup']}")

    # Secrets present / missing (informational — a missing secret is set later).
    _env_vars, missing = _resolve_env_vars(spec)
    if spec["_secretNames"]:
        print(f"    secrets:  {len(spec['_secretNames']) - len(missing)}/"
              f"{len(spec['_secretNames'])} resolved from environment")
        if missing:
            print(f"      WARN: not in environment (set later in Render): {', '.join(missing)}")
    print()

    # --- DRY RUN: compose + print, no network, no key needed. ---
    if args.dry_run:
        payload = _build_service_payload(spec, repo_url, args.owner_id or "own-DRYRUN")
        # Never print resolved secret VALUES to stdout: mask any envVar whose key
        # is a declared secret name. The real (non-dry-run) POST is unaffected.
        masked = _mask_secret_values(payload, set(spec["_secretNames"]))
        print("DRY RUN — would POST /v1/services with:")
        print(json.dumps(masked, indent=2))
        if spec.get("envGroup"):
            print(f"\nThen POST /v1/env-groups/<id of {spec['envGroup']}>/services/<new id>")
        return 0

    api_key = args.api_key
    if not api_key:
        print("error: no Render API key. Set RENDER_API_KEY or pass --api-key.\n"
              "       Generate one: Render dashboard -> avatar -> Account Settings\n"
              "       -> API Keys -> Create API Key.", file=sys.stderr)
        return 1

    # Idempotency: bail if a service with this name already exists.
    try:
        existing = _find_service_by_name(api_key, spec["name"])
    except RuntimeError as e:
        print(f"error: could not query existing services: {e}", file=sys.stderr)
        return 1
    if existing:
        print(f"IDEMPOTENT: a service named '{spec['name']}' already exists "
              f"(id {existing.get('id')}). Nothing created.")
        url = existing.get("serviceDetails", {}).get("url") or existing.get("dashboardUrl")
        if url:
            print(f"  {url}")
        return 0

    # Owner.
    try:
        owner_id = args.owner_id or _resolve_owner_id(api_key, args.owner_name)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    # Create.
    try:
        payload = _build_service_payload(spec, repo_url, owner_id)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"--> Creating Render service '{spec['name']}'...")
    try:
        created = _request("POST", DEFAULT_API_URL.rstrip("/") + "/services", api_key, body=payload)
    except RuntimeError as e:
        print(f"error: create failed: {e}", file=sys.stderr)
        return 1
    service = created.get("service", created) if isinstance(created, dict) else {}
    service_id = service.get("id")
    print(f"  created: {service_id}")
    svc_url = service.get("serviceDetails", {}).get("url") or service.get("dashboardUrl")
    if svc_url:
        print(f"  {svc_url}")

    # Attach env group (best-effort).
    if spec.get("envGroup") and service_id:
        grp_name = spec["envGroup"]
        grp_id = _find_env_group_id(api_key, grp_name)
        if not grp_id:
            print(f"  WARN: env group '{grp_name}' not found; skipped. Attach it in "
                  f"the dashboard, or create it first.")
        else:
            link_url = (
                DEFAULT_API_URL.rstrip("/")
                + f"/env-groups/{grp_id}/services/{service_id}"
            )
            try:
                _request("POST", link_url, api_key)
                print(f"  attached env group '{grp_name}'")
            except RuntimeError as e:
                print(f"  WARN: could not attach env group '{grp_name}': {e}")

    print()
    print(f"==> Done. Render is building '{spec['name']}' now — watch the deploy in "
          f"the dashboard or with the Render CLI (`render logs`).")
    return 0
