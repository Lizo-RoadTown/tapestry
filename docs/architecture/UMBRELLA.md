# Tapestry architecture — UMBRELLA

The canonical home of the enterprise-scale architecture for the project-intelligence platform.

**Status:** Initial spawn 2026-06-12. The prior stub at `the-loom/docs/architecture/UMBRELLA.md` points forward to this document; that stub stays in place during the parallel-build phase as a cross-link.

## What this document covers

- The bounded contexts (apps, services, engine, packages, integrations, templates, infra) and what each owns
- The data flow end-to-end (telemetry, candidates, promotion decisions, policy state, audit)
- The deploy topology (which Render service is what, where Vercel apps live, MCP wiring, JWT/auth boundaries)
- The ownership matrix (which agent owns which slice)
- How Tapestry relates to the existing legacy prototype repos

## The architecture in one paragraph

**Tapestry is the recursive skill-engine platform.** Users + operators run consuming projects (templates seeded from `templates/`). Each consuming project's agent emits session-end upskilling reports + telemetry to platform `services/`. The `engine/local-observer` parses sessions into candidates. `services/candidate-registry` stores them. `services/policy` decides on promotion. `engine/skill-compiler` turns approved candidates into runnable skills. `apps/web-dashboard` lets the operator watch and act on the loop. `packages/sdk` + `packages/cli` make Tapestry installable into new consuming projects.

## Bounded contexts

### `apps/` — operator-facing surfaces

| App | Purpose | Source prototype |
|---|---|---|
| `web-dashboard/` | Operator dashboard: skill library, tool library, candidates, promotions, observability | `the-loom/apps/web-dashboard/` (live, Vercel-deployed at `loom.humancensys.com`) |
| `admin-console/` | Administrative surfaces (tenant management, audit log inspection, policy editing) | Not yet built |
| `docs-site/` | Public documentation site (architecture, API, SDK guides) | Not yet built |

### `services/` — bounded backend services

Each service owns one concern, has its own deploy unit, exposes a clear API.

| Service | Purpose | Source prototype | Render service (if deployed) |
|---|---|---|---|
| `agent-context/` | Memory MCP — cross-session, cross-project semantic memory | `the-loom/services/agent-context/` | `loom-agent-context.onrender.com` |
| `project-registry/` | Project / repo / machine registration + tenant resolution | `the-loom/services/project-registry/` | `loom-project-registry.onrender.com` |
| `project-observatory/` | Telemetry aggregation for observation (Grafana + project-formation views) | `the-loom/services/project-observatory/` | `loom-project-observatory.onrender.com` |
| `candidate-registry/` | Path A + Path B promotion candidates (status, evidence, signals) | `the-loom/services/architecture-registry/` (may split into two) | `loom-architecture-registry.onrender.com` |
| `architecture-registry/` | Durable ratified structure (architecture nodes, ADR records, ratified skills) | same prototype source | same |
| `policy/` | Policy decisions: promote, hold, reject, demote. Audit-immutable | `the-loom/services/policy/` | `loom-policy.onrender.com` |
| `audit-log/` | Cross-service audit log aggregation + retention | Partial (each service has its own audit today) | — |
| `telemetry-ingestion/` | OTLP ingest + signal/event normalization upstream of Observatory | `the-loom/adapters/.../observatory hooks` + Project Observatory | — |
| `skill-making/` | Receives bridge messages from `engine/`, emits registration acks | `Make_Skills/services/skill_making/bridge_receiver.py` (stub) | — |

### `engine/` — the recursive skill engine

The compute layer: agent loop, observation, compilation, adaptation.

| Slot | Purpose | Source prototype |
|---|---|---|
| `agency-to-structure/` | The core engine that converts repeated agency into structure (the agency-to-structure boundary rule, applied) | `Make_Skills/core/` (runtime, providers, orchestration, auth, db) |
| `skill-compiler/` | SKILL.md → runnable `langchain` `StructuredTool` | `Make_Skills/core/skill_making/compiler.py` |
| `local-observer/` | Watches sessions + memory writes + tool calls; emits candidates | `the-loom/adapters/claude-code/loom-discipline/scripts/observer.py` |
| `adapters/{classroom,development,research,operations}/` | Project-type adapters: watches list, pattern triggers, system prompts, default skills, observatory events | `Make_Skills/adapters/{classroom,development,research-project}/` + new `operations/` |

### `packages/` — distributable shared code

| Package | Purpose | Source prototype |
|---|---|---|
| `sdk/` | Tapestry SDK for consumer integration | Not yet built |
| `cli/` | `loom init` / `tapestry init` CLI for project spawning | `the-loom/scripts/new-loom-project.ps1` (manual placeholder) |
| `shared-types/` | TypeScript / Pydantic types shared across apps + services | Scattered today |
| `schemas/` | OpenAPI + JSON Schema + SQL migrations as schemas | Scattered today |
| `auth/` | Shared auth: tenant resolution, JWT verification | `the-loom/services/agent-context/auth_bridge.py` + `Make_Skills/core/auth/` |
| `ui/` | Shared React component library across apps | Not yet built |

### `integrations/` — connectors

| Integration | Purpose | Source prototype |
|---|---|---|
| `mcp/` | MCP server packaging + manifest publishing | `the-loom/services/agent-context/` (already an MCP) |
| `vscode/` | VSCode extension | Not yet built |
| `claude-code/` | Claude Code plugin (the discipline plugin) | `Lizo-RoadTown/claude-skills-marketplace/plugins/make-skills-discipline/` (now `loom-discipline`) |
| `codex/` | OpenAI Codex CLI integration | Not yet built |
| `github/` | GitHub Actions + GitHub App | Not yet built |
| `grafana/` | Grafana dashboards + alerts | Embedded in `the-loom/services/project-observatory/` |

### `templates/` — seed templates for new projects

| Template | Project type | Source prototype |
|---|---|---|
| `classroom-project/` | Classroom-support apps | `Lizo-RoadTown/classroom-hub-starter` + `Make_Skills/adapters/classroom/default-seed/` |
| `software-project/` | Software dev repos | `Lizo-RoadTown/web-starter` + `Make_Skills/adapters/development/default-seed/` |
| `research-project/` | Research / knowledge-synthesis | `Make_Skills/adapters/research-project/default-seed/` |
| `operations-project/` | Operations / SRE workflows | Not yet built |

### `infra/` — deploy artifacts

| Path | Purpose |
|---|---|
| `docker/` | Dockerfiles + docker-compose for local dev |
| `terraform/` | IaC for cloud deploys (Render, Vercel, Postgres, S3) |
| `migrations/` | Cross-service migration tooling |
| `deploy/` | Render `render.yaml`, Vercel configs, deploy scripts |

## Data flow (end-to-end)

```text
Consuming project session
  ↓
Plugin (loom-discipline) emits telemetry + session-end upskilling report
  ↓
services/telemetry-ingestion → services/project-observatory (Grafana)
                              ↘ engine/local-observer
                                  ↓
                              POSTs candidates to services/candidate-registry
                                  ↓
                              services/policy decides (manual first, automation later)
                                  ↓
                              If promoted:
                                  ↓
                              engine/skill-compiler compiles
                                  ↓
                              services/architecture-registry stores durable structure
                                  ↓
                              packages/sdk pulls into consumer projects on next sync
```

## Ownership matrix

| Agent | Domain | Spawned? |
|---|---|---|
| **operator (Liz)** | Decisions on naming, scope, sequencing, agent spawning, what merges, what archives | Always |
| **loom-agent** | Currently: `the-loom/` (legacy platform prototype). Eventual: Tapestry `services/` consolidation + `engine/local-observer/` import + `apps/web-dashboard/` import | Spawned, active in `the-loom` |
| **MS-agent** | Currently: `Make_Skills/` (legacy engine prototype). Eventual: Tapestry `engine/` consolidation + `services/skill-making/` + `templates/*` from default-seed/ | Spawned, active in `Make_Skills` |
| **Tapestry-agent** | Eventually: cross-service consolidation, schema unification, API contract enforcement, the migration choreography | **Not yet spawned** — open decision |
| **security-review-agent** | Reviewing candidate of kind=`inline_tool`/`external_tool` touching FS/network/shell. Veto power. Possibly extending to architecture-pattern + service kinds | **Not yet spawned** |

The matrix is intentionally small. We aren't planning for many agents — we're planning for clean separation of concerns. New agent roles go through periodic-architectural-checkin discipline.

## How Tapestry relates to legacy repos

See [`../migration/legacy-repo-inventory.md`](../migration/legacy-repo-inventory.md).

Summary: prototype repos remain primary development homes. Tapestry slots get populated incrementally as each piece matures. No big-bang migration; no premature consolidation. Tapestry catches up to the prototypes; the prototypes don't pause for Tapestry.

## Related

- [`../migration/README.md`](../migration/README.md) — migration approach
- [`../migration/legacy-repo-inventory.md`](../migration/legacy-repo-inventory.md) — per-repo audit
- [`../migration/import-map.md`](../migration/import-map.md) — what moves where
- `../adr/` — architectural decision records as Tapestry decisions land
