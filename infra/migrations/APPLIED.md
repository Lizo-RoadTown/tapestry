# Applied-state ledger — which migration ran where

One row per (migration file × database). This file is the record of applied
state for the TAPESTRY series; update it in the same change that applies a
migration. "Not applied" rows are listed so absence is explicit, never
guessed. Convention: migrations run manually via the Render PSQL console
(the-loom/infra/migrations/README.md convention); every application adds a
row here with evidence. Tapestry's series is the canonical schema
source-of-truth per [ADR-0003](../../docs/adr/0003-shared-postgres-schema-source-of-truth.md).

> The-loom has its OWN, separately numbered applied series (its 005/006 are
> candidate-type alters — numbering collision only, no table overlap). Its
> ledger-of-record is the-loom/infra/migrations/README.md. New applications
> there are frozen; new schema work happens in this series.

| File | Database | Applied | Evidence |
|---|---|---|---|
| 000_init_platform.sql | live loom-postgres | yes (via the-loom series, pre-fork) | the-loom migrations README |
| 001_init_memory.sql | live loom-postgres | yes (forklift, agent-context cutover 2026-06-21) | runbook 02; records table live (209 rows at cutover) |
| 001_init_memory.sql | tapestry staging Postgres | yes (staging parity 2026-06-20) | render.yaml staging block |
| 002_init_projects.sql | live loom-postgres | yes (project-registry live) | runbook 03 |
| 004_init_policy.sql | live loom-postgres | yes (equivalent applied via the-loom's 004; tapestry file is a forklift copy) | the-loom series; policy_decisions live |
| 005_init_telemetry.sql | live loom-postgres | **NOT APPLIED** | gate for runbook 05 step A2 |
| 005_init_telemetry.sql | tapestry staging Postgres | yes (observer-capacity staging, 2026-08-23) | render.yaml:101-137 staging observatory reads it |
| 006_init_observation_signals.sql | live loom-postgres | **NOT APPLIED** | gate for runbook 05 step A2 |
| 006_init_observation_signals.sql | tapestry staging Postgres | yes (2026-08-23) | staging observation_signals |
| 007_init_candidates.sql | live loom-postgres | **NOT APPLIED** (live candidates table predates it via the-loom series; 007 is the consolidated forklift, gated by the architecture-registry repoint checks 1/1b/1c) | render.yaml:200-206 |

Unknowns are listed as NOT APPLIED until verified against the database —
never silently converted to applied (prototype-reconstruction procedure,
step 2).
