"""HTTP transport wrapper for the Tapestry docs MCP.

Mirrors the pattern from `the-loom/services/agent-context/mcp_http.py` —
StreamableHTTPSessionManager held as a module-level singleton, entered/exited
via FastAPI lifespan, mounted into the app at the requested path.

No auth middleware. The Tapestry docs are public read-only; gating them would
add friction without benefit.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from mcp_server import server


_session_manager: StreamableHTTPSessionManager | None = None


def _build_session_manager() -> StreamableHTTPSessionManager:
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
    mgr = get_session_manager()
    async with mgr.run():
        yield


def mount_into(app: FastAPI, path: str = "/mcp") -> None:
    mgr = get_session_manager()
    app.mount(path, mgr.handle_request)
