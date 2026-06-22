# Proposal: The web-dashboard becomes the Project Observatory console

**Status:** Open — needs operator decisions on UI home, cross-project scoping, and observatory-service migration timing (see Open questions).
**Authors:** Liz, agent-assisted (Tapestry-agent), with an outside agent's reframe
**Date:** 2026-06-22
**Governed by:** [Canon: User-Agent Interface Observatory](../canon/user-agent-interface-observatory.md). The primary object is the **user-agent interface**; projects are containers; the layers below are **per-interface signal dimensions**, not per-project panels.

## Problem

Step 6 lifted `the-loom/apps/web-dashboard/` into `apps/web-dashboard/` byte-identically. What landed is a **single-project upskilling console**: a candidates queue (Promote/Hold/Reject), a recent-decisions verification list, and a Grafana iframe — all scoped to one tenant (the self-host operator), reading from `loom-architecture-registry` + `loom-policy`. Its own README frames it as "the-loom's running interface… Tapestry, which is unrelated" ([apps/web-dashboard/README.md:9](../../apps/web-dashboard/README.md)).

That framing is now stale. Tapestry's stated value is **cross-project memory, agent updates, and pattern promotion across projects**, and its named failure mode is **invisible absence** — memory missing, hooks not firing, architecture snapshots gone, agent drift, silent assumptions. The dashboard is the natural surface for making that absence visible. Scoped to one project and one signal (upskilling candidates), it does not do that.

There is also already a tapestry concept for this: `services/project-observatory/` — *"Telemetry aggregation for observation; Grafana-backed views of project formation + runtime activity"* ([services/project-observatory/README.md](../../services/project-observatory/README.md)), the migration target of the live `loom-project-observatory.onrender.com`, and the home ADR-0001 assigns to the **runtime-observer** ([docs/adr/0001-observer-topology.md:21](../adr/0001-observer-topology.md)). The dashboard should be that service's UI surface.

## Insight

The dashboard is not "Grafana but for agents." It is **a surface for watching agency become structure** — project morphology over time: how each connected project is forming, drifting, learning, breaking, and stabilizing. Grafana-style runtime telemetry is one input among several; the deeper content is the shape of each project and the loop that turns repeated behavior into durable structure (observe → candidate → policy decision → compiled skill).

Per the governing canon, the deeper content is more specific than "project shape": the primary object is the **user-agent interface** — a recurring coordination surface where the operator expresses intent, an agent acts, project structure constrains it, memory is used/missed/corrected, friction appears, and repeated patterns may become durable structure. A project contains many such interfaces; the observer tracks project shape *because* shape determines where interfaces are and how they change. The dashboard therefore organizes everything below **around interfaces**, with projects as their containers.

The honest constraint, which the UI must encode rather than paper over: **most of the runtime signal does not exist yet.** The observer today is a static shape-drift scanner — *"the observer reliably catches frontmatter+description shape drift. It does not observe runtime invocation patterns, telemetry events, cross-session signals, or session-end upskilling reports"* ([docs/proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md:38](2026-06-18-runtime-observation-deferred-to-tapestry.md)). `services/project-observatory/` is a ~24-line stub ([same doc:216](2026-06-18-runtime-observation-deferred-to-tapestry.md)). So every layer must be labeled **available now**, **planned signal**, or **missing instrumentation**.

## Decision: evolve `apps/web-dashboard/` into the Project Observatory console — interfaces as first-class objects, projects as containers

The dashboard becomes a cross-project console whose first-class object is the **user-agent interface**. Its model is the canon hierarchy:

```text
Operator
  ↓
User-Agent Interfaces        (the first-class objects)
  ↓
Projects                     (containers of interfaces)
  ↓
Architecture / Runtime / Memory / Observer / Friction / Upskilling   (signal dimensions per interface)
```

For each interface, the console tracks: purpose · agent role · operator expectation · architecture context · memory dependencies · runtime signals · friction signals · correction history · candidate durable structure ([canon: Required UI Model](../canon/user-agent-interface-observatory.md)). It answers, per interface and rolled up per project: is it wired correctly? what changed? what are agents doing? what is the observer seeing? what friction recurs? what is ready to become durable structure? what is missing/stale/broken/drifting?

The 7 layers below are **signal dimensions attached to interfaces**, not standalone per-project panels. Each is backed by a concrete tapestry data source and carries an honest availability tag. The hard new problem the canon introduces — **how an interface is identified/derived**, since interfaces are not directly instrumented today — is P1 below and Open question 5.

### Signal dimension → data source → availability (attached per interface)

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

// The first-class object (canon). Interfaces are derived, not yet instrumented.
type UserAgentInterface = {
  id: string;
  projectId: string;          // its container
  purpose: string;
  agentRole: string;
  operatorExpectation: string;
  architectureContext: string[];   // shape elements that define this surface
  signals: Record<SignalDimensionKey, SignalSlot>;   // the dimensions below
  status: "active" | "emerging" | "changed" | "degraded" | "stable";
};

type SignalDimensionKey =
  | "shape" | "runtime" | "memory" | "friction"
  | "observer" | "upskilling" | "policy";

type SignalSlot = {
  availability: SignalAvailability;
  source: string;            // e.g. "project-registry:/projects"
  emptyReason?: string;      // shown when availability !== "available"
};
```

Cross-project scoping rides the existing self-host/RLS pattern: every backend call resolves a `project_id` (from `project-registry`) and a `tenant_id` (self-host → `SELF_HOST_TENANT_ID`). The console fans out per project, and within each project per interface, rather than assuming one of either.

## Implementation phases

| Phase | Scope | Output | Blocks |
|---|---|---|---|
| **P1: Interface model + first derivation** | Define what a user-agent interface is operationally; derive a first-pass interface set per project from architecture shape (snapshots) × agent roles (CLAUDE.md / adapters) × `project-registry`; the per-interface availability shell | The first-class object exists; projects render as containers of derived interfaces with honest "missing" signal tags | All later phases (everything hangs off interfaces) |
| **P2: Fleet + shape, organized by interface** | Fleet overview from `project-registry`; per-project shape from architecture-snapshots; attach shape signals to interfaces | A real cross-project console showing interfaces, wiring, and shape | — |
| **P3: Observer / upskilling / policy per interface** | Generalize the lifted candidates/decisions loop from one tenant to per-project, and attribute candidates to the interface that produced them | Observer + Upskilling + Policy dimensions, per interface | Step 7 (`architecture-registry` + `policy` migrated) |
| **P4: Memory + friction per interface** | Memory writes/recalls + staleness; aggregate `feedback`/`lesson` memos into per-interface friction + correction history | Memory + Friction dimensions | Needs a friction-classification pass over agent-context |
| **P5: Runtime telemetry per interface** | Wire `telemetry-ingestion`/`project-observatory` once the runtime-observer exists; attribute runtime signals to interfaces | Runtime dimension (real, not iframe-only) | **Blocked on** runtime-observer build (deferred per ADR-0001 / runtime-observation proposal; loom-agent's lane) |

## Two-mode notes

| Mode | What changes |
|---|---|
| **Self-host** | One operator tenant (`SELF_HOST_TENANT_ID`); the "fleet" is the operator's own connected projects via `project-registry`. No auth header; RLS scopes to the operator. This is the mode the lifted dashboard already targets. |
| **Hosted-multitenant** | The console mints/attaches a Bearer JWT; "fleet" is scoped to the authenticated tenant's projects; per-project + per-tenant RLS both apply. Deferred (JWT minting in the Next.js layer is unbuilt), but the layer/scoping model above is designed so it does not need a rewrite to add. |

## Open questions

1. **UI home:** evolve `apps/web-dashboard/` in place, move it to `apps/admin-console/` (also a slot), or stand up a new app? Recommendation: evolve `apps/web-dashboard/` (the loop code is already there) and retire/repoint the README framing.
2. **Cross-project scoping model:** confirm "console fans out per `project_id` from `project-registry`, each call self-host-RLS-scoped" as the mechanism — or is there a preferred aggregation service (the `project-observatory` service itself) that should own the fan-out server-side?
3. **`services/project-observatory/` migration timing:** it's the runtime-observer home and a stub. Does P4 wait for the runtime-observer to be built (currently deferred), or does the observatory service migrate first as the aggregation API even before runtime signals exist?
4. **Friction layer source:** aggregate `feedback`/`lesson` memories from `agent-context` as the friction signal (P4), or wait for dedicated friction instrumentation?
5. **Interface derivation (the canon's hard new question):** how is a user-agent interface identified? Options: (a) derive heuristically from architecture shape × agent roles × project areas (cheap, approximate, available now); (b) declare interfaces explicitly in each project's `.project-intelligence/` (precise, manual); (c) infer from runtime/session signals once they exist (accurate, blocked on instrumentation). Recommendation: start with (a) in P1 and let (b)/(c) refine it.

## What this implies for the next action

P1 (interface model + first derivation) is the pivot: it needs no new instrumentation — it derives a first-pass interface set from data that already exists (architecture snapshots, `project-registry`, project `CLAUDE.md`/adapters) and renders projects as containers of interfaces with honest "missing" tags on the signal dimensions. That is the smallest build that makes the canon real in the UI. It should wait on the operator's answers to Open question 1 (UI home) and 5 (derivation approach), and the observer/policy dimensions (P3) wait on Step 7 (`architecture-registry` + `policy` migration).

## Sources

- [`docs/canon/user-agent-interface-observatory.md`](../canon/user-agent-interface-observatory.md) — **the governing canon** (user-agent interface = primary object)
- [`apps/web-dashboard/`](../../apps/web-dashboard/) — the lifted Step 6 console (page.tsx, candidates/page.tsx, dashboard/page.tsx)
- [`services/project-observatory/README.md`](../../services/project-observatory/README.md) — the named concept + live source
- [`docs/adr/0001-observer-topology.md`](../adr/0001-observer-topology.md) — self-observer (static shape-drift) vs runtime-observer (→ project-observatory) vs decomposer vs policy
- [`docs/proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md`](2026-06-18-runtime-observation-deferred-to-tapestry.md) — what runtime observation does/does not do today (§ line 38, 216)
- [`docs/architecture/UMBRELLA.md`](../architecture/UMBRELLA.md) — the canonical model
- [`docs/plans/2026-06-22-extended-migration-audit.md`](../plans/2026-06-22-extended-migration-audit.md) — Step-7 services (architecture-registry, policy) the observer/policy layers depend on
- External: the operator-relayed reframe (Project Observatory, the 8 layers, "watching agency become structure"); tapestry public docs at tapestry-khaki.vercel.app (`/`, `/start/what-stays-on-track/`)
