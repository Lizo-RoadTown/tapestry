"""Tests for registration_handler.py (Bridge PR C).

Two groups:

1. apply_ack — outcome-to-status mapping + audit reason composition;
   tested with a mocked storage layer (no DB).
2. Helpers — _outcome_reason produces the right shape per outcome.

The HTTP endpoint (POST /skill-registered) is exercised via a separate
smoke test post-deploy; unit tests here cover the handler module.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

_SVC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC))

import bridge_models  # noqa: E402
import registration_handler  # noqa: E402


CANONICAL_SELF_HOST_TENANT_ID = "1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8"


def _ack_kwargs(**overrides: Any) -> dict[str, Any]:
    """Minimal-but-valid RegistrationAck kwargs."""
    promotion_id = uuid4()
    base = dict(
        promotion_id=promotion_id,
        registered_at="2026-06-12T22:00:00Z",
        outcome="compiled",
        skill=bridge_models.AckSkillDetails(
            skill_id=uuid4(),
            name="test-skill",
            version="0.1.0",
            source_origin="promoted",
            compiled_at="2026-06-12T22:00:00Z",
            capability_tags=["test"],
            tenant_id=UUID(CANONICAL_SELF_HOST_TENANT_ID),
        ),
        the_loom_metadata=bridge_models.AckTheLoomMetadata(
            pattern_signature="sha256:" + "0" * 40,
            promotion_id=promotion_id,
        ),
    )
    base.update(overrides)
    return base


def _candidate_row(candidate_id: UUID, **overrides: Any) -> dict[str, Any]:
    """Minimal candidate row mimicking storage output."""
    base = {
        "id": str(candidate_id),
        "project_id": "63846bc6-4519-4216-8d71-c7df71290eb9",
        "instance_id": "",
        "source_path": "path_a",
        "candidate_type": "skill",
        "status": "promotion_requested",
        "evidence_refs": [],
        "signals": {"skill_name": "test-skill"},
        "tenant_id": CANONICAL_SELF_HOST_TENANT_ID,
        "created_at": 1781294000.0,
        "updated_at": 1781294000.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. apply_ack — outcome-to-status mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_ack_compiled_sets_status_promoted(monkeypatch):
    ack = bridge_models.RegistrationAck(**_ack_kwargs(outcome="compiled"))
    expected_id = ack.promotion_id

    calls: list[Any] = []

    async def fake_update(cid, status, tenant, *, reason=None):
        calls.append({"cid": cid, "status": status, "tenant": tenant, "reason": reason})
        return _candidate_row(cid, status=status)

    import storage
    monkeypatch.setattr(storage, "update_candidate_status", fake_update)

    row = await registration_handler.apply_ack(ack, CANONICAL_SELF_HOST_TENANT_ID)

    assert len(calls) == 1
    assert calls[0]["cid"] == expected_id
    assert calls[0]["status"] == "promoted"
    assert calls[0]["tenant"] == CANONICAL_SELF_HOST_TENANT_ID
    assert "compiled" in calls[0]["reason"].lower()
    assert row["status"] == "promoted"


@pytest.mark.asyncio
async def test_apply_ack_rejected_sets_status_rejected(monkeypatch):
    ack = bridge_models.RegistrationAck(
        **_ack_kwargs(
            outcome="rejected",
            skill=None,
            compilation_diagnostics=bridge_models.AckCompilationDiagnostics(
                errors=[
                    {"phase": "validator", "message": "duplicate name 'test-skill'",
                    }
                ],
            ),
        )
    )

    captured: dict[str, Any] = {}

    async def fake_update(cid, status, tenant, *, reason=None):
        captured.update({"status": status, "reason": reason})
        return _candidate_row(cid, status=status)

    import storage
    monkeypatch.setattr(storage, "update_candidate_status", fake_update)

    await registration_handler.apply_ack(ack, CANONICAL_SELF_HOST_TENANT_ID)

    assert captured["status"] == "rejected"
    assert "duplicate" in captured["reason"].lower()


@pytest.mark.asyncio
async def test_apply_ack_queued_human_review_appends_audit_without_status_change(
    monkeypatch,
):
    """No-transition outcome: status stays, but an evidence_refs entry is
    appended (via update_candidate_status reusing current_status as target)."""
    ack = bridge_models.RegistrationAck(
        **_ack_kwargs(outcome="queued_human_review", skill=None)
    )
    cid = ack.promotion_id

    async def fake_get(c, t):
        return _candidate_row(c, status="promotion_requested")

    captured: dict[str, Any] = {}

    async def fake_update(c, status, tenant, *, reason=None):
        captured.update({"status": status, "reason": reason})
        return _candidate_row(c, status=status)

    import storage
    monkeypatch.setattr(storage, "get_candidate", fake_get)
    monkeypatch.setattr(storage, "update_candidate_status", fake_update)

    await registration_handler.apply_ack(ack, CANONICAL_SELF_HOST_TENANT_ID)

    # Status passed to update is the SAME as current_status (no transition);
    # the call still fires so the reason lands in evidence_refs.
    assert captured["status"] == "promotion_requested"
    assert "human review" in captured["reason"].lower()


@pytest.mark.asyncio
async def test_apply_ack_ack_deferred_records_audit_without_status_change(
    monkeypatch,
):
    ack = bridge_models.RegistrationAck(
        **_ack_kwargs(outcome="ack_deferred", skill=None)
    )

    async def fake_get(c, t):
        return _candidate_row(c, status="promotion_requested")

    captured: dict[str, Any] = {}

    async def fake_update(c, status, tenant, *, reason=None):
        captured.update({"status": status, "reason": reason})
        return _candidate_row(c, status=status)

    import storage
    monkeypatch.setattr(storage, "get_candidate", fake_get)
    monkeypatch.setattr(storage, "update_candidate_status", fake_update)

    await registration_handler.apply_ack(ack, CANONICAL_SELF_HOST_TENANT_ID)

    assert captured["status"] == "promotion_requested"
    assert "deferred" in captured["reason"].lower()


@pytest.mark.asyncio
async def test_apply_ack_raises_when_candidate_missing(monkeypatch):
    """RLS-hidden or genuinely-missing candidate → CandidateNotFoundError."""
    ack = bridge_models.RegistrationAck(**_ack_kwargs(outcome="compiled"))

    async def fake_update(*_args, **_kwargs):
        return None  # mimics RLS-hidden or non-existent

    import storage
    monkeypatch.setattr(storage, "update_candidate_status", fake_update)

    with pytest.raises(registration_handler.CandidateNotFoundError):
        await registration_handler.apply_ack(ack, CANONICAL_SELF_HOST_TENANT_ID)


@pytest.mark.asyncio
async def test_apply_ack_raises_when_candidate_missing_on_no_transition_outcome(
    monkeypatch,
):
    """Same privacy invariant for queued_human_review / ack_deferred paths."""
    ack = bridge_models.RegistrationAck(
        **_ack_kwargs(outcome="ack_deferred", skill=None)
    )

    async def fake_get(*_args, **_kwargs):
        return None

    import storage
    monkeypatch.setattr(storage, "get_candidate", fake_get)

    with pytest.raises(registration_handler.CandidateNotFoundError):
        await registration_handler.apply_ack(ack, CANONICAL_SELF_HOST_TENANT_ID)


# ---------------------------------------------------------------------------
# 2. Audit reason composition
# ---------------------------------------------------------------------------


def test_outcome_reason_compiled_names_skill():
    ack = bridge_models.RegistrationAck(**_ack_kwargs(outcome="compiled"))
    reason = registration_handler._outcome_reason(ack)
    assert "compiled" in reason.lower()
    assert "test-skill" in reason
    assert "0.1.0" in reason


def test_outcome_reason_rejected_summarizes_errors():
    ack = bridge_models.RegistrationAck(
        **_ack_kwargs(
            outcome="rejected",
            skill=None,
            compilation_diagnostics=bridge_models.AckCompilationDiagnostics(
                errors=[
                    {"phase": "validator", "message": "frontmatter missing description"
                    },
                    {"phase": "validator", "message": "and another error"
                    },
                ],
            ),
        )
    )
    reason = registration_handler._outcome_reason(ack)
    assert "rejected" in reason.lower()
    assert "2 errors" in reason
    assert "frontmatter" in reason


def test_outcome_reason_truncates_long_error_messages():
    long_msg = "x" * 500
    ack = bridge_models.RegistrationAck(
        **_ack_kwargs(
            outcome="rejected",
            skill=None,
            compilation_diagnostics=bridge_models.AckCompilationDiagnostics(
                errors=[
                    {"phase": "validator", "message": long_msg
                    }
                ],
            ),
        )
    )
    reason = registration_handler._outcome_reason(ack)
    # First error truncated to 120 chars per the implementation; total reason
    # well under any reasonable database column limit.
    assert len(reason) < 400


def test_outcome_reason_ack_deferred_mentions_kind():
    ack = bridge_models.RegistrationAck(
        **_ack_kwargs(outcome="ack_deferred", skill=None)
    )
    reason = registration_handler._outcome_reason(ack)
    assert "deferred" in reason.lower()
    assert "kind" in reason.lower()
