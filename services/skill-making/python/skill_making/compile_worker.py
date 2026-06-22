"""Bridge compile worker — orchestrates compile + ack.

Runs as a FastAPI BackgroundTask after the receiver returns 202 to the
loom. By that time the response is already on the wire; the worker
takes its time without blocking the inbound request.

Flow:
  1. Call skill_compiler.compiler.compile_from_bridge_candidate
     -> CompiledSkillResult (outcome + skill_id + name + reason)
  2. Load the promoted_skills row to pull source_tenant_id +
     pattern_signature (needed for the ack body — loom side scopes by
     source_tenant_id, not engine_tenant_id, per
     loom_agent_bridge_complete_status_and_secret_2026_06_12_evening)
  3. Build RegistrationAck per the wire contract
  4. Call skill_making.ack_sender.send_registration_ack
  5. On ack failure: log loudly; engine state stays at 'compiled' so a
     repair script could re-ack. The-loom dedups by promotion_id so
     re-acks are safe.

Tenant context: receives `engine_tenant_id` as an explicit argument
(NOT via the ContextVar) because FastAPI BackgroundTasks lose request
scope. This is the documented convention in
core/auth/tenant_context.py:18.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from skill_compiler.compiler import (
    CompiledSkillResult,
    compile_from_bridge_candidate,
)
from skill_making.ack_sender import AckSendError, send_registration_ack
from skill_making.idempotency import update_response
from skill_making.models import (
    AckDiagnostics,
    AckLoomMetadata,
    AckSkill,
    CompileOutcome,
    RegistrationAck,
)

log = logging.getLogger("skill_making.compile_worker")


async def _load_ack_context(
    pool: AsyncConnectionPool,
    promotion_id: UUID,
    engine_tenant_id: str,
) -> tuple[str, str] | None:
    """Read source_tenant_id + pattern_signature from promoted_skills.

    Both are needed for the ack body: source_tenant_id goes into
    AckSkill.tenant_id (loom side scopes by it), pattern_signature
    echoes into the_loom_metadata.

    Returns (source_tenant_id, pattern_signature) or None if the row
    disappeared (shouldn't happen — the compile just touched it).
    """
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (engine_tenant_id,),
            )
            cur = await conn.execute(
                """
                SELECT source_tenant_id::text, pattern_signature
                FROM promoted_skills
                WHERE promotion_id = %s::uuid
                """,
                (str(promotion_id),),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return row[0], row[1]


def _build_ack(
    promotion_id: UUID,
    compiled: CompiledSkillResult,
    source_tenant_id: str,
    pattern_signature: str,
) -> RegistrationAck:
    """Convert (CompiledSkillResult + loom-side scoping fields) into a
    wire-contract RegistrationAck."""
    now_iso = datetime.now(timezone.utc).isoformat()

    if compiled.outcome == "compiled":
        assert compiled.skill_id is not None
        assert compiled.name is not None
        assert compiled.version is not None
        skill_block = AckSkill(
            skill_id=compiled.skill_id,
            name=compiled.name,
            version=compiled.version,
            source_origin="promoted",
            capability_tags=compiled.capability_tags,
            tenant_id=UUID(source_tenant_id),
            compiled_at=now_iso,
        )
        diagnostics = None
    else:
        skill_block = None
        # `reason` from the compiler is a short human-readable string;
        # we wrap it in the ack's diagnostics structure so the-loom can
        # display it.
        diagnostics = AckDiagnostics(
            errors=[{"phase": "compiler", "message": compiled.reason or "compile failed"}],
        )

    return RegistrationAck(
        promotion_id=promotion_id,
        registered_at=now_iso,
        outcome=CompileOutcome(compiled.outcome),
        skill=skill_block,
        compilation_diagnostics=diagnostics,
        the_loom_metadata=AckLoomMetadata(
            pattern_signature=pattern_signature,
            promotion_id=promotion_id,
        ),
    )


async def compile_and_ack(
    pool: AsyncConnectionPool,
    promotion_id: UUID,
    engine_tenant_id: str,
) -> None:
    """Background-task entry point. Compile a queued candidate then ack
    the result back to the-loom.

    Does NOT raise on ack failure — the engine state in promoted_skills
    is the source of truth; the-loom can pull or be re-acked manually.
    Compile failures DO get acked (as outcome=rejected).
    """
    try:
        compiled = await compile_from_bridge_candidate(
            pool, promotion_id, engine_tenant_id
        )
    except Exception:
        log.exception(
            "compile_and_ack: compile crashed for promotion_id=%s tenant=%s",
            promotion_id, engine_tenant_id,
        )
        return  # No ack — engine state is unchanged; loom will retry or pull.

    # Update the idempotency row so 409 replays surface existing_skill_id
    # per wire-contract section 1. The original 202 body was
    # `{promotion_id, status: "queued"}`; replace with the compiled-state
    # body so duplicate POSTs of the same promotion_id get back the
    # skill_id (the spec-required field for the-loom's reconciliation).
    if compiled.outcome == "compiled" and compiled.skill_id is not None:
        await update_response(
            pool,
            promotion_id,
            {
                "promotion_id": str(promotion_id),
                "status": "compiled",
                "existing_skill_id": str(compiled.skill_id),
            },
        )

    ctx = await _load_ack_context(pool, promotion_id, engine_tenant_id)
    if ctx is None:
        log.error(
            "compile_and_ack: promoted_skills row vanished after compile "
            "(promotion_id=%s) — cannot build ack",
            promotion_id,
        )
        return
    source_tenant_id, pattern_signature = ctx

    ack = _build_ack(promotion_id, compiled, source_tenant_id, pattern_signature)

    try:
        await send_registration_ack(ack)
    except AckSendError:
        log.exception(
            "compile_and_ack: ack POST failed for promotion_id=%s. "
            "Engine state stays at status=%r; loom can re-ack via "
            "repair script or its dispatch retry.",
            promotion_id, compiled.outcome,
        )
