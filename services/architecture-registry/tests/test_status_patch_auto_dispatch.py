"""Tests for the in-service auto-dispatch trigger at PATCH /candidates/{id}/status.

When the target status is 'promotion_requested' AND the candidate's
candidate_type is 'skill', the endpoint MUST schedule a fastapi.BackgroundTask
that calls promote_dispatcher.dispatch_promotion. Dispatch failure MUST NOT
fail the PATCH response — the BackgroundTask runs after the response is sent.

Kind filter is skill-only because only kind=skill has a destination handler
in the engine today (per `bridge_closed_end_to_end_2026_06_13`). The 8 other
candidate kinds ack-defer at the engine; dispatching them would pollute
promotion state.

Fixture shape: TestClient + monkeypatch (does NOT mirror test_promote_dispatcher.py,
which tests the dispatcher module directly). TestClient deterministically drains
BackgroundTasks before client.patch(...) returns, so no sleep / no async test
loop is needed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

_SVC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC))

import auth_bridge  # noqa: E402
import main  # noqa: E402
import promote_dispatcher  # noqa: E402
import storage  # noqa: E402


# A valid-UUID tenant for the auth bypass. The endpoint's response_model=Candidate
# requires `tenant_id: UUID` so a string like "test-tenant-id" fails validation
# before the auto-dispatch logic ever runs.
TEST_TENANT_ID = "11111111-2222-3333-4444-555555555555"


def _candidate_row(*, candidate_id, candidate_type="skill", status="promotion_requested"):
    """Build a complete Candidate-model-compatible dict.

    The endpoint declares response_model=Candidate (main.py:188), which requires
    every Candidate field. Partial dicts fail at FastAPI response validation
    BEFORE the auto-dispatch trigger fires. This helper produces the minimum
    complete row a real storage call would return.
    """
    return {
        "id": str(candidate_id),
        "project_id": "99999999-0000-0000-0000-000000000000",
        "instance_id": "",
        "source_path": "path_b",
        "candidate_type": candidate_type,
        "status": status,
        "evidence_refs": [],
        "signals": {},
        "tenant_id": TEST_TENANT_ID,
        "created_at": 0.0,
        "updated_at": 0.0,
    }


@pytest.fixture
def client():
    """TestClient with auth bypass. BackgroundTasks drain before client returns."""
    main.app.dependency_overrides[auth_bridge.verify_bearer] = lambda: TEST_TENANT_ID
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_skill_promote_request_fires_dispatch(monkeypatch, client):
    """Transitioning a skill candidate to promotion_requested fires dispatch."""
    candidate_id = uuid4()
    storage_row = _candidate_row(candidate_id=candidate_id, candidate_type="skill", status="promotion_requested")

    async def fake_update(*args, **kwargs):
        return storage_row

    monkeypatch.setattr(storage, "update_candidate_status", fake_update)

    dispatch_mock = AsyncMock(return_value={"promotion_id": str(candidate_id), "status": "queued"})
    monkeypatch.setattr(promote_dispatcher, "dispatch_promotion", dispatch_mock)

    response = client.patch(
        f"/candidates/{candidate_id}/status",
        json={"status": "promotion_requested"},
    )

    assert response.status_code == 200
    # BackgroundTasks drain BEFORE TestClient returns — no sleep needed.
    dispatch_mock.assert_called_once()
    args, kwargs = dispatch_mock.call_args
    assert args[0] == candidate_id
    assert args[1] == TEST_TENANT_ID


def test_skill_non_promotion_status_does_not_fire(monkeypatch, client):
    """Transitioning a skill candidate to a non-promotion_requested status
    does NOT fire dispatch. The guard requires both kind=skill AND
    target_status=promotion_requested.
    """
    candidate_id = uuid4()
    storage_row = _candidate_row(candidate_id=candidate_id, candidate_type="skill", status="observed")

    async def fake_update(*args, **kwargs):
        return storage_row

    monkeypatch.setattr(storage, "update_candidate_status", fake_update)

    dispatch_mock = AsyncMock()
    monkeypatch.setattr(promote_dispatcher, "dispatch_promotion", dispatch_mock)

    response = client.patch(
        f"/candidates/{candidate_id}/status",
        json={"status": "observed"},
    )

    assert response.status_code == 200
    dispatch_mock.assert_not_called()


def test_non_skill_kind_does_not_fire(monkeypatch, client):
    """Transitioning a non-skill candidate to promotion_requested does NOT
    fire dispatch. The kind filter prevents dispatching agent/inline_tool/
    etc. candidates that have no engine destination handler.
    """
    candidate_id = uuid4()
    storage_row = _candidate_row(candidate_id=candidate_id, candidate_type="agent", status="promotion_requested")

    async def fake_update(*args, **kwargs):
        return storage_row

    monkeypatch.setattr(storage, "update_candidate_status", fake_update)

    dispatch_mock = AsyncMock()
    monkeypatch.setattr(promote_dispatcher, "dispatch_promotion", dispatch_mock)

    response = client.patch(
        f"/candidates/{candidate_id}/status",
        json={"status": "promotion_requested"},
    )

    assert response.status_code == 200
    dispatch_mock.assert_not_called()


def test_dispatch_failure_does_not_fail_patch(monkeypatch, client):
    """Dispatch failure inside the BackgroundTask MUST NOT fail the PATCH.
    The response is sent BEFORE the background task runs; any exception
    raised inside the task is logged and absorbed.
    """
    candidate_id = uuid4()
    storage_row = _candidate_row(candidate_id=candidate_id, candidate_type="skill", status="promotion_requested")

    async def fake_update(*args, **kwargs):
        return storage_row

    monkeypatch.setattr(storage, "update_candidate_status", fake_update)

    async def raising_dispatch(*args, **kwargs):
        raise promote_dispatcher.DispatchError(status=500, body="engine down")

    monkeypatch.setattr(promote_dispatcher, "dispatch_promotion", raising_dispatch)

    response = client.patch(
        f"/candidates/{candidate_id}/status",
        json={"status": "promotion_requested"},
    )

    # The PATCH must still return 200 with the row body. Dispatch failure
    # is fire-and-forget — operator's status flip succeeds regardless.
    assert response.status_code == 200
    assert response.json()["status"] == "promotion_requested"
    # The DispatchError was raised + logged + absorbed during the
    # BackgroundTasks drain; the PATCH response is unaffected.
