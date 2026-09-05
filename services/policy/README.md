# `services/policy/`

**Status:** Migrated from the-loom (Lift/Refactor, CORE DIRECTIVE 2). Code present; **not yet cut over** (the live `loom-policy` Render service still builds from the-loom until the operator performs the repoint — see [Cutover](#cutover)).

The Policy Service: the audit-of-record for operator/agent decisions over candidate status transitions. It records `approve` / `reject` / `hold` / `demote` decisions, exposes them for query, and derives a per-candidate policy-state aggregate. Phase 5 of the recursive-skill engine.

**Intentionally SOFT this phase.** It RECORDS decisions and exposes policy-state; it does NOT call architecture-registry to apply them. The architecture-registry's `PATCH /candidates/{id}/status` remains the write surface; a downstream caller (UI / future workflow agent) reads policy-state, then issues the PATCH. This keeps the bounded-context contract clean and decouples deploys.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness probe (no DB touch). |
| POST | `/decisions` | Record a decision. `CheckViolation → 400` guard on enum drift. |
| GET | `/decisions` | List (filters: `candidate_id`, `decision_kind`; `limit`/`offset`). Ordered `decided_at DESC`. |
| GET | `/candidates/{candidate_id}/policy-state` | Per-candidate aggregate: summary (`is_held` / `is_approved_for` / `is_rejected`) + full decision chain. Empty aggregate (not 404) if no decisions. |

## Layout

- `main.py` — FastAPI app + all endpoints. `CheckViolation → 400` handler preserved at the decision-create path.
- `models.py` — Pydantic models. `DECISION_KIND` (4 kinds) + `TARGET_STATUS` (the 7 candidate statuses). `extra="forbid"` on request bodies blocks client-supplied `tenant_id`.
- `storage.py` — async psycopg3 pool + RLS tenant scoping via `set_config('app.tenant_id', …, true)`. No UPDATE path (audit-immutable by construction).
- `auth_bridge.py` — shim re-exporting `packages/auth/python/loom_auth/auth_bridge` (self-host / hosted-multitenant). Identical to architecture-registry's.
- `tests/` — invariant + contract tests. `pytest` green (12 tests, DB-free).

## Two-mode

Every path is agnostic to how the tenant was resolved. Self-host: `SELF_HOST_TENANT_ID` (env-driven, falls back to the all-zeros UUID that the RLS COALESCE default also uses — fail-closed). Hosted-multitenant: the JWT `tenant_id` claim. RLS does the isolation; the code never branches on mode. The invariant that the auth fallback equals the migration's RLS COALESCE default is pinned by `tests/test_policy_invariants.py::test_self_host_fallback_matches_migration_rls_default`.

## Audit-immutability

`policy_decisions` has **no UPDATE RLS policy** — UPDATE attempts fail as a policy violation. Decisions are append-only; to revise one, file a NEW decision with `extra.supersedes = <old_decision_id>`. This is pinned by `test_migration_has_no_update_policy`.

## Cross-service id discipline (Pillar 0)

`candidate_id` is owned by architecture-registry. Policy stores it but adds **no foreign key** — the audit trail is allowed to reference candidates that were later deleted, and an FK would couple deploy order across bounded contexts. Cross-context joins happen at the read layer.

## Schema / migration

`infra/migrations/004_init_policy.sql` — the `policy_decisions` table, CHECK constraints, indexes, and RLS policies. Kept at **004** (not renumbered): slot 004 is free in Tapestry, and policy is a single migration with no intermediate evolution to consolidate (contrast the candidate schema, whose the-loom 003/005/006 collapsed into Tapestry 007). It is **idempotent** and a **no-op replay** against the live DB. No `ALTER COLUMN` width fix is needed (contrast 007's R1): 004 is policy's original creation migration, so no column is pre-existing-and-narrower.

## Cutover

Cutover is a **repoint of the EXISTING `loom-policy` Render service** at the Tapestry repo + `rootDir services/policy` — the same mechanism used for agent-context and architecture-registry. **NOT** a new/duplicate service: same name → same URL → the dashboard and any policy-state readers keep working unchanged. It reuses the LIVE `loom-postgres` (no `databases:`/`fromDatabase`; `LOOM_DB_URL` is a `sync:false` secret). The disabled service block is in `infra/deploy/render.yaml` (`autoDeploy:false`; does nothing until the operator enables it). policy is SOFT/pure-audit → **no** `LOOM_SKILL_BRIDGE_SECRET`, **no** engine URLs.

**Steps (operator, per runbook):**

1. **GATE — verify the live DB matches the migrated models BEFORE repointing.**
   - **CHECK constraints** — confirm the live `policy_decisions_kind_check` is exactly `approve, reject, hold, demote` and `policy_decisions_target_status_check` is exactly the 7 candidate statuses in `models.py::TARGET_STATUS`:
     ```sql
     SELECT conname, pg_get_constraintdef(oid)
     FROM pg_constraint
     WHERE conrelid = 'policy_decisions'::regclass AND contype = 'c';
     ```
   - **Column widths** — `SELECT column_name, character_maximum_length FROM information_schema.columns WHERE table_name='policy_decisions' AND column_name IN ('decision_kind','target_status');` must be ≥ 16 and ≥ 24 respectively. Expected to already hold (004 is the original creation migration).
   - **Tenant continuity** — `SELECT DISTINCT tenant_id FROM policy_decisions;` must equal the `SELF_HOST_TENANT_ID` you set in step 4 (`1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8`). If they differ, self-host reads scope to the nil UUID and return **zero** historical decisions. STOP and fix the env var first.
2. Apply `004_init_policy.sql` against the live DB if desired for parity — it is a safe no-op (idempotent guards; live rows already satisfy the CHECKs).
3. Get written operator authorization; ensure the-loom blueprint stops deploying `loom-policy` (ONE-BLUEPRINT invariant).
4. Enable the block in `infra/deploy/render.yaml`, set `LOOM_DB_URL` (live loom-postgres) + `LOOM_JWT_PUBLIC_KEY` (from the shared secret group) + **`SELF_HOST_TENANT_ID=1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8`**, and repoint the Render service.
5. Smoke: `/health`, a read `GET /decisions`, and a `GET /candidates/{id}/policy-state`. **Do not POST test decisions to the live registry.**

**Rollback:** re-point the Render service's repo back to the-loom (code byte-parity; the shared DB is untouched by a repoint).

## Source

`the-loom/services/policy/` (live: `loom-policy.onrender.com`, shipped 2026-06-12).
