# Proposal: The web-dashboard becomes the Project Observatory console

**Status:** Open — needs operator decisions on UI home, cross-project scoping, and observatory-service migration timing (see Open questions).
**Authors:** Liz, agent-assisted (Tapestry-agent), with an outside agent's reframe
**Date:** 2026-06-22

## Problem

Step 6 lifted `the-loom/apps/web-dashboard/` into `apps/web-dashboard/` byte-identically. What landed is a **single-project upskilling console**: a candidates queue (Promote/Hold/Reject), a recent-decisions verification list, and a Grafana iframe — all scoped to one tenant (the self-host operator), reading from `loom-architecture-registry` + `loom-policy`. Its own README frames it as "the-loom's running interface… Tapestry, which is unrelated" ([apps/web-dashboard/README.md:9](../../apps/web-dashboard/README.md)).

That framing is now stale. Tapestry's stated value is **cross-project memory, agent updates, and pattern promotion across projects**, and its named failure mode is **invisible absence** — memory missing, hooks not firing, architecture snapshots gone, agent drift, silent assumptions. The dashboard is the natural surface for making that absence visible. Scoped to one project and one signal (upskilling candidates), it does not do that.

There is also already a tapestry concept for this: `services/project-observatory/` — *"Telemetry aggregation for observation; Grafana-backed views of project formation + runtime activity"* ([services/project-observatory/README.md](../../services/project-observatory/README.md)), the migration target of the live `loom-project-observatory.onrender.com`, and the home ADR-0001 assigns to the **runtime-observer** ([docs/adr/0001-observer-topology.md:21](../adr/0001-observer-topology.md)). The dashboard should be that service's UI surface.

## Insight

The dashboard is not "Grafana but for agents." It is **a surface for watching agency become structure** — project morphology over time: how each connected project is forming, drifting, learning, breaking, and stabilizing. Grafana-style runtime telemetry is one input among several; the deeper content is the shape of each project and the loop that turns repeated behavior into durable structure (observe → candidate → policy decision → compiled skill).

The honest constraint, which the UI must encode rather than paper over: **most of the runtime signal does not exist yet.** The observer today is a static shape-drift scanner — *"the observer reliably catches frontmatter+description shape drift. It does not observe runtime invocation patterns, telemetry events, cross-session signals, or session-end upskilling reports"* ([docs/proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md:38](2026-06-18-runtime-observation-deferred-to-tapestry.md)). `services/project-observatory/` is a ~24-line stub ([same doc:216](2026-06-18-runtime-observation-deferred-to-tapestry.md)). So every layer must be labeled **available now**, **planned signal**, or **missing instrumentation**.

## Decision: evolve `apps/web-dashboard/` into the Project Observatory console — a layered, cross-project surface backed by `services/project-observatory/`

The dashboard becomes a multi-project console answering: (1) is this project wired correctly? (2) what changed recently? (3) what are the agents doing? (4) what is the observer seeing? (5) what friction keeps recurring? (6) what is ready to become durable structure? (7) what is missing, stale, broken, or drifting?

Each question is a **layer**. Each layer is backed by a concrete tapestry data source and carries an honest availability tag.

### Layer → data source → availability

| Layer | Shows | Data source | Availability |
|---|---|---|---|
| **Fleet overview** | all projects, last activity, wiring status, active agents | `services/project-registry` (`/projects`, `/repos`, `/machines`) — **live** | **Available now** (projects/repos/machines exist; "wiring status" + "active agents" need derivation) |
| **Project shape** | architecture snapshot, services, repos, deps, recent changes | architecture-snapshot/diff artifacts (`scripts/architecture_snapshot.py`, `docs/architecture-snapshots/`) | **Available now** (static snapshots exist per project; cross-project aggregation is new) |
| **Runtime telemetry** | sessions, tool calls, agent turns, failures, latency, retries | `services/telemetry-ingestion` + `services/project-observatory` + Grafana | **Planned** (hook telemetry → Grafana exists; cross-project query API + observatory service are stub/unbuilt) |
| **Memory layer** | writes, recalls, stale memos, cross-project memos, missing MCP | `services/agent-context` (loom-memory MCP) — **live** | **Available now** for writes/recalls; **missing** for staleness + missing-MCP detection |
| **Friction layer** | corrections, repeated misunderstandings, boundary violations | `feedback`/`lesson` memories in agent-context (not aggregated) | **Missing instrumentation** (signal exists as memos; no aggregation/classification) |
| **Observer layer** | candidates, drift findings, hot paths, orphaned skills, degraded patterns | `services/architecture-registry` (candidates) + `self-observer` cron | **Partial** — shape-drift candidates **available**; `hot_path`/`orphaned`/`degrading` are **missing** (runtime-observer unbuilt) |
| **Upskilling layer** | repeated behavior → candidate → decision → compiled skill | architecture-registry candidates + `services/policy` + `services/skill-making` | **Available now** for the candidate→decision hops; compiled-skill linkage **partial** |
| **Policy/audit layer** | what was promoted/held/rejected, who decided, evidence trail | `services/policy` (`/decisions`) + `services/audit-log` | **Available now** (the lifted candidates page already does this for one project) |

### Adopt from the lifted dashboard
- The candidates queue + Promote/Hold/Reject loop and the policy/audit wiring: keep as the **Observer + Upskilling + Policy layers** for a single project; generalize to N projects.
- The "strip the theater, show only real signal" discipline already in the code ([apps/web-dashboard/app/page.tsx:14](../../apps/web-dashboard/app/page.tsx)) — extend it: a layer with no real signal shows "missing instrumentation," not a fake chart.

### Reject
- "Grafana for agents" framing. Grafana is one embed in the Runtime-telemetry layer, not the product.
- Shipping all eight layers at once. Most runtime signal is unbuilt; building UI ahead of signal produces theater.

## Code sketch

A single availability enum the UI renders per layer, so absence is a first-class state:

```typescript
type SignalAvailability = "available" | "planned" | "missing";

type ObservatoryLayer = {
  key: "fleet" | "shape" | "telemetry" | "memory" | "friction"
     | "observer" | "upskilling" | "policy";
  availability: SignalAvailability;
  source: string;            // e.g. "project-registry:/projects"
  emptyReason?: string;      // shown when availability !== "available"
};
```

Cross-project scoping rides the existing self-host/RLS pattern: every backend call resolves a `project_id` (from `project-registry`) and a `tenant_id` (self-host → `SELF_HOST_TENANT_ID`); the console fans out per project rather than assuming one.

## Implementation phases

| Phase | Scope | Output | Blocks |
|---|---|---|---|
| **P1: Fleet + shape (available-now spine)** | Fleet overview from `project-registry`; per-project shape from architecture-snapshots; the availability-tag framework | A real multi-project console showing wiring + shape, honest "missing" tags elsewhere | All later layers (establishes the layer/availability shell) |
| **P2: Generalize observer/upskilling/policy to N projects** | Lift the existing candidates/decisions loop from one tenant to per-project | Observer + Upskilling + Policy layers, cross-project | — |
| **P3: Memory + friction layers** | Memory writes/recalls + staleness; aggregate `feedback`/`lesson` memos into a friction view | Memory + Friction layers | Needs a friction-classification pass over agent-context |
| **P4: Runtime telemetry** | Wire `telemetry-ingestion`/`project-observatory` once the runtime-observer exists | Runtime-telemetry layer (real, not iframe-only) | **Blocked on** runtime-observer build (deferred per ADR-0001 / runtime-observation proposal) |

## Two-mode notes

| Mode | What changes |
|---|---|
| **Self-host** | One operator tenant (`SELF_HOST_TENANT_ID`); the "fleet" is the operator's own connected projects via `project-registry`. No auth header; RLS scopes to the operator. This is the mode the lifted dashboard already targets. |
| **Hosted-multitenant** | The console mints/attaches a Bearer JWT; "fleet" is scoped to the authenticated tenant's projects; per-project + per-tenant RLS both apply. Deferred (JWT minting in the Next.js layer is unbuilt), but the layer/scoping model above is designed so it does not need a rewrite to add. |

## Open questions

1. **UI home:** evolve `apps/web-dashboard/` in place, move it to `apps/admin-console/` (also a slot), or stand up a new app? Recommendation: evolve `apps/web-dashboard/` (the loop code is already there) and retire/repoint the README framing.
2. **Cross-project scoping model:** confirm "console fans out per `project_id` from `project-registry`, each call self-host-RLS-scoped" as the mechanism — or is there a preferred aggregation service (the `project-observatory` service itself) that should own the fan-out server-side?
3. **`services/project-observatory/` migration timing:** it's the runtime-observer home and a stub. Does P4 wait for the runtime-observer to be built (currently deferred), or does the observatory service migrate first as the aggregation API even before runtime signals exist?
4. **Friction layer source:** aggregate `feedback`/`lesson` memories from `agent-context` as the friction signal (P3), or wait for dedicated friction instrumentation?

## What this implies for the next action

P1 is the only phase that needs no new instrumentation: a multi-project shell over `project-registry` + architecture-snapshots with the availability-tag framework, honestly marking the rest "planned"/"missing." That is the smallest build that turns the lifted single-project console into the Project Observatory, and it is the right first PR — but it should wait on the operator's answer to Open question 1 (UI home) and on Step 7 (`architecture-registry` + `policy` migration), since the observer/policy layers read those services.

## Sources

- [`apps/web-dashboard/`](../../apps/web-dashboard/) — the lifted Step 6 console (page.tsx, candidates/page.tsx, dashboard/page.tsx)
- [`services/project-observatory/README.md`](../../services/project-observatory/README.md) — the named concept + live source
- [`docs/adr/0001-observer-topology.md`](../adr/0001-observer-topology.md) — self-observer (static shape-drift) vs runtime-observer (→ project-observatory) vs decomposer vs policy
- [`docs/proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md`](2026-06-18-runtime-observation-deferred-to-tapestry.md) — what runtime observation does/does not do today (§ line 38, 216)
- [`docs/architecture/UMBRELLA.md`](../architecture/UMBRELLA.md) — the canonical model
- [`docs/plans/2026-06-22-extended-migration-audit.md`](../plans/2026-06-22-extended-migration-audit.md) — Step-7 services (architecture-registry, policy) the observer/policy layers depend on
- External: the operator-relayed reframe (Project Observatory, the 8 layers, "watching agency become structure"); tapestry public docs at tapestry-khaki.vercel.app (`/`, `/start/what-stays-on-track/`)
