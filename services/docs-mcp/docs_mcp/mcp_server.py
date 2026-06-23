"""MCP tool definitions for the Tapestry docs MCP.

Three tools, all public read-only:

  tapestry_docs_search — top-N matching slugs + excerpts
  tapestry_docs_read   — full body of a named doc
  tapestry_docs_list   — all slugs, optionally filtered to a section

The Index instance is module-level (constructed at startup by main.py via
build_server()). MCP HTTP transport routes each tool call to the handlers
defined here.
"""
from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from indexer import Index


_index: Index | None = None


def set_index(index: Index) -> None:
    """main.py calls this once at startup with the loaded corpus."""
    global _index
    _index = index


def _require_index() -> Index:
    if _index is None:
        raise RuntimeError(
            "docs index not initialized — call set_index() before serving requests"
        )
    return _index


server: Server = Server("tapestry-docs-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="tapestry_docs_search",
            description=(
                "Search the Tapestry documentation for relevant pages. "
                "Returns ranked slugs + title + score + snippet excerpt. "
                "Use this when the operator asks 'where does Tapestry explain X' "
                "or when you need to ground an answer in a documented concept."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language search query.",
                        "minLength": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of hits to return.",
                        "minimum": 1,
                        "maximum": 25,
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="tapestry_docs_read",
            description=(
                "Read the full markdown body of a Tapestry documentation page. "
                "Use this after tapestry_docs_search returns a relevant slug, "
                "or when you already know the slug (e.g., 'systems/observer')."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": (
                            "The doc slug — matches the URL path on the docs site "
                            "(e.g., 'systems/observer', 'explanation/signal-hierarchy', "
                            "'index' for the overview page)."
                        ),
                    },
                },
                "required": ["slug"],
            },
        ),
        Tool(
            name="tapestry_docs_list",
            description=(
                "List all Tapestry documentation slugs, optionally filtered to a "
                "section ('start', 'how-to', 'explanation', 'systems', "
                "'observatory', 'reference')."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "description": "Optional section filter. Omit to list all slugs.",
                    },
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    idx = _require_index()

    if name == "tapestry_docs_search":
        query = arguments.get("query", "")
        limit = int(arguments.get("limit", 5))
        hits = idx.search(query, limit=limit)
        payload = [
            {"slug": h.slug, "title": h.title, "score": h.score, "snippet": h.snippet}
            for h in hits
        ]
        return [TextContent(type="text", text=json.dumps({"hits": payload}, indent=2))]

    if name == "tapestry_docs_read":
        slug = arguments.get("slug", "")
        doc = idx.get(slug)
        if doc is None:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"slug not found: {slug}"}),
            )]
        return [TextContent(
            type="text",
            text=json.dumps({
                "slug": doc.slug,
                "title": doc.title,
                "description": doc.description,
                "section": doc.section,
                "body": doc.body,
            }, indent=2),
        )]

    if name == "tapestry_docs_list":
        section = arguments.get("section")
        slugs = idx.list_slugs(section=section if section else None)
        return [TextContent(type="text", text=json.dumps({"slugs": slugs}, indent=2))]

    return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]
