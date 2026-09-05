"""Pydantic models for the Architecture Registry (candidate slice).

Mirrors the shape conventions in services/project-registry/models.py — keep
field names matching the SQL schema (infra/migrations/007_init_candidates.sql)
so storage.py can map rows -> dict -> Pydantic without renaming logic.

Two-mode commitment: same model shapes for self-host and hosted-multitenant.
The tenant_id is server-injected (from auth_bridge), never accepted from
the client body.

## Migration lineage (Tapestry)

In the-loom, candidate_type's CHECK evolved across three migrations
(003 init 4-kind → 005 rename → 006 expand to 9-kind). Tapestry consolidates
that terminal state into ONE migration, infra/migrations/007_init_candidates.sql,
which creates the candidates table already at the 9-kind CHECK. The LIVE
loom-postgres is already at the 9-kind state (the-loom's 006), so 007 is
idempotent and a no-op replay against it. The 9 kinds below MUST stay in
lockstep with 007's candidates_type_check.
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# CHECK-constraint enum values — keep in lockstep with
# infra/migrations/007_init_candidates.sql (all three CHECKs now live in that
# single consolidated migration):
#   - SOURCE_PATH        ← candidates_source_path_check
#   - CANDIDATE_TYPE     ← candidates_type_check (9 kinds)
#   - STATUS             ← candidates_status_check
#
# The 9 candidate_type kinds map 1:1 to docs/proposals/2026-06-12-promotion-
# categorization.md §4.1-§4.9. Adding a 10th kind requires (a) doc update in §4,
# (b) a new migration expanding this CHECK, (c) Pydantic Literal update here, and
# (d) test pointer update in test_candidate_invariants.py.
SOURCE_PATH = Literal["path_a", "path_b"]
CANDIDATE_TYPE = Literal[
    "skill",                  # §4.1
    "inline_tool",            # §4.2 (renamed from 'tool' in the-loom migration 006)
    "external_tool",          # §4.3
    "architecture_pattern",   # §4.4
    "service",                # §4.5
    "machine_support",        # §4.6
    "process",                # §4.7
    "agent",                  # §4.8
    "orchestration",          # §4.9
]
STATUS = Literal[
    "draft", "observed", "recurring", "stable",
    "promotion_requested", "promoted", "rejected",
]


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------


class CandidateCreate(BaseModel):
    """POST /candidates body. Tenant_id NOT accepted from the client —
    it's resolved server-side via auth_bridge."""

    model_config = ConfigDict(extra="forbid")

    project_id: UUID = Field(
        ..., description="The project this candidate belongs to. Must be visible to caller's tenant."
    )
    instance_id: str = Field(
        default="",
        max_length=128,
        description="The .project-intelligence/ folder content hash that emitted this. Empty for Path B candidates.",
    )
    source_path: SOURCE_PATH = Field(
        ..., description="path_a (local observer) | path_b (platform observatory)."
    )
    candidate_type: CANDIDATE_TYPE = Field(
        ...,
        description=(
            "One of the 9 kinds from docs/proposals/2026-06-12-promotion-"
            "categorization.md §4: skill | inline_tool | external_tool | "
            "architecture_pattern | service | machine_support | process | "
            "agent | orchestration."
        ),
    )
    status: STATUS = Field(
        default="draft",
        description="Lifecycle state. New candidates almost always start at 'draft'.",
    )
    evidence_refs: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Pointers to evidence backing the candidate. Shape evolves with the "
            "observer; Phase 2 expected entries like "
            "{kind: 'memory_record', id: 'feedback_...'} or "
            "{kind: 'telemetry_event', trace_id: '...'}."
        ),
    )
    signals: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Computed promotion-threshold signals per "
            "docs/proposals/2026-05-25-agency-optimizer-pattern.md:207-216. "
            "Includes repeated_across_sessions, repeated_across_tasks, "
            "repeated_across_projects, has_clear_triggers, has_stable_steps, "
            "has_stable_outputs, reduces_need_for_live_judgment."
        ),
    )


class CandidateStatusUpdate(BaseModel):
    """PATCH /candidates/{id}/status body — narrow surface: only the
    status field is mutable through this endpoint. Evidence + signals
    get amended via a separate future endpoint when needed."""

    model_config = ConfigDict(extra="forbid")

    status: STATUS
    reason: Optional[str] = Field(
        default=None,
        max_length=1024,
        description=(
            "Optional free-form reason for the transition. Persisted alongside "
            "the status change for auditability (added to evidence_refs as a "
            "{kind: 'status_change', from, to, reason, ts} entry)."
        ),
    )


class Candidate(BaseModel):
    """Full candidate row as returned by GET / POST / PATCH responses."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    project_id: UUID
    instance_id: str
    source_path: SOURCE_PATH
    candidate_type: CANDIDATE_TYPE
    status: STATUS
    evidence_refs: list[dict[str, Any]]
    signals: dict[str, Any]
    tenant_id: UUID
    created_at: float
    updated_at: float


class CandidateList(BaseModel):
    """GET /candidates response envelope."""

    candidates: list[Candidate]
