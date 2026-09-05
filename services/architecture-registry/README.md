# `services/architecture-registry/`

**Status:** Migrated from the-loom (Lift/Refactor, CORE DIRECTIVE 2). Code present; **not yet cut over** (the live `loom-architecture-registry` Render service still builds from the-loom until the operator performs the repoint — see [Cutover](#cutover)).

The Architecture Registry's candidate slice: the promotion-candidate store. It accepts promotion candidates from Path A (local observer) and Path B (platform observatory), persists them, exposes them for query, drives their status lifecycle, and bridges promoted `skill` candidates to the Make_Skills engine.

Per the ratified recommendation, the **candidate-registry lives here** — candidates are NOT split into a separate service. The `services/candidate-registry/` slot stays a stub.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness probe (no DB touch). |
| POST | `/candidates` | Register a candidate (Path A + Path B). Pre-checks project visibility (cross-tenant FK guard). |
| GET | `/candidates` | List (filters: `project_id`, `status`, `source_path`, `candidate_type`; `limit`/`offset`). |
| GET | `/candidates/{id}` | Get one (404 if absent or RLS-hidden). |
| PATCH | `/candidates/{id}/status` | Transition status (+ optional `reason` appended to `evidence_refs` as a `status_change` audit entry). Auto-dispatches to the engine when target=`promotion_requested` AND kind=`skill`. |
| POST | `/candidates/{id}/dispatch-promotion` | Manual re-dispatch to the engine. |
| POST | `/skill-registered` | Engine→registry `RegistrationAck` receiver. HMAC-authed (`X-MakeSkills-Signature`), NOT a Bearer endpoint. |

## Layout

- `main.py` — FastAPI app + all endpoints. The defensive `CheckViolation → 400` handler (anticipating Pydantic↔SQL enum drift) is preserved at the candidate-create path.
- `models.py` — Pydantic models. `CANDIDATE_TYPE` has exactly the **9 kinds**; `extra="forbid"` on request bodies blocks client-supplied `tenant_id`.
- `storage.py` — async psycopg3 pool + RLS tenant scoping via `set_config('app.tenant_id', …, true)`.
- `auth_bridge.py` — shim re-exporting `packages/auth/python/loom_auth/auth_bridge` (self-host / hosted-multitenant).
- `bridge_hmac.py`, `bridge_models.py`, `promote_dispatcher.py`, `registration_handler.py` — the skill-making bridge (HMAC sign/verify, wire contract, dispatch, ack apply).
- `tests/` — invariant + contract + dispatcher + handler + auto-dispatch tests. `pytest` green (66 tests, DB-free).

## Two-mode

Every path is agnostic to how the tenant was resolved. Self-host: `SELF_HOST_TENANT_ID` (env-driven, falls back to the all-zeros UUID that the RLS COALESCE default also uses — fail-closed). Hosted-multitenant: the JWT `tenant_id` claim. RLS does the isolation; the code never branches on mode.

## Schema / migration

`infra/migrations/007_init_candidates.sql` — the candidates table at the terminal **9-kind** `candidate_type` CHECK, RLS policies, indexes, and the `updated_at` trigger.

This **consolidates** the-loom's three candidate migrations (`003_init_candidates` + `005_alter_candidate_type` + `006_expand_candidate_type_to_9_kinds`) into one, renumbered to the next free Tapestry number (003/004 predate the split; 005/006 are already taken by telemetry + observation-signals). It is consolidated rather than three-renumbered on purpose: the intermediate 4-kind CHECK cannot be safely replayed against the already-9-kind live DB. The migration is **idempotent** and a **no-op replay** against the live DB. See the header of the SQL file for the full rationale.

## Cutover

Cutover is a **repoint of the EXISTING `loom-architecture-registry` Render service** at the Tapestry repo + `rootDir services/architecture-registry` — the same mechanism used for agent-context. It is **NOT** a new/duplicate service: same name → same URL → both observers and the dashboard keep working unchanged. It reuses the LIVE `loom-postgres` (no `databases:`/`fromDatabase`; `LOOM_DB_URL` is a `sync:false` secret). The disabled service block is in `infra/deploy/render.yaml` (`autoDeploy:false`; does nothing until the operator enables it).

**Steps (operator, per runbook):**

1. **GATE — verify the live DB matches the migrated models BEFORE repointing.** Confirm the live `candidates_type_check` is exactly the 9 kinds in `models.py::CANDIDATE_TYPE`:
   ```sql
   SELECT pg_get_constraintdef(oid)
   FROM pg_constraint
   WHERE conname = 'candidates_type_check';
   ```
   It must list: `skill, inline_tool, external_tool, architecture_pattern, service, machine_support, process, agent, orchestration`. If it does not match, STOP — do not repoint.
2. Apply `007_init_candidates.sql` against the live DB if desired for parity — it is a safe no-op there (idempotent guards; live rows already satisfy the 9-kind CHECK).
3. Get written operator authorization.
4. Ensure the-loom blueprint stops deploying `loom-architecture-registry` (ONE-BLUEPRINT invariant).
5. Enable the block in `infra/deploy/render.yaml`, set `LOOM_DB_URL` (live loom-postgres) + `LOOM_SKILL_BRIDGE_SECRET` (same value as the engine) + `LOOM_JWT_PUBLIC_KEY`, and repoint the Render service.
6. Smoke: `/health`, a read `GET /candidates`, and a signed `/skill-registered` round-trip. **Do not POST test candidates to the live registry.**

**Rollback:** re-point the Render service's repo back to the-loom (code byte-identical; the shared DB is untouched by a repoint).

## Source

`the-loom/services/architecture-registry/` (live: `loom-architecture-registry.onrender.com`).
