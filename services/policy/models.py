"""Pydantic models for the Policy Service (Phase 5 decisions slice).

Mirrors the shape conventions in services/architecture-registry/models.py
and services/project-registry/models.py — keep field names matching the
SQL schema (infra/migrations/004_init_policy.sql) so storage.py can map
rows -> dict -> Pydantic without renaming logic.

Two-mode commitment: same model shapes for self-host and hosted-multitenant.
tenant_id is server-injected (from auth_bridge), never accepted from the
client body — extra='forbid' on inbound models enforces this.
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# CHECK-constraint enum values — keep in lockstep with
# infra/migrations/004_init_policy.sql (policy_decisions_kind_check +
# policy_decisions_target_status_check). The target_status enum mirrors
# candidates.status from infra/migrations/007_init_candidates.sql
# (candidates_status_check), so the Policy Service can authorize
# transitions named in the candidates vocabulary. The cross-service match
# is pinned by tests/test_policy_invariants.py::
# test_target_status_matches_candidates_status.
DECISION_KIND = Literal["approve", "reject", "hold", "demote"]
TARGET_STATUS = Literal[
    "draft", "observed", "recurring", "stable",
    "promotion_requested", "promoted", "rejected",
]


# ---------------------------------------------------------------------------
# Decision — POST + response shape
# ---------------------------------------------------------------------------


class DecisionCreate(BaseModel):
    """POST /decisions body. Tenant_id NOT accepted from the client —
    resolved server-side via auth_bridge."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID = Field(
        ..., description="The candidate this decision applies to. UUID matches candidates.id."
    )
    decision_kind: DECISION_KIND = Field(
        ..., description="approve | reject | hold | demote"
    )
    target_status: Optional[TARGET_STATUS] = Field(
        default=None,
        description=(
            "The candidate status this decision authorizes. NULL for 'hold' "
            "decisions (pause without specifying target). For 'demote' "
            "decisions, names the new (lower or 'rejected') status."
        ),
    )
    reason: str = Field(
        default="",
        max_length=4096,
        description="Operator-supplied rationale. Persisted for auditability.",
    )
    decided_by: str = Field(
        default="operator",
        max_length=128,
        description=(
            "Who made the decision. 'operator' (default), 'system:auto', "
            "or 'agent:<kind>' for agent-recorded decisions."
        ),
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Forward-compat slot for {parent_decision_id, supersedes, "
            "reviewed_by_chain, escalation_ref}. Stored as JSONB."
        ),
    )


class Decision(BaseModel):
    """Full policy_decisions row as returned by POST + GET responses."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    candidate_id: UUID
    decision_kind: DECISION_KIND
    target_status: Optional[TARGET_STATUS]
    reason: str
    decided_by: str
    decided_at: float
    tenant_id: UUID
    extra: dict[str, Any]


class DecisionList(BaseModel):
    """GET /decisions response envelope."""

    decisions: list[Decision]


# ---------------------------------------------------------------------------
# Policy-state aggregate (read-side convenience)
# ---------------------------------------------------------------------------


class PolicyStateSummary(BaseModel):
    """Per-candidate aggregate of decision history. Computed at read time
    by GET /candidates/{candidate_id}/policy-state — NOT a stored table.

    The aggregate is what downstream callers (eventually the upskilling
    dashboard, eventually architecture-registry's promotion-governance
    logic) use to decide 'should this status transition be allowed?'
    """

    candidate_id: UUID = Field(..., description="The candidate this state describes.")
    decision_count: int = Field(..., description="Number of decisions on file.")
    latest_kind: Optional[DECISION_KIND] = Field(
        default=None,
        description="The most recent decision's kind. None if no decisions yet.",
    )
    latest_target_status: Optional[TARGET_STATUS] = Field(
        default=None,
        description="The most recent decision's target_status. None for hold or no decisions.",
    )
    is_held: bool = Field(
        ..., description="True iff the most recent decision is a non-superseded 'hold'."
    )
    is_approved_for: Optional[TARGET_STATUS] = Field(
        default=None,
        description=(
            "The status this candidate is currently approved to advance to. "
            "Computed as: most recent 'approve' decision's target_status, unless "
            "superseded by a later reject/hold/demote."
        ),
    )
    is_rejected: bool = Field(
        ...,
        description=(
            "True iff the most recent non-superseded decision is 'reject'. "
            "Equivalent to: candidate is currently blocked from advancing."
        ),
    )


class PolicyState(BaseModel):
    """GET /candidates/{candidate_id}/policy-state response.

    Pairs the summary with the full decision chain for auditability. The
    UI can render the chain as a timeline; backends can use the summary
    for fast yes/no transition checks.
    """

    summary: PolicyStateSummary
    decisions: list[Decision]
