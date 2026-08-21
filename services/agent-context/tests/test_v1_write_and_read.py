"""
Integration tests for POST /v1/write + POST /v1/read — the REST counterparts
to the loom-memory MCP's memory_write + memory_read tools.

Added 2026-06-18 (B1 of the runtime-observation followup) so non-MCP clients
(the self-observer Render cron in particular) can write synthesis memos +
read the prior synthesis to compute consecutive-scan health flags. The
MCP HTTP transport requires a session handshake that is heavy for a
one-shot Python cron; the REST counterparts let it use simple httpx POSTs.

Per `tapestry/docs/research/2026-06-18-outside-review-runtime-observation-followup.md`
§5.5.2 + the drift-watcher's nudge to honor §3.3 (which needs prior-memo
read to compute "2 consecutive scans" thresholds).

Test approach mirrors test_v1_recall.py exactly:
  - httpx.AsyncClient + ASGITransport (no port binding)
  - Lifespan NOT entered (mcp_http singleton constraint)
  - storage.insert_records / storage.get_by_id mocked at the request layer
  - conftest provides jwt_minter + test_private_key
"""
from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport


@pytest_asyncio.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    from main import app
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac


# Test-only synthetic UUID. Production self-host tenant resolves from
# the SELF_HOST_TENANT_ID env var (see packages/auth/python/loom_auth/auth_bridge.py).
_SELF_HOST_TENANT = "99999999-9999-4999-9999-999999999999"

_VALID_WRITE_BODY = {
    "name": "test_synthesis_memo",
    "record_type": "project",
    "content": "Test synthesis memo body.",
    "project_tags": ["the-loom"],
    "actor": "self-observer",
    "why": "test fixture",
}


# ---------------------------------------------------------------------------
# /v1/write
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_self_host_no_auth_inserts_with_self_host_tenant(http_client):
    """No Authorization → SELF_HOST_TENANT_ID flows to storage (anonymous
    access defaults ON, so no header falls through to the self-host tenant)."""
    from main import SELF_HOST_TENANT_ID as expected_tenant

    with patch("storage.insert_records", return_value=1) as mock_insert:
        resp = await http_client.post("/v1/write", json=_VALID_WRITE_BODY)

    assert resp.status_code == 200, f"unexpected {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    assert body == {"ok": True, "name": "test_synthesis_memo", "inserted": 1}
    mock_insert.assert_called_once()
    kwargs = mock_insert.call_args.kwargs
    assert kwargs["tenant_id"] == expected_tenant
    # records[0] should carry the name as the id, plus type/content/etc.
    records = kwargs["records"]
    assert len(records) == 1
    assert records[0]["id"] == "test_synthesis_memo"
    assert records[0]["type"] == "project"
    assert records[0]["content"] == "Test synthesis memo body."
    assert records[0]["actor"] == "self-observer"
    assert records[0]["why"] == "test fixture"


@pytest.mark.asyncio
async def test_write_valid_bearer_inserts_with_claim_tenant(http_client, jwt_minter):
    """Valid bearer → tenant from claim flows to storage."""
    custom_tenant = "fffefefe-1111-2222-3333-aaaaaaaaaaaa"
    token = jwt_minter(custom_tenant)

    with patch("storage.insert_records", return_value=1) as mock_insert:
        resp = await http_client.post(
            "/v1/write",
            headers={"Authorization": f"Bearer {token}"},
            json=_VALID_WRITE_BODY,
        )

    assert resp.status_code == 200
    assert mock_insert.call_args.kwargs["tenant_id"] == custom_tenant


@pytest.mark.asyncio
async def test_write_invalid_bearer_returns_401(http_client):
    resp = await http_client.post(
        "/v1/write",
        headers={"Authorization": "Bearer this-is-not-a-real-jwt"},
        json=_VALID_WRITE_BODY,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_write_no_auth_anon_disabled_returns_401(http_client, monkeypatch):
    """Memory-auth gate applies to /v1/write too: with anonymous access
    disabled and no header, the write is rejected 401 (no silent insert)."""
    monkeypatch.setenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", "0")
    with patch("storage.insert_records", return_value=1) as mock_insert:
        resp = await http_client.post("/v1/write", json=_VALID_WRITE_BODY)
    assert resp.status_code == 401
    mock_insert.assert_not_called()


@pytest.mark.asyncio
async def test_write_shared_secret_inserts_with_self_host_tenant(http_client, monkeypatch):
    """Bearer == shared secret → self-host tenant flows to storage on write."""
    from main import SELF_HOST_TENANT_ID as expected_tenant

    monkeypatch.setenv("TAPESTRY_MEMORY_API_KEY", "s3cret-shared-key")
    with patch("storage.insert_records", return_value=1) as mock_insert:
        resp = await http_client.post(
            "/v1/write",
            headers={"Authorization": "Bearer s3cret-shared-key"},
            json=_VALID_WRITE_BODY,
        )
    assert resp.status_code == 200, f"unexpected {resp.status_code}: {resp.text[:200]}"
    assert mock_insert.call_args.kwargs["tenant_id"] == expected_tenant


@pytest.mark.asyncio
async def test_write_invalid_record_type_returns_422(http_client):
    """record_type must be one of the 10 VALID_TYPES values."""
    bad_body = dict(_VALID_WRITE_BODY, record_type="banana")
    with patch("storage.insert_records", return_value=1):
        resp = await http_client.post("/v1/write", json=bad_body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_write_empty_name_returns_422(http_client):
    bad_body = dict(_VALID_WRITE_BODY, name="")
    with patch("storage.insert_records", return_value=1):
        resp = await http_client.post("/v1/write", json=bad_body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_write_idempotent_upsert_returns_inserted_count(http_client):
    """storage.insert_records uses ON CONFLICT DO UPDATE (storage.py:217).
    The REST contract returns whatever count storage reports (still 1
    for an upsert)."""
    with patch("storage.insert_records", return_value=1) as mock_insert:
        # First call
        resp1 = await http_client.post("/v1/write", json=_VALID_WRITE_BODY)
        # Second call with same name — upsert
        resp2 = await http_client.post("/v1/write", json=_VALID_WRITE_BODY)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["inserted"] == 1
    assert resp2.json()["inserted"] == 1
    assert mock_insert.call_count == 2


# ---------------------------------------------------------------------------
# /v1/read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_self_host_no_auth_returns_record(http_client):
    """GET by name → storage.get_by_id, returns the row body."""
    fake_row = {
        "id": "test_synthesis_memo",
        "type": "project",
        "content": "Test memo body.",
        "project_tags": ["the-loom"],
        "ts": 1780000000.0,
        "why": "fixture",
        "tenant_id": _SELF_HOST_TENANT,
        "visibility": "private",
        "actor": "self-observer",
    }
    with patch("storage.get_by_id", return_value=fake_row) as mock_get:
        resp = await http_client.post(
            "/v1/read",
            json={"name": "test_synthesis_memo"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"memory": fake_row}
    mock_get.assert_called_once()
    kwargs = mock_get.call_args.kwargs
    # Allow either positional or kwarg passing of record_id
    args = mock_get.call_args.args
    assert ("test_synthesis_memo" in args) or (kwargs.get("record_id") == "test_synthesis_memo")
    from main import SELF_HOST_TENANT_ID as expected_tenant
    assert kwargs.get("tenant_id") == expected_tenant


@pytest.mark.asyncio
async def test_read_not_found_returns_404(http_client):
    """storage.get_by_id returns None → 404."""
    with patch("storage.get_by_id", return_value=None):
        resp = await http_client.post(
            "/v1/read",
            json={"name": "does_not_exist"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_read_invalid_bearer_returns_401(http_client):
    resp = await http_client.post(
        "/v1/read",
        headers={"Authorization": "Bearer not-a-real-jwt"},
        json={"name": "anything"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_read_empty_name_returns_422(http_client):
    with patch("storage.get_by_id", return_value=None):
        resp = await http_client.post("/v1/read", json={"name": ""})
    assert resp.status_code == 422
