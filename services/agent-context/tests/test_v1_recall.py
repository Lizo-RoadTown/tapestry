"""
Integration tests for POST /v1/recall — the REST counterpart to the
loom-memory MCP's memory_recall tool, added in v0.1.7 (commit aedb60c).

Covers the JWT-required vs self-host fallback behavior + the tenant
isolation envelope that auth_bridge / _resolve_tenant_for_rest enforces.
This is the Pass 8 work, refocused on the REST endpoint because the
original Make_Skills MCP integration test was skipped due to module-
level singleton-reentry issues in mcp_http.py that need a production
refactor (StreamableHTTPSessionManager + LoomTokenVerifier are held as
module-level singletons; per-test fresh-app construction needs them
parameterizable). That MCP test is preserved as a skipped placeholder
in test_memory_mcp_hosted.py.

Test approach:
  - httpx.AsyncClient + ASGITransport — no port binding, no docker
  - asgi-lifespan LifespanManager — fires the FastAPI lifespan that
    enters the MCP session manager (TestClient doesn't fire lifespan;
    /mcp/memory would 500 without it — though these tests don't hit
    that path, we keep the lifespan-active fixture for consistency)
  - conftest.py provides the test RSA keypair + jwt_minter helper

The tests use the FastAPI app from main.py directly. The MCP singleton
issue doesn't affect /v1/recall because that endpoint doesn't share state
with mcp_http; tests can run in sequence without reset.

Note on DB: the storage.search() path requires a live Postgres + the
records table. These tests treat storage as a black box at the request
layer — they verify auth/routing/response shape, not the embedding or
RLS. For full RLS isolation tests against a real DB, see Phase 8+ test
work (not in scope here).
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
    """AsyncClient wired to the FastAPI app's ASGI app.

    Lifespan is intentionally NOT entered. The app's lifespan calls
    mcp_http.session_lifespan which calls StreamableHTTPSessionManager.run(),
    and that manager is a module-level singleton in mcp_http.py — it can
    only be entered once per process. Running it per-test breaks on the
    second test ("can only be called once per instance").

    /v1/recall doesn't touch the MCP transport, so we skip the lifespan
    entirely here. storage pool init is lazy on first DB call (and we
    mock storage.search in every test), so no pool needs setup or close.
    """
    from main import app
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth + routing tests (don't touch the DB; storage.search is mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_host_no_auth_returns_200_with_self_host_tenant(http_client):
    """No Authorization header → self-host fallback. The handler
    resolves SELF_HOST_TENANT_ID (read from env in production; tests
    use whatever the module resolved at import time) and calls
    storage.search with it. We mock storage.search to verify it's
    called with that resolved tenant_id without needing a real DB."""
    from main import SELF_HOST_TENANT_ID as expected_tenant

    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            json={"context": "self-host smoke test", "n": 3},
        )

    assert resp.status_code == 200, f"unexpected {resp.status_code}: {resp.text[:200]}"
    assert resp.json() == {"memories": []}
    # Confirm storage.search was called with SELF_HOST_TENANT_ID
    mock_search.assert_called_once()
    kwargs = mock_search.call_args.kwargs
    assert kwargs["tenant_id"] == expected_tenant, (
        f"expected self-host tenant {expected_tenant}, got {kwargs['tenant_id']!r}"
    )


@pytest.mark.asyncio
async def test_valid_bearer_resolves_to_claim_tenant(http_client, jwt_minter):
    """Bearer + valid RS256 JWT → handler verifies + extracts tenant_id
    from claim. storage.search receives that tenant, not the self-host
    fallback."""
    custom_tenant = "fffefefe-1111-2222-3333-aaaaaaaaaaaa"
    token = jwt_minter(custom_tenant)

    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            headers={"Authorization": f"Bearer {token}"},
            json={"context": "hosted-mode test", "n": 5},
        )

    assert resp.status_code == 200, f"unexpected {resp.status_code}: {resp.text[:200]}"
    mock_search.assert_called_once()
    assert mock_search.call_args.kwargs["tenant_id"] == custom_tenant


@pytest.mark.asyncio
async def test_invalid_bearer_returns_401(http_client):
    """Garbage Bearer token → 401 from JWT verification. Critical: this
    must NOT silently fall back to self-host (a malformed Bearer means
    the caller TRIED to authenticate and failed; we reject rather than
    treat them as Liz)."""
    resp = await http_client.post(
        "/v1/recall",
        headers={"Authorization": "Bearer this-is-not-a-real-jwt"},
        json={"context": "should fail auth", "n": 1},
    )
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}: {resp.text[:200]}"


@pytest.mark.asyncio
async def test_malformed_authorization_header_returns_401(http_client):
    """Authorization header not in `Bearer <token>` form → 401."""
    resp = await http_client.post(
        "/v1/recall",
        headers={"Authorization": "NotBearer something"},
        json={"context": "malformed auth", "n": 1},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_missing_tenant_id_claim_returns_401(http_client, test_private_key):
    """A JWT signed correctly but missing the tenant_id claim → 401.
    Defense against tokens issued for non-loom purposes."""
    import time as _time
    from jose import jwt

    now = int(_time.time())
    bad_token = jwt.encode(
        {"sub": "user", "iat": now, "exp": now + 600},  # no tenant_id
        test_private_key,
        algorithm="RS256",
    )

    resp = await http_client.post(
        "/v1/recall",
        headers={"Authorization": f"Bearer {bad_token}"},
        json={"context": "missing tenant claim", "n": 1},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_payload_validation_n_out_of_range(http_client):
    """Pydantic enforces n in [1, 50]; n=0 → 422 unprocessable entity."""
    with patch("storage.search", return_value=[]):
        resp = await http_client.post(
            "/v1/recall",
            json={"context": "n out of range", "n": 0},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_payload_validation_context_empty(http_client):
    """Pydantic enforces context min_length=1; empty string → 422."""
    with patch("storage.search", return_value=[]):
        resp = await http_client.post(
            "/v1/recall",
            json={"context": "", "n": 5},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_project_tags_passes_through_to_storage(http_client):
    """project_tags=[\"the-loom\"] reaches storage.search as project_tags arg."""
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            json={
                "context": "project-tag passthrough",
                "n": 5,
                "project_tags": ["the-loom"],
            },
        )
    assert resp.status_code == 200
    assert mock_search.call_args.kwargs.get("project_tags") == ["the-loom"]


@pytest.mark.asyncio
async def test_empty_project_tags_passes_none_to_storage(http_client):
    """Empty project_tags=[] → None passthrough (storage.search interprets
    None as 'no project filter', not 'match empty tags')."""
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            json={"context": "empty tags", "n": 5, "project_tags": []},
        )
    assert resp.status_code == 200
    # Per main.py:147 — `payload.project_tags or None` converts [] to None
    assert mock_search.call_args.kwargs.get("project_tags") is None


# ---------------------------------------------------------------------------
# Memory-auth gate (2026-08-08) — anonymous flag + shared secret
#
# NOTE ON EMPTY BEARER: the REST path (main.py:_resolve_tenant_for_rest) does
# NOT treat an empty `Bearer ` as anonymous — it rejects it as malformed
# (main.py:72-74). This differs from the MCP middleware, which routes empty
# `Bearer ` through the anonymous gate (mcp_self_host_middleware.py:189-199).
# The tests below pin the REST path's ACTUAL behavior.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_auth_anon_disabled_returns_401(http_client, monkeypatch):
    """(b) LOOM_ALLOW_ANONYMOUS_SELF_HOST=0 + no header → 401. The gate
    closes the anonymous escape hatch once every client carries the key."""
    monkeypatch.setenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", "0")
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            json={"context": "anon disabled", "n": 1},
        )
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}: {resp.text[:200]}"
    mock_search.assert_not_called()


@pytest.mark.asyncio
async def test_no_auth_anon_default_on_returns_200(http_client, monkeypatch):
    """(a) Anonymous defaults ON: with the flag unset, no header → self-host
    tenant (independent of whether a key is configured)."""
    from main import SELF_HOST_TENANT_ID as expected_tenant

    monkeypatch.delenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", raising=False)
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            json={"context": "anon default on", "n": 1},
        )
    assert resp.status_code == 200
    assert mock_search.call_args.kwargs["tenant_id"] == expected_tenant


@pytest.mark.asyncio
async def test_shared_secret_bearer_resolves_to_self_host(http_client, monkeypatch):
    """(c) Bearer == the configured shared secret → self-host tenant. Checked
    before JWT verification (the key is not a JWT)."""
    from main import SELF_HOST_TENANT_ID as expected_tenant

    monkeypatch.setenv("TAPESTRY_MEMORY_API_KEY", "s3cret-shared-key")
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            headers={"Authorization": "Bearer s3cret-shared-key"},
            json={"context": "shared secret", "n": 1},
        )
    assert resp.status_code == 200, f"unexpected {resp.status_code}: {resp.text[:200]}"
    assert mock_search.call_args.kwargs["tenant_id"] == expected_tenant


@pytest.mark.asyncio
async def test_shared_secret_via_loom_alias(http_client, monkeypatch):
    """LOOM_MEMORY_API_KEY alias resolves the same as TAPESTRY_MEMORY_API_KEY."""
    from main import SELF_HOST_TENANT_ID as expected_tenant

    monkeypatch.delenv("TAPESTRY_MEMORY_API_KEY", raising=False)
    monkeypatch.setenv("LOOM_MEMORY_API_KEY", "alias-key")
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            headers={"Authorization": "Bearer alias-key"},
            json={"context": "alias key", "n": 1},
        )
    assert resp.status_code == 200
    assert mock_search.call_args.kwargs["tenant_id"] == expected_tenant


@pytest.mark.asyncio
async def test_wrong_shared_secret_returns_401(http_client, monkeypatch):
    """(d) A Bearer that is neither the shared secret nor a valid JWT → 401,
    even with anonymous access ON (the caller tried to authenticate)."""
    monkeypatch.setenv("TAPESTRY_MEMORY_API_KEY", "the-right-key")
    monkeypatch.delenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", raising=False)
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            headers={"Authorization": "Bearer the-wrong-key"},
            json={"context": "wrong key", "n": 1},
        )
    assert resp.status_code == 401
    mock_search.assert_not_called()


@pytest.mark.asyncio
async def test_empty_bearer_rest_returns_401(http_client, monkeypatch):
    """(e) REST path: empty `Bearer ` → 401 malformed. Unlike the MCP
    middleware, the REST path does NOT route empty Bearer through the
    anonymous gate — see the NOTE at the top of this section."""
    monkeypatch.delenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", raising=False)
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            headers={"Authorization": "Bearer "},
            json={"context": "empty bearer", "n": 1},
        )
    assert resp.status_code == 401
    mock_search.assert_not_called()


@pytest.mark.asyncio
async def test_anon_flag_independent_of_key_set(http_client, monkeypatch, jwt_minter):
    """(f) The anonymous gate is INDEPENDENT of whether a key is configured.
    With a key set AND anon ON, all three succeed via the REST path:
    no header → self-host, shared secret → self-host, valid JWT → claim."""
    from main import SELF_HOST_TENANT_ID as self_host_tenant

    monkeypatch.setenv("TAPESTRY_MEMORY_API_KEY", "coexist-key")
    monkeypatch.delenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", raising=False)

    # no header → anonymous still works despite the key being set
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall", json={"context": "no header", "n": 1}
        )
    assert resp.status_code == 200
    assert mock_search.call_args.kwargs["tenant_id"] == self_host_tenant

    # shared secret → self-host tenant
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            headers={"Authorization": "Bearer coexist-key"},
            json={"context": "key", "n": 1},
        )
    assert resp.status_code == 200
    assert mock_search.call_args.kwargs["tenant_id"] == self_host_tenant

    # valid JWT → claim tenant (still works with a key configured)
    custom_tenant = "abcabcab-1111-2222-3333-dddddddddddd"
    token = jwt_minter(custom_tenant)
    with patch("storage.search", return_value=[]) as mock_search:
        resp = await http_client.post(
            "/v1/recall",
            headers={"Authorization": f"Bearer {token}"},
            json={"context": "jwt", "n": 1},
        )
    assert resp.status_code == 200
    assert mock_search.call_args.kwargs["tenant_id"] == custom_tenant


@pytest.mark.asyncio
async def test_response_passes_storage_rows_through_unchanged(http_client):
    """The handler returns whatever storage.search returns, wrapped in
    {memories: [...]}. No filtering, no transformation."""
    fake_memories = [
        {
            "id": "fake-1",
            "type": "feedback",
            "content": "fake memory body",
            "project_tags": [],
            "ts": 1780000000.0,
            "why": "test fixture",
            "tenant_id": "99999999-9999-4999-9999-999999999999",
            "visibility": "private",
        }
    ]
    with patch("storage.search", return_value=fake_memories):
        resp = await http_client.post(
            "/v1/recall",
            json={"context": "passthrough", "n": 1},
        )
    assert resp.status_code == 200
    assert resp.json() == {"memories": fake_memories}
