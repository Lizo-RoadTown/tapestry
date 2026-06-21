"""Postgres-backed idempotency store for the bridge receiver.

The wire contract makes `promotion_id` the idempotency key: retries with
the same promotion_id MUST return the same response the receiver gave
the first time. This implementation stores the response body + status
code at the moment of first acceptance and replays on retry.

No RLS — the store is bridge infrastructure, checked before tenant
context is even resolved. The promotion_id is a UUID4 (cryptographically
wide) so cross-tenant key collisions are not realistic.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


async def get_existing(
    pool: AsyncConnectionPool,
    promotion_id: UUID,
) -> tuple[int, dict[str, Any]] | None:
    """Look up a prior response for this promotion_id.

    Returns (status_code, response_json) if a prior response exists, or
    None if this is a fresh promotion_id. The receiver replays the prior
    response verbatim on retries.
    """
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT status_code, response_json
            FROM bridge_idempotency
            WHERE promotion_id = %s::uuid
            """,
            (str(promotion_id),),
        )
        row = await cur.fetchone()
        if not row:
            return None
        status_code, response_json = row
        # psycopg returns jsonb as already-parsed dict in newer versions,
        # but accept the str case too for robustness.
        if isinstance(response_json, str):
            response_json = json.loads(response_json)
        return status_code, response_json


async def record(
    pool: AsyncConnectionPool,
    promotion_id: UUID,
    status_code: int,
    response_json: dict[str, Any],
) -> None:
    """Store a (status, response) for a given promotion_id.

    Uses INSERT ... ON CONFLICT DO NOTHING so concurrent first-time
    POSTs of the same promotion_id are race-safe: the winner stores its
    response, the loser's INSERT is a no-op, both then retry-read via
    `get_existing` to get the canonical answer.
    """
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO bridge_idempotency
                    (promotion_id, status_code, response_json)
                VALUES (%s::uuid, %s, %s::jsonb)
                ON CONFLICT (promotion_id) DO NOTHING
                """,
                (str(promotion_id), status_code, json.dumps(response_json)),
            )


async def update_response(
    pool: AsyncConnectionPool,
    promotion_id: UUID,
    response_json: dict[str, Any],
) -> None:
    """Overwrite the stored response body for an existing idempotency row.

    Used by compile_worker after compile completes: the original 202 body
    was `{promotion_id, status: "queued"}`. Once compiled, the row is
    rewritten to include `existing_skill_id` so the 409 replay path
    surfaces the spec-required field to the-loom (per wire-contract
    section 1 + `loom_agent_to_ms_agent_coordinated_alignment_plan_2026_06_13`).
    Status code stays at the original (202); the receiver bumps to 409
    on duplicate-after-accepted at replay time.
    """
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE bridge_idempotency
                SET response_json = %s::jsonb
                WHERE promotion_id = %s::uuid
                """,
                (json.dumps(response_json), str(promotion_id)),
            )
