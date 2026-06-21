"""Pin the wire-contract pydantic schema shape.

Per `loom_agent_to_ms_agent_coordinated_alignment_plan_2026_06_13`,
`services/skill_making/models.py` is the canonical wire contract.
These tests pin the EXACT field placement (top-level vs nested) and
field names so any future drift caught by Loom-agent in
`lesson_third_spec_drift_payload_schema_2026_06_13` becomes a test
failure here BEFORE the bridge breaks at runtime.

Any change to these tests requires a coordinated change on the loom
side's `bridge_models.py` AND an annotated entry in
`docs/proposals/2026-05-25-skill-making-bridge.md`.
"""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from skill_making.models import (
    AckSkill,
    BridgeError,
    BridgeErrorCode,
    CandidateKind,
    CompileOutcome,
    PromotionCandidatePayload,
    RegistrationAck,
)


def _valid_candidate_dict() -> dict:
    """Minimum valid PromotionCandidatePayload as a dict."""
    return {
        "schema_version": "1.0",
        "promotion_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "source_system": "loom",
        "is_global": False,
        "candidate_kind": "skill",
        "pattern_signature": "test-sig",
        "source": {
            "frontmatter": {
                "name": "test-skill",
                "description": "a test",
            },
            "body_md": "# test",
        },
        "evidence_refs": [],
        "signals": {},
        "capability_tags": [],
        "triggers": [],
        "callbacks": {
            "registration_ack": "https://example.com/ack",
            "telemetry": "https://example.com/telemetry",
        },
    }


def test_valid_payload_parses():
    payload = PromotionCandidatePayload.model_validate(_valid_candidate_dict())
    assert payload.candidate_kind == CandidateKind.SKILL


def test_tenant_id_is_non_nullable():
    """Pin Option B: tenant_id is non-nullable UUID.

    Loom-agent's lesson_third_spec_drift caught this drift. Catalog
    scope is the separate `is_global` flag.
    """
    d = _valid_candidate_dict()
    d["tenant_id"] = None
    with pytest.raises(ValidationError):
        PromotionCandidatePayload.model_validate(d)


def test_is_global_is_separate_from_tenant_id():
    d = _valid_candidate_dict()
    d["is_global"] = True
    payload = PromotionCandidatePayload.model_validate(d)
    assert payload.is_global is True
    assert payload.tenant_id is not None


def test_candidate_kind_required_top_level():
    """Pin: candidate_kind is a top-level field, not nested in source."""
    d = _valid_candidate_dict()
    del d["candidate_kind"]
    with pytest.raises(ValidationError):
        PromotionCandidatePayload.model_validate(d)


def test_candidate_kind_accepts_all_9_kinds():
    """Pin the full 9-kind taxonomy."""
    for kind in (
        "skill",
        "inline_tool",
        "external_tool",
        "architecture_pattern",
        "service",
        "machine_support",
        "process",
        "agent",
        "orchestration",
    ):
        d = _valid_candidate_dict()
        d["candidate_kind"] = kind
        payload = PromotionCandidatePayload.model_validate(d)
        assert payload.candidate_kind.value == kind


def test_candidate_kind_rejects_unknown():
    d = _valid_candidate_dict()
    d["candidate_kind"] = "not-a-kind"
    with pytest.raises(ValidationError):
        PromotionCandidatePayload.model_validate(d)


def test_capability_tags_top_level_not_in_frontmatter():
    """Pin Loom-agent adjustment #2: derived fields are top-level."""
    d = _valid_candidate_dict()
    d["capability_tags"] = ["search", "tagged"]
    payload = PromotionCandidatePayload.model_validate(d)
    assert payload.capability_tags == ["search", "tagged"]


def test_frontmatter_extra_fields_rejected():
    """Pin: SourceFrontmatter is extra='forbid'. capability_tags + triggers
    are NOT in frontmatter (they're top-level per adjustment #2)."""
    d = _valid_candidate_dict()
    d["source"]["frontmatter"]["capability_tags"] = ["wrong-place"]
    with pytest.raises(ValidationError):
        PromotionCandidatePayload.model_validate(d)


def test_source_body_md_field_name():
    """Pin: source.body_md (NOT source.content). Was the drift in lesson #3."""
    d = _valid_candidate_dict()
    d["source"]["content"] = d["source"].pop("body_md")
    with pytest.raises(ValidationError):
        PromotionCandidatePayload.model_validate(d)


def test_source_format_field_rejected():
    """Pin: source.format does NOT exist on engine side. Loom dropped this
    from their model per the coordinated plan."""
    d = _valid_candidate_dict()
    d["source"]["format"] = "markdown"
    with pytest.raises(ValidationError):
        PromotionCandidatePayload.model_validate(d)


def test_callbacks_field_names():
    """Pin: callbacks.telemetry (NOT telemetry_endpoint). Was the drift."""
    d = _valid_candidate_dict()
    d["callbacks"] = {
        "registration_ack": "https://example.com/ack",
        "telemetry_endpoint": "https://example.com/telemetry",
    }
    with pytest.raises(ValidationError):
        PromotionCandidatePayload.model_validate(d)


def test_top_level_extra_field_rejected():
    """Pin: extra='forbid' at the top level — drift is loud, not silent."""
    d = _valid_candidate_dict()
    d["some_new_field"] = "drift!"
    with pytest.raises(ValidationError):
        PromotionCandidatePayload.model_validate(d)


def test_registration_ack_skill_tenant_id_required_when_compiled():
    """Pin: AckSkill.tenant_id is non-nullable UUID. Per
    loom_agent_bridge_complete_status_and_secret memo: the-loom scopes
    by source UUIDs; ack must carry source_tenant_id, not engine's UUID."""
    skill = AckSkill(
        skill_id=uuid.uuid4(),
        name="test",
        version="0.1.0",
        source_origin="promoted",
        capability_tags=[],
        tenant_id=uuid.uuid4(),
        compiled_at="2026-06-13T00:00:00+00:00",
    )
    ack = RegistrationAck(
        promotion_id=uuid.uuid4(),
        registered_at="2026-06-13T00:00:00+00:00",
        outcome=CompileOutcome.COMPILED,
        skill=skill,
        the_loom_metadata={
            "pattern_signature": "sig",
            "promotion_id": str(uuid.uuid4()),
        },
    )
    assert ack.skill is not None
    assert ack.skill.tenant_id is not None


def test_bridge_error_code_enum_exhaustive():
    """Pin: 4 known error codes. Adding a new one requires bridge spec
    update on both sides."""
    assert set(BridgeErrorCode) == {
        BridgeErrorCode.HMAC_INVALID,
        BridgeErrorCode.SCHEMA_INVALID,
        BridgeErrorCode.DUPLICATE_PROMOTION_ID,
        BridgeErrorCode.UNKNOWN_SOURCE_TENANT,
    }


def test_compile_outcome_enum_exhaustive():
    """Pin: 3 wire-contract outcomes. (`ack_deferred` is a receiver-side
    response_body status, not a CompileOutcome — non-skill kinds don't
    invoke the compiler at all.)"""
    assert set(CompileOutcome) == {
        CompileOutcome.COMPILED,
        CompileOutcome.REJECTED,
        CompileOutcome.QUEUED_HUMAN_REVIEW,
    }


def test_bridge_error_extra_rejected():
    """Pin: BridgeError is extra='forbid'."""
    with pytest.raises(ValidationError):
        BridgeError.model_validate(
            {"code": "hmac_invalid", "message": "x", "extra_field": "no"}
        )
