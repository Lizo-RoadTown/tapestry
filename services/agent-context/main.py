"""loom-agent-context — Agent Context Service.

Owns: Agent (kind), Session, Artifact; cross-project memory storage.
Hosts: project-scoped Agency Optimizer sub-service (V2.x).
Writes to: loom-postgres (Postgres + pgvector).
Issues: JWTs (has LOOM_JWT_PRIVATE_KEY).

Phase 2 (this file as of commit 43cc0e6 onward):
  - /health endpoint (existing)
  - /mcp/memory — MCP HTTP transport mount via StreamableHTTPSessionManager
    + LoomTokenVerifier bearer auth (mcp_http.mount_into)
  - Storage layer auto-init (storage.get_pool lazy-init on first DB call)

v0.1.7 (2026-06-01) adds:
  - POST /v1/recall — REST endpoint for SessionStart hook auto-recall.
    Bypasses MCP transport for simpler one-shot calls from hook scripts
    (stdlib urllib instead of MCP HTTP handshake). Self-host falls back
    to SELF_HOST_TENANT_ID when no Bearer; matches project-registry's
    auth_bridge.verify_bearer pattern.

Phase 3+ adds:
  - REST endpoints for the dashboard's memory browser
  - Project Registry integration
  - JWT issuance endpoint
  - Telemetry emission via OTel
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
import time
from typing import Any, AsyncIterator, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel, Field

import mcp_http
import storage


# Stable self-host tenant_id — sourced from the canonical loom_auth
# package via the auth_bridge shim (PR-prep-2b consolidation 2026-06-19).
# All loom services that fall back to self-host land in the same tenant
# envelope; canonical lives at packages/auth/python/loom_auth/auth_bridge.py.
from auth_bridge import SELF_HOST_TENANT_ID  # noqa: E402


async def _resolve_tenant_for_rest(
    authorization: Optional[str] = Header(None),
) -> str:
    """FastAPI dependency: resolves tenant_id for REST endpoints.

    Self-host (no Authorization header): returns SELF_HOST_TENANT_ID.
    Hosted (Bearer + LOOM_JWT_PUBLIC_KEY env): RS256-verifies, returns
    the JWT's tenant_id claim.

    Distinct from the MCP transport's auth (which uses LoomTokenVerifier
    and rejects without Bearer). REST endpoints accept self-host mode
    for the SessionStart hook + dev workflows; matches
    services/project-registry/auth_bridge.py:verify_bearer pattern.
    """
    if not authorization:
        return SELF_HOST_TENANT_ID

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise HTTPException(401, "Malformed Authorization header")
    token = parts[1].strip()

    public_key = os.environ.get("LOOM_JWT_PUBLIC_KEY")
    if not public_key:
        raise HTTPException(
            401, "JWT verification unavailable (LOOM_JWT_PUBLIC_KEY unset)"
        )

    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(401, "Invalid token")

    tid = claims.get("tenant_id")
    sub = claims.get("sub")
    if not tid or not sub:
        raise HTTPException(401, "Token missing tenant_id or sub claim")
    return tid


class RecallRequest(BaseModel):
    context: str = Field(..., min_length=1, max_length=4000,
                         description="Semantic search anchor — short description "
                                     "of what the conversation is about.")
    n: int = Field(default=5, ge=1, le=50,
                   description="Max memories to return.")
    project_tags: list[str] = Field(default_factory=list,
                                    description="Optional — restrict to memories "
                                                "tagged with at least one of these "
                                                "projects. Empty = all of user's "
                                                "memories (cross-project).")


class RecallResponse(BaseModel):
    memories: list[dict[str, Any]]


# Memory types — must match mcp_server.py:92-97 VALID_TYPES exactly.
# Pinned by test_v1_write_invalid_record_type_returns_422.
_VALID_RECORD_TYPES = {
    "decision", "lesson", "preference", "skill_idea", "topic", "fact",
    "user", "feedback", "project", "reference",
}


class WriteRequest(BaseModel):
    """POST /v1/write body. The MCP memory_write tool's REST counterpart.

    `name` becomes the record's id; on conflict the row is upserted (atomic
    INSERT ... ON CONFLICT DO UPDATE at storage.py:217-232). All other
    fields map directly to the records table columns.
    """
    name: str = Field(..., min_length=1, max_length=256,
                      description="Stable name — used as the row id for upsert.")
    record_type: Literal[
        "decision", "lesson", "preference", "skill_idea", "topic", "fact",
        "user", "feedback", "project", "reference",
    ] = Field(..., description="One of the 10 VALID_TYPES values.")
    content: str = Field(..., min_length=1,
                         description="Full body markdown.")
    project_tags: list[str] = Field(default_factory=list)
    source_thread_id: str = Field(default="", max_length=128)
    ts: float = Field(default=0.0)
    why: str = Field(default="")
    actor: str = Field(default="unknown", max_length=64,
                       description="Which agent wrote this. 'self-observer' for cron, "
                                   "'claude-code' for interactive sessions, etc.")
    extra: dict[str, Any] = Field(default_factory=dict)


class WriteResponse(BaseModel):
    ok: bool
    name: str
    inserted: int


class ReadRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256,
                      description="Exact name of the record to read.")


class ReadResponse(BaseModel):
    memory: dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan: enter/exit the MCP session manager + close
    the Postgres pool on shutdown. The MCP session manager MUST be
    entered before any HTTP request hits its mount."""
    async with mcp_http.session_lifespan(app):
        try:
            yield
        finally:
            await storage.close_pool()


app = FastAPI(
    title="loom-agent-context",
    version="0.3.0",
    lifespan=lifespan,
)

# Mount the MCP HTTP transport at /mcp/memory.
# Bearer-auth-gated by LoomTokenVerifier (auth_bridge.py); on each
# request, the verifier reads OAuth-shaped bearer token, sets
# mcp_server.tenant_ctx_var from JWT's tenant_id claim, then the
# MCP SDK dispatches to one of the 6 tool handlers.
mcp_http.mount_into(app, path="/mcp/memory")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "loom-agent-context"}


@app.post("/v1/recall", response_model=RecallResponse)
async def recall(
    payload: RecallRequest,
    tenant_id: str = Depends(_resolve_tenant_for_rest),
) -> dict:
    """Semantic memory recall — REST counterpart to the loom-memory MCP's
    memory_recall tool. Designed for hook scripts that can't easily do
    the MCP HTTP transport handshake from a one-shot Python process.

    Same underlying storage.search() — same semantic search via pgvector
    HNSW + bge-small-en-v1.5 embedding. Same tenant scoping via RLS.
    """
    rows = await storage.search(
        query=payload.context,
        tenant_id=tenant_id,
        limit=payload.n,
        project_tags=payload.project_tags or None,
    )
    return {"memories": rows}


@app.post("/v1/write", response_model=WriteResponse)
async def write(
    payload: WriteRequest,
    tenant_id: str = Depends(_resolve_tenant_for_rest),
) -> dict:
    """Memory write — REST counterpart to the loom-memory MCP's memory_write
    tool. Designed for non-MCP clients (the self-observer Render cron in
    particular) that can't easily do the MCP HTTP transport handshake.

    `name` becomes the row id; on conflict the row is upserted atomically
    via INSERT ... ON CONFLICT DO UPDATE (storage.py:217-232) — same path
    the MCP write tool uses. Idempotent by name.

    Tenant scoping is identical to /v1/recall: self-host falls back to
    SELF_HOST_TENANT_ID, hosted-multitenant verifies the bearer JWT and
    uses the tenant_id claim. Malformed bearer → 401 (NOT silent fallback).
    """
    record = {
        "id": payload.name,
        "type": payload.record_type,
        "content": payload.content,
        "project_tags": payload.project_tags,
        "source_thread_id": payload.source_thread_id,
        "ts": payload.ts if payload.ts > 0 else time.time(),
        "why": payload.why,
        "actor": payload.actor,
        "extra": payload.extra,
    }
    inserted = await storage.insert_records(
        records=[record],
        tenant_id=tenant_id,
    )
    return {"ok": True, "name": payload.name, "inserted": inserted}


@app.post("/v1/read", response_model=ReadResponse)
async def read(
    payload: ReadRequest,
    tenant_id: str = Depends(_resolve_tenant_for_rest),
) -> dict:
    """Exact-name memory read — REST counterpart to the loom-memory MCP's
    memory_read tool. Returns the single row matching `name` (= row id) or
    404 if absent.

    Distinct from /v1/recall (semantic search). Used by the self-observer
    cron to read its prior `self_observer_synthesis_latest` memo before
    writing the new one (needed to compute "2 consecutive scans" health
    thresholds per the runtime-observation-followup §3.3).

    Tenant scoping identical to /v1/write + /v1/recall.
    """
    row = await storage.get_by_id(
        record_id=payload.name,
        tenant_id=tenant_id,
    )
    if row is None:
        raise HTTPException(404, f"Memory not found: {payload.name}")
    return {"memory": row}
