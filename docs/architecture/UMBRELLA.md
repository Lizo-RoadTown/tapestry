# Tapestry architecture — UMBRELLA

The canonical home of the enterprise-scale architecture for the project-intelligence platform.

**Status:** Initial spawn 2026-06-12. Reframed 2026-06-13 per operator: Tapestry is the canonical product system; the-loom + Make_Skills are legacy prototype/source repos that will be migrated into Tapestry and retired after parity. The prior stub at `the-loom/docs/architecture/UMBRELLA.md` points forward to this document; that stub stays in place during the migration phase as a cross-link to the canonical architecture.

> **2026-06-18 reconciliation patch.** This document was the stalest binding doc while CLAUDE.md routes new agents to it as authoritative. Three corrections applied below to match the v1 roadmap + PROBE'd reality (see [`../plans/2026-06-18-unified-integration-understanding.md`](../plans/2026-06-18-unified-integration-understanding.md) §5): (1) `candidate-registry/` is **absorbed by** `architecture-registry/` (they share a table), not a separate service; (2) `project-observatory/` is a **23-line `/health` stub** today, not a mature deployed service — its Phase-6 content is built in Tapestry; (3) the observer topology (self-observer / local-observer / runtime-observer / observation-decomposer / project-observatory) is being resolved in [`../adr/0001-observer-topology.md`](../adr/0001-observer-topology.md) — do not read the rows below as settling it.

## Framing rules (binding)

1. **Tapestry is the canonical product system.** the-loom + Make_Skills are legacy source repos.
2. **Every capability listed below is a Tapestry product capability.** Some are currently prototyped in the legacy repos. During migration, the prototype version remains live as a source/compatibility provider — temporarily.
3. **Once a capability reaches parity in Tapestry, the legacy version is frozen.** Once all useful capabilities are migrated, the legacy repo is archived or made read-only.
4. **No final runtime dependency on the-loom or Make_Skills as separate systems.** Customers experience ONE product: Tapestry.
5. **Migration remains incremental.** No big-bang. But the destination is not optional — every prototype change should have a declared import path into Tapestry.
6. **New product-facing architecture decisions land in Tapestry first.** Prototype repos may continue only for isolated experiments or pre-migration stabilization.

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
| `project-observatory/` | Read/query/visibility layer over observations + signals (Grafana views). **STUB today: `the-loom/services/project-observatory/main.py` is 23 lines (`/health` only); Phase-6 content is built in Tapestry, not lifted.** Observer topology pending [ADR-0001](../adr/0001-observer-topology.md). | `the-loom/services/project-observatory/` (stub) | `loom-project-observatory.onrender.com` |
| ~~`candidate-registry/`~~ **(ABSORBED)** | Path A + Path B promotion candidates — **merged into `architecture-registry/` (shared table) per v1 roadmap §3; this slot is retired, not a separate service.** Physical dir removal deferred to migration execution. | `the-loom/services/architecture-registry/` | `loom-architecture-registry.onrender.com` |
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
| `cli/` | `tapestry init` / `tapestry init` CLI for project spawning | `the-loom/scripts/new-loom-project.ps1` (manual placeholder) |
| `shared-types/` | TypeScript / Pydantic types shared across apps + services | Scattered today |
| `schemas/` | OpenAPI + JSON Schema + SQL migrations as schemas | Scattered today |
| `auth/` | Shared auth: tenant resolution, JWT verification | `the-loom/services/agent-context/auth_bridge.py` + `Make_Skills/core/auth/` |
| `ui/` | Shared React component library across apps | Not yet built |

### `integrations/` — connectors

| Integration | Purpose | Source prototype |
|---|---|---|
| `mcp/` | MCP server packaging + manifest publishing | `the-loom/services/agent-context/` (already an MCP) |
| `vscode/` | VSCode extension | Not yet built |
| `claude-code/` | Claude Code plugin (the discipline plugin) | `Lizo-RoadTown/claude-skills-marketplace/plugins/make-skills-discipline/` (now `tapestry-discipline`) |
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
Plugin (tapestry-discipline) emits telemetry + session-end upskilling report
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
| **operator (Liz)** | Canonical decisions on naming, scope, sequencing, agent spawning, what merges, what archives | Always |
| **Tapestry-agent** | **Owns the canonical product system.** Migration choreography, import maps, API/schema contracts, naming consistency, ADR discipline, deciding what imports / what retires / what stays prototype-only. Actively prevents the-loom and Make_Skills from continuing as permanent product boundaries. | **Spawn now** per operator directive 2026-06-13 |
| **loom-agent** | Legacy-source steward for `the-loom/`. Stabilizes capabilities pre-migration; hands them off to Tapestry-agent on parity. Not a permanent role. | Spawned, active in `the-loom` (transitional) |
| **MS-agent** | Legacy-source steward for `Make_Skills/`. Stabilizes engine + skill-making + adapters + templates pre-migration; hands them off to Tapestry-agent on parity. Not a permanent role. | Spawned, active in `Make_Skills` (transitional) |
| **security-review-agent** | Reviewing candidate of kind=`inline_tool`/`external_tool` touching FS/network/shell. Veto power. Possibly extending to architecture-pattern + service kinds | **Not yet spawned** |

The matrix is intentionally small. Tapestry-agent is the only permanent product role; the legacy-source stewards retire when their source repos are archived.

## How Tapestry relates to legacy repos

See [`../migration/legacy-repo-inventory.md`](../migration/legacy-repo-inventory.md).

**Summary:** Tapestry is the canonical product system. the-loom and Make_Skills are legacy source repos.

- **the-loom** is the source prototype for: agent-context MCP, project-registry, project-observatory, telemetry-ingestion, architecture/candidate-registry, policy, audit patterns, dashboard, Claude Code discipline plugin, scaffolder/CLI source material, auth bridge, Grafana integration, deploy configuration. Each migrates into a named Tapestry destination; the legacy version freezes on parity.
- **Make_Skills** is the source prototype for: agency-to-structure engine, skill-compiler, bridge receiver, skill-making services, project-type adapters, default template seeds, runtime/tool telemetry. Each migrates into a named Tapestry destination; the legacy version freezes on parity.

Migration is incremental — no big-bang, no pause-and-port. But the destination is not optional. Each prototype change should carry a declared import path into Tapestry. Once all useful capabilities are migrated, the legacy repo is archived or made read-only. **No final runtime dependency on the-loom or Make_Skills as separate systems.**

Prior framings that implied permanent boundaries ("loom-side ownership", "Tapestry subscribes to loom", "Tapestry catches up to prototypes") are superseded by this rule.

## Related

- [`../migration/README.md`](../migration/README.md) — migration approach
- [`../migration/legacy-repo-inventory.md`](../migration/legacy-repo-inventory.md) — per-repo audit
- [`../migration/import-map.md`](../migration/import-map.md) — what moves where
- `../adr/` — architectural decision records as Tapestry decisions land
