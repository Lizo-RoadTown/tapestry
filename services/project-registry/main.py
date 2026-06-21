"""
loom-project-registry — the bounded context that knows what projects exist.

Per docs/proposals/2026-05-25-platform-data-model.md:69 ("Project Registry
owns Project, Repo, Machine") this service is the authoritative registration
mechanism by which a consuming project DECLARES ITSELF to the-loom. Once
registered, the project's telemetry / memory / discipline events can be
scoped to it.

Endpoints (all tenant-scoped via auth_bridge.verify_bearer):

  POST   /projects                    — register a new project
  GET    /projects                    — list this tenant's projects
  GET    /projects/{id}               — get one
  GET    /projects/by-slug/{slug}     — lookup by human-readable slug (used by loom init for idempotency)
  PATCH  /projects/{id}               — partial update
  DELETE /projects/{id}               — hard delete (cascades to repos + machines)

  POST   /projects/{id}/repos         — register a repo under a project
  GET    /projects/{id}/repos         — list repos
  DELETE /repos/{id}                  — delete one

  POST   /projects/{id}/machines      — register / upsert a machine under a project
  GET    /projects/{id}/machines      — list machines
  DELETE /machines/{id}               — delete one

Auth mode: per auth_bridge.verify_bearer's docstring — self-host (no header)
falls back to the stable SELF_HOST_TENANT_ID matching agent-context.
Hosted-multitenant verifies RS256 with LOOM_JWT_PUBLIC_KEY.

Cross-tenant FK guard: before any repos/machines INSERT, the handler calls
storage.get_project() — if the target project is RLS-hidden (belongs to a
different tenant), 404 instead of letting the FK constraint succeed silently
(Postgres FK checks bypass RLS).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Response

import auth_bridge
import models
import storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the connection pool on startup; close on shutdown.

    Pool opens lazily on first query — no need to force here. Just ensure
    shutdown closes it cleanly so the Render service drains pool members
    before the process exits.
    """
    yield
    await storage.close_pool()


app = FastAPI(
    title="loom-project-registry",
    version="0.1.0",
    description="Authoritative registry of Projects/Repos/Machines for the-loom platform.",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Does NOT touch the database — Render's health check
    runs every ~10s and shouldn't bounce on transient DB blips."""
    return {"status": "ok", "service": "loom-project-registry"}


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


@app.post("/projects", response_model=models.Project, status_code=201)
async def create_project(
    payload: models.ProjectCreate,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    """Register a new project. Slug must be unique per tenant."""
    try:
        row = await storage.create_project(
            slug=payload.slug,
            name=payload.name,
            description=payload.description,
            kind=payload.kind,
            extra=payload.extra,
            tenant_id=tenant_id,
        )
    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            409, f"Project with slug '{payload.slug}' already exists for this tenant"
        )
    return row


@app.get("/projects", response_model=models.ProjectList)
async def list_projects(
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    rows = await storage.list_projects(
        tenant_id=tenant_id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return {"projects": rows}


@app.get("/projects/{project_id}", response_model=models.Project)
async def get_project(
    project_id: UUID,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    row = await storage.get_project(project_id, tenant_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return row


@app.get("/projects/by-slug/{slug}", response_model=models.Project)
async def get_project_by_slug(
    slug: str,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    """Lookup by slug — used by `loom init` for idempotency (check before
    creating)."""
    row = await storage.get_project_by_slug(slug, tenant_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return row


@app.patch("/projects/{project_id}", response_model=models.Project)
async def update_project(
    project_id: UUID,
    payload: models.ProjectUpdate,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    row = await storage.update_project(
        project_id,
        tenant_id,
        name=payload.name,
        description=payload.description,
        kind=payload.kind,
        extra=payload.extra,
        archived_at=payload.archived_at,
    )
    if not row:
        raise HTTPException(404, "Project not found")
    return row


@app.delete("/projects/{project_id}")
async def delete_project(
    project_id: UUID,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> Response:
    # FastAPI 0.115.4 asserts "204 must not have a response body" at
    # decoration time when the handler has a return annotation other than
    # Response. Return a bare Response(204) instead of relying on the
    # decorator's status_code= kwarg.
    n = await storage.delete_project(project_id, tenant_id)
    if n == 0:
        raise HTTPException(404, "Project not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Repos
# ---------------------------------------------------------------------------


async def _assert_project_visible(project_id: UUID, tenant_id: str) -> None:
    """Defense-in-depth: confirm the project belongs to this tenant BEFORE
    inserting a child row. Postgres FK validation bypasses RLS, so without
    this guard a caller could (in theory) create a repo/machine referencing
    another tenant's project. The resulting row would be unreachable due to
    tenant_id mismatch on read, but it shouldn't exist at all."""
    p = await storage.get_project(project_id, tenant_id)
    if not p:
        raise HTTPException(404, "Project not found")


@app.post("/projects/{project_id}/repos", response_model=models.Repo, status_code=201)
async def create_repo(
    project_id: UUID,
    payload: models.RepoCreate,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    # Path is authoritative — caller can't sneak a different project_id
    # via the body. Both must agree to reduce ambiguity.
    if payload.project_id != project_id:
        raise HTTPException(400, "Body project_id must match path project_id")
    await _assert_project_visible(project_id, tenant_id)
    try:
        row = await storage.create_repo(
            project_id=project_id,
            url=payload.url,
            default_branch=payload.default_branch,
            tenant_id=tenant_id,
        )
    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            409, f"Repo '{payload.url}' already registered under this project"
        )
    return row


@app.get("/projects/{project_id}/repos", response_model=models.RepoList)
async def list_repos(
    project_id: UUID,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    await _assert_project_visible(project_id, tenant_id)
    rows = await storage.list_repos(project_id, tenant_id)
    return {"repos": rows}


@app.delete("/repos/{repo_id}")
async def delete_repo(
    repo_id: UUID,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> Response:
    n = await storage.delete_repo(repo_id, tenant_id)
    if n == 0:
        raise HTTPException(404, "Repo not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------


@app.post("/projects/{project_id}/machines", response_model=models.Machine, status_code=201)
async def create_machine(
    project_id: UUID,
    payload: models.MachineCreate,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    if payload.project_id != project_id:
        raise HTTPException(400, "Body project_id must match path project_id")
    await _assert_project_visible(project_id, tenant_id)
    row = await storage.create_machine(
        project_id=project_id,
        hostname=payload.hostname,
        os_name=payload.os,
        checkout_path=payload.checkout_path,
        tenant_id=tenant_id,
    )
    return row


@app.get("/projects/{project_id}/machines", response_model=models.MachineList)
async def list_machines(
    project_id: UUID,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    await _assert_project_visible(project_id, tenant_id)
    rows = await storage.list_machines(project_id, tenant_id)
    return {"machines": rows}


@app.delete("/machines/{machine_id}")
async def delete_machine(
    machine_id: UUID,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> Response:
    n = await storage.delete_machine(machine_id, tenant_id)
    if n == 0:
        raise HTTPException(404, "Machine not found")
    return Response(status_code=204)
