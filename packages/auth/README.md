# `packages/auth/`

**Status:** Populated — Step 1 (auth consolidation), 2026-06-20.

Shared JWT auth + tenant resolution for Tapestry services. Lifted verbatim from the canonical `the-loom/packages/auth/` that PR-prep-2b consolidated (the-loom commits `23b3055` + `77aaabc`, which merged the prior 4 duplicate `auth_bridge.py` copies into one).

## Public API (`loom_auth`)

| Symbol | Consumer |
|---|---|
| `verify_bearer` | FastAPI dependency (architecture-registry, policy, project-registry, future services) |
| `LoomTokenVerifier` | MCP SDK `TokenVerifier` (agent-context HTTP transport) |
| `SELF_HOST_TENANT_ID` | stable self-host tenant UUID (`1d8ec1b3-…`) |
| `tenant_ctx_var` | per-request tenant contextvar (shared by both consumers) |
| `resolve_tenant` | plain-call accessor (contextvar → `SELF_HOST_TENANT_ID` fallback) |

## Two-mode

- **Self-host** (no auth header / no `LOOM_JWT_PUBLIC_KEY`) → `SELF_HOST_TENANT_ID`.
- **Hosted-multitenant** (Bearer RS256 JWT + public key) → `tenant_id` claim drives RLS.
- Bearer-present-but-unverifiable → 401 (never silent self-host fallback).

The `mcp` import is lazy-guarded (`try/except ImportError`) so the 3 FastAPI services that never instantiate `LoomTokenVerifier` don't need `mcp` in their venv — preserved verbatim from the-loom fix `77aaabc` (the regression that broke 3 deploys on 2026-06-19; do not undo).

## Decision: Lift (minimal change)

- Files copied byte-identical from `the-loom/packages/auth/` (verified `cmp`). The package was deliberately shape-for-lift.
- **Package name `loom_auth` kept as-is for now** — renaming to a Tapestry name touches every importer and is a deferred decision (no functional impact; the-loom services still import `loom_auth`). Tracked, not done here.
- Companion: [`../../infra/migrations/000_init_platform.sql`](../../infra/migrations/000_init_platform.sql) (platform `tenants` + `tenant_id_mapping`).

## Provenance / related
- the-loom: `packages/auth/python/loom_auth/` (`23b3055`, `77aaabc`)
- loom-memory: `session_state_pr_prep_2b_shipped_2026_06_19`, `decision_tenant_id_mapping_option_b_2026_06_12`
- Plan: [`../../docs/plans/2026-06-18-tapestry-migration-readiness-and-execution.md`](../../docs/plans/2026-06-18-tapestry-migration-readiness-and-execution.md) §5 Step 1
