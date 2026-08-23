# `services/telemetry-ingestion/`

**Status:** Populated — Phase 0 task 2 (observer-capacity build), 2026-08-23. Receiver migrated from the-loom; Postgres persistence + read API are later tasks.

Coordination-telemetry receiver. The write-side entry point for the observer's read-substrate: engine/hook/tool events arrive here, get authenticated + validated, and (from task 3 on) land in Postgres where the runtime-observer and self-observer can read them without depending on Grafana Cloud.

## What's here

Migrated **verbatim** from `the-loom/services/telemetry-ingestion/` (retired) as the working base:

- `bridge_hmac.py` — HMAC-SHA256 transport auth (`X-MakeSkills-Signature`, ±5-min replay window, shared `LOOM_SKILL_BRIDGE_SECRET`). Authenticates the sender, not the tenant.
- `bridge_models.py` — the Pydantic wire contract (`TelemetryEvent` / `TelemetryBatch`). Keeps `extra='forbid'` and the **no-message-content privacy invariant** (structural metadata only).
- `main.py` — FastAPI receiver: `GET /health` + `POST /skill-used` (verify HMAC -> parse -> `apply_batch` -> 202 ack).
- `skill_usage_handler.py` — `apply_batch`, still the **log-only** emit (stdout -> Loki). Marked at the top of file for Phase 0 task 3 replacement.

Added new in Tapestry (task 2):

- `db.py` — Postgres pool + `tenant_transaction()` wrapper, mirroring `services/agent-context` and `services/project-registry`: same `LOOM_DB_URL` env var, same `set_config('app.tenant_id', …, true)` RLS mechanism. **Present but unused by `apply_batch` until task 3.**
- `requirements.txt` — fastapi/uvicorn/pydantic + psycopg/psycopg-pool (versions matched to the sibling services).

Companion schema: [`../../infra/migrations/005_init_telemetry.sql`](../../infra/migrations/005_init_telemetry.sql) — `telemetry_events` + `telemetry_rollup_daily`, RLS-scoped by `app.tenant_id` (already merged, Phase 0 task 1).

## Two-mode

- **Self-host:** the whole point of the Postgres substrate — a self-host operator with no Grafana Cloud still gets stored, queryable telemetry. `db.py` scopes to `SELF_HOST_TENANT_ID` (falls back to the all-zeros UUID the 005 policies default to).
- **Hosted-multitenant:** same substrate, tenant-scoped by the JWT tenant claim. `db.py` is agnostic to how the tenant was resolved — it only stamps `app.tenant_id`; RLS does the isolation.

## What's next (later PRs, not this one)

Per [`docs/plans/2026-08-23-observer-capacity-build-sequence.md`](../../docs/plans/2026-08-23-observer-capacity-build-sequence.md) Phase 0:

- **Task 3** — replace the log-only `apply_batch` with the Postgres write (`telemetry_events` INSERT + `telemetry_rollup_daily` UPSERT) inside a tenant-scoped transaction using `db.py`.
- **Task 4** — `POST /hook-event` + bare-key -> contract mapper.
- **Task 6** — read/query API (`/telemetry/invocations`, then counts / signals / episode) that the runtime-observer and self-observer call.

## Provenance

- the-loom: `services/telemetry-ingestion/` (log-only receiver; no DB, no read API).
- Plan: `docs/plans/2026-08-23-observer-capacity-build-sequence.md` (Phase 0 task breakdown).
