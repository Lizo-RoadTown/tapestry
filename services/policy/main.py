"""
loom-policy — Phase 5 of the recursive-skill engine.

Operator/agent governance over candidate status transitions. Today the
Phase 2 observer auto-transitions draft -> observed -> recurring (purely
observational states). Higher transitions (recurring -> stable ->
promotion_requested -> promoted | rejected) need explicit policy
decisions before architecture-registry applies them.

This service is the audit-of-record for those decisions. It is
intentionally SOFT in this phase — it RECORDS decisions and exposes a
policy-state aggregate, but does NOT call architecture-registry to apply
them. The architecture-registry's PATCH /candidates/{id}/status remains
the write surface; a downstream caller (UI / future workflow agent)
reads policy-state, then issues the PATCH. This keeps the bounded-context
contract clean and lets us iterate the policy semantics without coupling
deploys.

Endpoints:
  POST /decisions                                  — record a decision
  GET  /decisions                                  — list (filters: candidate_id, decision_kind)
  GET  /candidates/{candidate_id}/policy-state     — aggregate over a candidate's decisions
  GET  /health                                     — Render health probe

Auth: per auth_bridge.verify_bearer's docstring — self-host (no header)
falls back to SELF_HOST_TENANT_ID; hosted-multitenant verifies RS256 with
LOOM_JWT_PUBLIC_KEY.

NOT included in this slice (per Liz's "don't overbuild" guidance):
  - Transition-rule enforcement (any kind/target accepted; the audit
    chain is the truth, semantics live downstream)
  - Cross-service candidate existence check (audit may reference a
    later-deleted candidate; this is by design — see migration header)
  - Background demotion scheduler (recurring -> demote on N-session
    silence). Phase 5+; today operators file demote decisions manually.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException

import auth_bridge
import models
import storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Pool opens lazily on first query; close cleanly on shutdown so the
    Render service drains pool members before the process exits."""
    yield
    await storage.close_pool()


app = FastAPI(
    title="loom-policy",
    version="0.1.0",
    description=(
        "Phase 5 of the recursive-skill engine: the Policy Service. "
        "Records operator/agent approval decisions over candidate status "
        "transitions. Audit-immutable by DB construction."
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
    pattern as services/architecture-registry/main.py."""
    return {"status": "ok", "service": "loom-policy"}


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


@app.post("/decisions", response_model=models.Decision, status_code=201)
async def create_decision(
    payload: models.DecisionCreate,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    """Record a new policy decision.

    Audit-immutable: once written, decisions can be SELECTed and DELETEd
    (with proper tenant scoping) but cannot be UPDATEd — the migration
    deliberately omits an UPDATE policy. If a decision needs revision,
    file a NEW decision that supersedes it (set
    `extra.supersedes = <old_decision_id>`).
    """
    try:
        row = await storage.create_decision(
            candidate_id=payload.candidate_id,
            decision_kind=payload.decision_kind,
            target_status=payload.target_status,
            reason=payload.reason,
            decided_by=payload.decided_by,
            extra=payload.extra,
            tenant_id=tenant_id,
        )
    except psycopg.errors.CheckViolation as e:
        # Should never happen because the Pydantic Literal types match
        # the SQL CHECK values exactly. If it does, the Pydantic <-> SQL
        # enum sync drifted; surface as 400 instead of leaking 500.
        raise HTTPException(400, f"Invalid enum value: {e}")

    return row


@app.get("/decisions", response_model=models.DecisionList)
async def list_decisions(
    candidate_id: Optional[UUID] = None,
    decision_kind: Optional[models.DECISION_KIND] = None,
    limit: int = 100,
    offset: int = 0,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    """List decisions, ordered by decided_at DESC. Filters compose with AND.
    Tenant scoping is enforced via RLS, not via WHERE clause.

    Common query shapes:
      GET /decisions?candidate_id=<uuid>           — full chain for one candidate
      GET /decisions?decision_kind=approve         — operator audit view
      GET /decisions?decision_kind=hold            — pending review queue
    """
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit must be between 1 and 500")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")

    rows = await storage.list_decisions(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        decision_kind=decision_kind,
        limit=limit,
        offset=offset,
    )
    return {"decisions": rows}


# ---------------------------------------------------------------------------
# Policy-state aggregate
# ---------------------------------------------------------------------------


@app.get(
    "/candidates/{candidate_id}/policy-state",
    response_model=models.PolicyState,
)
async def get_policy_state(
    candidate_id: UUID,
    tenant_id: str = Depends(auth_bridge.verify_bearer),
) -> dict:
    """Return the audit-chain aggregate for one candidate: summary +
    full decisions list.

    The summary fields (is_held, is_approved_for, is_rejected) are
    derived at read time from the latest decision; they're the "fast
    yes/no" view for downstream callers that need to gate a status
    transition.

    Returns an empty aggregate (decision_count=0, all flags false) if no
    decisions exist for this candidate — does NOT 404. A candidate with
    no decisions is a perfectly valid state ('the observer auto-handled
    it in the observational tier, no policy intervention yet'). The
    caller can distinguish "no decisions" from "candidate doesn't exist
    at all" by hitting architecture-registry's GET /candidates/{id}.
    """
    state = await storage.get_policy_state(candidate_id, tenant_id)
    return state
