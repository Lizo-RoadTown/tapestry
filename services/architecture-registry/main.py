"""
loom-architecture-registry — Phase 1 candidate-registry slice.

Per the ratified build sequence in
loom-memory:loom_agent_to_ms_agent_pillar_2_sequence_ratified_2026_06_12,
this service is the minimum slice of the eventual Architecture Registry
needed to unblock Phase 2 (local observer) + Phase 3 (cross-project
Pattern Detection) + Phase 6 (the upskilling dashboard). It does ONE thing well:
accept promotion candidates from Path A (local observer) and Path B
(platform observatory), persist them, expose them for query, and let
status transitions happen.

Deliberately NOT included (Liz's "don't overbuild" guidance):
  - architecture_nodes / architecture_edges endpoints
  - decisions endpoints
  - observations endpoints
  - tasks endpoints
  - policy decisions
  - audit-event mirror

Endpoints:
  POST   /candidates                       — register a new candidate
  GET    /candidates                       — list (filters: project_id, status, source_path, candidate_type)
  GET    /candidates/{id}                  — get one
  PATCH  /candidates/{id}/status           — narrow surface: status only (with optional reason)
  GET    /health                           — Render health probe

Auth: per auth_bridge.verify_bearer's docstring — self-host (no header)
falls back to SELF_HOST_TENANT_ID; hosted-multitenant verifies RS256 with
LOOM_JWT_PUBLIC_KEY.

Cross-tenant FK guard: before INSERTing a candidate that references a
project, the handler calls storage.is_project_visible() — Postgres FK
checks bypass RLS, so this is defense-in-depth. Same pattern at
services/project-registry/main.py:189-198.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator, Optional
from uuid import UUID

import psycopg
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request

import auth_bridge
import bridge_hmac
import bridge_models
import models
import promote_dispatcher
import registration_handler
import storage

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Pool opens lazily on first query; close cleanly on shutdown so the
    Render service drains pool members before the process exits."""
    yield
    await storage.close_pool()


app = FastAPI(
    title="loom-architecture-registry",
    version="0.1.0",
    description=(
        "Phase 1 of the recursive-skill engine: the minimum candidate "
        "registry slice. Accepts promotion candidates from Path A (local "
        "observer) and Path B (platform observatory) and tracks their "
        "lifecycle through the standard state machine."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Does NOT touch the database — Render's health check
    runs every ~10s and shouldn't bounce on transient DB blips. Same
    pattern as services/project-registry/main.py:75-79 and
    services/agent-context/main.py /health."""
    return {"status": "ok", "service": "loom-architecture-registry"}


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


@app.post("/candidates", response_model=models.Candidate, status_code=201)
async def create_candidate(
    payload: models.CandidateCreate,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    """Register a new promotion candidate.

    The body's `project_id` must reference a project visible to the
    caller's tenant — pre-checked here because Postgres FK validation
    bypasses RLS (see storage.is_project_visible docstring).
    """
    if not await storage.is_project_visible(payload.project_id, tenant_id):
        raise HTTPException(
            404, f"Project {payload.project_id} not found for this tenant"
        )

    try:
        row = await storage.create_candidate(
            project_id=payload.project_id,
            instance_id=payload.instance_id,
            source_path=payload.source_path,
            candidate_type=payload.candidate_type,
            status=payload.status,
            evidence_refs=payload.evidence_refs,
            signals=payload.signals,
            tenant_id=tenant_id,
        )
    except psycopg.errors.ForeignKeyViolation:
        # Race: project deleted between is_project_visible() and INSERT.
        # Rare but possible. Same 404 framing.
        raise HTTPException(
            404, f"Project {payload.project_id} not found for this tenant"
        )
    except psycopg.errors.CheckViolation as e:
        # CHECK constraint failed — should never happen because the
        # Pydantic Literal types match the SQL CHECK values exactly. If
        # it ever does, the Pydantic <-> SQL enum sync drifted; surface
        # as a 400 instead of leaking a 500.
        raise HTTPException(400, f"Invalid enum value: {e}")

    return row


@app.get("/candidates", response_model=models.CandidateList)
async def list_candidates(
    project_id: Optional[UUID] = None,
    status: Optional[models.STATUS] = None,
    source_path: Optional[models.SOURCE_PATH] = None,
    candidate_type: Optional[models.CANDIDATE_TYPE] = None,
    limit: int = 100,
    offset: int = 0,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    """List candidates, ordered by created_at DESC. Filters compose with
    AND. Tenant scoping is enforced via RLS, not via WHERE clause.

    The most common query shapes the upskilling surface needs:
      GET /candidates?status=stable                  — what's ready for promotion
      GET /candidates?status=promotion_requested     — what's awaiting governance
      GET /candidates?project_id=<uuid>              — per-project history
      GET /candidates?source_path=path_b             — platform-detected only
    """
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit must be between 1 and 500")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")

    rows = await storage.list_candidates(
        tenant_id=tenant_id,
        project_id=project_id,
        status=status,
        source_path=source_path,
        candidate_type=candidate_type,
        limit=limit,
        offset=offset,
    )
    return {"candidates": rows}


@app.get("/candidates/{candidate_id}", response_model=models.Candidate)
async def get_candidate(
    candidate_id: UUID,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    """Get one candidate by id. 404 if not found or if RLS hides it
    (other tenant)."""
    row = await storage.get_candidate(candidate_id, tenant_id)
    if not row:
        raise HTTPException(404, "Candidate not found")
    return row


@app.patch(
    "/candidates/{candidate_id}/status",
    response_model=models.Candidate,
)
async def update_candidate_status(
    candidate_id: UUID,
    payload: models.CandidateStatusUpdate,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    """Transition the candidate's status. The valid transitions are
    enforced LOOSELY at this phase — any source_status -> any target_status
    in the enum is accepted. Phase 5 (Policy Service) will tighten this
    with explicit transition rules; for now an operator can move a
    candidate back to 'observed' from 'rejected' if they want to retry.

    If `reason` is provided, an audit entry of shape
    `{kind: "status_change", from, to, reason}` is appended to
    `evidence_refs` for traceability.

    Auto-trigger: when the target status is 'promotion_requested' AND the
    candidate's candidate_type is 'skill', schedule a fastapi.BackgroundTask
    that calls promote_dispatcher.dispatch_promotion. The PATCH response is
    sent FIRST; the dispatch fires after, owned by Starlette's response
    cycle. Dispatch failure is logged and absorbed.

    Kind filter is skill-only because only kind=skill has an engine
    destination handler today (bridge_closed_end_to_end_2026_06_13). The
    8 other candidate kinds ack-defer; dispatching them pollutes promotion
    state.

    Tapestry-survival note: this trigger lives at the HTTP endpoint layer.
    If Tapestry's policy daemon writes status='promotion_requested' via the
    same PATCH endpoint, this code ports unchanged. If the policy daemon
    writes status directly to the DB or via a private storage API that
    bypasses the HTTP endpoint, this trigger MUST migrate (database
    trigger, domain-event handler, or post-commit hook in storage).
    """
    row = await storage.update_candidate_status(
        candidate_id, payload.status, tenant_id, reason=payload.reason
    )
    if not row:
        raise HTTPException(404, "Candidate not found")

    if payload.status == "promotion_requested" and row.get("candidate_type") == "skill":
        background_tasks.add_task(_dispatch_with_logging, candidate_id, tenant_id)

    return row


async def _dispatch_with_logging(candidate_id: UUID, tenant_id: str) -> None:
    """Background-task wrapper. Calls dispatcher; logs and absorbs failures.

    asyncio.CancelledError is BaseException (not Exception) and propagates
    correctly. DispatchError + CandidateNotFoundError are Exception
    subclasses and are absorbed here — the PATCH has already returned 200,
    so propagating them would surface nowhere useful.
    """
    try:
        await promote_dispatcher.dispatch_promotion(candidate_id, tenant_id)
    except Exception as exc:  # noqa: BLE001 — truly fire-and-forget
        logger.warning(
            "auto_dispatch_failed",
            extra={
                "candidate_id": str(candidate_id),
                "tenant_id": str(tenant_id),
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )


# ---------------------------------------------------------------------------
# Skill-making bridge — manual dispatch endpoint (PR B)
# ---------------------------------------------------------------------------


@app.post("/candidates/{candidate_id}/dispatch-promotion")
async def dispatch_promotion_endpoint(
    candidate_id: UUID,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    """Send the candidate to the Make_Skills engine via the skill-making
    bridge.

    Explicit/manual re-dispatch endpoint. Auto-trigger on status='promotion_requested'
    now lives in update_candidate_status (above) — see the BackgroundTasks block
    at the kind=skill filter. This endpoint remains for manual re-dispatch
    (e.g., after a transient engine failure caused the background task to
    log-and-absorb).

    Returns the engine's parsed ack response (typically:
    `{"promotion_id": "...", "status": "queued" | "duplicate" |
    "ack_deferred"}`). Status codes:

    - 200: engine accepted; body = engine's response
    - 404: candidate not found OR RLS-hidden from caller's tenant
    - 502: engine returned non-2xx OR transport error — body includes
      the engine status + response excerpt for debugging

    Per the bridge spec at Make_Skills `docs/proposals/2026-05-25-skill-
    making-bridge.md` + loom-memory bridge_sequencing_parallel_ratified_
    2026_06_12_evening.
    """
    try:
        ack = await promote_dispatcher.dispatch_promotion(candidate_id, tenant_id)
    except promote_dispatcher.CandidateNotFoundError:
        # Local: candidate doesn't exist OR RLS hides it from the caller's
        # tenant. Same response for both — privacy invariant.
        raise HTTPException(404, "Candidate not found in registry")
    except promote_dispatcher.DispatchError as e:
        # Engine-side failure (non-2xx response, transport error, or
        # malformed response). Surface as 502 with upstream context.
        # This is DISTINCT from CandidateNotFoundError; the engine
        # returning 404 (e.g., wrong route) used to be misclassified
        # as "Candidate not found" before the exception-type split.
        raise HTTPException(
            502,
            detail={
                "upstream_status": e.status,
                "upstream_body_excerpt": e.body[:500],
            },
        )
    return ack


# ---------------------------------------------------------------------------
# Skill-making bridge — registration ack receiver (PR C)
# ---------------------------------------------------------------------------


@app.post("/skill-registered")
async def receive_registration_ack(
    request: Request,
    x_makeskills_signature: Optional[str] = Header(None),
) -> dict:
    """Receive the engine's RegistrationAck callback. Engine-to-loom
    direction: NOT a user endpoint. Auth is via HMAC signature in
    `X-MakeSkills-Signature` header (NOT a Bearer JWT) — both sides share
    `LOOM_SKILL_BRIDGE_SECRET`.

    Per the spec at Make_Skills `docs/proposals/2026-05-25-skill-making-
    bridge.md` §2 + PR #69's ack-defer extension.

    Flow:

    1. Read raw body bytes BEFORE parsing — signature verification needs
       the exact bytes the engine sent
    2. Verify HMAC; 401 on any failure (missing/malformed/old/tampered)
    3. Parse `RegistrationAck`; 400 on Pydantic validation failure
    4. Apply the ack to the candidate via `registration_handler.apply_ack`
    5. Return 200 with the updated candidate row

    Status codes:

    - 200: ack applied; body = the updated candidate row
    - 400: malformed ack body (Pydantic validation failed)
    - 401: HMAC signature missing / malformed / outside timestamp window /
      mismatch (NO information about WHICH check failed leaks via body —
      defense against probing in hosted-multitenant)
    - 404: candidate referenced by `ack.promotion_id` is not visible
      under the v1.0 tenant scope (SELF_HOST_TENANT_ID self-host;
      hosted-multitenant gap tracked in registration_handler.py docstring)

    Tenant scope: v1.0 uses SELF_HOST_TENANT_ID for the storage call
    regardless of outcome. Rationale: the engine just acknowledges OUR
    promotion, the candidate is ours, RLS scopes correctly. Hosted-
    multitenant follow-up: derive tenant_id from `ack.skill.tenant_id`
    (when outcome=compiled) or from a bridge_dispatches lookup table
    (for non-compiled outcomes).
    """
    # Step 1: raw body BEFORE parsing.
    raw_body_bytes = await request.body()
    raw_body = raw_body_bytes.decode("utf-8")

    # Step 2: HMAC verify.
    try:
        bridge_hmac.verify_signature(raw_body, x_makeskills_signature)
    except bridge_hmac.BridgeAuthError:
        # NOTE: error detail intentionally generic. Don't leak whether
        # timestamp or signature was the failing check.
        raise HTTPException(401, "Invalid signature")

    # Step 3: parse.
    try:
        ack = bridge_models.RegistrationAck.model_validate_json(raw_body)
    except Exception as e:
        raise HTTPException(400, f"Malformed ack body: {e}")

    # Step 4: apply (self-host tenant scope).
    try:
        row = await registration_handler.apply_ack(
            ack, auth_bridge.SELF_HOST_TENANT_ID
        )
    except registration_handler.CandidateNotFoundError:
        raise HTTPException(
            404,
            f"Candidate referenced by promotion_id {ack.promotion_id} "
            f"not visible under current tenant scope",
        )

    return row
