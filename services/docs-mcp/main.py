"""tapestry-docs-mcp — Tapestry documentation MCP service.

FastAPI app exposing:

  GET  /health               — service health
  GET  /llms.txt             — flattened corpus per llmstxt.org convention
  GET  /.well-known/mcp.json — MCP discovery manifest
  POST /mcp/*                — MCP HTTP transport (tools: search, read, list)

The corpus is loaded once at startup from `DOCS_ROOT` (default:
`apps/docs-site/src/content/docs/` relative to this file) and indexed
in memory. To pick up doc edits, redeploy the service.

Public read-only. No auth.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

import corpus
import indexer
import mcp_http
import mcp_server


_DEFAULT_SITE_BASE_URL = "https://tapestry-khaki.vercel.app"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load + index the docs corpus at startup; enter the MCP session manager."""
    docs_root = corpus.default_docs_root()
    docs = corpus.load_corpus(docs_root)
    index = indexer.Index(docs)
    mcp_server.set_index(index)

    # Stash the rendered llms.txt + discovery manifest on app.state so the
    # GET handlers don't have to recompute them per request.
    site_base = os.environ.get("SITE_BASE_URL", _DEFAULT_SITE_BASE_URL)
    app.state.llms_txt = corpus.build_llms_txt(docs, site_base_url=site_base)
    app.state.mcp_manifest = _build_mcp_manifest(site_base)
    app.state.docs_count = len(docs)

    async with mcp_http.session_lifespan(app):
        yield


def _build_mcp_manifest(site_base_url: str) -> dict:
    """Construct the MCP discovery manifest published at /.well-known/mcp.json."""
    mcp_url = os.environ.get(
        "MCP_PUBLIC_URL",
        f"{site_base_url.rstrip('/')}/mcp",  # placeholder until the service has its own URL
    )
    return {
        "name": "tapestry-docs",
        "description": (
            "MCP server exposing the Tapestry platform documentation as queryable "
            "tools. Use these tools to ground answers in canonical docs instead of "
            "pattern-matching from training data."
        ),
        "url": mcp_url,
        "transport": "http",
        "site": site_base_url,
        "tools": [
            "tapestry_docs_search",
            "tapestry_docs_read",
            "tapestry_docs_list",
        ],
    }


app = FastAPI(
    title="tapestry-docs-mcp",
    version="0.1.0",
    lifespan=lifespan,
)

mcp_http.mount_into(app, path="/mcp")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "tapestry-docs-mcp",
        "docs_count": getattr(app.state, "docs_count", 0),
    }


@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt() -> str:
    return app.state.llms_txt


@app.get("/.well-known/mcp.json")
async def mcp_discovery() -> JSONResponse:
    return JSONResponse(app.state.mcp_manifest)
