"""
Postgres-backed storage for the Policy Service (Phase 5 decisions slice).

Mirrors services/architecture-registry/storage.py — async psycopg3 +
connection pool + tenant scoping via set_config() (NOT SET LOCAL, which
rejects bind parameters; see lesson_postgres_set_local_no_bind_params in
loom-memory).

Public API (Phase 5 scope only — don't overbuild):
  create_decision
  list_decisions
  get_policy_state              # the aggregate over a candidate's decisions

All functions take `tenant_id` explicitly — set on the transaction's
`app.tenant_id` GUC so the RLS policies in 004_init_policy.sql filter
correctly. The application layer (main.py) passes the tenant_id from
auth_bridge.tenant_ctx_var (hosted mode) or SELF_HOST_TENANT_ID.

## Two-mode commitment

Self-host and hosted-multitenant share this code verbatim. The only
mode-sensitive value is `tenant_id` itself; RLS does the rest. There is
NO UPDATE path here by design — the migration omits an UPDATE policy, so
audit-immutability is enforced at the DB layer in both modes.

## Cross-service id discipline (Pillar 0)

candidate_id is owned by architecture-registry. We do NOT validate that
it exists; if a caller files a decision against a nonexistent
candidate_id, the row is still recorded (the audit trail is allowed to
reference candidates that were later deleted — see migration header for
why FK is intentionally absent). Cross-service joins happen at the read
layer per docs/proposals/2026-05-25-platform-data-model.md.
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
                    "LOOM_DB_URL unset. Required for loom-policy. "
                    "In Render this is a sync:false secret (shared loom-postgres)."
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


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """psycopg3 returns JSONB as already-decoded Python values, but
    defensively decode if a row comes back stringified (older psycopg
    paths). Same shape as architecture-registry/storage.py:_normalize_row."""
    if row is None:
        return row
    v = row.get("extra")
    if isinstance(v, str):
        try:
            row["extra"] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            row["extra"] = {}
    return row


# ---------------------------------------------------------------------------
# Decision CRUD (no U — by design; see header)
# ---------------------------------------------------------------------------


async def create_decision(
    *,
    candidate_id: UUID,
    decision_kind: str,
    target_status: Optional[str],
    reason: str,
    decided_by: str,
    extra: dict[str, Any],
    tenant_id: str,
) -> dict[str, Any]:
    """INSERT a new policy decision. Returns the row including
    server-generated id + decided_at default."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO policy_decisions (
                        candidate_id, decision_kind, target_status,
                        reason, decided_by, extra, tenant_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING
                        id, candidate_id, decision_kind, target_status,
                        reason, decided_by, decided_at, tenant_id, extra
                    """,
                    (
                        str(candidate_id),
                        decision_kind,
                        target_status,
                        reason,
                        decided_by,
                        Jsonb(extra),
                        tenant_id,
                    ),
                )
                row = await cur.fetchone()
                return _normalize_row(row)


async def list_decisions(
    *,
    tenant_id: str,
    candidate_id: Optional[UUID] = None,
    decision_kind: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """SELECT decisions with optional filters. Tenant-scoped via RLS.
    Ordered by decided_at DESC (most recent first — matches the operator
    audit queue UX)."""
    where_parts: list[str] = []
    params: list[Any] = []

    if candidate_id is not None:
        where_parts.append("candidate_id = %s")
        params.append(str(candidate_id))
    if decision_kind is not None:
        where_parts.append("decision_kind = %s")
        params.append(decision_kind)

    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + " AND ".join(where_parts)

    params.append(limit)
    params.append(offset)

    sql = f"""
        SELECT
            id, candidate_id, decision_kind, target_status,
            reason, decided_by, decided_at, tenant_id, extra
        FROM policy_decisions
        {where_clause}
        ORDER BY decided_at DESC
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


# ---------------------------------------------------------------------------
# Policy-state aggregate (read-side derivation)
# ---------------------------------------------------------------------------


async def get_policy_state(
    candidate_id: UUID, tenant_id: str
) -> dict[str, Any]:
    """Compute the per-candidate aggregate: full decision chain (newest
    first) + a summary that downstream callers can use for fast yes/no
    transition checks.

    The summary rules (cf. models.PolicyStateSummary docstring):
      - latest_kind / latest_target_status come from row[0] (newest).
      - is_held: latest is 'hold' AND not superseded (i.e., it IS the
        latest decision; any later approve/reject/demote unsets the hold).
        Since rows are sorted DESC, this is just: rows[0].kind == 'hold'.
      - is_rejected: rows[0].kind == 'reject'.
      - is_approved_for: rows[0].kind == 'approve' → its target_status,
        else None. (Any later non-approve decision implicitly supersedes
        a prior approve, matching audit-trail-is-truth semantics.)

    Returns {summary: dict, decisions: list[dict]} — main.py wraps in the
    Pydantic PolicyState model.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id, candidate_id, decision_kind, target_status,
                        reason, decided_by, decided_at, tenant_id, extra
                    FROM policy_decisions
                    WHERE candidate_id = %s
                    ORDER BY decided_at DESC
                    """,
                    (str(candidate_id),),
                )
                rows = [_normalize_row(r) for r in await cur.fetchall()]

    if not rows:
        summary = {
            "candidate_id": str(candidate_id),
            "decision_count": 0,
            "latest_kind": None,
            "latest_target_status": None,
            "is_held": False,
            "is_approved_for": None,
            "is_rejected": False,
        }
        return {"summary": summary, "decisions": []}

    latest = rows[0]
    latest_kind = latest["decision_kind"]
    latest_target = latest.get("target_status")
    summary = {
        "candidate_id": str(candidate_id),
        "decision_count": len(rows),
        "latest_kind": latest_kind,
        "latest_target_status": latest_target,
        "is_held": latest_kind == "hold",
        "is_approved_for": latest_target if latest_kind == "approve" else None,
        "is_rejected": latest_kind == "reject",
    }
    return {"summary": summary, "decisions": rows}
