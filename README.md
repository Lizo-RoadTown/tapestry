# Tapestry

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**The enterprise system-of-record monorepo for the project-intelligence platform.** Tapestry is where the prototype boundaries — discovered through the existing multi-repo experimentation — consolidate into a clean architecture once each piece has matured in its current home.

## What Tapestry is

A single source-control house with **bounded services, clear APIs, clear schemas, clear deploy units, clear ownership**. Internal structure:

- **`apps/`** — user-facing and operator-facing surfaces (web dashboard, admin console, docs site)
- **`services/`** — bounded backend services (agent context, project registry, project observatory, candidate registry, architecture registry, policy, audit log, telemetry ingestion, skill-making)
- **`engine/`** — the recursive skill engine (agency-to-structure core, skill compiler, local observer, per-project-type adapters)
- **`packages/`** — distributable shared code (SDK, CLI, shared types, schemas, auth, UI components)
- **`integrations/`** — connectors (MCP, VSCode, Claude Code, Codex, GitHub, Grafana)
- **`templates/`** — project-type seed templates (classroom, software, research, operations)
- **`infra/`** — deploy artifacts (Docker, Terraform, migrations, deploy configs)
- **`docs/`** — architecture, ADRs, API contracts, security, migration
- **`deprecated/`** — legacy imports retained while audit completes

## Parallel-build status

**This is a parallel-build, not a pause-and-migrate.** The existing prototype repos (`the-loom`, `Make_Skills`, `loom-platform`, plus consuming projects) **continue to be built in**. Tapestry slots are seeded incrementally as each piece matures in its current home.

This is intentional: a lot of the architecture is still being discovered through experimentation. Premature consolidation would import unfinished structure into a "clean" repo where the messiness would just relocate.

See [`docs/migration/README.md`](docs/migration/README.md) for the migration approach.

## What's here today (initial spawn)

- The skeleton directory tree with per-slot READMEs explaining each slot's purpose and source
- Architecture docs in [`docs/architecture/`](docs/architecture/) — canonical version of the platform's bounded contexts
- Migration docs in [`docs/migration/`](docs/migration/) — inventory + import map + what-to-keep / what-to-retire / naming-corrections
- `LICENSE` (Apache 2.0)
- `CLAUDE.md` (agent discipline)
- `ROADMAP.md` (what's in flight in legacy repos + migration sequencing)

**Zero code yet.** Imports happen in deliberate small PRs as legacy sources mature.

## How to consume / extend Tapestry today

This repo is **private during the prototype phase**. Once the architecture stabilizes and imports complete, Tapestry will flip public — that's the "enterprise public release" target.

While private:

1. Engine work continues in `Lizo-RoadTown/Make_Skills`
2. Platform work continues in `Lizo-RoadTown/the-loom`
3. Consuming-project prototypes continue in their own repos (Hub, SDE_Extraction, loom-platform, etc.)
4. Imports to Tapestry happen via curated PRs that pull stable pieces in and update the relevant `docs/migration/import-map.md` entry

## License

Apache 2.0 — see [LICENSE](LICENSE).
