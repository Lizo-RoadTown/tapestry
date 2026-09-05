"""Pydantic models for the skill-making bridge (the-loom → Make_Skills engine).

Per the spec at Make_Skills `docs/proposals/2026-05-25-skill-making-bridge.md`
+ Loom-agent's 5 ratification adjustments (loom-memory:
loom_agent_skill_bridge_ratification_2026_06_12_evening) + MS-agent's PR #69
incorporation (loom-memory: ms_agent_phase_4_sketch_updated_pr_69_2026_06_12).

Three message types:

1. PromotionCandidate — the-loom → engine. "This pattern is stable; here's
   the source material."
2. RegistrationAck — engine → the-loom. "Compiled (or rejected); here's the
   skill_id (or diagnostics)."
3. TelemetryBatch — engine → the-loom. "These skills ran in these threads
   with these outcomes."

## Adjustments baked in (vs the original spec)

- `tenant_id` is required UUID (not nullable). For self-host this is the
  canonical SELF_HOST_TENANT_ID (1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8).
- `candidate_kind` at top level of PromotionCandidate. v1.0 receiver
  handles `kind="skill"` fully; other kinds get ack-defer (status
  "kind_not_yet_handled").
- `source.frontmatter` requires only `{name, description}`. capability_tags
  + triggers are derived from observer signals by promote_dispatcher and
  injected separately as `derived_metadata` at top level.
- Callback URLs default to Render service URLs:
    registration_ack → https://loom-architecture-registry.onrender.com/skill-registered
    telemetry_endpoint → https://loom-telemetry-ingestion.onrender.com/skill-used

## What this module does NOT do

- HMAC signing / verification (lives in bridge_hmac.py)
- Sending requests (lives in promote_dispatcher.py — future PR)
- Receiving requests (lives in registration_handler.py + skill_usage_handler.py
  — future PRs)

This is the wire-contract schema layer only. The engine side has the
mirror image in Make_Skills `services/skill_making/bridge_models.py` (or
equivalent); both sides must agree on field names + types.
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Per docs/proposals/2026-06-12-promotion-categorization.md §4 (the 9-kind
# taxonomy), matches services/architecture-registry/models.py CANDIDATE_TYPE.
CANDIDATE_KIND = Literal[
    "skill",
    "inline_tool",
    "external_tool",
    "architecture_pattern",
    "service",
    "machine_support",
    "process",
    "agent",
    "orchestration",
]

# Receiver outcomes per the spec §2 + PR #69's ack-defer extension.
ACK_OUTCOME = Literal[
    "compiled",
    "rejected",
    "queued_human_review",
    "ack_deferred",  # PR #69 ack-defer for non-skill kinds in v1.0
]

# Telemetry outcomes per the spec §3.
TELEMETRY_OUTCOME = Literal["success", "error", "timeout"]

# The wire-contract version. The receiver advertises supported versions at
# GET /access/webhook/skill-promotion/versions. Both sides must agree.
SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# 1. PromotionCandidate (the-loom → engine)
# ---------------------------------------------------------------------------


class CandidateSourceFrontmatter(BaseModel):
    """Required frontmatter on the source markdown. Adjustment #2: only
    name + description are required; capability_tags + triggers are
    derived by promote_dispatcher and live in derived_metadata."""

    model_config = ConfigDict(extra="forbid")

    # Match engine's models.py:SourceFrontmatter caps (name 120, desc 500).
    # Engine has extra='forbid'; we must too.
    name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Suggested skill name. May be renamed on conflict.",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="One-line summary for the skill catalog.",
    )


class CandidateSource(BaseModel):
    """Matches engine's models.py:CandidateSource exactly. NO `format` field
    (engine `extra='forbid'` rejects it). Field name is `body_md` not
    `content`. See loom-memory: lesson_third_spec_drift_payload_schema_2026_06_13."""

    model_config = ConfigDict(extra="forbid")

    frontmatter: CandidateSourceFrontmatter
    body_md: str = Field(
        ...,
        min_length=1,
        description="The skill source body (markdown).",
    )


class EvidenceRef(BaseModel):
    """Single piece of evidence the-loom's observer collected. Matches
    engine's models.py:EvidenceRef."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(..., description="Evidence kind (e.g. 'skill_invocation_count').")
    ref: str = Field(..., description="Reference to the evidence source.")
    captured_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp when captured. Optional.",
    )


class Signals(BaseModel):
    """Observer-computed signals that drove promotion. Engine's model has
    extra='allow' (NOT forbid) — flexibility point for loom-side fields."""

    model_config = ConfigDict(extra="allow")

    skill_name: Optional[str] = None
    repeat_count: Optional[int] = None


class CandidateCallbacks(BaseModel):
    """URLs the engine POSTs back to. Field name is `telemetry` (NOT
    `telemetry_endpoint`) to match engine's models.py:Callbacks."""

    model_config = ConfigDict(extra="forbid")

    registration_ack: str = Field(
        ...,
        description="Engine POSTs the ack here (HMAC-signed).",
    )
    telemetry: str = Field(
        ...,
        description="Engine POSTs telemetry batches here (HMAC-signed).",
    )


class PromotionCandidate(BaseModel):
    """the-loom → engine. POST {engine}/bridge/promotion-candidate.

    Signed with HMAC-SHA256 of (timestamp + body) in X-Loom-Signature, Stripe-
    style header format `t=<unix>,v1=<hex>`.

    Field shape matches engine's models.py:PromotionCandidatePayload EXACTLY.
    The engine's models.py is the canonical wire contract (per coordinated
    alignment with MS-agent, 2026-06-13). Any divergence here breaks the
    bridge with HTTP 400 schema_invalid.

    Critical departures from the original 2026-05-25 wire spec doc:
    - `promoted_at` REMOVED (engine extra='forbid' rejects it)
    - `source.format` REMOVED
    - `source.content` → `source.body_md`
    - `derived_metadata.{capability_tags,triggers}` MOVED to top-level
    - `evidence` object REPLACED with `evidence_refs: list[EvidenceRef]`
    - `signals` ADDED at top-level
    - `source_system: "loom"` + `is_global: False` ADDED
    - `callbacks.telemetry_endpoint` → `callbacks.telemetry`
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default=SCHEMA_VERSION,
        pattern=r"^\d+\.\d+$",
        description="Wire contract version.",
    )
    promotion_id: UUID = Field(
        ...,
        description="Unique per candidate; the-loom-generated; dedup key.",
    )
    tenant_id: UUID = Field(
        ...,
        description=(
            "Adjustment #1: REQUIRED, not nullable. Source-side UUID; "
            "engine resolves via tenant_id_mapping table (Option B). "
            "SELF_HOST_TENANT_ID for self-host."
        ),
    )
    source_system: str = Field(
        default="loom",
        description="Identifies the source platform (always 'loom' for the-loom).",
    )
    is_global: bool = Field(
        default=False,
        description="True iff this candidate is a global (cross-tenant) skill candidate.",
    )
    candidate_kind: CANDIDATE_KIND = Field(
        ...,
        description=(
            "Adjustment #3: top-level kind from the 9-kind taxonomy. v1.0 "
            "receiver handles 'skill' fully; others get ack-defer."
        ),
    )
    pattern_signature: str = Field(
        ...,
        min_length=1,
        description="Semantic dedup key; same signature = same pattern.",
    )
    source: CandidateSource
    evidence_refs: list[EvidenceRef] = Field(
        default_factory=list,
        description="Observer-collected evidence refs (list of {kind, ref, captured_at}).",
    )
    signals: Signals = Field(
        default_factory=Signals,
        description="Observer-computed signals (skill_name, repeat_count, free-form fields).",
    )
    capability_tags: list[str] = Field(
        default_factory=list,
        description=(
            "Adjustment #2: TOP-LEVEL (NOT in source.frontmatter). Derived from "
            "observer signals by promote_dispatcher."
        ),
    )
    triggers: list[str] = Field(
        default_factory=list,
        description=(
            "Adjustment #2: TOP-LEVEL (NOT in source.frontmatter). Derived from "
            "observer signals by promote_dispatcher."
        ),
    )
    callbacks: CandidateCallbacks


class PromotionCandidateAck(BaseModel):
    """Engine's immediate 202 response to a promotion candidate POST."""

    model_config = ConfigDict(extra="forbid")

    promotion_id: UUID
    status: Literal["queued", "duplicate", "ack_deferred"] = Field(
        ...,
        description=(
            "queued = will be compiled; duplicate = pattern_signature already "
            "promoted (see PromotionCandidateAckConflict); ack_deferred = "
            "non-skill kind in v1.0, candidate recorded but no compile."
        ),
    )


# ---------------------------------------------------------------------------
# 2. RegistrationAck (engine → the-loom)
# ---------------------------------------------------------------------------


class AckSkillDetails(BaseModel):
    """Matches engine's models.py:AckSkill EXACTLY. No `skill_source_location`
    (engine doesn't send it; spec doc said it would but implementation chose
    not to). See loom-memory: lesson_third_spec_drift_payload_schema_2026_06_13."""

    model_config = ConfigDict(extra="forbid")

    skill_id: UUID = Field(..., description="Engine's permanent skill ID.")
    name: str = Field(..., description="Final skill name; may differ from suggested.")
    version: str = Field(
        ...,
        description="Semver; bumps on every recompile.",
    )
    source_origin: str = Field(
        default="promoted",
        description="Engine sends 'promoted' for bridge-promoted skills.",
    )
    capability_tags: list[str] = Field(default_factory=list)
    tenant_id: UUID = Field(
        ...,
        description=(
            "Source-side tenant UUID (the-loom's UUID), echoed back. "
            "Engine does NOT send its own engine_tenant_id (Option B mapping)."
        ),
    )
    compiled_at: str = Field(..., description="ISO 8601 timestamp.")


class AckCompilationDiagnostics(BaseModel):
    """Matches engine's models.py:AckDiagnostics EXACTLY. Engine sends
    `errors` and `warnings` as `list[dict[str, str]]` — plain dicts, NOT
    structured Pydantic objects. The handler accesses them as
    `errors[0]["message"]` not `errors[0].message`.

    The dicts typically carry `phase` + `message` keys per the compiler's
    wrapping logic, but the schema doesn't enforce that — engine could
    add other keys per-error without contract violation."""

    model_config = ConfigDict(extra="forbid")

    errors: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[dict[str, str]] = Field(default_factory=list)


class AckTheLoomMetadata(BaseModel):
    """Echoed back so the-loom can update its index without keeping a
    separate join table."""

    model_config = ConfigDict(extra="forbid")

    pattern_signature: str
    promotion_id: UUID


class RegistrationAck(BaseModel):
    """engine → the-loom. POST {callbacks.registration_ack}.

    Signed with HMAC-SHA256 in X-MakeSkills-Signature.
    """

    model_config = ConfigDict(extra="forbid")

    promotion_id: UUID = Field(..., description="Echoed from the candidate; idempotency key.")
    schema_version: Literal["1.0"] = Field(default=SCHEMA_VERSION)
    registered_at: str = Field(..., description="ISO 8601 timestamp.")
    outcome: ACK_OUTCOME
    skill: Optional[AckSkillDetails] = Field(
        default=None,
        description="Present iff outcome='compiled'.",
    )
    compilation_diagnostics: Optional[AckCompilationDiagnostics] = Field(
        default=None,
        description="Present iff outcome in {'rejected', 'queued_human_review'}.",
    )
    the_loom_metadata: AckTheLoomMetadata


# ---------------------------------------------------------------------------
# 3. TelemetryBatch (engine → the-loom)
# ---------------------------------------------------------------------------


class TelemetryEvent(BaseModel):
    """Per-invocation telemetry. Privacy: NO message content, NO response
    content, NO PII. Structural metadata only."""

    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
    thread_id: UUID = Field(
        ...,
        description="Engine's thread, NOT consumer's user_id.",
    )
    tenant_id: UUID = Field(
        ...,
        description="Adjustment #1: required, not nullable.",
    )
    invoked_at: str = Field(..., description="ISO 8601 timestamp.")
    outcome: TELEMETRY_OUTCOME
    latency_ms: int = Field(..., ge=0)
    tokens_in: int = Field(..., ge=0)
    tokens_out: int = Field(..., ge=0)
    model: str = Field(
        ...,
        description="Model identifier, e.g. 'claude-opus-4-7'.",
    )
    trigger_context: str = Field(
        ...,
        max_length=64,
        description=(
            "Short CATEGORICAL tag, NOT the message text. e.g. "
            "'user message', 'autonomous loop tick'."
        ),
    )


class TelemetryBatch(BaseModel):
    """engine → the-loom. POST {callbacks.telemetry_endpoint}.

    Signed with HMAC-SHA256. Up to 1000 events per batch.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = Field(default=SCHEMA_VERSION)
    batch_id: UUID = Field(..., description="Dedup key for the batch.")
    events: list[TelemetryEvent] = Field(
        ...,
        min_length=1,
        max_length=1000,
    )


# ---------------------------------------------------------------------------
# Error envelope (for 400/401/409 responses)
# ---------------------------------------------------------------------------


class BridgeFieldError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    issue: str


class BridgeErrorResponse(BaseModel):
    """400 Bad Request body — list of field-level errors. Other failures
    (401 invalid signature, 503 engine maintenance) use plain HTTP status
    with no body."""

    model_config = ConfigDict(extra="forbid")

    errors: list[BridgeFieldError] = Field(..., min_length=1)


class BridgeDuplicateResponse(BaseModel):
    """409 Conflict body — pattern_signature already promoted to skill_id."""

    model_config = ConfigDict(extra="forbid")

    promotion_id: UUID
    existing_skill_id: UUID
