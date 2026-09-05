"""
Postgres-backed storage for the Architecture Registry (Phase 1 candidate slice).

Mirrors services/project-registry/storage.py — async psycopg3 + connection
pool + tenant scoping via set_config() (NOT SET LOCAL, which rejects bind
parameters; see lesson_postgres_set_local_no_bind_params).

Public API (Phase 1 scope only — don't overbuild):
  create_candidate
  get_candidate
  list_candidates
  update_candidate_status

All functions take `tenant_id` explicitly — set on the transaction's
`app.tenant_id` GUC so the RLS policies in 007_init_candidates.sql filter
correctly. The application layer (main.py) passes the tenant_id from
auth_bridge.tenant_ctx_var (hosted mode) or the self-host stable UUID.

## Two-mode commitment

Self-host and hosted-multitenant share this code verbatim. The only mode-
sensitive value is `tenant_id` itself; RLS does the rest.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Optional
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool


# ---------------------------------------------------------------------------
# Connection pool — singleton, lazy-init
# ---------------------------------------------------------------------------

_pool: AsyncConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def _configure_connection(conn: psycopg.AsyncConnection) -> None:
    conn.row_factory = dict_row


async def get_pool() -> AsyncConnectionPool:
    global _pool
    async with _pool_lock:
        if _pool is None:
            dsn = os.environ.get("LOOM_DB_URL")
            if not dsn:
                raise RuntimeError(
                    "LOOM_DB_URL unset. Required for loom-architecture-registry. "
                    "In Render this is auto-injected via fromDatabase."
                )
            _pool = AsyncConnectionPool(
                conninfo=dsn,
                min_size=2,
                max_size=10,
                open=False,
                configure=_configure_connection,
            )
            await _pool.open()
        return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def _set_tenant(conn: psycopg.AsyncConnection, tenant_id: str) -> None:
    """Set app.tenant_id for the current transaction. RLS policies read
    this via current_setting('app.tenant_id', true). Use set_config() —
    NOT SET LOCAL — because SET rejects bind parameters at parse time.

    See lesson_postgres_set_local_no_bind_params in loom-memory."""
    await conn.execute(
        "SELECT set_config('app.tenant_id', %s, true)", (tenant_id,)
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """psycopg3 returns JSONB as already-decoded Python values, but UUID
    columns come back as `uuid.UUID` instances. Pydantic accepts UUID
    fields as either UUID or str so no conversion needed. This helper
    exists for symmetry with project-registry/storage.py:_strip_jsonb."""
    if row is None:
        return row
    # Defensive: if psycopg ever returned JSONB as str (older versions),
    # decode here so callers always see dict/list.
    for jsonb_col in ("evidence_refs", "signals"):
        v = row.get(jsonb_col)
        if isinstance(v, str):
            try:
                row[jsonb_col] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                row[jsonb_col] = [] if jsonb_col == "evidence_refs" else {}
    return row


# ---------------------------------------------------------------------------
# Project visibility check (cross-tenant FK guard)
# ---------------------------------------------------------------------------


async def is_project_visible(project_id: UUID, tenant_id: str) -> bool:
    """Return True iff the given project_id exists AND belongs to the
    caller's tenant. Used by main.py before INSERTing a candidate row
    that references a project — Postgres FK validation bypasses RLS, so
    without this guard a caller could create a candidate referencing
    another tenant's project. Same defense-in-depth as
    services/project-registry/main.py:_assert_project_visible.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM projects WHERE id = %s",
                    (str(project_id),),
                )
                row = await cur.fetchone()
                return row is not None


# ---------------------------------------------------------------------------
# Candidate CRUD (Phase 1 minimum slice)
# ---------------------------------------------------------------------------


async def create_candidate(
    *,
    project_id: UUID,
    instance_id: str,
    source_path: str,
    candidate_type: str,
    status: str,
    evidence_refs: list[dict[str, Any]],
    signals: dict[str, Any],
    tenant_id: str,
) -> dict[str, Any]:
    """INSERT a new candidate. Returns the row including server-generated
    id + created_at + updated_at. Raises psycopg.errors.ForeignKeyViolation
    if project_id doesn't exist (caller should have pre-checked with
    is_project_visible to give a 404 instead of a 500)."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO candidates (
                        project_id, instance_id, source_path, candidate_type,
                        status, evidence_refs, signals, tenant_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING
                        id, project_id, instance_id, source_path,
                        candidate_type, status, evidence_refs, signals,
                        tenant_id, created_at, updated_at
                    """,
                    (
                        str(project_id),
                        instance_id,
                        source_path,
                        candidate_type,
                        status,
                        Jsonb(evidence_refs),
                        Jsonb(signals),
                        tenant_id,
                    ),
                )
                row = await cur.fetchone()
                return _normalize_row(row)


async def get_candidate(
    candidate_id: UUID, tenant_id: str
) -> Optional[dict[str, Any]]:
    """SELECT one candidate by id. Returns None if not found OR if RLS
    hides it (other tenant)."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id, project_id, instance_id, source_path,
                        candidate_type, status, evidence_refs, signals,
                        tenant_id, created_at, updated_at
                    FROM candidates
                    WHERE id = %s
                    """,
                    (str(candidate_id),),
                )
                row = await cur.fetchone()
                return _normalize_row(row) if row else None


async def list_candidates(
    *,
    tenant_id: str,
    project_id: Optional[UUID] = None,
    status: Optional[str] = None,
    source_path: Optional[str] = None,
    candidate_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """SELECT candidates with optional filters. Tenant-scoped via RLS.
    Ordered by created_at DESC (most recent first — matches the upskilling
    UI's expected listing)."""
    where_parts: list[str] = []
    params: list[Any] = []

    if project_id is not None:
        where_parts.append("project_id = %s")
        params.append(str(project_id))
    if status is not None:
        where_parts.append("status = %s")
        params.append(status)
    if source_path is not None:
        where_parts.append("source_path = %s")
        params.append(source_path)
    if candidate_type is not None:
        where_parts.append("candidate_type = %s")
        params.append(candidate_type)

    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + " AND ".join(where_parts)

    params.append(limit)
    params.append(offset)

    sql = f"""
        SELECT
            id, project_id, instance_id, source_path,
            candidate_type, status, evidence_refs, signals,
            tenant_id, created_at, updated_at
        FROM candidates
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()
                return [_normalize_row(r) for r in rows]


async def update_candidate_status(
    candidate_id: UUID,
    new_status: str,
    tenant_id: str,
    *,
    reason: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """PATCH the status field. Optionally append a {kind: status_change}
    entry to evidence_refs for auditability. Returns the updated row,
    or None if not found (or RLS-hidden).

    The updated_at trigger from 007_init_candidates.sql refreshes
    the timestamp automatically — no need to touch it here.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                # Get current state first so we can record the from->to
                # transition in evidence_refs if a reason is provided.
                await cur.execute(
                    "SELECT status, evidence_refs FROM candidates WHERE id = %s",
                    (str(candidate_id),),
                )
                current = await cur.fetchone()
                if current is None:
                    return None

                if reason is not None:
                    # Append audit entry. Use server-side NOW for ts so
                    # the timestamp comes from the same clock as the
                    # trigger-set updated_at.
                    audit = {
                        "kind": "status_change",
                        "from": current["status"],
                        "to": new_status,
                        "reason": reason,
                    }
                    existing = current.get("evidence_refs") or []
                    if isinstance(existing, str):
                        try:
                            existing = json.loads(existing)
                        except (json.JSONDecodeError, TypeError):
                            existing = []
                    new_evidence = list(existing) + [audit]
                    await cur.execute(
                        """
                        UPDATE candidates
                        SET status = %s, evidence_refs = %s
                        WHERE id = %s
                        RETURNING
                            id, project_id, instance_id, source_path,
                            candidate_type, status, evidence_refs, signals,
                            tenant_id, created_at, updated_at
                        """,
                        (new_status, Jsonb(new_evidence), str(candidate_id)),
                    )
                else:
                    await cur.execute(
                        """
                        UPDATE candidates
                        SET status = %s
                        WHERE id = %s
                        RETURNING
                            id, project_id, instance_id, source_path,
                            candidate_type, status, evidence_refs, signals,
                            tenant_id, created_at, updated_at
                        """,
                        (new_status, str(candidate_id)),
                    )

                row = await cur.fetchone()
                return _normalize_row(row) if row else None
