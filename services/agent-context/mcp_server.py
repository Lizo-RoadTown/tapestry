"""
MCP server exposing the shared memory store for the-loom.

Six tools, matching the Claude Code session memory protocol's operations:

  memory_read(name)              — fetch one memory by name
  memory_list(record_type?)      — index entries (no body)
  memory_write(name, content,
               record_type, why?)— upsert a memory row
  memory_delete(name)            — soft-delete (visibility="deleted")
  memory_search(query, ...)      — semantic search over content
  memory_recall(context, n=5)    — top-N relevant for a conversation start

Two transports:

- **Stdio** (`if __name__ == "__main__":` block at bottom) — Liz's local
  self-host invocation. No auth; tenant_ctx_var stays at its default
  (the stable self-host UUID below). Wire via .claude/mcp.json:

      {"loom-memory": {"command": "python", "args": ["-m", "services.agent-context.mcp_server"]}}

- **HTTP** — wired by mcp_http.py + mcp/memory-server/main.py. Every
  request is gated by LoomTokenVerifier (auth_bridge.py); on success
  the verifier sets tenant_ctx_var with the JWT-derived tenant_id.

Ported from Make_Skills/platform/api/memory/mcp_server.py with three
material changes:
  1. `from . import lance` (sync, LanceDB) → `from . import storage`
     (async, Postgres + pgvector). All handlers became `async def`
     and use `await storage.*`. Already were async-def in the SDK
     contract; the lance calls were sync-in-async (event-loop-blocking).
  2. tenant_ctx_var default: string "default" → stable UUID
     (uuid5 from 'liz.loom.humancensys.com'). Matches the schema's
     tenant_id UUID NOT NULL column.
  3. memory_write simplification: Make_Skills did delete-then-insert
     because LanceDB lacks UPSERT. storage.insert_records uses Postgres
     INSERT...ON CONFLICT DO UPDATE — one atomic call. Dropped the
     intermediate `existing` fetch + manual delete. `replaced_existing`
     field in the response is gone; if you need it, do a get_by_id
     first.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

import storage


# ---------------------------------------------------------------------------
# Per-request tenant (set by HTTP transport's TokenVerifier; default for stdio)
# ---------------------------------------------------------------------------

# Add packages/auth/python to sys.path so `loom_auth` is importable without
# pip install. parents[0]=agent-context/, parents[1]=services/, parents[2]=the-loom/.
_PKG_PATH = Path(__file__).resolve().parents[2] / "packages" / "auth" / "python"
if str(_PKG_PATH) not in sys.path:
    sys.path.insert(0, str(_PKG_PATH))

from loom_auth import SELF_HOST_TENANT_ID, tenant_ctx_var  # noqa: E402

# Back-compat alias. PR-prep-2b (2026-06-19) consolidated the
# self-host UUID into `loom_auth.SELF_HOST_TENANT_ID`. Kept here so
# `from mcp_server import DEFAULT_SELF_HOST_TENANT_ID` still works for
# tests/test_mcp_self_host_fallback.py:212 and any external readers.
DEFAULT_SELF_HOST_TENANT_ID = SELF_HOST_TENANT_ID


def _resolve_tenant() -> str:
    """Return the per-request tenant_id for MCP operations.

    Self-host stdio: returns SELF_HOST_TENANT_ID (canonical UUID; the
    contextvar's default is None, so the fallback applies).
    Self-host HTTP: middleware sets the contextvar to SELF_HOST_TENANT_ID
    (or env-overridden value); returns it.
    Hosted HTTP: returns the JWT-derived tenant_id set by LoomTokenVerifier.
    """
    return tenant_ctx_var.get() or SELF_HOST_TENANT_ID


# Soft-delete marker — preserves the row but excludes it from reads/list/search.
VISIBILITY_DELETED = "deleted"

# Memory types — runtime episodic (recorder emits these from /chat turns) +
# session long-term (typed-file friction-as-memory protocol). The schema's
# CHECK constraint enforces this; we list here so input validation can
# reject early instead of at the DB layer.
VALID_RUNTIME_TYPES = frozenset(
    {"decision", "lesson", "preference", "skill_idea", "topic", "fact"}
)
VALID_SESSION_TYPES = frozenset({"user", "feedback", "project", "reference"})
VALID_TYPES = VALID_RUNTIME_TYPES | VALID_SESSION_TYPES


# ---------------------------------------------------------------------------
# Helpers — bridge the file-protocol's typed-file convention to records rows
# ---------------------------------------------------------------------------


def _id_from_name(name: str) -> str:
    """Memory name (e.g. 'feedback_documentation_tone') IS the row id.
    No filesystem extension; the protocol is name-centric."""
    return name.strip()


def _row_to_client_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Strip internal fields and return a client-friendly shape."""
    return {
        "name": row.get("id"),
        "type": row.get("type"),
        "content": row.get("content"),
        "why": row.get("why"),
        "ts": row.get("ts"),
        "visibility": row.get("visibility"),
        "actor": row.get("actor"),
    }


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

server: Server = Server("loom-memory")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="memory_read",
            description=(
                "Read a single memory by name. Returns the typed memory's "
                "type, content, why, and timestamp. Returns null if absent."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Memory name (matches the file-protocol's filename "
                            "without extension, e.g. 'feedback_documentation_tone')."
                        ),
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="memory_list",
            description=(
                "List memories as index entries (no body). Returns an "
                "array of {name, type, ts, summary} entries. Optionally "
                "filter by record_type."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "record_type": {
                        "type": "string",
                        "enum": sorted(VALID_TYPES),
                    },
                    "limit": {"type": "integer", "default": 100},
                },
            },
        ),
        Tool(
            name="memory_write",
            description=(
                "Upsert a memory. Creates a new row or replaces an existing "
                "one with the same name. The record_type is one of: "
                + ", ".join(sorted(VALID_TYPES))
                + ". 'why' is the reason field used for feedback / project / "
                "lesson / decision memories — academically grounded as the "
                "WHY-bound-to-content property of episodic memory."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "content": {
                        "type": "string",
                        "description": "Full body markdown. Frontmatter is optional and treated as content.",
                    },
                    "record_type": {
                        "type": "string",
                        "enum": sorted(VALID_TYPES),
                    },
                    "why": {
                        "type": "string",
                        "description": "Optional. Reason / motivation for feedback / project / lesson / decision memories.",
                    },
                    "actor": {
                        "type": "string",
                        "description": "Optional. Which agent kind wrote this — e.g. 'claude-code', 'cursor', 'subagent:researcher-coordinator'. Defaults to 'unknown'.",
                    },
                    "project_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional. Which projects this memory applies to. Empty/missing = cross-project (the user's default scope).",
                    },
                    "extra": {
                        "type": "object",
                        "description": "Optional. Free-form metadata: orchestration_id, run_id, parent_session_id, affected_entities, trigger, outcome, etc.",
                    },
                },
                "required": ["name", "content", "record_type"],
            },
        ),
        Tool(
            name="memory_delete",
            description=(
                "Soft-delete a memory. The row is preserved with visibility='deleted' "
                "so recovery is possible; reads / list / search exclude it."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="memory_search",
            description=(
                "Semantic search over memory content. Returns top-N by vector "
                "similarity. Optionally filter by record_type and project_tags."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "record_type": {
                        "type": "string",
                        "enum": sorted(VALID_TYPES),
                    },
                    "project_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="memory_recall",
            description=(
                "Load top-N memories relevant to a conversation context. "
                "Use at session start to surface accumulated knowledge without "
                "reading every memory file. Returns full memory bodies. "
                "Defaults to all of the user's memories (cross-project)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": (
                            "A short description of what the conversation is about "
                            "(e.g. 'starting work on the auth flow'). Used as the "
                            "semantic search anchor."
                        ),
                    },
                    "project_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional. Restrict to memories tagged with at least one of these projects. Empty = all of user's memories.",
                    },
                    "n": {"type": "integer", "default": 5},
                },
                "required": ["context"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Single dispatch entry. Each branch maps to one tool and returns a JSON-ish
    response wrapped in a TextContent block (MCP's content envelope)."""

    tenant_id = _resolve_tenant()

    if name == "memory_read":
        row = await storage.get_by_id(
            record_id=_id_from_name(arguments["name"]),
            tenant_id=tenant_id,
            include_deleted=False,
        )
        result = _row_to_client_dict(row) if row else None
        return [TextContent(type="text", text=json.dumps(result))]

    if name == "memory_list":
        record_type = arguments.get("record_type")
        limit = int(arguments.get("limit", 100))
        rows = await storage.list_records(
            tenant_id=tenant_id,
            limit=limit,
            record_type=record_type,
            include_public=False,
        )
        # Drop deleted; project the index-entry shape.
        entries = [
            {
                "name": r.get("id"),
                "type": r.get("type"),
                "ts": r.get("ts"),
                "summary": (r.get("content") or "").split("\n", 1)[0][:200],
                "actor": r.get("actor"),
            }
            for r in rows
            if r.get("visibility") != VISIBILITY_DELETED
        ]
        return [TextContent(type="text", text=json.dumps(entries))]

    if name == "memory_write":
        record_type = arguments["record_type"]
        if record_type not in VALID_TYPES:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": f"invalid record_type: {record_type}"}
                    ),
                )
            ]
        record = {
            "id": _id_from_name(arguments["name"]),
            "type": record_type,
            "content": arguments["content"],
            "project_tags": arguments.get("project_tags", []),
            "source_thread_id": "",
            "ts": time.time(),
            "why": arguments.get("why", ""),
            "actor": arguments.get("actor", "unknown"),
            "extra": arguments.get("extra", {}),
        }
        # Atomic upsert via INSERT...ON CONFLICT DO UPDATE in storage layer.
        # Make_Skills did delete-then-insert (LanceDB lacks UPSERT); we don't.
        inserted = await storage.insert_records(
            [record], tenant_id=tenant_id, visibility="private"
        )
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "ok": True,
                        "name": record["id"],
                        "inserted": inserted,
                    }
                ),
            )
        ]

    if name == "memory_delete":
        # Soft-delete: re-insert the row with visibility='deleted'. Preserves
        # content so a future memory_recover() can undelete.
        existing = await storage.get_by_id(
            record_id=_id_from_name(arguments["name"]),
            tenant_id=tenant_id,
            include_deleted=True,
        )
        if existing is None:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"ok": False, "reason": "not_found"}),
                )
            ]
        if existing.get("visibility") == VISIBILITY_DELETED:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"ok": True, "already_deleted": True}),
                )
            ]
        record = {
            "id": _id_from_name(arguments["name"]),
            "type": existing.get("type") or "project",
            "content": existing.get("content") or "",
            "project_tags": existing.get("project_tags") or [],
            "source_thread_id": existing.get("source_thread_id") or "",
            "ts": existing.get("ts") or time.time(),
            "why": existing.get("why") or "",
            "actor": existing.get("actor") or "unknown",
            "extra": existing.get("extra") or {},
        }
        await storage.insert_records(
            [record], tenant_id=tenant_id, visibility=VISIBILITY_DELETED
        )
        return [TextContent(type="text", text=json.dumps({"ok": True}))]

    if name == "memory_search":
        rows = await storage.search(
            query=arguments["query"],
            tenant_id=tenant_id,
            limit=int(arguments.get("limit", 5)),
            record_type=arguments.get("record_type"),
            project_tags=arguments.get("project_tags"),
            include_public=False,
        )
        # Soft-deleted rows are excluded by the storage layer's WHERE
        # clauses when caller has visibility != 'deleted' default, but
        # the search() function doesn't currently filter — keep the
        # post-filter here defensively until storage.search exposes
        # a `exclude_deleted` flag (deferred).
        results = [
            _row_to_client_dict(r)
            for r in rows
            if r.get("visibility") != VISIBILITY_DELETED
        ]
        return [TextContent(type="text", text=json.dumps(results))]

    if name == "memory_recall":
        rows = await storage.search(
            query=arguments["context"],
            tenant_id=tenant_id,
            limit=int(arguments.get("n", 5)),
            project_tags=arguments.get("project_tags"),
            include_public=False,
        )
        results = [
            _row_to_client_dict(r)
            for r in rows
            if r.get("visibility") != VISIBILITY_DELETED
        ]
        return [TextContent(type="text", text=json.dumps(results))]

    return [
        TextContent(
            type="text", text=json.dumps({"error": f"unknown tool: {name}"})
        )
    ]


# ---------------------------------------------------------------------------
# Stdio entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
