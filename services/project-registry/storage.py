"""
Postgres-backed storage for the Project Registry.

Mirrors the pattern in services/agent-context/storage.py — async psycopg3 +
connection pool + tenant scoping via set_config() (NOT SET LOCAL, which
rejects bind parameters; see lesson at infra/migrations/001_init_memory.sql
and the storage.py fix in services/agent-context/storage.py:136).

Public API:
  create_project / get_project / list_projects / update_project / delete_project
  create_repo    / get_repo    / list_repos    / update_repo    / delete_repo
  create_machine / get_machine / list_machines / update_machine / delete_machine

All functions take `tenant_id` explicitly — set on the transaction's
app.tenant_id GUC so the RLS policies in 002_init_projects.sql filter
correctly. The application layer (main.py) passes the tenant_id from
auth_bridge.tenant_ctx_var (hosted mode) or the self-host stable UUID.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
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
                    "LOOM_DB_URL unset. Required for loom-project-registry. "
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
    NOT SET LOCAL — because SET rejects bind parameters at parse time."""
    await conn.execute(
        "SELECT set_config('app.tenant_id', %s, true)", (tenant_id,)
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_jsonb(row: dict[str, Any]) -> dict[str, Any]:
    """psycopg3 returns JSONB columns as already-decoded dicts; ensure
    the `extra` field is a dict (defensive — psycopg should already do this)."""
    if "extra" in row and isinstance(row["extra"], str):
        try:
            row["extra"] = json.loads(row["extra"])
        except (json.JSONDecodeError, TypeError):
            row["extra"] = {}
    return row


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


async def create_project(
    *,
    slug: str,
    name: str,
    description: str,
    kind: str,
    extra: dict[str, Any],
    tenant_id: str,
) -> dict[str, Any]:
    """Insert a new project. Server generates id + created_at.

    Raises psycopg.errors.UniqueViolation if (tenant_id, slug) collides.
    Raises psycopg.errors.CheckViolation if kind not in ('dev','archived','paused').
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO projects (slug, name, description, kind, tenant_id, extra)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id, slug, name, description, kind, tenant_id, created_at,
                              archived_at, extra
                    """,
                    (slug, name, description, kind, tenant_id, json.dumps(extra)),
                )
                row = await cur.fetchone()
                return _strip_jsonb(dict(row)) if row else {}


async def get_project(project_id: UUID, tenant_id: str) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, slug, name, description, kind, tenant_id, created_at,
                           archived_at, extra
                    FROM projects WHERE id = %s
                    """,
                    (str(project_id),),
                )
                row = await cur.fetchone()
                return _strip_jsonb(dict(row)) if row else None


async def get_project_by_slug(slug: str, tenant_id: str) -> dict[str, Any] | None:
    """Look up a project by slug. Useful for `loom init` idempotency
    (caller checks if a project with this slug already exists before
    creating)."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, slug, name, description, kind, tenant_id, created_at,
                           archived_at, extra
                    FROM projects WHERE slug = %s
                    """,
                    (slug,),
                )
                row = await cur.fetchone()
                return _strip_jsonb(dict(row)) if row else None


async def list_projects(
    tenant_id: str,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    where = "" if include_archived else "WHERE archived_at IS NULL"
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    SELECT id, slug, name, description, kind, tenant_id, created_at,
                           archived_at, extra
                    FROM projects {where}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = await cur.fetchall()
                return [_strip_jsonb(dict(r)) for r in rows]


async def update_project(
    project_id: UUID,
    tenant_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    kind: str | None = None,
    extra: dict[str, Any] | None = None,
    archived_at: float | None = None,
) -> dict[str, Any] | None:
    """Partial update. Only non-None fields are updated. Returns the
    updated row, or None if the project doesn't exist (or RLS hid it).

    Raises psycopg.errors.CheckViolation if kind not in ('dev','archived','paused').
    """
    sets: list[str] = []
    params: list[Any] = []
    if name is not None:
        sets.append("name = %s")
        params.append(name)
    if description is not None:
        sets.append("description = %s")
        params.append(description)
    if kind is not None:
        sets.append("kind = %s")
        params.append(kind)
    if extra is not None:
        sets.append("extra = %s::jsonb")
        params.append(json.dumps(extra))
    if archived_at is not None:
        sets.append("archived_at = %s")
        params.append(archived_at)
    if not sets:
        return await get_project(project_id, tenant_id)
    params.append(str(project_id))
    sql = f"""
        UPDATE projects SET {", ".join(sets)}
        WHERE id = %s
        RETURNING id, slug, name, description, kind, tenant_id, created_at,
                  archived_at, extra
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                row = await cur.fetchone()
                return _strip_jsonb(dict(row)) if row else None


async def delete_project(project_id: UUID, tenant_id: str) -> int:
    """Hard-delete a project. CASCADE drops associated repos + machines.
    Returns rowcount (0 or 1). Soft-delete (archive) uses update_project
    with archived_at."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM projects WHERE id = %s", (str(project_id),)
                )
                return cur.rowcount


# ---------------------------------------------------------------------------
# Repo CRUD
# ---------------------------------------------------------------------------


async def create_repo(
    *,
    project_id: UUID,
    url: str,
    default_branch: str,
    tenant_id: str,
) -> dict[str, Any]:
    """Insert a new repo. RLS on projects table prevents adding a repo
    to a project the requesting tenant doesn't own (FK lookup fails).
    Returns the new row or raises on FK / unique violation."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO repos (project_id, url, default_branch, tenant_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, project_id, url, default_branch, tenant_id, created_at
                    """,
                    (str(project_id), url, default_branch, tenant_id),
                )
                row = await cur.fetchone()
                return dict(row) if row else {}


async def list_repos(
    project_id: UUID, tenant_id: str
) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, project_id, url, default_branch, tenant_id, created_at
                    FROM repos WHERE project_id = %s
                    ORDER BY created_at DESC
                    """,
                    (str(project_id),),
                )
                rows = await cur.fetchall()
                return [dict(r) for r in rows]


async def delete_repo(repo_id: UUID, tenant_id: str) -> int:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM repos WHERE id = %s", (str(repo_id),)
                )
                return cur.rowcount


# ---------------------------------------------------------------------------
# Machine CRUD
# ---------------------------------------------------------------------------


async def create_machine(
    *,
    project_id: UUID,
    hostname: str,
    os_name: str,
    checkout_path: str,
    tenant_id: str,
) -> dict[str, Any]:
    """Insert (or upsert by project_id+hostname). If the machine already
    exists for this project, update last_seen_at + os + checkout_path
    instead of failing."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO machines (project_id, hostname, os, checkout_path, tenant_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (project_id, hostname) DO UPDATE SET
                        os = EXCLUDED.os,
                        checkout_path = EXCLUDED.checkout_path,
                        last_seen_at = EXTRACT(EPOCH FROM NOW())
                    RETURNING id, project_id, hostname, os, checkout_path,
                              tenant_id, created_at, last_seen_at
                    """,
                    (str(project_id), hostname, os_name, checkout_path, tenant_id),
                )
                row = await cur.fetchone()
                return dict(row) if row else {}


async def list_machines(
    project_id: UUID, tenant_id: str
) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, project_id, hostname, os, checkout_path,
                           tenant_id, created_at, last_seen_at
                    FROM machines WHERE project_id = %s
                    ORDER BY last_seen_at DESC
                    """,
                    (str(project_id),),
                )
                rows = await cur.fetchall()
                return [dict(r) for r in rows]


async def delete_machine(machine_id: UUID, tenant_id: str) -> int:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM machines WHERE id = %s", (str(machine_id),)
                )
                return cur.rowcount
