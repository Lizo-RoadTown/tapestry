"""
Compile a student-authored SKILL.md into a callable tool the deepagents
runtime can invoke. Per docs/proposals/pillar-1b-agent-runtime.md Decision 2:

  - Tool name = skill.name (short identifier).
  - Tool description = skill.description (what the LLM uses to decide
    when to reach for this skill — load-bearing).
  - Tool body wraps the user's task in a prompt that prepends skill.body_md
    as guidance, then invokes the model for execution.

This matches how the existing /skills/run endpoint composes prompts.
The difference: there, the dashboard explicitly picks a skill; here,
the agent's LLM picks among compiled tools by their descriptions.

This module also hosts the bridge-side compile entry point
`compile_from_bridge_candidate` (Phase 4 — PR B). That path is
model-agnostic: it persists the candidate's SKILL.md source into the
student_skills catalog with collision-resolved naming. Actual tool
compilation (`compile_skill_to_tool` above) runs LATER at agent build
time, against whichever model the agent runtime is configured for.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from langchain_core.tools import StructuredTool
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

    from typing import Any as StudentSkill  # engine runtime not lifted in Step 4 (type-only)

log = logging.getLogger("skill_compiler")


class _SkillInput(BaseModel):
    """The argument every compiled skill takes — the task to apply it to."""

    task: str = Field(
        ...,
        description=(
            "The user's task or question that this skill should be applied to. "
            "Pass the relevant context, question, or request as a single string."
        ),
    )


def compile_skill_to_tool(
    skill: "StudentSkill",
    model: "BaseChatModel",
    *,
    source_tenant_id: str | None = None,
    model_name: str | None = None,
) -> StructuredTool:
    """Turn a StudentSkill row into a langchain StructuredTool.

    The returned tool is async — when invoked by the agent's LLM, it
    runs a sub-call to the *same* model with the skill body prepended
    to the user's task. The skill body is treated as authoritative
    guidance for the sub-call.

    Telemetry (PR-prep-1): when `source_tenant_id` is provided (i.e. the
    caller resolved the loom-side UUID via
    `tenant_mapping.lookup_source_tenant`), each invocation enqueues a
    `TelemetryEvent` to the in-process collector. Failures in the
    telemetry path are swallowed — telemetry MUST NOT block the agent's
    response. When `source_tenant_id` is None, no telemetry is emitted
    (e.g. tenants without a mapping row, or when the collector isn't
    running).
    """
    skill_name = skill.name
    skill_description = skill.description
    skill_body = skill.body_md
    skill_id = skill.id  # captured for the telemetry event

    # Lazy import to avoid circular deps + to keep telemetry costs out
    # of the hot path when not configured.
    from time import perf_counter
    from uuid import uuid4

    async def _run(task: str) -> str:
        """Apply this skill to a task and return the result."""
        prompt = (
            f"Apply the **{skill_name}** skill (defined below) to the user's "
            f"task. Follow the skill's structure — PROBE / DECIDE / ACT / REPORT — "
            f"as the authoritative guidance for how to handle this task.\n\n"
            f"---\n\n## Skill body\n\n{skill_body}\n\n---\n\n"
            f"## Task\n\n{task.strip()}"
        )
        start = perf_counter()
        outcome = "success"
        tokens_in = 0
        tokens_out = 0
        result = None
        try:
            result = await model.ainvoke(
                [{"role": "user", "content": prompt}]
            )
        except Exception as e:
            outcome = "error"
            log.exception("skill %s sub-call failed", skill_name)
            _emit_telemetry(
                start=start,
                outcome=outcome,
                tokens_in=0,
                tokens_out=0,
                skill_id=skill_id,
                source_tenant_id=source_tenant_id,
                model_name=model_name,
            )
            return f"[skill {skill_name!r} failed: {e}]"

        # Extract token counts from langchain's usage_metadata when
        # available — providers expose this differently; we try the
        # standardized langchain_core path first.
        usage = getattr(result, "usage_metadata", None) or {}
        tokens_in = int(usage.get("input_tokens", 0) or 0)
        tokens_out = int(usage.get("output_tokens", 0) or 0)

        _emit_telemetry(
            start=start,
            outcome=outcome,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            skill_id=skill_id,
            source_tenant_id=source_tenant_id,
            model_name=model_name,
        )

        # `content` may be a string or a list of content blocks. Extract text.
        content = getattr(result, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        return str(result)

    # Sanitize the tool name — must be a valid identifier for most
    # langchain backends. Replace anything non-alphanumeric with underscore.
    sanitized_name = "".join(
        c if c.isalnum() or c == "_" else "_" for c in skill_name
    ) or "skill"

    return StructuredTool.from_function(
        coroutine=_run,
        name=sanitized_name,
        description=skill_description,
        args_schema=_SkillInput,
    )


def _emit_telemetry(
    *,
    start: float,
    outcome: str,
    tokens_in: int,
    tokens_out: int,
    skill_id: UUID,
    source_tenant_id: str | None,
    model_name: str | None,
) -> None:
    """Best-effort telemetry emission. Failures are logged + swallowed.

    Skips when `source_tenant_id` is None (the runtime couldn't reverse-
    look-up the loom-side UUID — see tenant_mapping.lookup_source_tenant).
    Better to skip than to emit an event with a wrong-or-missing
    tenant_id that the loom-side would reject.
    """
    if source_tenant_id is None:
        return
    try:
        from time import perf_counter

        from skill_making.telemetry_collector import record_event
        from skill_making.telemetry_sender import build_event

        latency_ms = int((perf_counter() - start) * 1000)
        event = build_event(
            skill_id=skill_id,
            thread_id="",  # filled by runtime when wired (deepagents thread_id
            # isn't trivially available here; the v0 collector accepts empty)
            tenant_id=UUID(source_tenant_id),
            outcome=outcome,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model_name or "unknown",
            trigger_context="skill_tool_invocation",
        )
        record_event(event)
    except Exception:
        log.debug("telemetry emission failed; ignoring", exc_info=True)


# ---------------------------------------------------------------------------
# Phase 4 bridge-side compile entry point (PR B)
# ---------------------------------------------------------------------------

# Cap on name-collision suffix bumping. If a tenant somehow already has
# this many `-promoted-N` skills with the same base name, something is
# very wrong upstream — we'd rather reject than spin forever.
MAX_COLLISION_SUFFIX_ATTEMPTS = 100


@dataclass(frozen=True)
class CompiledSkillResult:
    """Outcome of `compile_from_bridge_candidate`. Mirrors the wire
    contract's `RegistrationAck.outcome` semantics."""

    outcome: str  # "compiled" | "rejected" | "queued_human_review"
    skill_id: UUID | None
    name: str | None
    version: str | None
    reason: str | None
    capability_tags: list[str]


async def _resolve_name_collision(
    pool: AsyncConnectionPool,
    engine_tenant_id: str,
    suggested_name: str,
) -> tuple[str, str | None]:
    """Pick a final name for a bridge-sourced skill.

    Returns (final_name, reason_if_renamed). Reason is None if no rename
    happened.

    Strategy per the Phase 4 sketch:
      - If `suggested_name` doesn't collide in student_skills (for this
        tenant), use it as-is.
      - If it collides, append `-promoted-N` and bump N until unique.
      - If we exceed MAX_COLLISION_SUFFIX_ATTEMPTS, return outcome=rejected
        upstream (raises ValueError here; the caller catches).

    Same-content-collision detection (rejecting an exact-content duplicate)
    is NOT done here — `pattern_signature` idempotency in the receiver
    handles that case before we ever reach the compiler. If we're called,
    the upstream determined this is a NEW promotion of a DIFFERENT pattern.
    """
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (engine_tenant_id,),
            )
            cur = await conn.execute(
                """
                SELECT name FROM student_skills
                WHERE tenant_id = %s::uuid AND name LIKE %s
                """,
                (engine_tenant_id, f"{suggested_name}%"),
            )
            existing = {row[0] for row in await cur.fetchall()}

    if suggested_name not in existing:
        return suggested_name, None

    for n in range(1, MAX_COLLISION_SUFFIX_ATTEMPTS + 1):
        candidate = f"{suggested_name}-promoted-{n}"
        if candidate not in existing:
            return candidate, (
                f"renamed from {suggested_name!r} to {candidate!r} "
                "due to name collision in the student_skills catalog"
            )

    raise ValueError(
        f"could not resolve name collision after "
        f"{MAX_COLLISION_SUFFIX_ATTEMPTS} attempts for base "
        f"name={suggested_name!r}"
    )


async def compile_from_bridge_candidate(
    pool: AsyncConnectionPool,
    promotion_id: UUID,
    engine_tenant_id: str,
) -> CompiledSkillResult:
    """Compile a bridge-delivered candidate.

    Model-agnostic — no LLM call at promote time. Loads the candidate
    row from `promoted_skills` (RLS-scoped by `engine_tenant_id`),
    resolves naming collisions against the tenant's existing
    `student_skills`, INSERTs the skill, and updates the
    `promoted_skills` row's status + skill_id.

    Tool compilation (`compile_skill_to_tool` above) runs LATER at
    agent build time against whichever model the runtime is configured
    for. This function only persists the source + metadata.

    Args:
        pool: shared application pool. RLS scoping is via per-transaction
            `set_config('app.tenant_id', engine_tenant_id, true)`.
        promotion_id: the wire-contract idempotency key. Identifies the
            promoted_skills row to compile.
        engine_tenant_id: the engine-side tenant UUID (already resolved
            from the loom-side UUID via tenant_id_mapping in the receiver).

    Returns:
        CompiledSkillResult capturing the outcome. The caller
        (compile_worker) is responsible for converting this into a
        RegistrationAck and sending it via ack_sender.
    """
    # 1. Load the queued candidate row.
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (engine_tenant_id,),
            )
            cur = await conn.execute(
                """
                SELECT source_name, source_description, body_md,
                       capability_tags, pattern_signature, status,
                       skill_id
                FROM promoted_skills
                WHERE promotion_id = %s::uuid
                """,
                (str(promotion_id),),
            )
            row = await cur.fetchone()

    if not row:
        log.error("compile_from_bridge_candidate: no promoted_skills row for promotion_id=%s", promotion_id)
        return CompiledSkillResult(
            outcome="rejected",
            skill_id=None,
            name=None,
            version=None,
            reason="no promoted_skills row found for this promotion_id",
            capability_tags=[],
        )

    (suggested_name, description, body_md, capability_tags,
     pattern_signature, current_status, existing_skill_id) = row

    # 2. Idempotency on COMPILE itself — if the row is already compiled,
    # return the existing result. The receiver's idempotency catches
    # most cases; this handles the race where the receiver returned 202
    # twice (shouldn't happen given the DB unique constraint, but defend).
    if current_status == "compiled" and existing_skill_id:
        log.info(
            "compile_from_bridge_candidate: promotion_id=%s already compiled, returning existing skill_id=%s",
            promotion_id, existing_skill_id,
        )
        return CompiledSkillResult(
            outcome="compiled",
            skill_id=existing_skill_id,
            name=suggested_name,
            version="0.1.0",
            reason=None,
            capability_tags=capability_tags or [],
        )

    if current_status != "queued":
        log.error(
            "compile_from_bridge_candidate: promotion_id=%s in unexpected status=%s",
            promotion_id, current_status,
        )
        return CompiledSkillResult(
            outcome="rejected",
            skill_id=None,
            name=None,
            version=None,
            reason=f"candidate row in unexpected status {current_status!r}",
            capability_tags=[],
        )

    # 3. Resolve name collision.
    try:
        final_name, rename_reason = await _resolve_name_collision(
            pool, engine_tenant_id, suggested_name
        )
    except ValueError as e:
        return CompiledSkillResult(
            outcome="rejected",
            skill_id=None,
            name=None,
            version=None,
            reason=str(e),
            capability_tags=capability_tags or [],
        )

    # 4. INSERT into student_skills + UPDATE promoted_skills.
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (engine_tenant_id,),
            )
            cur = await conn.execute(
                """
                INSERT INTO student_skills (
                    tenant_id, agent_id, name, description, body_md, version
                ) VALUES (
                    %s::uuid, NULL, %s, %s, %s, 1
                )
                RETURNING id
                """,
                (engine_tenant_id, final_name, description, body_md),
            )
            new_row = await cur.fetchone()
            if not new_row:
                # Defensive — INSERT ... RETURNING should always return.
                log.error(
                    "compile_from_bridge_candidate: INSERT returned no id "
                    "for promotion_id=%s", promotion_id,
                )
                return CompiledSkillResult(
                    outcome="rejected",
                    skill_id=None,
                    name=None,
                    version=None,
                    reason="student_skills INSERT returned no id (DB anomaly)",
                    capability_tags=capability_tags or [],
                )
            new_skill_id = new_row[0]

            await conn.execute(
                """
                UPDATE promoted_skills
                SET status = 'compiled', skill_id = %s::uuid, updated_at = now()
                WHERE promotion_id = %s::uuid
                """,
                (str(new_skill_id), str(promotion_id)),
            )

    log.info(
        "compile_from_bridge_candidate: promotion_id=%s -> skill_id=%s name=%r tenant=%s",
        promotion_id, new_skill_id, final_name, engine_tenant_id,
    )
    return CompiledSkillResult(
        outcome="compiled",
        skill_id=new_skill_id,
        name=final_name,
        version="0.1.0",
        reason=rename_reason,
        capability_tags=capability_tags or [],
    )
