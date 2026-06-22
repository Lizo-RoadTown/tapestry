# Proposal: The Observatory — the coordination-reinforcement console

**Status:** Open — needs operator decisions on cross-project scoping, observatory-service timing, friction source, and context derivation (see Open questions).
**Authors:** Liz, agent-assisted (Tapestry-agent)
**Date:** 2026-06-22
**Governed by:** [Canon: User-Agent Coordination Reinforcement](../canon/user-agent-coordination-reinforcement.md). Tapestry is a user/agent support and reinforcement system; the primary object is **operator-agent coordination**; memory, telemetry, observability, architecture, friction/correction, upskilling, and policy are **reinforcement mechanisms**; projects are environments; interfaces/surfaces are one manifestation.

## Problem

Step 6 lifted `the-loom/apps/web-dashboard/` into `apps/web-dashboard/` byte-identically — a single-project upskilling console (candidates queue + a Grafana iframe), scoped to one tenant. Tapestry is not that. Tapestry strengthens, stabilizes, and evolves operator-agent coordination over time, and its named failure mode is **invisible absence** (memory missing, hooks not firing, snapshots gone, drift, silent assumptions). There is no surface that shows the health of coordination across projects and the mechanisms reinforcing it.

## Insight

The console is not "Grafana for agents," and it is not an interface monitor. It shows **coordination** — the object — and the **mechanisms** that reinforce it. Projects are the environments coordination occurs in; a surface (interface/workflow) is one manifestation, attached to a coordination context. The honest constraint, which the UI encodes rather than papers over: most coordination signal is not instrumented yet — the observer is a static shape-drift scanner only ([runtime-observation-deferred:38](2026-06-18-runtime-observation-deferred-to-tapestry.md)), and `services/project-observatory/` is a ~24-line stub ([same:216](2026-06-18-runtime-observation-deferred-to-tapestry.md)). So every mechanism is labeled **available / planned / missing**, shown by glyph + label (not color alone).

## Decision: build the Observatory in the docs site, organized object → mechanisms → contexts

Operator decision (2026-06-22): the console lives **inside the docs site** (`apps/docs-site/src/pages/observatory.astro`, route `/observatory`) — same Astro project, deploy, and domain — not a separate Next.js app. A first version is built (PR #32), styled with the SDE_Extraction design system.

The model:

```text
Coordination                      (the object — what Tapestry reinforces)
  ↓ reinforced by
Mechanisms                        (memory · telemetry · observability · architecture ·
  ↓                                friction/correction · upskilling · policy · runtime)
Coordination contexts             (instances, each anchored on coordination_context_id)
  ↓ within
Projects (environments) · Surfaces (one manifestation)
```

### Mechanism → data source → availability

| Mechanism | Reinforces | Data source | Availability |
|---|---|---|---|
| Memory | learning persists + is recalled in time | `services/agent-context` (loom-memory MCP) — live | available (writes/recalls); missing for staleness/miss detection |
| Architecture analysis | shape changes that alter coordination are caught | architecture snapshots/diffs (`scripts/architecture_snapshot.py`) | available (static per repo) |
| Policy & audit | decisions about durability are recorded + replayable | `services/policy` + `services/audit-log` | available |
| Observability | observer surfaces drift/stabilization | `services/architecture-registry` + self-observer | planned (shape-drift only; not coordination-attributed) |
| Upskilling | repeated coordination becomes a skill | architecture-registry + `services/skill-making` | planned |
| Telemetry | actions attributable to coordination quality | the coordination-telemetry contract (below) + `telemetry-ingestion` | planned |
| Friction / correction | recurring misunderstandings made legible | `feedback`/`lesson` memos (not aggregated) | missing |
| Runtime analysis | invocation/tool/session behavior as coordination health | runtime-observer (`services/project-observatory`) | missing |

## Telemetry contract (Tapestry-agent owns; transport is loom-agent's)

Because the console consumes it, Tapestry-agent owns the coordination-telemetry **contract**: the model + attributes. loom-agent owns the transport (OTLP collector, `telemetry-ingestion`, Grafana). The model is **not** `project → service → trace → span`; it is anchored on `coordination_context_id` (not `interface_id`), and every significant event answers: *did this strengthen, weaken, or reveal something about coordination?* Attributes: `coordination_context_id`, `project_id`, `surface_id`/`surface_type`, `agent_id`/`agent_role`, `user_intent_id`, `memory_read_count`/`memory_write_count`/`memory_miss`, `correction_present`, `friction_type`, `upskill_candidate`, `architecture_context_hash`, `diff_report_id`. (Relayed for transport: `tapestry_to_loom_agent_otel_coordination_context_shape_2026_06_22`.)

## Implementation phases

| Phase | Scope | Output | Blocks |
|---|---|---|---|
| **P1: Object→mechanisms→contexts shell** (done, PR #32) | the model rendered with honest availability; derived contexts | A real coordination-reinforcement console; absence shown, not faked | All later phases |
| **P2: Wire available mechanisms to live data** | memory (agent-context), architecture (snapshots), policy/audit per context | available mechanisms read real state | Step 7 (architecture-registry + policy migrated) for the observer/policy reads |
| **P3: Friction / correction + upskilling** | aggregate `feedback`/`lesson` memos into per-context friction; attribute candidates | Friction + Upskilling mechanisms | a friction-classification pass over agent-context |
| **P4: Telemetry + runtime** | emit the coordination-telemetry contract; wire runtime-observer | Telemetry + Runtime mechanisms (real) | **Blocked on** runtime-observer build (deferred; loom-agent transport) |

## Two-mode notes

| Mode | What changes |
|---|---|
| **Self-host** | One operator tenant; coordination contexts are the operator's own across connected projects (`project-registry`); RLS scopes to the operator. |
| **Hosted-multitenant** | Console attaches a Bearer JWT; contexts scoped to the tenant; per-project + per-tenant RLS. Deferred; the coordination_context anchor does not need a rewrite to add it. |

## Open questions

1. **Cross-project scoping:** client fans out per `project_id` (`project-registry`), or does `services/project-observatory` own server-side aggregation of coordination contexts?
2. **`services/project-observatory/` timing:** migrate the aggregation API first, or wait for the runtime-observer it houses (currently deferred)?
3. **Friction source:** aggregate `feedback`/`lesson` memos now (P3), or wait for dedicated friction instrumentation?
4. **Context derivation:** how is a coordination context identified — derived heuristically from project environment × agent roles × surfaces (cheap, P1's approach), declared in `.project-intelligence/`, or inferred from runtime once instrumented?

## What this implies for the next action

P2: wire the already-available mechanisms (memory, architecture, policy) to live data per coordination context — turning the derived shell (PR #32) into a partial live readout, still honest about the planned/missing mechanisms. Waits on Open question 1 and on Step 7 for the policy/observer reads.

## Sources

- [`docs/canon/user-agent-coordination-reinforcement.md`](../canon/user-agent-coordination-reinforcement.md) — **the governing canon**
- [`apps/docs-site/src/pages/observatory.astro`](../../apps/docs-site/src/pages/observatory.astro) — the built console (PR #32)
- [`docs/adr/0001-observer-topology.md`](../adr/0001-observer-topology.md) — observer roles
- [`docs/proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md`](2026-06-18-runtime-observation-deferred-to-tapestry.md) — what coordination-quality signal does not exist yet
- [`docs/plans/2026-06-22-extended-migration-audit.md`](../plans/2026-06-22-extended-migration-audit.md) — Step-7 services the policy/observer mechanisms read
