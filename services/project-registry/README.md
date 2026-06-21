# `services/project-registry/`

**Status:** Populated — Step 3 (project-registry lift), 2026-06-20. Code lifted; **not yet deployed** (runbook gates pending).

Project / repo / machine registration + tenant resolution.

## What's here

Verbatim **Lift** (`cmp`-verified identical) of `the-loom/services/project-registry/`: `main.py` (CRUD for projects/repos/machines), `models.py`, `storage.py` (Postgres, RLS by tenant), `auth_bridge.py` (shim → `loom_auth`, resolves via `parents[2]/packages/auth/python`), `requirements.txt`.

Companion schema: [`../../infra/migrations/002_init_projects.sql`](../../infra/migrations/002_init_projects.sql) — forklift of `projects`/`repos`/`machines` (per [ADR-0003](../../docs/adr/0003-shared-postgres-schema-source-of-truth.md)).

## Migration status

Governed by [`runbooks/03-project-registry.md`](../../docs/migration-cicd/runbooks/03-project-registry.md). **Decision: Lift.** The net-new **signup endpoint** (roadmap §5 Step 3) is NOT part of this verbatim lift — it's deferred. Cutover is the same re-source pattern as the MCP (preserve name `loom-project-registry` + URL + DB), but lower blast radius (CRUD service, not the memory MCP).

## Provenance
- the-loom: `services/project-registry/` (live at `loom-project-registry.onrender.com`)
- loom-memory: `tapestry_step2_staging_parity_verified_2026_06_20` (precedent)
