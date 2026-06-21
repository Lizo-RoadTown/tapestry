"""Cross-system tenant UUID resolution for the bridge receiver.

The bridge carries the SOURCE side's tenant UUID (e.g. the-loom's
`1d8ec1b3-...`). The engine has its own tenant UUIDs (e.g. Make_Skills'
`00000000-...` for self-host, gen_random_uuid() values per hosted tenant).
Option B from `decision_tenant_id_mapping_option_b_2026_06_12`: an
explicit `tenant_id_mapping` table reconciles them.

Reads are unscoped (no `tenant_conn`) because tenant context isn't yet
resolved when we look up the mapping — that's literally what we're
resolving. Writes are operator-tooling only (seeding additional
hosted-mode mappings); not exposed through user-facing API.
"""
from __future__ import annotations

from psycopg_pool import AsyncConnectionPool


class UnknownSourceTenantError(Exception):
    """Raised when the receiver gets a candidate whose source tenant_id
    has no row in `tenant_id_mapping`. The receiver surfaces this as a
    400 with `error.code = "unknown_source_tenant"` so the operator can
    configure the mapping before retries succeed."""

    def __init__(self, source_system: str, source_tenant_id: str):
        self.source_system = source_system
        self.source_tenant_id = source_tenant_id
        super().__init__(
            f"No tenant_id_mapping row for ({source_system!r}, {source_tenant_id!r}). "
            "Operator must INSERT a mapping row before bridge POSTs from this "
            "source tenant can be accepted."
        )


async def resolve_engine_tenant(
    pool: AsyncConnectionPool,
    source_system: str,
    source_tenant_id: str,
) -> str:
    """Look up `engine_tenant_id` for a given (source_system, source_tenant_id).

    Returns the engine-side UUID as a string suitable for setting on
    `app.tenant_id`. Raises `UnknownSourceTenantError` if no mapping
    exists — the receiver translates this to a 400 response.

    This query intentionally does NOT go through `tenant_conn` — the
    mapping table has no RLS, and at lookup time we don't yet have a
    tenant scope (resolving it IS the point).
    """
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT engine_tenant_id::text
            FROM tenant_id_mapping
            WHERE source_system = %s AND source_tenant_id = %s::uuid
            """,
            (source_system, source_tenant_id),
        )
        row = await cur.fetchone()
        if not row:
            raise UnknownSourceTenantError(source_system, source_tenant_id)
        return row[0]


async def lookup_source_tenant(
    pool: AsyncConnectionPool,
    engine_tenant_id: str,
    *,
    source_system: str = "loom",
) -> str | None:
    """Reverse-lookup: given an engine-side tenant UUID, return the
    source-side UUID for `source_system`.

    Used by the telemetry collector: the runtime knows the engine-side
    UUID (e.g. `00000000-...` for self-host), but the wire contract's
    TelemetryEvent + RegistrationAck.skill.tenant_id both carry the
    SOURCE-side UUID (the-loom's `1d8ec1b3-...` for self-host) so the
    consumer can scope by their native tenancy.

    Returns `None` if no mapping exists for this engine_tenant_id (e.g.
    the runtime spun up with a tenant that was never registered for
    bridge traffic). Caller should skip the telemetry event in that case
    — better than poisoning the wire with a wrong UUID.

    Same unscoped-query rationale as `resolve_engine_tenant`: the
    `tenant_id_mapping` table has no RLS.
    """
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT source_tenant_id::text
            FROM tenant_id_mapping
            WHERE engine_tenant_id = %s::uuid AND source_system = %s
            LIMIT 1
            """,
            (engine_tenant_id, source_system),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return row[0]
