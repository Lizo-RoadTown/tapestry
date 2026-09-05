"""Tests for promote_dispatcher.py (Bridge PR B).

Three groups:

1. Derivation helpers (no I/O) — capability_tags, triggers, pattern_signature
2. build_promotion_candidate — payload assembly produces valid PromotionCandidate
3. dispatch_promotion — end-to-end with mocked httpx (no real network)

The endpoint wiring (POST /candidates/{id}/dispatch-promotion) is covered
by end-to-end smoke testing post-deploy; unit tests here cover the module.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

_SVC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC))

import bridge_hmac  # noqa: E402
import bridge_models  # noqa: E402
import promote_dispatcher  # noqa: E402


CANONICAL_SELF_HOST_TENANT_ID = "1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8"


@pytest.fixture(autouse=True)
def _set_test_secret(monkeypatch):
    monkeypatch.setenv("LOOM_SKILL_BRIDGE_SECRET", "test-secret")


def _candidate_row(**overrides: Any) -> dict[str, Any]:
    """Minimal candidate row mimicking storage.get_candidate output."""
    base = {
        "id": str(uuid4()),
        "project_id": "63846bc6-4519-4216-8d71-c7df71290eb9",
        "instance_id": "",
        "source_path": "path_a",
        "candidate_type": "skill",
        "status": "recurring",
        "evidence_refs": [
            {"kind": "skill_invocation_count", "count": 3},
            {"kind": "skill_invocation_count", "count": 5},
        ],
        "signals": {
            "skill_name": "infrastructure-mapping",
            "sessions_seen": 2,
            "count_this_session": 3,
        },
        "tenant_id": CANONICAL_SELF_HOST_TENANT_ID,
        "created_at": 1781243624.250351,
        "updated_at": 1781243624.250351,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Derivation helpers
# ---------------------------------------------------------------------------


def test_derive_capability_tags_includes_kind_and_skill_name():
    row = _candidate_row()
    tags = promote_dispatcher.derive_capability_tags(row)
    assert "skill" in tags
    assert "infrastructure-mapping" in tags


def test_derive_capability_tags_returns_sorted_unique():
    row = _candidate_row()
    tags = promote_dispatcher.derive_capability_tags(row)
    assert tags == sorted(set(tags))


def test_derive_capability_tags_omits_missing_skill_name():
    row = _candidate_row(signals={})
    tags = promote_dispatcher.derive_capability_tags(row)
    assert tags == ["skill"]


def test_derive_triggers_includes_session_count():
    row = _candidate_row()
    triggers = promote_dispatcher.derive_triggers(row)
    assert any("2 sessions" in t for t in triggers)
    assert any("infrastructure-mapping" in t for t in triggers)


def test_derive_triggers_handles_missing_signals():
    row = _candidate_row(signals={})
    triggers = promote_dispatcher.derive_triggers(row)
    assert triggers == []


def test_pattern_signature_deterministic():
    row1 = _candidate_row()
    row2 = _candidate_row()
    assert promote_dispatcher._pattern_signature(row1) == (
        promote_dispatcher._pattern_signature(row2)
    )


def test_pattern_signature_changes_with_skill_name():
    row1 = _candidate_row()
    row2 = _candidate_row(signals={"skill_name": "different-name"})
    assert promote_dispatcher._pattern_signature(row1) != (
        promote_dispatcher._pattern_signature(row2)
    )


def test_pattern_signature_independent_of_tenant_id():
    """Pattern dedup is CONTENT-shaped, not tenant-shaped. Two tenants with
    the same observed pattern produce the same signature; the engine's
    tenant-scoped catalog handles actual isolation."""
    row1 = _candidate_row(tenant_id=CANONICAL_SELF_HOST_TENANT_ID)
    row2 = _candidate_row(tenant_id=str(uuid4()))
    assert promote_dispatcher._pattern_signature(row1) == (
        promote_dispatcher._pattern_signature(row2)
    )


# ---------------------------------------------------------------------------
# 2. Payload assembly
# ---------------------------------------------------------------------------


def test_build_promotion_candidate_constructs_valid_payload():
    row = _candidate_row()
    payload = promote_dispatcher.build_promotion_candidate(
        row, CANONICAL_SELF_HOST_TENANT_ID
    )
    assert payload.schema_version == "1.0"
    assert str(payload.tenant_id) == CANONICAL_SELF_HOST_TENANT_ID
    assert payload.candidate_kind == "skill"
    # capability_tags moved to top-level per engine canonical shape
    assert "infrastructure-mapping" in payload.capability_tags


def test_build_promotion_candidate_propagates_caller_tenant_id():
    """Critical dual-mode property: the bridge tenant_id matches the
    auth-resolved tenant_id, NOT anything from the row."""
    row = _candidate_row(tenant_id="not-this-uuid")
    caller_tenant = CANONICAL_SELF_HOST_TENANT_ID
    payload = promote_dispatcher.build_promotion_candidate(row, caller_tenant)
    assert str(payload.tenant_id) == caller_tenant


def test_build_promotion_candidate_uses_provided_promotion_id():
    row = _candidate_row()
    fixed = uuid4()
    payload = promote_dispatcher.build_promotion_candidate(
        row, CANONICAL_SELF_HOST_TENANT_ID, promotion_id=fixed
    )
    assert payload.promotion_id == fixed


def test_build_promotion_candidate_emits_evidence_refs_list():
    """Engine canonical: evidence_refs is a list of EvidenceRef{kind, ref, captured_at}
    at top level. NO `evidence` object wrapper (that was the old shape)."""
    row = _candidate_row()  # has 2 evidence_refs in fixture
    payload = promote_dispatcher.build_promotion_candidate(
        row, CANONICAL_SELF_HOST_TENANT_ID
    )
    assert len(payload.evidence_refs) >= 1
    for ref in payload.evidence_refs:
        assert ref.kind  # non-empty
        assert ref.ref  # non-empty


def test_build_promotion_candidate_accepts_uuid_object_project_id():
    """REGRESSION TEST for the 2026-06-12 production 500.

    psycopg3 returns UUID columns as `uuid.UUID` instances. The dispatcher
    must accept that type without crashing. The new schema no longer has
    a `projects_observed` field, so we just verify the builder constructs
    successfully when project_id is a UUID instance."""
    row = _candidate_row(project_id=uuid4())  # UUID object, not string
    payload = promote_dispatcher.build_promotion_candidate(
        row, CANONICAL_SELF_HOST_TENANT_ID
    )
    # No crash = test passes; pattern_signature should reference the
    # stringified project_id internally.
    assert payload.pattern_signature


def test_build_promotion_candidate_handles_empty_signals():
    """If no signals, evidence_refs may be empty list (engine accepts that)."""
    row = _candidate_row(
        evidence_refs=[{"kind": "session_boundary"}],
        signals={"sessions_seen": 4},
    )
    payload = promote_dispatcher.build_promotion_candidate(
        row, CANONICAL_SELF_HOST_TENANT_ID
    )
    # Just verify it constructs without crashing
    assert payload.signals.repeat_count == 4


def test_build_promotion_candidate_emits_render_callback_urls():
    """Adjustment #4 default — callbacks point at Render services.
    Field name is `telemetry` (NOT `telemetry_endpoint`) per engine canonical."""
    row = _candidate_row()
    payload = promote_dispatcher.build_promotion_candidate(
        row, CANONICAL_SELF_HOST_TENANT_ID
    )
    assert "loom-architecture-registry.onrender.com" in payload.callbacks.registration_ack
    assert "loom-telemetry-ingestion.onrender.com" in payload.callbacks.telemetry


def test_build_promotion_candidate_honors_env_overrides(monkeypatch):
    monkeypatch.setenv(
        "LOOM_REGISTRATION_ACK_URL", "https://example.test/ack"
    )
    monkeypatch.setenv(
        "LOOM_TELEMETRY_CALLBACK_URL", "https://example.test/telem"
    )
    row = _candidate_row()
    payload = promote_dispatcher.build_promotion_candidate(
        row, CANONICAL_SELF_HOST_TENANT_ID
    )
    assert payload.callbacks.registration_ack == "https://example.test/ack"
    assert payload.callbacks.telemetry == "https://example.test/telem"


# ---------------------------------------------------------------------------
# 3. dispatch_promotion (mocked httpx)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json = json_body
        self.text = text or (json.dumps(json_body) if json_body else "")

    def json(self) -> dict:
        if self._json is None:
            raise ValueError("no json")
        return self._json


class _FakeClient:
    """Stand-in for httpx.AsyncClient — captures the request, returns a fixture."""

    def __init__(self, response: _FakeResponse):
        self.response = response
        self.captured: dict[str, Any] = {}

    async def post(self, url: str, *, content: str, headers: dict) -> _FakeResponse:
        self.captured = {"url": url, "content": content, "headers": headers}
        return self.response


@pytest.mark.asyncio
async def test_dispatch_promotion_raises_candidate_not_found_when_missing(
    monkeypatch,
):
    """Local row-not-found raises CandidateNotFoundError (NOT
    DispatchError(404)). This distinction lets the endpoint map local
    misses to 404 'Candidate not found in registry' and engine 404s to
    502 with upstream context — they used to collide.

    Privacy invariant: CandidateNotFoundError fires for BOTH 'doesn't
    exist' AND 'exists in another tenant' (RLS-hidden). Same exception,
    same endpoint response — no cross-tenant probing surface."""
    async def fake_get_candidate(*_args, **_kwargs):
        return None

    import storage
    monkeypatch.setattr(storage, "get_candidate", fake_get_candidate)

    with pytest.raises(promote_dispatcher.CandidateNotFoundError):
        await promote_dispatcher.dispatch_promotion(
            uuid4(), CANONICAL_SELF_HOST_TENANT_ID
        )


@pytest.mark.asyncio
async def test_dispatch_promotion_engine_404_raises_dispatch_error_not_candidate_not_found(
    monkeypatch,
):
    """Engine-returned 404 (e.g., wrong route, deployment in maintenance)
    raises DispatchError(404), NOT CandidateNotFoundError. The endpoint
    distinguishes them: DispatchError → 502 with upstream context;
    CandidateNotFoundError → 404 'Candidate not found in registry'.

    REGRESSION TEST for the 2026-06-13 smoke debugging where this
    collision misled diagnosis by ~15 minutes."""
    row = _candidate_row()

    async def fake_get_candidate(*_args, **_kwargs):
        return row

    import storage
    monkeypatch.setattr(storage, "get_candidate", fake_get_candidate)

    client = _FakeClient(_FakeResponse(404, text="Not Found"))
    with pytest.raises(promote_dispatcher.DispatchError) as exc:
        await promote_dispatcher.dispatch_promotion(
            UUID(row["id"]), CANONICAL_SELF_HOST_TENANT_ID, http_client=client
        )
    # Not the CandidateNotFoundError sentinel:
    assert exc.value.status == 404
    assert not isinstance(exc.value, promote_dispatcher.CandidateNotFoundError)


@pytest.mark.asyncio
async def test_dispatch_promotion_signs_and_posts(monkeypatch):
    """Full happy path: row → payload → HMAC sign → POST → return ack.
    Verifies the wire-level signature matches what bridge_hmac.verify_signature
    accepts, so a real engine would accept what we send."""
    row = _candidate_row()

    async def fake_get_candidate(*_args, **_kwargs):
        return row

    import storage
    monkeypatch.setattr(storage, "get_candidate", fake_get_candidate)

    ack = {"promotion_id": str(uuid4()), "status": "queued"}
    client = _FakeClient(_FakeResponse(202, json_body=ack))

    result = await promote_dispatcher.dispatch_promotion(
        UUID(row["id"]), CANONICAL_SELF_HOST_TENANT_ID, http_client=client
    )

    assert result == ack
    assert "/bridge/promotion-candidate" in client.captured["url"]
    assert client.captured["headers"]["Content-Type"] == "application/json"
    assert "X-Loom-Signature" in client.captured["headers"]
    # Round-trip: the signature we sent must verify against the body we sent.
    bridge_hmac.verify_signature(
        client.captured["content"], client.captured["headers"]["X-Loom-Signature"]
    )

    # v1.0 invariant: promotion_id == candidate_id. This lets the
    # registration_handler look up the candidate from the echoed ack
    # without needing a separate mapping table.
    body_dict = json.loads(client.captured["content"])
    assert body_dict["promotion_id"] == row["id"]


@pytest.mark.asyncio
async def test_dispatch_promotion_raises_on_engine_5xx(monkeypatch):
    row = _candidate_row()

    async def fake_get_candidate(*_args, **_kwargs):
        return row

    import storage
    monkeypatch.setattr(storage, "get_candidate", fake_get_candidate)

    client = _FakeClient(_FakeResponse(503, text="maintenance"))
    with pytest.raises(promote_dispatcher.DispatchError) as exc:
        await promote_dispatcher.dispatch_promotion(
            UUID(row["id"]), CANONICAL_SELF_HOST_TENANT_ID, http_client=client
        )
    assert exc.value.status == 503
    assert "maintenance" in exc.value.body


@pytest.mark.asyncio
async def test_dispatch_promotion_propagates_tenant_id_to_wire(monkeypatch):
    """Verifies the dual-mode-critical property: the tenant_id flowing into
    the bridge payload is the CALLER-supplied one, regardless of what the
    row's tenant_id column says (which is RLS-controlled anyway)."""
    row = _candidate_row(tenant_id="00000000-0000-0000-0000-000000000000")
    caller_tenant = CANONICAL_SELF_HOST_TENANT_ID

    async def fake_get_candidate(*_args, **_kwargs):
        return row

    import storage
    monkeypatch.setattr(storage, "get_candidate", fake_get_candidate)

    client = _FakeClient(_FakeResponse(202, json_body={"status": "queued"}))
    await promote_dispatcher.dispatch_promotion(
        UUID(row["id"]), caller_tenant, http_client=client
    )

    body_dict = json.loads(client.captured["content"])
    assert body_dict["tenant_id"] == caller_tenant
