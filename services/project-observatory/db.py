"""Postgres connection pool + tenant-scoped transaction wrapper for
project-observatory (the runtime-observer's home).

Phase 1 of the observer-capacity build (docs/plans/2026-08-23-observer-
capacity-build-sequence.md). project-observatory reads the SAME loom-postgres
that telemetry-ingestion writes: the Phase-0 telemetry substrate
(`infra/migrations/005_init_telemetry.sql` — telemetry_events +
telemetry_rollup_daily) is the observer's INPUT, and the observation-signals
store (`infra/migrations/006_init_observation_signals.sql` —
observation_signals) is its OUTPUT. Both are RLS-scoped by app.tenant_id.

This module is copied near-verbatim from
services/telemetry-ingestion/db.py — the canonical tenant-scoped pool — so
every service builds its pool, reads the DB URL, and scopes tenants the SAME
way:

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
telemetry-ingestion and agent-context. It only stamps `app.tenant_id` on the
transaction; the RLS policies in 005/006 do the isolation. The caller passes
the resolved tenant_id string:

  - self-host: SELF_HOST_TENANT_ID (falls back to the all-zeros UUID, matching
    the COALESCE default baked into every 005/006 policy so an unset GUC fails
    closed to that same tenant). Resolved by tenant.py in this service.
  - hosted-multitenant: the tenant_id claim from the verified Bearer JWT
    (added when project-observatory gains hosted read auth).

Both paths flow through `tenant_transaction()` identically — no branching
here on mode.

## Status

Present in this scaffold (Phase 1 task 2). Used by the signal computation
(task 3, reads 005) and the materialization entrypoint (task 4, writes
observation_signals) and the read endpoint (task 5, reads 006) — none of
which exist yet. The pool opens lazily on the first `get_pool()` call.
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

    Same env var + same pool sizing (min=2, max=10) as telemetry-ingestion,
    project-registry and agent-context. In Render, LOOM_DB_URL is auto-injected
    via a fromDatabase reference; for local dev set it in .env.
    """
    global _pool
    async with _pool_lock:
        if _pool is None:
            dsn = os.environ.get("LOOM_DB_URL")
            if not dsn:
                raise RuntimeError(
                    "LOOM_DB_URL unset. Required for loom-project-observatory's "
                    "reads of the Postgres telemetry substrate "
                    "(infra/migrations/005_init_telemetry.sql) and writes of "
                    "observation_signals (006_init_observation_signals.sql). "
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
    005_init_telemetry.sql and 006_init_observation_signals.sql read it via
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
    exception. This is the single entry point the runtime-observer uses to
    read the 005 substrate (task 3) and to write observation_signals
    (task 4):

        async with tenant_transaction(tenant_id) as conn:
            await conn.execute(READ_ROLLUP_SQL, params)     # task 3
            await conn.execute(INSERT_SIGNAL_SQL, params)   # task 4

    Two-mode: `tenant_id` is whatever the caller resolved (SELF_HOST_TENANT_ID
    or the JWT tenant claim). This wrapper does not care which — it only
    sets the GUC the RLS policies compare against.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await set_tenant(conn, tenant_id)
            yield conn
