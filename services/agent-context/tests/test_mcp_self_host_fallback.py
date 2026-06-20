"""
Layer 8 of the concrete-rule pattern (docs/CORE_DIRECTIVES.md Directive 1):
unit tests for the MCP HTTP transport's self-host fallback middleware.

The middleware lives at services/agent-context/mcp_self_host_middleware.py.
It replaces the MCP SDK's RequireAuthMiddleware so that:

  1. No Authorization header -> self-host tenant (SELF_HOST_TENANT_ID)
  2. Bearer + valid RS256 JWT  -> tenant from JWT's tenant_id claim
  3. Bearer + invalid JWT      -> 401
  4. Authorization but not Bearer -> 401

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
async def test_empty_bearer_token_returns_401(middleware):
    """`Authorization: Bearer ` (empty token) -> 401."""
    scope = _scope(authorization=b"Bearer ")
    send, captured = _capture_send()
    await middleware(scope, _noop_receive, send)

    assert captured[0]["status"] == 401
    assert not middleware._test_downstream_calls


# ---------------------------------------------------------------------------
# Concrete-rule invariant: SELF_HOST_TENANT_ID matches the other files
# ---------------------------------------------------------------------------


def test_self_host_tenant_id_matches_canonical():
    """The middleware's SELF_HOST_TENANT_ID must match the same constant in:
      - services/agent-context/main.py:44
      - services/agent-context/mcp_server.py:70
      - services/project-registry/auth_bridge.py:30
      - infra/migrations/001_init_memory.sql:200-202

    If these drift, RLS policies will silently filter to zero rows for one
    of the paths. This test is the static check that catches drift before
    deploy."""
    from mcp_self_host_middleware import SELF_HOST_TENANT_ID as MW_UUID
    from mcp_server import DEFAULT_SELF_HOST_TENANT_ID as SERVER_UUID
    from main import SELF_HOST_TENANT_ID as REST_UUID

    canonical = "1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8"
    assert MW_UUID == canonical, f"middleware drift: {MW_UUID}"
    assert SERVER_UUID == canonical, f"mcp_server drift: {SERVER_UUID}"
    assert REST_UUID == canonical, f"main drift: {REST_UUID}"
