"""Self-host fallback middleware for the loom-memory MCP HTTP transport.

The MCP HTTP transport at /mcp/memory was originally gated by the MCP SDK's
RequireAuthMiddleware (see mcp_http.py docstring) — that returns 401 to any
request without a valid Bearer token. The REST endpoint at /v1/recall, in
contrast, falls back to SELF_HOST_TENANT_ID when no Authorization header is
present (main.py:_resolve_tenant_for_rest).

The MCP transport's stricter posture meant that **every project's Claude Code
session needed a minted JWT to use memory tools** — and in practice the
plugin and project mcp.json files never carried one, so memory tool calls
silently went missing across the fleet.

This module re-establishes parity with the REST behavior: present-but-invalid
Bearer is still rejected (security), but a fully absent Authorization header
falls through to the stable self-host tenant. Same envelope the REST endpoint
uses, same pattern documented in `feedback_pre_response_discipline`.

## Security envelope (must hold)

| Request                          | Outcome                              |
|----------------------------------|--------------------------------------|
| No Authorization header          | Self-host tenant (SELF_HOST_TENANT_ID) |
| Bearer + valid RS256 JWT         | Tenant from JWT's `tenant_id` claim    |
| Bearer + malformed JWT           | 401 (DO NOT silently fall through)     |
| Bearer + expired JWT             | 401                                    |
| Bearer + missing tenant_id claim | 401                                    |
| Authorization but not "Bearer"   | 401                                    |

The asymmetry (no header → fallback; bad header → reject) is deliberate.
A caller who TRIES to authenticate and fails should be told they failed,
not silently downgraded to a different tenant's data.

## Why a custom middleware (not patching the SDK's RequireAuthMiddleware)

The MCP SDK's BearerAuthBackend returns `None` from `authenticate()` when no
Authorization header is present. Starlette's AuthenticationMiddleware then
leaves the user anonymous. Downstream RequireAuthMiddleware sees no auth and
returns 401. We can't change the SDK; we replace the chain entirely with
this single middleware that handles all four cases uniformly.

## Where this runs in the ASGI stack

This middleware sits BEFORE the MCP session manager's `handle_request`. It
sets `tenant_ctx_var` (the contextvar consumed by mcp_server.py's tool
handlers) and then passes through. No downstream auth machinery is needed
because we've already established the tenant.
"""
from __future__ import annotations

import os
from typing import Awaitable, Callable

from jose import JWTError, jwt

import sys
from pathlib import Path

# Import the canonical contextvar directly (not via mcp_server's re-export)
# so this module stays decoupled from mcp_server's module-level state.
# parents[0]=agent-context/, parents[1]=services/, parents[2]=the-loom/
_PKG_PATH = Path(__file__).resolve().parents[2] / "packages" / "auth" / "python"
if str(_PKG_PATH) not in sys.path:
    sys.path.insert(0, str(_PKG_PATH))

from loom_auth import tenant_ctx_var  # noqa: E402


# Stable self-host tenant_id. MUST match:
#   - services/agent-context/main.py:44 (SELF_HOST_TENANT_ID)
#   - services/agent-context/mcp_server.py:70 (DEFAULT_SELF_HOST_TENANT_ID)
#   - services/project-registry/auth_bridge.py:30
#   - infra/migrations/001_init_memory.sql:200-202
#
# Public-template note: in the genericized template, this becomes
# os.environ.get("LOOM_SELF_HOST_TENANT_ID", "<generated-at-init>"). For
# Liz's instance it stays a constant.
SELF_HOST_TENANT_ID = os.environ.get(
    "LOOM_SELF_HOST_TENANT_ID",
    "1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8",
)


ASGIScope = dict
ASGIReceive = Callable[[], Awaitable[dict]]
ASGISend = Callable[[dict], Awaitable[None]]
ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]


async def _send_401(send: ASGISend, reason: str) -> None:
    """Emit a minimal HTTP 401 response. Matches the SDK's response shape
    closely enough that clients won't choke on missing headers."""
    body = f'{{"error":"{reason}"}}'.encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"www-authenticate", b'Bearer realm="loom-memory"'),
        ],
    })
    await send({"type": "http.response.body", "body": body})


class SelfHostFallbackAuthMiddleware:
    """ASGI middleware: bridge the four-case auth table at module top.

    Constructed once at app startup; called per request. Holds a lazy
    public-key cache (read on first JWT verification).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._public_key: str | None = None

    def _get_public_key(self) -> str | None:
        """Lazy-load LOOM_JWT_PUBLIC_KEY on first use. Returns None if env
        var unset — in that case any Bearer is rejected as unverifiable
        (still better than failing app startup if the key is missing)."""
        if self._public_key is None:
            self._public_key = os.environ.get("LOOM_JWT_PUBLIC_KEY")
        return self._public_key

    def _verify_bearer(self, raw_token: str) -> str | None:
        """Verify an RS256 Bearer token. Returns tenant_id on success, None
        on any failure (caller turns None into 401). Mirrors main.py's
        _resolve_tenant_for_rest verification logic exactly — the asymmetry
        intentionally surfaces the same failure mode through both paths."""
        public_key = self._get_public_key()
        if not public_key:
            return None
        try:
            claims = jwt.decode(
                raw_token,
                public_key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
        except JWTError:
            return None
        tenant_id = claims.get("tenant_id")
        sub = claims.get("sub")
        if not tenant_id or not sub:
            return None
        return tenant_id

    async def __call__(
        self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend
    ) -> None:
        if scope["type"] != "http":
            # Lifespan / other ASGI events — passthrough untouched.
            await self.app(scope, receive, send)
            return

        # Extract Authorization header from the raw headers list. ASGI
        # scope.headers is a list of (bytes, bytes) tuples.
        auth_header: bytes | None = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"authorization":
                auth_header = value
                break

        # Case 1: No Authorization header → self-host fallback.
        if auth_header is None:
            tenant_ctx_var.set(SELF_HOST_TENANT_ID)
            await self.app(scope, receive, send)
            return

        # Case 2-4: Authorization header present. Must be "Bearer <token>"
        # and the token must verify. Any other shape → 401.
        try:
            auth_str = auth_header.decode("latin-1")
        except UnicodeDecodeError:
            await _send_401(send, "Malformed Authorization header")
            return

        parts = auth_str.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            await _send_401(send, "Malformed Authorization header")
            return

        token = parts[1].strip()
        tenant_id = self._verify_bearer(token)
        if tenant_id is None:
            await _send_401(send, "Invalid or expired token")
            return

        # Case 2: valid Bearer → tenant from claim.
        tenant_ctx_var.set(tenant_id)
        await self.app(scope, receive, send)
