# 0001 — observer-topology

**Date:** 2026-06-18
**Status:** Proposed — seeded by Tapestry-agent per outside-reviewer guidance; pending operator ratification
**Operator decision:** Not yet ratified. Outside reviewer (2026-06-18) directed this ADR be opened and seeded; operator "generally agrees." Final component boundaries are the operator's call.

## Context

The corpus disagrees on where observation lives in Tapestry, and the disagreement is load-bearing because CLAUDE.md routes new agents to UMBRELLA as authoritative while UMBRELLA is stale on this exact point (see reconciliation C3/C4/G6 in [`../plans/2026-06-18-unified-integration-understanding.md`](../plans/2026-06-18-unified-integration-understanding.md)).

Specifically:
- The readiness plan maps the **self-observer cron** into `services/project-observatory/`, citing "MANIFESTO §4.3" — but MANIFESTO §4.3 actually names `tapestry/services/self-observer/`, and the binding memo lists project-observatory and self-observer as *separate* capabilities. The plan mis-cites both. (C4)
- `engine/local-observer/` (Path A candidates — half the loop) has **no migration source or owner** in any table. (G6)
- The runtime-observation deferral introduces a **runtime-observer** (computes signals) AND an **observation-decomposer** (splits repeated behavior into mixed artifact candidates) — the decomposer is the named fatal-flaw fix and must not be collapsed into "the observer."

"Observer" is being treated as one thing. It is at least five things plus a read layer, a registry, and a gate. Without first-class component boundaries, Tapestry will map observers to services but silently drop the decomposition layer — exactly the failure the loop is supposed to prevent.

## Decision (proposed — to ratify)

Name observation as distinct components, do not merge them into "project-observatory":

| Component | Role | Provisional home |
|---|---|---|
| **self-observer** | static repo/document **shape-drift scanner** (the 6h cron today) | `services/` — either `services/project-observatory/` or a dedicated `observers/static-repo-scanner` package; role named "static shape-drift scanner", NOT "the observer" |
| **local-observer** | per-session / project-local **Path A** observer | `engine/local-observer/` (UMBRELLA already names this; needs a migration source + owner — resolves G6) |
| **runtime-observer** | runtime telemetry/signal observer (computes `hot_path`, `orphaned`, `degrading`) | `services/project-observatory/` |
| **observation-decomposer** | splits repeated behavior into a SET of mixed artifact candidates | `engine/observation-decomposer/` (compute) — open sub-question vs `services/candidate-decomposer/` |
| **project-observatory** | read/query/visibility layer over observations + signals + dashboards | `services/project-observatory/` |
| **architecture-registry** | canonical candidate state + durable structure (absorbs candidate-registry) | `services/architecture-registry/` |
| **policy** | promotion + activation gate | `services/policy/` |

## Open sub-questions for the ratification pass

1. Does the observation-decomposer live in `engine/` (compute) or `services/` (durable)? (Q8 from the runtime-observation proposal)
2. Does the static self-observer migrate INTO project-observatory or stay a sibling package? Either is acceptable if its role is named "static shape-drift scanner."
3. local-observer's migration source — `the-loom`'s in-plugin `observer.py` (Path A POSTer) vs net-new authoring.
4. Risk classifier (the Level-4 cascade gate input) — its own sub-component, blocks the policy daemon (per the runtime-observation proposal §3 caveats).

## Consequences

- Makes safe auto-decomposition possible (the decomposer has a named home rather than being absorbed).
- Forces UMBRELLA + MANIFESTO §4.3 to be reconciled to one topology (see the stale-doc patch PR on branch `tapestry-unified-integration-plan`).
- Locks the constraint: observation signals are NOT candidate kinds (the existing 9-kind enum stays; signals go in the existing `signals` field).

## Related
- Proposal: [`../proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md`](../proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md)
- Durable artifact: [`../research/2026-06-18-outside-review-runtime-observation-followup.md`](../research/2026-06-18-outside-review-runtime-observation-followup.md)
- Plan: [`../plans/2026-06-18-unified-integration-understanding.md`](../plans/2026-06-18-unified-integration-understanding.md) §3, §5 (C4/G6)
- loom-memory: `tapestry_agent_unified_understanding_synthesis_2026_06_18`
