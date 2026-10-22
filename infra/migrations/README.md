# `infra/migrations/`

The canonical schema series for the fleet's shared Postgres
([ADR-0003](../../docs/adr/0003-shared-postgres-schema-source-of-truth.md):
tapestry owns the schema source-of-truth; proven schemas are forklifted,
redesigns are explicit decisions).

## Convention

- Migrations are **applied manually** via the Render PSQL console (the
  convention inherited from the-loom's series), one file at a time, in
  numeric order where dependencies exist.
- **Every application is recorded in [`APPLIED.md`](APPLIED.md)** — file ×
  database × date × evidence — in the same change. An unrecorded
  application does not count as applied; an unverified state is recorded as
  NOT APPLIED or unknown, never guessed.
- Migrations are written idempotent (`IF NOT EXISTS` / additive) so a
  re-run is safe.
- **Numbering:** this series is canonical. The-loom's separately numbered
  legacy series (its 005/006 are candidate-type alters) is frozen; the
  collision with this series' 005/006 is numbering-only, no table overlap.
  New schema work lands here.

## Current files

| File | Creates |
|---|---|
| 000_init_platform.sql | platform base |
| 001_init_memory.sql | records (loom memory, pgvector) |
| 002_init_projects.sql | projects / repos / machines |
| 004_init_policy.sql | policy_decisions |
| 005_init_telemetry.sql | telemetry_events + telemetry_rollup_daily (RLS) |
| 006_init_observation_signals.sql | observation_signals (signals ≠ candidates) |
| 007_init_candidates.sql | candidates (consolidated 9-kind) |
