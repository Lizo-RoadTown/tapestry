"""
Layer 8 of the concrete-rule pattern (docs/CORE_DIRECTIVES.md Directive 1):
unit tests for the MCP HTTP transport's self-host fallback middleware.

The middleware lives at services/agent-context/mcp_self_host_middleware.py.
It replaces the MCP SDK's RequireAuthMiddleware. As of the memory-auth gate
(2026-08-08) the resolution table is:

  1. No Authorization header (or empty `Bearer `) -> anonymous path:
       - anonymous_access_allowed() (LOOM_ALLOW_ANONYMOUS_SELF_HOST != "0",
         default ON) -> self-host tenant (SELF_HOST_TENANT_ID)
       - anonymous disabled -> 401
  2. Bearer == shared secret (TAPESTRY_MEMORY_API_KEY / LOOM_MEMORY_API_KEY),
     constant-time compared -> self-host tenant
  3. Bearer + valid RS256 JWT  -> tenant from JWT's tenant_id claim
  4. Bearer + invalid/expired JWT, or wrong shared secret -> 401
  5. Authorization present but not "Bearer" -> 401

The anonymous gate and the shared secret are INDEPENDENT switches (a
configured key does NOT close anonymous access — see
auth_bridge.anonymous_access_allowed).

This file tests the middleware in isolation — calling it directly with
synthesized ASGI scope/receive/send to assert the contextvar gets set
correctly for each path. We do NOT spin up the full MCP transport here
because of the StreamableHTTPSessionManager singleton-reentry limitation
documented in test_memory_mcp_hosted.py.

If any of these tests fails, the concrete rule is broken — fix before
landing.
"""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture
def middleware():
    """Construct a fresh middleware instance for each test, with a
    mock downstream app that records what it received."""
    from mcp_self_host_middleware import SelfHostFallbackAuthMiddleware

    calls: list[dict[str, Any]] = []

    async def downstream(scope, receive, send):
        # Record that downstream was reached (i.e. auth allowed through).
        # Capture tenant_ctx_var at this point — that's what the tool handlers see.
        from mcp_server import tenant_ctx_var
        calls.append({"tenant_in_ctx": tenant_ctx_var.get()})

    mw = SelfHostFallbackAuthMiddleware(downstream)
    mw._test_downstream_calls = calls  # type: ignore[attr-defined]
    return mw


def _scope(authorization: bytes | None = None) -> dict:
    """Synthesize an ASGI HTTP scope. Optionally with Authorization header."""
    headers: list[tuple[bytes, bytes]] = [(b"content-type", b"application/json")]
    if authorization is not None:
        headers.append((b"authorization", authorization))
    return {"type": "http", "headers": headers, "path": "/mcp/memory/"}


async def _noop_receive() -> dict:
    return {"type": "http.request", "body": b"", "more_body": False}


def _capture_send():
    """Return (send_callable, captured_messages_list) — async-friendly."""
    captured: list[dict] = []

    async def send(msg: dict) -> None:
        captured.append(msg)

    return send, captured


# ---------------------------------------------------------------------------
# Case 1: No Authorization header -> self-host fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_auth_header_falls_back_to_self_host(middleware):
    """Most common path: hook scripts, plugin connections, dev sessions
    all send no Authorization header. Middleware must set tenant to
    SELF_HOST_TENANT_ID and pass through to downstream."""
    from mcp_self_host_middleware import SELF_HOST_TENANT_ID

    scope = _scope(authorization=None)
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    # Downstream reached (no 401 sent)
    assert middleware._test_downstream_calls, "downstream not reached"
    assert middleware._test_downstream_calls[0]["tenant_in_ctx"] == SELF_HOST_TENANT_ID
    # No HTTP response from middleware itself (downstream owns that)
    assert not captured


# ---------------------------------------------------------------------------
# Case 2: Valid Bearer JWT -> tenant from claim
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_bearer_resolves_to_claim_tenant(middleware, jwt_minter):
    """Hosted-multitenant path: Bearer + valid RS256 JWT sets tenant
    from the JWT's tenant_id claim."""
    custom_tenant = "fffefefe-1111-2222-3333-aaaaaaaaaaaa"
    token = jwt_minter(custom_tenant)

    scope = _scope(authorization=f"Bearer {token}".encode("ascii"))
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert middleware._test_downstream_calls, "downstream not reached"
    assert middleware._test_downstream_calls[0]["tenant_in_ctx"] == custom_tenant
    assert not captured


# ---------------------------------------------------------------------------
# Case 3: Bearer + invalid token -> 401 (no silent fallback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_bearer_returns_401(middleware):
    """Bearer + garbage token. CRITICAL: must NOT silently fall back to
    self-host. A caller who tried and failed should be rejected."""
    scope = _scope(authorization=b"Bearer this-is-not-a-real-jwt")
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    # 401 emitted
    assert captured, "no response from middleware"
    assert captured[0]["type"] == "http.response.start"
    assert captured[0]["status"] == 401
    # Downstream NOT reached
    assert not middleware._test_downstream_calls


@pytest.mark.asyncio
async def test_expired_bearer_returns_401(middleware, jwt_minter):
    """Expired JWTs must be rejected with 401, not fall back to self-host."""
    expired_token = jwt_minter("fff-fff", expires_in_seconds=-1)
    scope = _scope(authorization=f"Bearer {expired_token}".encode("ascii"))
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert captured[0]["status"] == 401
    assert not middleware._test_downstream_calls


@pytest.mark.asyncio
async def test_bearer_missing_tenant_id_claim_returns_401(middleware, test_private_key):
    """A JWT signed correctly but missing the tenant_id claim -> 401.
    Defense against tokens issued for non-loom purposes."""
    from jose import jwt as _jwt

    now = int(time.time())
    bad_token = _jwt.encode(
        {"sub": "user", "iat": now, "exp": now + 600},  # no tenant_id
        test_private_key,
        algorithm="RS256",
    )
    scope = _scope(authorization=f"Bearer {bad_token}".encode("ascii"))
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert captured[0]["status"] == 401
    assert not middleware._test_downstream_calls


# ---------------------------------------------------------------------------
# Case 4: Malformed Authorization header -> 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_bearer_authorization_returns_401(middleware):
    """Authorization header that's not Bearer (Basic, Digest, etc.) -> 401."""
    scope = _scope(authorization=b"Basic dXNlcjpwYXNz")
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert captured[0]["status"] == 401
    assert not middleware._test_downstream_calls


@pytest.mark.asyncio
async def test_empty_bearer_token_treated_as_anonymous(middleware, monkeypatch):
    """NEW behavior: `Authorization: Bearer ` (empty token) is treated as
    the anonymous path, NOT malformed. With anonymous access ON (default),
    it falls through to the self-host tenant. This keeps a static .mcp.json
    referencing ${TAPESTRY_MEMORY_API_KEY} valid when that var is unset
    (mcp_self_host_middleware.py:189-199)."""
    from mcp_self_host_middleware import SELF_HOST_TENANT_ID

    monkeypatch.delenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", raising=False)
    scope = _scope(authorization=b"Bearer ")
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert middleware._test_downstream_calls, "downstream not reached"
    assert middleware._test_downstream_calls[0]["tenant_in_ctx"] == SELF_HOST_TENANT_ID
    assert not captured


# ---------------------------------------------------------------------------
# Anonymous gate (2026-08-08): LOOM_ALLOW_ANONYMOUS_SELF_HOST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_auth_header_anon_default_on_falls_through(middleware, monkeypatch):
    """(a) Anonymous defaults ON: with the flag unset, no header -> tenant."""
    from mcp_self_host_middleware import SELF_HOST_TENANT_ID

    monkeypatch.delenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", raising=False)
    scope = _scope(authorization=None)
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert middleware._test_downstream_calls
    assert middleware._test_downstream_calls[0]["tenant_in_ctx"] == SELF_HOST_TENANT_ID
    assert not captured


@pytest.mark.asyncio
async def test_no_auth_header_anon_disabled_returns_401(middleware, monkeypatch):
    """(b) LOOM_ALLOW_ANONYMOUS_SELF_HOST=0 + no header -> 401. Once every
    client carries the key, the operator flips this off to close the
    anonymous escape hatch."""
    monkeypatch.setenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", "0")
    scope = _scope(authorization=None)
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert captured, "no response from middleware"
    assert captured[0]["status"] == 401
    assert not middleware._test_downstream_calls


@pytest.mark.asyncio
async def test_empty_bearer_anon_disabled_returns_401(middleware, monkeypatch):
    """(e) Empty `Bearer ` follows the anonymous gate: 401 when anon off."""
    monkeypatch.setenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", "0")
    scope = _scope(authorization=b"Bearer ")
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert captured[0]["status"] == 401
    assert not middleware._test_downstream_calls


# ---------------------------------------------------------------------------
# Shared secret (TAPESTRY_MEMORY_API_KEY / LOOM_MEMORY_API_KEY)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shared_secret_bearer_resolves_to_self_host(middleware, monkeypatch):
    """(c) Bearer == the configured shared secret -> self-host tenant,
    checked before JWT verification (the key is not a JWT)."""
    from mcp_self_host_middleware import SELF_HOST_TENANT_ID

    monkeypatch.setenv("TAPESTRY_MEMORY_API_KEY", "s3cret-shared-key")
    scope = _scope(authorization=b"Bearer s3cret-shared-key")
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert middleware._test_downstream_calls, "downstream not reached"
    assert middleware._test_downstream_calls[0]["tenant_in_ctx"] == SELF_HOST_TENANT_ID
    assert not captured


@pytest.mark.asyncio
async def test_shared_secret_via_loom_alias(middleware, monkeypatch):
    """The LOOM_MEMORY_API_KEY alias resolves the same as the canonical
    TAPESTRY_MEMORY_API_KEY (auth_bridge._memory_api_key)."""
    from mcp_self_host_middleware import SELF_HOST_TENANT_ID

    monkeypatch.delenv("TAPESTRY_MEMORY_API_KEY", raising=False)
    monkeypatch.setenv("LOOM_MEMORY_API_KEY", "alias-key")
    scope = _scope(authorization=b"Bearer alias-key")
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert middleware._test_downstream_calls
    assert middleware._test_downstream_calls[0]["tenant_in_ctx"] == SELF_HOST_TENANT_ID


@pytest.mark.asyncio
async def test_wrong_shared_secret_returns_401(middleware, monkeypatch):
    """(d) A Bearer that is neither the shared secret nor a valid JWT -> 401.
    With anon even ON, a present-but-wrong Bearer is rejected (the caller
    TRIED to authenticate and failed)."""
    monkeypatch.setenv("TAPESTRY_MEMORY_API_KEY", "the-right-key")
    monkeypatch.delenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", raising=False)
    scope = _scope(authorization=b"Bearer the-wrong-key")
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert captured[0]["status"] == 401
    assert not middleware._test_downstream_calls


@pytest.mark.asyncio
async def test_anon_flag_independent_of_key_set(middleware, monkeypatch, jwt_minter):
    """(f) The anonymous gate is INDEPENDENT of whether a key is configured.
    With a key set AND anon ON, all three succeed: no header -> tenant,
    shared secret -> tenant, valid JWT -> claim tenant. A configured key
    does NOT close anonymous access (auth_bridge.anonymous_access_allowed)."""
    from mcp_self_host_middleware import SELF_HOST_TENANT_ID
    from mcp_self_host_middleware import SelfHostFallbackAuthMiddleware

    monkeypatch.setenv("TAPESTRY_MEMORY_API_KEY", "coexist-key")
    monkeypatch.delenv("LOOM_ALLOW_ANONYMOUS_SELF_HOST", raising=False)

    # Build a fresh middleware+recorder per sub-case so the recorded calls
    # don't bleed together.
    def _fresh():
        calls: list[dict[str, Any]] = []

        async def downstream(scope, receive, send):
            from mcp_server import tenant_ctx_var
            calls.append({"tenant_in_ctx": tenant_ctx_var.get()})

        mw = SelfHostFallbackAuthMiddleware(downstream)
        mw._test_downstream_calls = calls  # type: ignore[attr-defined]
        return mw

    # no header -> anonymous still works despite key being set
    mw = _fresh()
    send, captured = _capture_send()
    await mw(_scope(authorization=None), _noop_receive, send)
    assert mw._test_downstream_calls[0]["tenant_in_ctx"] == SELF_HOST_TENANT_ID
    assert not captured

    # shared secret -> self-host tenant
    mw = _fresh()
    send, captured = _capture_send()
    await mw(_scope(authorization=b"Bearer coexist-key"), _noop_receive, send)
    assert mw._test_downstream_calls[0]["tenant_in_ctx"] == SELF_HOST_TENANT_ID
    assert not captured

    # valid JWT -> claim tenant (still works with a key configured)
    mw = _fresh()
    custom_tenant = "abcabcab-1111-2222-3333-dddddddddddd"
    token = jwt_minter(custom_tenant)
    send, captured = _capture_send()
    await mw(_scope(authorization=f"Bearer {token}".encode("ascii")), _noop_receive, send)
    assert mw._test_downstream_calls[0]["tenant_in_ctx"] == custom_tenant
    assert not captured


# ---------------------------------------------------------------------------
# Concrete-rule invariant: SELF_HOST_TENANT_ID matches the other files
# ---------------------------------------------------------------------------


def test_self_host_tenant_id_matches_canonical():
    """The middleware's SELF_HOST_TENANT_ID must agree with the same
    constant in:
      - services/agent-context/main.py
      - services/agent-context/mcp_server.py
      - services/project-registry/auth_bridge.py
      - packages/auth/python/loom_auth/auth_bridge.py (canonical)

    All four read from the same env var (SELF_HOST_TENANT_ID, with
    LOOM_SELF_HOST_TENANT_ID as deprecated alias). The drift this test
    catches is per-service CONSISTENCY — every path must resolve to the
    same value for a given deployment's env. The specific UUID is per
    deployment; the test does not pin one."""
    from mcp_self_host_middleware import SELF_HOST_TENANT_ID as MW_UUID
    from mcp_server import DEFAULT_SELF_HOST_TENANT_ID as SERVER_UUID
    from main import SELF_HOST_TENANT_ID as REST_UUID

    assert MW_UUID == SERVER_UUID, f"middleware vs mcp_server drift: {MW_UUID} != {SERVER_UUID}"
    assert MW_UUID == REST_UUID, f"middleware vs main drift: {MW_UUID} != {REST_UUID}"
