# `services/project-observatory/`

**Status:** Scaffold — Phase 1 task 2 (observer-capacity build), 2026-08-23. DB pool, thresholds, self-host tenant resolver, and a `/health` app are in place; the signal computation, materialization entrypoint, and read endpoint are NOT here yet.

## Purpose

The **runtime-observer**'s home (ADR-0001 [`docs/adr/0001-observer-topology.md`](../../docs/adr/0001-observer-topology.md): runtime-observer + read layer live here).

It reads the Phase-0 telemetry substrate directly from **Postgres** (`loom-postgres`), computes observation signals over a window, and writes them to `observation_signals`, which this service also serves:

- **Reads** `telemetry_events` + `telemetry_rollup_daily` ([`../../infra/migrations/005_init_telemetry.sql`](../../infra/migrations/005_init_telemetry.sql)) — the events/rollups telemetry-ingestion persists.
- **Computes** the signals ADR-0001 names — `hot_path`, `orphaned`, `degrading` — plus `blind`, per artifact over an observation window.
- **Writes** those to `observation_signals` ([`../../infra/migrations/006_init_observation_signals.sql`](../../infra/migrations/006_init_observation_signals.sql)); signals are **evidence, not candidates** (no automation level, no activation).
- **Serves** the stored signals from the read layer (Phase 1 task 5).
- A **Render cron** triggers the compute pass on a schedule; this process serves health now and the read endpoint later.

> No Grafana/Loki dependency. Earlier stubs framed this slot as "Grafana-backed views" — that is retired. The observer reads Postgres so a self-host operator with no Grafana Cloud still gets stored, queryable telemetry and signals (self-host parity, per [`../../docs/plans/2026-08-23-observer-capacity-build-sequence.md`](../../docs/plans/2026-08-23-observer-capacity-build-sequence.md)).

## What's here (Phase 1 task 2 scaffold)

- `db.py` — Postgres pool + `tenant_transaction()` wrapper, copied near-verbatim from `services/telemetry-ingestion/db.py`: same `LOOM_DB_URL` env var, same `set_config('app.tenant_id', …, true)` RLS mechanism. Reads the 005 substrate and writes 006, both RLS-scoped.
- `config.py` — the signal-computation thresholds (window, `hot_path`, `degrading`) + the `SIGNAL_KINDS` tuple that matches the 006 CHECK. All values are design defaults, tunable in one place. Imported by the compute step (task 3).
- `tenant.py` — the self-host tenant resolver (`SELF_HOST_TENANT_ID` → `LOOM_SELF_HOST_TENANT_ID` → nil, fail-closed), duplicated from telemetry-ingestion's `read_api._resolve_read_tenant` / `skill_usage_handler._self_host_tenant_id` (separate Render deploys — nothing clean to import across the boundary; source of truth noted in-file).
- `main.py` — minimal FastAPI app: `GET /health` + a lifespan that closes the pool on shutdown (mirrors telemetry-ingestion).
- `requirements.txt` — fastapi/uvicorn + psycopg/psycopg-pool, versions matched to the sibling service.

## Two-mode

- **Self-host:** the point of the Postgres substrate — signals computed and stored without Grafana Cloud. `tenant.py` scopes to `SELF_HOST_TENANT_ID` (fails closed rather than reading/writing the all-zeros tenant).
- **Hosted-multitenant:** same substrate, tenant-scoped by the JWT tenant claim (added when this service gains hosted read auth). `db.py` is agnostic to how the tenant was resolved — it only stamps `app.tenant_id`; RLS does the isolation.

## What's next (later PRs, not this one)

Per [`../../docs/plans/2026-08-23-observer-capacity-build-sequence.md`](../../docs/plans/2026-08-23-observer-capacity-build-sequence.md) Phase 1:

- **Task 3** — the signal computation: read 005 over the window, compute `hot_path` / `orphaned` / `degrading` / `blind` using `config.py`'s thresholds.
- **Task 4** — the materialization entrypoint: write a run's signals to `observation_signals` (the Render cron target).
- **Task 5** — the read endpoint over `observation_signals`.

## Provenance

- the-loom: `services/project-observatory/` (health stub only; retired).
- Plan: [`../../docs/plans/2026-08-23-observer-capacity-build-sequence.md`](../../docs/plans/2026-08-23-observer-capacity-build-sequence.md) (Phase 1).
- Schema: [`../../infra/migrations/006_init_observation_signals.sql`](../../infra/migrations/006_init_observation_signals.sql) (observation_signals; already merged).
