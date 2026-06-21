"""Wire-contract pydantic models for the skill-making bridge.

Per `docs/proposals/2026-05-25-skill-making-bridge.md` (the wire contract)
and `docs/proposals/2026-06-12-bridge-receiver-and-compiler-phase-4-sketch.md`
(the receiver design, revised 2026-06-12 to incorporate Loom-agent's 5
ratification adjustments).

The `tenant_id` field carries the SOURCE side's tenant UUID (e.g. the
loom's `1d8ec1b3-...`). The receiver looks it up in `tenant_id_mapping`
to get the engine-side UUID before persisting. See
`decision_tenant_id_mapping_option_b_2026_06_12` in loom-memory for the
reasoning.
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CandidateKind(str, Enum):
    """The 9-kind promotion-candidate taxonomy.

    v1.0 receiver fully handles `SKILL`; the other 8 kinds are
    ack-deferred (recorded with status='kind_not_yet_handled', 202
    returned, no compile dispatch) so the audit chain stays intact
    while handlers ship in v1.1+.
    """

    SKILL = "skill"
    INLINE_TOOL = "inline_tool"
    EXTERNAL_TOOL = "external_tool"
    ARCHITECTURE_PATTERN = "architecture_pattern"
    SERVICE = "service"
    MACHINE_SUPPORT = "machine_support"
    PROCESS = "process"
    AGENT = "agent"
    ORCHESTRATION = "orchestration"


class SourceFrontmatter(BaseModel):
    """The minimal frontmatter we require in the candidate's SKILL.md.

    Per Loom-agent adjustment #2: capability_tags + triggers are NOT
    required here. The-loom's promote_dispatcher derives them from
    observer signals and injects them into the top-level payload's
    `capability_tags` + `triggers` fields. Frontmatter just needs the
    human-readable name + description.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)


class CandidateSource(BaseModel):
    """The SKILL.md source + its frontmatter."""

    model_config = ConfigDict(extra="forbid")

    frontmatter: SourceFrontmatter
    body_md: str = Field(min_length=1)


class EvidenceRef(BaseModel):
    """A single piece of evidence the-loom's observer collected to
    justify this candidate."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    ref: str
    captured_at: str | None = None


class Signals(BaseModel):
    """Observer-computed signals that drove promotion.

    capability_tags and triggers in the TOP-LEVEL payload are derived
    from these by the-loom's promote_dispatcher per adjustment #2.
    """

    model_config = ConfigDict(extra="allow")

    skill_name: str | None = None
    repeat_count: int | None = None


class Callbacks(BaseModel):
    """URLs the engine POSTs back to.

    Per Loom-agent adjustment #4: these point at the Render services,
    NOT the dashboard's Vercel hostname. Env-var configurable on the
    engine side via LOOM_REGISTRATION_ACK_URL + LOOM_TELEMETRY_CALLBACK_URL.
    """

    model_config = ConfigDict(extra="forbid")

    registration_ack: str
    telemetry: str


class PromotionCandidatePayload(BaseModel):
    """The wire-contract payload the-loom POSTs to /bridge/promotion-candidate.

    Per the 2026-06-12 ratification:
      - tenant_id is NON-NULLABLE UUID (adjustment #1)
      - is_global is a separate flag for catalog-scope (adjustment #1)
      - candidate_kind is the 9-kind taxonomy (adjustment #3)
      - capability_tags + triggers are derived (adjustment #2)
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    promotion_id: UUID
    tenant_id: UUID
    source_system: str = "loom"
    is_global: bool = False
    candidate_kind: CandidateKind
    pattern_signature: str = Field(min_length=1)
    source: CandidateSource
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    signals: Signals = Field(default_factory=Signals)
    capability_tags: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    callbacks: Callbacks


class ReceiverResponse(BaseModel):
    """The 202 body the receiver returns on accepted candidates."""

    model_config = ConfigDict(extra="forbid")

    promotion_id: UUID
    status: str
    outcome: str | None = None
    reason: str | None = None


class BridgeErrorCode(str, Enum):
    HMAC_INVALID = "hmac_invalid"
    SCHEMA_INVALID = "schema_invalid"
    DUPLICATE_PROMOTION_ID = "duplicate_promotion_id"
    UNKNOWN_SOURCE_TENANT = "unknown_source_tenant"


class BridgeError(BaseModel):
    """Structured error body the receiver returns on rejected POSTs."""

    model_config = ConfigDict(extra="forbid")

    code: BridgeErrorCode
    message: str
    details: dict[str, Any] | None = None


class CompileOutcome(str, Enum):
    COMPILED = "compiled"
    REJECTED = "rejected"
    QUEUED_HUMAN_REVIEW = "queued_human_review"


class AckSkill(BaseModel):
    """The compiled-skill block inside a registration ack. Present when
    outcome == 'compiled'. Per the wire contract section 2."""

    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
    name: str
    version: str
    source_origin: str = "promoted"
    capability_tags: list[str] = Field(default_factory=list)
    tenant_id: UUID
    compiled_at: str  # ISO 8601


class AckDiagnostics(BaseModel):
    """Diagnostics block when outcome != 'compiled'."""

    model_config = ConfigDict(extra="forbid")

    errors: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[dict[str, str]] = Field(default_factory=list)


class AckLoomMetadata(BaseModel):
    """The-loom's audit metadata echoed back per the wire contract."""

    model_config = ConfigDict(extra="forbid")

    pattern_signature: str
    promotion_id: UUID


class RegistrationAck(BaseModel):
    """The engine -> loom callback body after compile completes (or fails).

    POSTed to `LOOM_REGISTRATION_ACK_URL` (defaults to
    https://loom-architecture-registry.onrender.com/skill-registered).
    Signed with `X-MakeSkills-Signature` header in the same Stripe-style
    format the inbound POSTs use.

    Per wire contract section 2.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    promotion_id: UUID
    registered_at: str  # ISO 8601
    outcome: CompileOutcome
    skill: AckSkill | None = None
    compilation_diagnostics: AckDiagnostics | None = None
    the_loom_metadata: AckLoomMetadata
