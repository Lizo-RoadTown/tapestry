# packages/sdk

Shared runtime primitives for Tapestry services.

## Layout

```
sdk/
├── python/
│   ├── pyproject.toml       # loom-sdk package
│   └── loom_sdk/
│       ├── __init__.py
│       ├── db.py            # tenant_conn + shared pool helper
│       └── secrets.py       # pgcrypto BYO-API-key storage
```

## What lives here

- **db.py** — `tenant_conn(ctx)` async context manager. Every tenant-scoped query in any Tapestry service goes through this chokepoint. Sets `app.tenant_id` via SET LOCAL so Postgres RLS policies enforce isolation per-transaction.
- **secrets.py** — Tenant-scoped, encrypted-at-rest BYO API keys (pgcrypto `pgp_sym_encrypt`). **Requires the `student_secrets` table — see the module docstring; migration not yet shipped.**

## What will eventually live here

Per [`docs/plans/2026-06-22-extended-migration-audit.md`](../../docs/plans/2026-06-22-extended-migration-audit.md) §2.2:

- `providers/` — multi-provider LangChain resolver
- `tools/db.py` — read-only Postgres SQL tool for the agent
- `observability/` — Make_Skills' observability module

## Why this is a separate package from `packages/auth/`

- `packages/auth/` (`loom-auth`) owns identity + tenant resolution at the request boundary (FastAPI `verify_bearer`, MCP `LoomTokenVerifier`). Mode-aware (self-host vs hosted-multitenant). Light deps (jose, fastapi, mcp).
- `packages/sdk/` (`loom-sdk`) owns runtime primitives that any service uses INTERNALLY once tenant context is established. Heavier deps (psycopg, eventually langchain). Mode-orthogonal.

Services that need both depend on both. Services that only do request-boundary auth (e.g., a thin proxy) depend only on `loom-auth`.

## Earlier "slot, not yet built" framing

This README previously described `packages/sdk/` as an empty slot for a consumer-facing typed client. That framing was the originally-planned shape. The actual first inhabitants of the directory are runtime primitives — driven by audit §1.2 + §2.2's findings that Make_Skills' `core/db/db.py`, `core/auth/secrets.py`, and `core/runtime/` modules need a stable home, and `packages/auth/` would be over-broadened by absorbing them.

A consumer-facing typed client may still live under `packages/sdk/` in a sibling subdirectory (e.g. `packages/sdk/typescript/`, `packages/sdk/cli/`) when that work begins.
