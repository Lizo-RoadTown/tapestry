"""
Integration tests for the hosted-mode memory MCP HTTP transport.

KNOWN-ISSUE — SKIPPED until production refactor lands.

The MCP transport in mcp_http.py holds StreamableHTTPSessionManager and
LoomTokenVerifier as MODULE-LEVEL SINGLETONS (lines 49-50 of mcp_http.py
in this repo). main.py calls mount_into(app, "/mcp/memory") at import
time, registering the ASGI middleware sandwich against those singletons.

Multi-test consequences:
  - Resetting the singletons before each fixture instance doesn't unmount
    or re-wire the route — the FastAPI app still holds a reference to
    the OLD middleware sandwich.
  - LifespanManager re-enters mcp_http.session_lifespan per test, but
    StreamableHTTPSessionManager.run() asserts single-entry on the SAME
    manager instance.

The right fix is structural:
  1. Refactor mcp_http.mount_into to take a LoomTokenVerifier instance
     as a parameter (not pull from module-level _verifier).
  2. Refactor main.py to expose create_app() rather than module-level
     `app = ...`. Each test calls create_app() to get a fresh FastAPI
     instance with its own verifier + session manager + lifespan.
  3. Production behavior unchanged: uvicorn still gets module-level
     `app = create_app()` for the `uvicorn main:app` invocation.

That refactor is deferred to a follow-up. This test file is preserved
to:
  - Document the test surface (auth gating, tenant isolation at the MCP
    layer) so the refactor knows what to verify.
  - Be unskipped trivially once the refactor lands.

Equivalent coverage at the REST layer is in test_v1_recall.py — the
JWT-required vs self-host fallback behavior + auth resolution path are
exercised there. The MCP-specific behaviors not covered by REST tests:
  - JSON-RPC envelope wrapping of tool results
  - MCP middleware sandwich rejection of missing/invalid bearer
  - StreamableHTTPSessionManager session-id behavior
  - Tool call dispatch to memory_read / memory_write / memory_recall etc.

When the refactor lands, port the pattern from Make_Skills/platform/
tests/test_memory_mcp_hosted.py (HS256-based; the-loom uses RS256 so
swap _make_jwt to use conftest.jwt_minter).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="WIP: mcp_http module-level singletons block multi-test "
    "lifespan re-entry. Needs mount_into refactor to take verifier "
    "as param + main.py create_app() factory. REST-layer auth tests "
    "in test_v1_recall.py cover equivalent surface. See module docstring."
)


@pytest.mark.asyncio
async def test_mcp_missing_token_returns_401_placeholder():
    """When the refactor lands: assert /mcp/memory with no Authorization
    header returns 401 from RequireAuthMiddleware."""
    pytest.fail("not implemented — see module docstring")


@pytest.mark.asyncio
async def test_mcp_tenant_isolation_placeholder():
    """When the refactor lands: assert tenant A's Bearer JWT cannot read
    memories written by tenant B's Bearer JWT (the hosted-mode hard
    isolation invariant)."""
    pytest.fail("not implemented — see module docstring")
