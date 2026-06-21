"""Skill-making bridge receiver — front half (PR A).

Receives Path A + Path B promotion candidates from the-loom's
Architecture Registry over the wire contract defined at
`docs/proposals/2026-05-25-skill-making-bridge.md` and shaped per
`docs/proposals/2026-06-12-bridge-receiver-and-compiler-phase-4-sketch.md`
(revised 2026-06-12 to incorporate Loom-agent's 5 ratification
adjustments + `loom_agent_bridge_complete_status_and_secret_2026_06_12_evening`
for the Stripe-style HMAC format).

This module is the deterministic guard + intake layer. The compile +
ack layer ships in PR B. v1.0 receiver fully handles `kind=skill`
candidates (persists as `status='queued'`, awaiting PR B's compile
dispatch); the other 8 kinds in the 9-kind taxonomy ack-defer
(persisted as `status='kind_not_yet_handled'`, 202 returned with
`outcome='ack_deferred'`) so the audit chain stays unbroken while
handlers ship in v1.1+. See `loom_agent_to_ms_agent_ack_defer_ratified_2026_06_12_evening`.

Tenant ID reconciliation uses Option B: explicit mapping table per
`decision_tenant_id_mapping_option_b_2026_06_12`. The payload's
`tenant_id` carries the SOURCE side's UUID (the-loom's
`1d8ec1b3-...` for self-host); `resolve_engine_tenant` maps it to
the engine-side UUID (Make_Skills' `00000000-...` for self-host)
before any write.
"""
from __future__ import annotations

import json
from typing import Any

from psycopg_pool import AsyncConnectionPool
from pydantic import ValidationError

from skill_making.hmac_verify import (
    HmacVerificationError,
    verify_signature,
)
from skill_making.idempotency import get_existing, record
from skill_making.models import (
    BridgeError,
    BridgeErrorCode,
    CandidateKind,
    PromotionCandidatePayload,
    ReceiverResponse,
)
from skill_making.tenant_mapping import (
    UnknownSourceTenantError,
    resolve_engine_tenant,
)


class ReceiverResult:
    """The receiver's outcome as a (status_code, body) tuple, plus an
    optional `compile_request`. The FastAPI route translates the
    status_code + body into an HTTP response and, if `compile_request`
    is set, schedules a background task to compile + ack the candidate.

    Keeping `compile_request` here (rather than having the receiver
    schedule the task itself) keeps the receiver transport-agnostic —
    the verify script can call the receiver and either ignore the
    compile request or invoke the compile_worker directly.
    """

    __slots__ = ("status_code", "body", "compile_request")

    def __init__(
        self,
        status_code: int,
        body: dict[str, Any],
        compile_request: tuple[Any, str] | None = None,
    ):
        self.status_code = status_code
        self.body = body
        # (promotion_id: UUID, engine_tenant_id: str) — when set, the
        # route handler schedules compile_worker.compile_and_ack as a
        # FastAPI BackgroundTask after sending the 202 response.
        self.compile_request = compile_request


async def _persist_candidate(
    pool: AsyncConnectionPool,
    payload: PromotionCandidatePayload,
    engine_tenant_id: str,
    status: str,
) -> None:
    """Write the candidate row to promoted_skills under the engine-side
    tenant_id. RLS scopes by `app.tenant_id`; we set it to the resolved
    engine_tenant_id before insert."""
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (engine_tenant_id,),
            )
            await conn.execute(
                """
                INSERT INTO promoted_skills (
                    promotion_id, engine_tenant_id, source_system,
                    source_tenant_id, is_global, candidate_kind,
                    pattern_signature, source_name, source_description,
                    body_md, capability_tags, triggers, callbacks, status
                ) VALUES (
                    %s::uuid, %s::uuid, %s,
                    %s::uuid, %s, %s,
                    %s, %s, %s,
                    %s, %s::jsonb, %s::jsonb, %s::jsonb, %s
                )
                ON CONFLICT (promotion_id) DO NOTHING
                """,
                (
                    str(payload.promotion_id),
                    engine_tenant_id,
                    payload.source_system,
                    str(payload.tenant_id),
                    payload.is_global,
                    payload.candidate_kind.value,
                    payload.pattern_signature,
                    payload.source.frontmatter.name,
                    payload.source.frontmatter.description,
                    payload.source.body_md,
                    json.dumps(payload.capability_tags),
                    json.dumps(payload.triggers),
                    payload.callbacks.model_dump_json(),
                    status,
                ),
            )


async def receive_promotion_candidate(
    raw_body: bytes,
    signature: str,
    pool: AsyncConnectionPool,
    *,
    secret: str | None = None,
) -> ReceiverResult:
    """Entry point. The FastAPI route in services/api/main.py wraps this
    with HTTP plumbing; this function is transport-agnostic so it can be
    driven from a verification script or smoke test against a real pool.

    Deterministic flow, no LLM:
      1. HMAC verify (raw body, constant-time)
      2. Schema validate (pydantic)
      3. Idempotency check (replay prior response if promotion_id seen)
      4. Tenant resolution (source UUID -> engine UUID via mapping)
      5. Kind dispatch:
         - kind=skill            -> persist as 'queued',          202 queued
         - other 9-kind values   -> persist as 'kind_not_yet_handled', 202 ack_deferred
      6. Record in idempotency store

    Returns ReceiverResult(status_code, body). Body is either a
    ReceiverResponse (success path) or a BridgeError (failure path),
    both serialized as a dict.
    """
    # 1. HMAC verify FIRST. Reject before any DB read on bad signature.
    try:
        verify_signature(raw_body, signature, secret=secret)
    except HmacVerificationError as e:
        return ReceiverResult(
            401,
            BridgeError(
                code=BridgeErrorCode.HMAC_INVALID,
                message=str(e),
            ).model_dump(mode="json"),
        )

    # 2. Schema validate.
    try:
        payload_dict = json.loads(raw_body)
        payload = PromotionCandidatePayload.model_validate(payload_dict)
    except (json.JSONDecodeError, ValidationError) as e:
        details: dict[str, Any] | None = None
        if isinstance(e, ValidationError):
            details = {"errors": e.errors()}
        return ReceiverResult(
            400,
            BridgeError(
                code=BridgeErrorCode.SCHEMA_INVALID,
                message="Payload failed schema validation.",
                details=details,
            ).model_dump(mode="json"),
        )

    # 3. Idempotency check. Replay prior response verbatim.
    prior = await get_existing(pool, payload.promotion_id)
    if prior is not None:
        prior_status_code, prior_body = prior
        # On true duplicate (already-accepted promotion_id), spec says
        # 409. We re-return the original response code so retries are
        # idempotent — if the prior was a 202, we replay 202; if the
        # prior was a 4xx, we replay that. But the spec specifically
        # calls for 409 on duplicate-after-accepted; we honor that by
        # bumping a 202 replay to 409 with the same body.
        if prior_status_code == 202:
            return ReceiverResult(409, prior_body)
        return ReceiverResult(prior_status_code, prior_body)

    # 4. Tenant resolution.
    try:
        engine_tenant_id = await resolve_engine_tenant(
            pool, payload.source_system, str(payload.tenant_id)
        )
    except UnknownSourceTenantError as e:
        body = BridgeError(
            code=BridgeErrorCode.UNKNOWN_SOURCE_TENANT,
            message=str(e),
            details={
                "source_system": e.source_system,
                "source_tenant_id": e.source_tenant_id,
            },
        ).model_dump(mode="json")
        # Record so retries don't keep hitting the mapping table for an
        # unmapped tenant; the operator must configure + the-loom retry
        # with the same promotion_id then gets the same 400 until the
        # mapping is added. (Once mapping is added, the operator can
        # DELETE the idempotency row to allow a fresh attempt.)
        await record(pool, payload.promotion_id, 400, body)
        return ReceiverResult(400, body)

    # 5. Kind dispatch.
    compile_request: tuple[Any, str] | None = None
    if payload.candidate_kind == CandidateKind.SKILL:
        await _persist_candidate(pool, payload, engine_tenant_id, "queued")
        response_body = ReceiverResponse(
            promotion_id=payload.promotion_id,
            status="queued",
        ).model_dump(mode="json")
        status_code = 202
        # Schedule the compile + ack via the route handler's BackgroundTasks.
        # The receiver stays transport-agnostic; the route does the actual
        # task injection.
        compile_request = (payload.promotion_id, engine_tenant_id)
    else:
        # ack-defer per the 9-kind taxonomy; v1.0 only compiles skill.
        await _persist_candidate(
            pool, payload, engine_tenant_id, "kind_not_yet_handled"
        )
        response_body = ReceiverResponse(
            promotion_id=payload.promotion_id,
            status="kind_not_yet_handled",
            outcome="ack_deferred",
            reason=(
                f"candidate_kind={payload.candidate_kind.value!r} is not "
                "yet handled by this receiver version. The candidate is "
                "recorded; a future receiver version (v1.1+) will pick it up."
            ),
        ).model_dump(mode="json")
        status_code = 202

    # 6. Record the response for idempotent retries.
    await record(pool, payload.promotion_id, status_code, response_body)

    return ReceiverResult(status_code, response_body, compile_request=compile_request)
