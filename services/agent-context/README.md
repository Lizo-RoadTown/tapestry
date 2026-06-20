# `services/agent-context/`

**Status:** Populated — Step 2 (agent-context MCP lift), 2026-06-20. Code lifted; **not yet deployed** (runbook gates pending).

The loom-memory **MCP host** — cross-session, cross-project semantic memory. This is the service every session in every repo depends on (CORE DIRECTIVE 1).

## What's here

Verbatim **Lift** (`cmp`-verified identical) of `the-loom/services/agent-context/`:
- `main.py` — FastAPI app: `/health`, REST `/v1/write` + `/v1/read` (B1).
- `mcp_http.py` — MCP streamable-HTTP transport mounted at `/mcp/memory/`.
- `mcp_server.py` — MCP tool handlers (memory_read/write/recall/search/list/delete).
- `mcp_self_host_middleware.py` — sets `SELF_HOST_TENANT_ID` when no Bearer.
- `storage.py` — Postgres + pgvector; RLS by tenant.
- `auth_bridge.py` — thin shim re-exporting `loom_auth` from `packages/auth/` (resolves via `parents[2]/packages/auth/python` — works unchanged because Tapestry mirrors the-loom's layout).
- `tests/`, `requirements.txt`, `requirements-test.txt`.

Companion schema: [`../../infra/migrations/001_init_memory.sql`](../../infra/migrations/001_init_memory.sql) — forklift of the `records` table (per [ADR-0003](../../docs/adr/0003-shared-postgres-schema-source-of-truth.md)).

## Migration status

Governed by [`runbooks/02-agent-context-mcp.md`](../../docs/migration-cicd/runbooks/02-agent-context-mcp.md). **Decision: Lift.** The `auth_bridge.py` shim is kept as-is (removing it is a deferred Refactor). Safety design: the eventual deploy preserves the Render service name (`loom-agent-context`) + URL + DB (`loom-postgres`) so **consumers are unchanged** and rollback is re-pointing Render at the-loom.

## Provenance
- the-loom: `services/agent-context/` (live at `loom-agent-context.onrender.com`)
- loom-memory: `tapestry_decision_adr_0003_ratified_step2_runbook_proposed_2026_06_20`
