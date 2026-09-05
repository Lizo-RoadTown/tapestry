"""Invariant tests for the skill-making bridge wire contract.

Per loom-memory bridge_sequencing_parallel_ratified_2026_06_12_evening — PR A
of the loom-side bridge build. No runtime endpoints exist yet; this test file
pins the schema + HMAC layer so the engine side and loom side can build
against the same shapes independently.

Three invariant groups:

1. **bridge_models** shape — Pydantic validates the spec's adjustments
2. **HMAC sign/verify** roundtrip + tamper detection + replay window
3. **CANDIDATE_KIND ↔ CANDIDATE_TYPE cross-service sync** — the bridge's
   9-kind enum must match the architecture-registry's candidates table CHECK
   (drift here would let the dashboard accept a candidate kind the bridge
   can't represent, or vice versa)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest


_SVC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC))

import bridge_hmac  # noqa: E402
import bridge_models  # noqa: E402
import models  # noqa: E402  — for the CANDIDATE_TYPE sync test


CANONICAL_SELF_HOST_TENANT_ID = UUID("1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8")


# ---------------------------------------------------------------------------
# 1. bridge_models shape
# ---------------------------------------------------------------------------


def _minimal_candidate_kwargs(**overrides):
    """Construct a minimal-but-valid PromotionCandidate kwargs dict.

    Shape matches engine's canonical models.py:PromotionCandidatePayload
    (NOT the old 2026-05-25 wire spec doc which is now superseded).
    """
    defaults = dict(
        promotion_id=uuid4(),
        pattern_signature="sha256:" + "0" * 40,
        tenant_id=CANONICAL_SELF_HOST_TENANT_ID,
        candidate_kind="skill",
        source=bridge_models.CandidateSource(
            body_md="# A skill\n\nSome body text.",
            frontmatter=bridge_models.CandidateSourceFrontmatter(
                name="test-skill",
                description="A test skill for the bridge.",
            ),
        ),
        evidence_refs=[],
        callbacks=bridge_models.CandidateCallbacks(
            registration_ack="https://loom-architecture-registry.onrender.com/skill-registered",
            telemetry="https://loom-telemetry-ingestion.onrender.com/skill-used",
        ),
    )
    defaults.update(overrides)
    return defaults


def test_minimal_promotion_candidate_constructs():
    c = bridge_models.PromotionCandidate(**_minimal_candidate_kwargs())
    assert c.schema_version == "1.0"
    assert c.candidate_kind == "skill"


def test_promotion_candidate_rejects_null_tenant_id():
    """Adjustment #1: tenant_id is NOT nullable."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        bridge_models.PromotionCandidate(
            **_minimal_candidate_kwargs(tenant_id=None)
        )


def test_promotion_candidate_rejects_extra_fields():
    """extra='forbid' protection — no surprise tenant metadata can ride along."""
    from pydantic import ValidationError

    kwargs = _minimal_candidate_kwargs()
    # Try to add a rogue field via the JSON path (Pydantic catches this).
    payload = json.loads(
        bridge_models.PromotionCandidate(**kwargs).model_dump_json()
    )
    payload["surprise_field"] = "should be rejected"
    with pytest.raises(ValidationError):
        bridge_models.PromotionCandidate.model_validate(payload)


def test_promotion_candidate_rejects_non_taxonomy_kind():
    """candidate_kind is Literal to the 9 taxonomy values; reject anything else."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        bridge_models.PromotionCandidate(
            **_minimal_candidate_kwargs(candidate_kind="banish")
        )


def test_promotion_candidate_accepts_all_9_kinds():
    """All 9 taxonomy kinds must construct cleanly. v1.0 only handles 'skill'
    fully; the others get ack-defer per MS-agent's PR #69 + my counter-ratify."""
    for kind in bridge_models.CANDIDATE_KIND.__args__:
        bridge_models.PromotionCandidate(
            **_minimal_candidate_kwargs(candidate_kind=kind)
        )


def test_source_frontmatter_requires_only_name_and_description():
    """Adjustment #2: capability_tags + triggers are derived metadata, NOT in
    source frontmatter. Frontmatter requires only {name, description}."""
    fm = bridge_models.CandidateSourceFrontmatter(
        name="test", description="just two fields"
    )
    assert fm.name == "test"
    # Rejects extra (e.g., capability_tags) — those live in derived_metadata
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        bridge_models.CandidateSourceFrontmatter(
            name="test",
            description="x",
            capability_tags=["search"],  # WRONG location
        )


def test_capability_tags_and_triggers_are_top_level():
    """Adjustment #2 + alignment with engine canonical: capability_tags and
    triggers live at the TOP LEVEL of PromotionCandidate, NOT nested in any
    derived_metadata wrapper. Engine's models.py treats them top-level."""
    payload = bridge_models.PromotionCandidate(
        **_minimal_candidate_kwargs(
            capability_tags=["search", "summarize"],
            triggers=["when user asks for X"],
        )
    )
    assert "search" in payload.capability_tags
    assert payload.triggers == ["when user asks for X"]


def test_telemetry_event_has_no_message_content_field():
    """Privacy: TelemetryEvent's extra='forbid' means no message_content can be
    smuggled in. Pin this so a future contributor can't quietly add it."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        bridge_models.TelemetryEvent.model_validate(
            {
                "skill_id": str(uuid4()),
                "thread_id": str(uuid4()),
                "tenant_id": str(CANONICAL_SELF_HOST_TENANT_ID),
                "invoked_at": "2026-06-12T20:00:00Z",
                "outcome": "success",
                "latency_ms": 100,
                "tokens_in": 10,
                "tokens_out": 5,
                "model": "claude-opus-4-7",
                "trigger_context": "user message",
                "message_content": "hi there",  # WOULD-BE PRIVACY LEAK
            }
        )


def test_telemetry_batch_caps_at_1000_events():
    """Spec §3 caps batches at 1000 events to prevent oversize payloads."""
    from pydantic import ValidationError

    one_event = {
        "skill_id": str(uuid4()),
        "thread_id": str(uuid4()),
        "tenant_id": str(CANONICAL_SELF_HOST_TENANT_ID),
        "invoked_at": "2026-06-12T20:00:00Z",
        "outcome": "success",
        "latency_ms": 100,
        "tokens_in": 10,
        "tokens_out": 5,
        "model": "claude-opus-4-7",
        "trigger_context": "user message",
    }
    with pytest.raises(ValidationError):
        bridge_models.TelemetryBatch(
            batch_id=uuid4(),
            events=[one_event] * 1001,  # over the cap
        )


def test_registration_ack_outcome_includes_ack_deferred():
    """PR #69's ack-defer extension MUST be a valid outcome (not in original
    spec). Pin so neither side regresses it."""
    assert "ack_deferred" in bridge_models.ACK_OUTCOME.__args__


# ---------------------------------------------------------------------------
# 2. HMAC sign + verify
# ---------------------------------------------------------------------------


SECRET_FOR_TESTS = "test-shared-secret-do-not-use-in-prod"


@pytest.fixture(autouse=True)
def _set_test_secret(monkeypatch):
    monkeypatch.setenv("LOOM_SKILL_BRIDGE_SECRET", SECRET_FOR_TESTS)


def test_sign_verify_roundtrip():
    body = '{"hello": "world"}'
    header = bridge_hmac.sign(body)
    # Roundtrip: should not raise
    bridge_hmac.verify_signature(body, header)


def test_verify_rejects_missing_header():
    with pytest.raises(bridge_hmac.BridgeAuthError, match="Missing"):
        bridge_hmac.verify_signature("{}", None)


def test_verify_rejects_malformed_header():
    with pytest.raises(bridge_hmac.BridgeAuthError, match="Malformed"):
        bridge_hmac.verify_signature("{}", "garbage")


def test_verify_rejects_tampered_body():
    """If the body changes after signing, verification must fail."""
    body = '{"hello": "world"}'
    header = bridge_hmac.sign(body)
    tampered = '{"hello": "WORLD"}'
    with pytest.raises(bridge_hmac.BridgeAuthError, match="mismatch"):
        bridge_hmac.verify_signature(tampered, header)


def test_verify_rejects_tampered_signature():
    body = '{"hello": "world"}'
    header = bridge_hmac.sign(body)
    # Flip a byte in the digest portion
    parts = header.split(",v1=")
    bad_sig = parts[1][:-1] + ("0" if parts[1][-1] != "0" else "1")
    bad_header = f"{parts[0]},v1={bad_sig}"
    with pytest.raises(bridge_hmac.BridgeAuthError, match="mismatch"):
        bridge_hmac.verify_signature(body, bad_header)


def test_verify_rejects_old_timestamp(monkeypatch):
    """Replay protection: signatures older than the window are rejected even
    if otherwise valid."""
    body = '{"hello": "world"}'
    # Sign with a timestamp 10 minutes in the past
    past_ts = bridge_hmac._now_unix() - 10 * 60
    header = bridge_hmac.sign(body, timestamp=past_ts)
    with pytest.raises(bridge_hmac.BridgeAuthError, match="window"):
        bridge_hmac.verify_signature(body, header)


def test_verify_rejects_future_timestamp():
    """Clock skew protection: also rejects timestamps too far in the future."""
    body = '{"hello": "world"}'
    future_ts = bridge_hmac._now_unix() + 10 * 60
    header = bridge_hmac.sign(body, timestamp=future_ts)
    with pytest.raises(bridge_hmac.BridgeAuthError, match="window"):
        bridge_hmac.verify_signature(body, header)


def test_sign_raises_when_secret_unset(monkeypatch):
    """Configuration error: signing without a secret should fail LOUD,
    not silently produce a useless signature."""
    monkeypatch.delenv("LOOM_SKILL_BRIDGE_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="LOOM_SKILL_BRIDGE_SECRET"):
        bridge_hmac.sign("{}")


def test_verify_raises_when_secret_unset(monkeypatch):
    monkeypatch.delenv("LOOM_SKILL_BRIDGE_SECRET", raising=False)
    header = "t=" + str(bridge_hmac._now_unix()) + ",v1=" + "0" * 64
    with pytest.raises(RuntimeError, match="LOOM_SKILL_BRIDGE_SECRET"):
        bridge_hmac.verify_signature("{}", header)


# ---------------------------------------------------------------------------
# 3. Cross-service kind enum sync (bridge ↔ candidates)
# ---------------------------------------------------------------------------


def test_bridge_candidate_kind_matches_registry_candidate_type():
    """The bridge's CANDIDATE_KIND must equal the registry's CANDIDATE_TYPE.
    Drift = the dashboard could promote a candidate whose kind the bridge
    can't represent (or vice versa). Cross-service contract pin."""
    bridge_set = set(bridge_models.CANDIDATE_KIND.__args__)
    registry_set = set(models.CANDIDATE_TYPE.__args__)
    assert bridge_set == registry_set, (
        f"Drift: bridge={bridge_set}, registry={registry_set}"
    )
