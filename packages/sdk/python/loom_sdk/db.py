"""Tenant-scoped Postgres connection helper.

Every analytics query, every write, every read of tenant-scoped tables
goes through ``tenant_conn(ctx)``. The helper:

  1. Acquires a connection from the shared pool.
  2. Opens a transaction (so ``set_config(..., true)`` is transaction-local).
  3. Sets ``app.tenant_id`` to the current tenant.
  4. Yields the connection for the caller's queries.

Step 3 is the GUC that Postgres RLS policies read via
``current_setting('app.tenant_id', true)``. Because ``set_config(..., true)``
is the SQL equivalent of ``SET LOCAL``, the value dies with the transaction
and cannot leak to the next pgbouncer-pooled request.

The pool itself is created once via ``init_pool`` and released via
``close_pool``. Service main.py lifespans drive the lifecycle.

## Provenance

Ported verbatim from Make_Skills/core/db/db.py (audit §1.2, 2026-06-22).
Import paths adapted to loom_auth's TenantContext.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from loom_auth import TenantContext
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

log = logging.getLogger("loom_sdk.db")

_pool: AsyncConnectionPool | None = None


async def init_pool() -> AsyncConnectionPool:
    """Open the shared application pool. Called once from service lifespan."""
    global _pool
    if _pool is not None:
        return _pool
    db_url = os.environ["DATABASE_URL"]
    _pool = AsyncConnectionPool(
        conninfo=db_url,
        min_size=1,
        max_size=10,
        kwargs={"autocommit": False},
        open=False,
    )
    await _pool.open()
    log.info("application db pool open (min=1 max=10)")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is None:
        return
    await _pool.close()
    _pool = None


def get_pool() -> AsyncConnectionPool:
    """Return the open pool. Use only for queries that must NOT go through
    ``tenant_conn`` — i.e. queries that run BEFORE tenant context is
    resolved (the bridge receiver's tenant_id_mapping lookup is the
    canonical case). Tenant-scoped reads/writes must go through
    ``tenant_conn(ctx)`` so RLS gates them."""
    if _pool is None:
        raise RuntimeError("db pool not initialized; call init_pool() first")
    return _pool


@asynccontextmanager
async def tenant_conn(ctx: TenantContext) -> AsyncIterator[AsyncConnection]:
    """Per-request tenant-scoped connection.

    Usage::

        async with tenant_conn(ctx) as conn:
            await conn.execute("SELECT * FROM conversations WHERE ...")

    RLS policies then enforce that only rows matching ``ctx.tenant_id`` are
    visible. The transaction commits on clean exit, rolls back on exception.

    Also sets ``app.secrets_key`` from the ``MAKE_SKILLS_SECRETS_KEY`` env
    var when present, so SQL helpers can ``pgp_sym_decrypt`` without the
    plaintext key crossing the application boundary on read. Both GUCs are
    transaction-scoped (third arg ``true`` = SET LOCAL semantics) and die
    with the transaction — no leak across pgbouncer-pooled requests.
    """
    if _pool is None:
        raise RuntimeError("db pool not initialized; call init_pool() first")
    secrets_key = os.environ.get("MAKE_SKILLS_SECRETS_KEY")
    async with _pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (ctx.tenant_id,),
            )
            if secrets_key:
                await conn.execute(
                    "SELECT set_config('app.secrets_key', %s, true)",
                    (secrets_key,),
                )
            yield conn
