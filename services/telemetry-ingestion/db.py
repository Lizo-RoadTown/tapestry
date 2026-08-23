"""Postgres connection pool + tenant-scoped transaction wrapper for
telemetry-ingestion.

NEW in Tapestry Phase 0 task 2 (docs/plans/2026-08-23-observer-capacity-
build-sequence.md). The-loom's receiver had no DB layer — it logged to
Loki via stdout only. This module is the substrate access layer for the
telemetry store defined in `infra/migrations/005_init_telemetry.sql`
(telemetry_events + telemetry_rollup_daily, both RLS-scoped by
app.tenant_id).

Mirrors the canonical pattern in services/project-registry/storage.py and
services/agent-context/storage.py so all services build their pool, read
the DB URL, and scope tenants the SAME way:

  - env var: LOOM_DB_URL (same name as every other service)
  - pool: async psycopg3 AsyncConnectionPool, lazy singleton, min=2/max=10
  - tenant scoping: SELECT set_config('app.tenant_id', %s, true) inside an
    open transaction — the RLS "SET LOCAL app.tenant_id" mechanism. We use
    set_config() (NOT the literal `SET LOCAL app.tenant_id = $1`) because
    `SET` is a utility statement that rejects bind parameters at parse
    time; set_config(name, value, is_local=true) is the parameterizable,
    transaction-scoped equivalent. Lesson carried from
    services/agent-context/storage.py:129-143.

## Two-mode (self-host / hosted-multitenant)

This layer is AGNOSTIC to how the tenant was resolved — exactly like
agent-context. It only stamps `app.tenant_id` on the transaction; the
RLS policies in 005_init_telemetry.sql do the isolation. The caller
passes the resolved tenant_id string:

  - self-host: SELF_HOST_TENANT_ID (from loom_auth.auth_bridge; falls back
    to the all-zeros UUID, matching the COALESCE default baked into every
    005 policy so an unset GUC fails closed to that same tenant).
  - hosted-multitenant: the tenant_id claim from the verified Bearer JWT.

Both paths flow through `tenant_transaction()` identically — no branching
here on mode.

## Status

Present but UNUSED by apply_batch until Phase 0 task 3, which replaces the
log-only emit in skill_usage_handler.py with:

  - INSERT INTO telemetry_events (... ON CONFLICT (id) DO NOTHING)
  - UPSERT INTO telemetry_rollup_daily (... ON CONFLICT (pk) DO UPDATE
    SET invocation_count = telemetry_rollup_daily.invocation_count + 1, …)

both inside a single `async with tenant_transaction(tenant_id) as conn:`
block so the fact-row and its rollup increment commit atomically under the
same RLS scope.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


# ---------------------------------------------------------------------------
# Connection pool — singleton, lazy-init
# ---------------------------------------------------------------------------

_pool: AsyncConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def _configure_connection(conn: psycopg.AsyncConnection) -> None:
    """Every pooled connection returns dict rows (parity with the other
    services' storage layers)."""
    conn.row_factory = dict_row


async def get_pool() -> AsyncConnectionPool:
    """Lazy-init the connection pool. Reads `LOOM_DB_URL` from the env.

    Same env var + same pool sizing (min=2, max=10) as project-registry
    and agent-context. In Render, LOOM_DB_URL is auto-injected via a
    fromDatabase reference; for local dev set it in .env.
    """
    global _pool
    async with _pool_lock:
        if _pool is None:
            dsn = os.environ.get("LOOM_DB_URL")
            if not dsn:
                raise RuntimeError(
                    "LOOM_DB_URL unset. Required for loom-telemetry-ingestion's "
                    "Postgres substrate (infra/migrations/005_init_telemetry.sql). "
                    "In Render this is auto-injected via fromDatabase; for local "
                    "dev set it in .env."
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
    """Close the pool. Call on FastAPI shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Tenant scoping (RLS)
# ---------------------------------------------------------------------------


async def set_tenant(conn: psycopg.AsyncConnection, tenant_id: str) -> None:
    """Set `app.tenant_id` for the current transaction. The RLS policies in
    005_init_telemetry.sql read it via
    `current_setting('app.tenant_id', true)`.

    MUST be called inside an open transaction. Prefer `tenant_transaction()`
    below, which does this for you.

    Uses set_config() not `SET LOCAL app.tenant_id = $1`: SET is a utility
    statement and rejects bind parameters at parse time. The `true` third
    arg gives LOCAL (transaction-scoped) semantics — the setting is dropped
    at COMMIT/ROLLBACK, so a pooled connection never leaks one tenant's
    scope into the next checkout.
    """
    await conn.execute(
        "SELECT set_config('app.tenant_id', %s, true)", (tenant_id,)
    )


@asynccontextmanager
async def tenant_transaction(tenant_id: str) -> AsyncIterator[psycopg.AsyncConnection]:
    """Check out a pooled connection, open a transaction, stamp
    `app.tenant_id`, and yield the connection for tenant-scoped work.

    Everything done on the yielded connection runs under RLS for
    `tenant_id`; the transaction commits on clean exit and rolls back on
    exception. This is the single entry point Phase 0 task 3 uses for the
    telemetry_events INSERT + telemetry_rollup_daily UPSERT:

        async with tenant_transaction(tenant_id) as conn:
            await conn.execute(INSERT_EVENT_SQL, params)
            await conn.execute(UPSERT_ROLLUP_SQL, params)

    Two-mode: `tenant_id` is whatever the caller resolved (SELF_HOST_TENANT_ID
    or the JWT tenant claim). This wrapper does not care which — it only
    sets the GUC the RLS policies compare against.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await set_tenant(conn, tenant_id)
            yield conn
