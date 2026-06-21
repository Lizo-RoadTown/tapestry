"""
Pydantic models for the Project Registry API.

Three entities — Project, Repo, Machine — mirroring infra/migrations/002_init_projects.sql.

Each model has THREE variants:
  - {Entity}Create    — payload accepted on POST (subset of fields the caller
                        is allowed to set; server fills in id/tenant_id/timestamps)
  - {Entity}Update    — payload accepted on PATCH (all fields Optional)
  - {Entity}          — full row shape returned on GET (includes server-set fields)

Tenant_id is NEVER accepted in payload — it's always set by the server from
the request's JWT claims (via auth_bridge.tenant_ctx_var). This prevents a
client from claiming to write to another tenant by passing a different
tenant_id in the body.
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Project lifecycle states — matches the CHECK constraint in
# infra/migrations/002_init_projects.sql and the docs at
# docs/proposals/2026-05-25-platform-data-model.md:17.
ProjectKind = Literal["dev", "archived", "paused"]


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=128,
                      description="Human-readable identifier (e.g. 'the-loom'). "
                                  "Unique per tenant.")
    name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    kind: ProjectKind = "dev"
    extra: dict[str, Any] = Field(default_factory=dict,
                                   description="Free-form metadata.")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    description: Optional[str] = None
    kind: Optional[ProjectKind] = None
    extra: Optional[dict[str, Any]] = None
    archived_at: Optional[float] = Field(
        None, description="Set to a unix-epoch timestamp when transitioning "
                          "to kind='archived'."
    )


class Project(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str
    kind: ProjectKind
    tenant_id: UUID
    created_at: float
    archived_at: Optional[float] = None
    extra: dict[str, Any]


# ---------------------------------------------------------------------------
# Repo
# ---------------------------------------------------------------------------


class RepoCreate(BaseModel):
    project_id: UUID
    url: str = Field(..., min_length=1, max_length=512,
                     description="Git URL (e.g. https://github.com/owner/repo).")
    default_branch: str = Field(default="main", max_length=128)


class RepoUpdate(BaseModel):
    url: Optional[str] = Field(None, min_length=1, max_length=512)
    default_branch: Optional[str] = Field(None, max_length=128)


class Repo(BaseModel):
    id: UUID
    project_id: UUID
    url: str
    default_branch: str
    tenant_id: UUID
    created_at: float


# ---------------------------------------------------------------------------
# Machine
# ---------------------------------------------------------------------------


class MachineCreate(BaseModel):
    project_id: UUID
    hostname: str = Field(..., min_length=1, max_length=256,
                          description="socket.gethostname() of the machine.")
    os: str = Field(default="", max_length=64,
                    description="'windows', 'darwin', 'linux', etc.")
    checkout_path: str = Field(default="", max_length=1024,
                                description="Local filesystem path where the project "
                                            "repo is checked out on this machine.")


class MachineUpdate(BaseModel):
    os: Optional[str] = Field(None, max_length=64)
    checkout_path: Optional[str] = Field(None, max_length=1024)
    last_seen_at: Optional[float] = Field(
        None, description="Server updates this on every observation; "
                          "clients can also bump it explicitly."
    )


class Machine(BaseModel):
    id: UUID
    project_id: UUID
    hostname: str
    os: str
    checkout_path: str
    tenant_id: UUID
    created_at: float
    last_seen_at: float


# ---------------------------------------------------------------------------
# Convenience response models (lists)
# ---------------------------------------------------------------------------


class ProjectList(BaseModel):
    projects: list[Project]


class RepoList(BaseModel):
    repos: list[Repo]


class MachineList(BaseModel):
    machines: list[Machine]
