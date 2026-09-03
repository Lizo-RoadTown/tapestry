"""Dynamic scan-target discovery from the project-registry.

The observer's scan set is a STATIC CORE (config.static_core_targets) plus
every repo registered in the project-registry. This module builds the dynamic
part and merges it with the static core, de-duped.

Endpoints coded against (verified in services/project-registry/main.py):

  GET /projects            → {"projects": [Project, ...]}   (main.py:109-122)
      Project.id, Project.kind                              (models.py:58-67)
      list is tenant-scoped; include_archived defaults False (main.py:111) so
      archived projects are already excluded.

  GET /projects/{id}/repos → {"repos": [Repo, ...]}         (main.py:225-232)
      Repo.url, Repo.default_branch                         (models.py:87-93)

Auth: OBSERVER_JWT → Bearer on every request; unset → no header → the registry
resolves the request to its SELF_HOST_TENANT_ID (self-host). Same
auth_bridge.verify_bearer contract the registry enforces (main.py:110-114).

Soft-fail: any registry error (unreachable, non-200) logs a warning and yields
NO dynamic targets — the pass still runs against the static core. Better to
scan less than to crash the whole pass.
"""
from __future__ import annotations

import httpx

from config import (
    CONSUMING_REPO_DEFAULT_PATHS,
    AuthConfig,
    Endpoints,
    RegistryTarget,
    static_core_targets,
)


def _headers(auth: AuthConfig) -> dict[str, str]:
    """Bearer OBSERVER_JWT when present; no header = self-host at the registry."""
    headers = {"Accept": "application/json"}
    if auth.observer_jwt:
        headers["Authorization"] = f"Bearer {auth.observer_jwt}"
    return headers


def repo_slug_from_url(url: str) -> str | None:
    """Normalize a git URL to "owner/repo" (GitHub contents-API form).

    Handles https, ssh (git@github.com:owner/repo.git), trailing .git and
    slashes. Returns None if the last two path segments can't be recovered.
    """
    u = url.strip()
    if not u:
        return None
    # ssh form: git@github.com:owner/repo(.git)
    if u.startswith("git@"):
        _, _, path = u.partition(":")
    else:
        # strip scheme
        if "://" in u:
            u = u.split("://", 1)[1]
        # drop host
        path = u.partition("/")[2] if "/" in u else ""
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return None
    return f"{parts[-2]}/{parts[-1]}"


async def _fetch_projects(client: httpx.AsyncClient, endpoints: Endpoints) -> list[dict]:
    url = f"{endpoints.project_registry_url}/projects"
    resp = await client.get(url)
    if resp.status_code != 200:
        print(f"WARN: project-registry GET /projects {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json().get("projects", [])


async def _fetch_repos(
    client: httpx.AsyncClient, endpoints: Endpoints, project_id: str
) -> list[dict]:
    url = f"{endpoints.project_registry_url}/projects/{project_id}/repos"
    resp = await client.get(url)
    if resp.status_code != 200:
        print(
            f"WARN: project-registry GET /projects/{project_id}/repos "
            f"{resp.status_code}: {resp.text[:200]}"
        )
        return []
    return resp.json().get("repos", [])


async def discover_dynamic_targets(
    endpoints: Endpoints, auth: AuthConfig
) -> list[RegistryTarget]:
    """Every registered repo, as a RegistryTarget. Soft-fails to []."""
    targets: list[RegistryTarget] = []
    async with httpx.AsyncClient(
        timeout=30.0, headers=_headers(auth), follow_redirects=True
    ) as client:
        try:
            projects = await _fetch_projects(client, endpoints)
        except httpx.HTTPError as exc:
            print(f"WARN: project-registry unreachable, static-core only: {exc}")
            return []

        for project in projects:
            project_id = project.get("id")
            if not project_id:
                continue
            try:
                repos = await _fetch_repos(client, endpoints, str(project_id))
            except httpx.HTTPError as exc:
                print(f"WARN: repos fetch failed for project {project_id}: {exc}")
                continue
            for repo in repos:
                slug = repo_slug_from_url(repo.get("url", ""))
                if not slug:
                    print(f"WARN: could not parse repo url {repo.get('url')!r}; skipping")
                    continue
                targets.append(
                    RegistryTarget(
                        repo=slug,
                        paths=CONSUMING_REPO_DEFAULT_PATHS,
                        branch=repo.get("default_branch") or "main",
                        project_id=str(project_id),
                    )
                )
    return targets


def merge_targets(
    static_core: tuple[RegistryTarget, ...],
    dynamic: list[RegistryTarget],
) -> list[RegistryTarget]:
    """Static core first, then discovered repos not already in the core.

    De-dup is by repo slug (case-insensitive) so tapestry/marketplace are never
    scanned twice even when they are also registered in the project-registry.
    """
    core_slugs = {t.repo.lower() for t in static_core}
    merged: list[RegistryTarget] = list(static_core)
    seen = set(core_slugs)
    for t in dynamic:
        key = t.repo.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(t)
    return merged


async def build_scan_targets(
    endpoints: Endpoints, auth: AuthConfig
) -> list[RegistryTarget]:
    """Full scan set: static core + de-duped dynamic discovery."""
    dynamic = await discover_dynamic_targets(endpoints, auth)
    return merge_targets(static_core_targets(), dynamic)
