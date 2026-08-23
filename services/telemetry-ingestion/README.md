# `services/telemetry-ingestion/`

**Status:** Populated — Phase 0 tasks 2–4 + 6 (observer-capacity build), 2026-08-23. Receiver migrated from the-loom; Postgres persistence (task 3), the discipline-hook ingest + mapper (task 4), and the read API (task 6) are in place.

Coordination-telemetry receiver. The write-side entry point for the observer's read-substrate: engine/hook/tool events arrive here, get authenticated + validated, and (from task 3 on) land in Postgres where the runtime-observer and self-observer can read them without depending on Grafana Cloud.

## What's here

Migrated **verbatim** from `the-loom/services/telemetry-ingestion/` (retired) as the working base:

- `bridge_hmac.py` — HMAC-SHA256 transport auth (`X-MakeSkills-Signature`, ±5-min replay window, shared `LOOM_SKILL_BRIDGE_SECRET`). Authenticates the sender, not the tenant.
- `bridge_models.py` — the Pydantic wire contract (`TelemetryEvent` / `TelemetryBatch`). Keeps `extra='forbid'` and the **no-message-content privacy invariant** (structural metadata only).
- `main.py` — FastAPI receiver: `GET /health` + `POST /skill-used` + `POST /hook-events` (+ `/hook-event` alias). Each verifies HMAC on the raw body -> parses -> hands to its handler -> 202 ack.
- `skill_usage_handler.py` — `apply_batch`; Postgres write via the shared `persist.persist_events` (task 3).
- `hook_event_handler.py` — `apply_hook_events`; maps flat discipline-hook entries (bare keys + `tapestry.*` attrs) -> 005 columns, project-attributed by slug (task 4).
- `persist.py` — the shared low-level write path (`persist_events(conn, rows)`): the CTE `INSERT ... ON CONFLICT (id) DO NOTHING RETURNING` feeding the `telemetry_rollup_daily` UPSERT. Both `/skill-used` and `/hook-events` call it, so there is ONE verified dedup+rollup mechanism.

Added new in Tapestry (task 2):

- `db.py` — Postgres pool + `tenant_transaction()` wrapper, mirroring `services/agent-context` and `services/project-registry`: same `LOOM_DB_URL` env var, same `set_config('app.tenant_id', …, true)` RLS mechanism. **Present but unused by `apply_batch` until task 3.**
- `requirements.txt` — fastapi/uvicorn/pydantic + psycopg/psycopg-pool (versions matched to the sibling services).

Companion schema: [`../../infra/migrations/005_init_telemetry.sql`](../../infra/migrations/005_init_telemetry.sql) — `telemetry_events` + `telemetry_rollup_daily`, RLS-scoped by `app.tenant_id` (already merged, Phase 0 task 1).

## Two-mode

- **Self-host:** the whole point of the Postgres substrate — a self-host operator with no Grafana Cloud still gets stored, queryable telemetry. `db.py` scopes to `SELF_HOST_TENANT_ID` (falls back to the all-zeros UUID the 005 policies default to).
- **Hosted-multitenant:** same substrate, tenant-scoped by the JWT tenant claim. `db.py` is agnostic to how the tenant was resolved — it only stamps `app.tenant_id`; RLS does the isolation.

## What's next (later PRs, not this one)

Per [`docs/plans/2026-08-23-observer-capacity-build-sequence.md`](../../docs/plans/2026-08-23-observer-capacity-build-sequence.md) Phase 0:

- **Task 3 (done)** — the log-only `apply_batch` now writes to Postgres via `persist.persist_events` inside a tenant-scoped transaction.
- **Task 4 (done)** — `POST /hook-events` (+ `/hook-event`) + bare-key -> contract mapper (`hook_event_handler.py`). This is what gives telemetry PROJECT ATTRIBUTION: hook entries carry `project_id` (the slug) -> `project_slug`, and the signal flags (`tapestry.friction_present`, `tapestry.memory_miss`, `tapestry.correction_present`, `tapestry.upskill_candidate_present`) land in `attrs` under the exact names `/telemetry/signals` queries.
- **Task 6 (done)** — read/query API (`read_api.py`) that the runtime-observer and self-observer call.

### `/hook-events` contract (task 5's emitter must match)

- Method/path: `POST /hook-events` (canonical, batch) or `POST /hook-event` (single). Body is one entry object, a JSON array of entries, or `{"events": [...]}` (max 1000/request).
- Entry shape: the flat dict `_observability.log_event` writes (`ts`, `hook`, `phase`, `session_id`, `tool_name`, `project_id`, `exit_code`, `elapsed_ms`, `note`, `action`, plus any `tapestry.*` attrs).
- Auth: HMAC-SHA256 (`bridge_hmac`), header `X-Loom-Hook-Signature: t=<unix>,v1=<hex>`, shared secret **`LOOM_HOOK_BRIDGE_SECRET`** (separate from the engine's `LOOM_SKILL_BRIDGE_SECRET`). Verified on the raw bytes before parsing; ±5-min replay window.
- Idempotency: server derives a stable `uuid5` id from `session_id + hook_name + phase + tool_name + ts`, so task 7's `flush-hooks-jsonl` backfill can replay the same lines and dedup on `ON CONFLICT (id) DO NOTHING`.
- Ack: `202 {events_processed: N}` (replayed duplicates excluded).

## Provenance

- the-loom: `services/telemetry-ingestion/` (log-only receiver; no DB, no read API).
- Plan: `docs/plans/2026-08-23-observer-capacity-build-sequence.md` (Phase 0 task breakdown).
