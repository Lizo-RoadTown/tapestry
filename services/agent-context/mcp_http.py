"""
HTTP transport wrapper for the loom memory MCP server.

Constructs a StreamableHTTPSessionManager around the mcp_server.server
instance and exposes mount_into() to attach the ASGI handler to a
FastAPI app. The session manager must be entered via lifespan
(`async with session_manager.run(): ...`) before any HTTP request hits
it — main.py composes this in its FastAPI lifespan.

Self-host stdio mode never imports this. main.py wires it when running
the HTTP server.

## Auth chain (v0.1.8+) — replaces the SDK's RequireAuthMiddleware

Before v0.1.8, this module wrapped `handle_request` in the MCP SDK's
auth middleware sandwich (RequireAuthMiddleware → AuthContextMiddleware
→ AuthenticationMiddleware over BearerAuthBackend). That stack returned
401 to any request without a valid Bearer token.

The 401-on-no-Bearer posture meant that the fleet of consumer projects
needed minted JWTs everywhere — and in practice they never had them.
Memory tool calls silently went missing across every project except
the one that happened to have loom-memory configured ad-hoc.

v0.1.8 replaces that stack with `SelfHostFallbackAuthMiddleware`
(`mcp_self_host_middleware.py`) which gives the MCP transport the same
self-host-fallback envelope the REST `/v1/recall` already had:

  | Request                          | Outcome                            |
  | -------------------------------- | ---------------------------------- |
  | No Authorization header          | Self-host tenant (constant UUID)   |
  | Bearer + valid RS256 JWT         | Tenant from JWT `tenant_id` claim  |
  | Bearer + malformed / expired JWT | 401 (no silent fallback)           |
  | Authorization but not "Bearer"   | 401                                |

This is the SAME envelope `main.py:_resolve_tenant_for_rest` already
implements (main.py:47-89). The MCP and REST paths now have parity.

Background on what was removed:
  - `RequireAuthMiddleware` from `mcp.server.auth.middleware.bearer_auth`
  - `AuthContextMiddleware` from `mcp.server.auth.middleware.auth_context`
  - Starlette's `AuthenticationMiddleware` over `BearerAuthBackend`
  - The `LoomTokenVerifier` instance (its verification logic lives in
    `mcp_self_host_middleware._verify_bearer` now, but the file stays
    intact for backward-compatibility and for any future code paths
    that want to verify tokens directly).

## Known limitation (still deferred to Pass 8 test fixture work)

StreamableHTTPSessionManager.__init__ does NOT accept a token_verifier
kwarg, and the manager is held as a module-level singleton. Per-test
reconstruction is tricky — see services/agent-context/tests/
test_memory_mcp_hosted.py (skipped, with the documented blocker).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from mcp_self_host_middleware import SelfHostFallbackAuthMiddleware
from mcp_server import server


_session_manager: StreamableHTTPSessionManager | None = None


def _build_session_manager() -> StreamableHTTPSessionManager:
    """Construct the session manager. v0.1.8 removed the verifier
    module-level singleton — auth is now handled by
    SelfHostFallbackAuthMiddleware which is constructed fresh per
    mount_into() call."""
    return StreamableHTTPSessionManager(
        app=server,
        event_store=None,
        json_response=False,
        stateless=False,
    )


def get_session_manager() -> StreamableHTTPSessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = _build_session_manager()
    return _session_manager


@asynccontextmanager
async def session_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan that enters/exits the MCP session manager.
    main.py composes this with any other lifespan logic."""
    mgr = get_session_manager()
    async with mgr.run():
        yield


def mount_into(app: FastAPI, path: str = "/mcp/memory") -> None:
    """Attach the MCP HTTP handler to the FastAPI app under `path`,
    wrapped in SelfHostFallbackAuthMiddleware so every request resolves
    a tenant (either from a valid Bearer JWT or from the self-host
    fallback). The middleware sets `tenant_ctx_var` (consumed by the
    6 tool handlers in mcp_server.py) before passing through.

    See mcp_self_host_middleware.py for the four-case auth table."""
    mgr = get_session_manager()
    asgi = SelfHostFallbackAuthMiddleware(mgr.handle_request)
    app.mount(path, asgi)
