# 0001 — observer-topology

**Date:** 2026-06-18 (proposed) · 2026-06-19 (accepted)
**Status:** **Accepted**
**Operator decision:** Ratified 2026-06-19 by operator ("Fair, this is good, continue") after: outside reviewer's edits (conveyed via loom-memory `tapestry_agent_outside_review_response_to_adrs_0001_0002_2026_06_19`, operator-endorsed "yes"), loom-agent's corpus drift-check, and Tapestry-agent's 3 independent adversarial reviewers (boundary / consistency / logic-feasibility).

## Context

The corpus disagreed on where observation lives in Tapestry, and the disagreement is load-bearing because CLAUDE.md routes new agents to UMBRELLA as authoritative while UMBRELLA was stale on this exact point (reconciliation C3/C4/G6 in [`../plans/2026-06-18-unified-integration-understanding.md`](../plans/2026-06-18-unified-integration-understanding.md) §5).

"Observer" was being treated as one thing. It is at least five things plus a read layer, a registry, and a gate. Without first-class component boundaries, Tapestry would map observers to services but silently drop the **observation-decomposer** — the named fatal-flaw fix that splits repeated behavior into mixed artifact candidates instead of promoting a behavior "as one thing."

## Decision (ratified)

Observation is named as distinct components, NOT merged into "project-observatory":

| Component | Role | Home (ratified) |
|---|---|---|
| **self-observer** | static repo/document **shape-drift scanner** (the 6h cron today) | **`services/self-observer/`** (canonical per MANIFESTO §4.3, line 190). Role descriptor "static shape-drift scanner" lives in the service README/docstring — NOT a directory rename, NOT a new `observers/` top-level dir (see drift caveat below). |
| **local-observer** | per-session / project-local **Path A** observer | **`engine/local-observer/`** (canonical per MANIFESTO §4.4, line 208). Source material: the-loom plugin `adapters/claude-code/loom-discipline/scripts/observer.py`; the plugin becomes a **collector/adapter** that feeds the engine, which owns the canonical logic. |
| **runtime-observer** | runtime telemetry/signal observer (computes `hot_path`, `orphaned`, `degrading`) | **`services/project-observatory/`** |
| **observation-decomposer** | splits repeated behavior into a SET of mixed artifact candidates | **`engine/observation-decomposer/`** (compute/judgment transform; does not own durable state). See boundary dissent below. |
| **project-observatory** | read/query/visibility layer over observations + signals + dashboards | **`services/project-observatory/`** |
| **architecture-registry** | canonical candidate state + durable structure (absorbs candidate-registry) | **`services/architecture-registry/`** |
| **policy** | promotion + activation gate; owns risk classification + `max_auto_level` | **`services/policy/`** |

### Safety boundary (ratification-binding)

> The observation-decomposer does not activate artifacts. It emits decomposed artifact candidates with evidence, signals, and a **recommended automation level**. Canonical candidate state remains in `architecture-registry`. Activation remains **policy-gated**.

### Risk classifier (resolved)

Owned by **`services/policy/`** (NOT embedded in the decomposer, NOT a freestanding service yet). The decomposer may attach **advisory** risk hints; **policy is solely authoritative** for the Level-4 cascade gate and recomputes risk on absence/disagreement. The concrete module path is left to the policy-daemon design pass — do not hard-assert a filename for a component the runtime-observation followup §3.1 still calls undefined.

## Three taxonomies — do not conflate (disambiguation)

A future reader will otherwise chase a phantom "7 vs 9" mismatch. These are three distinct layers:
1. **This ADR's 7-component topology** — where observation logic lives.
2. The decomposer's **artifact-part → kind output map** (event→plugin/hook, deterministic→tool, judgment-situational→skill, judgment-ongoing→agent, multi-step→workflow, coordination→orchestration, side-effect→service, approval→policy, facts→memory) — what a decomposed observation becomes.
3. The **9-value `candidate_kind` enum** (`the-loom/services/architecture-registry/models.py:32-42`) — the persisted candidate type.

**Observation signals are NOT candidate kinds.** The 9-kind enum stays; signals go in the existing `signals` JSONB field.

## Boundary dissent (recorded, not blocking)

Tapestry-agent's boundary reviewer dissented on `engine/observation-decomposer/`: the engine-vs-services boundary rule is *local-agency vs cross-project-governance* (not compute-vs-state), and the decomposer consumes cross-project aggregated observations — arguably the-loom/services lineage. **Resolution: `engine/` stands**, because UMBRELLA defines `engine/` as "the compute layer: agent loop, **observation**, compilation, adaptation," `local-observer` (also observation) already lives in engine, and the runtime-observation followup §2.4 names `engine/observation-decomposer/` first. **Revisit trigger:** if, at decomposer build time, its data dependencies turn out to be dominated by cross-project registry/policy state rather than raw observations, reopen this placement.

## Deferred to downstream ADRs (NOT blockers for this topology ADR)

This ADR ratifies component **names + homes**. The following block the future **policy-daemon-activation** ADR, not this one (per runtime-observation followup §3.1):
- **Risk classifier** specification (undefined; gates Level-4 auto-staging).
- **Non-skill-handler blind spot** — only `kind=skill` has a destination handler today (`architecture-registry/main.py:234` dispatch is skill-only); 8/9 kinds dead-end. Monitoring coverage (`actionable_backlog_count`) is skill-only until the sibling `unsupported_candidate_count_by_kind` threshold lands.
- **Skill-vs-agent disambiguation** rule (skill = bounded to a single call site; agent = ongoing responsibility across calls).

## Consequences

- The decomposer has a named home and cannot be silently absorbed into project-observatory.
- UMBRELLA + MANIFESTO §4.3/§4.4 now reconcile to one topology (see the stale-doc patch on `tapestry-unified-integration-plan`).
- Locks: observation signals ≠ candidate kinds; decomposer never activates; policy owns risk + activation.

## Related
- loom-memory: `tapestry_agent_outside_review_response_to_adrs_0001_0002_2026_06_19`, `tapestry_agent_adr_review_synthesis_2026_06_18`, `tapestry_decision_adr_0001_0002_ratified_2026_06_19`
- [`../proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md`](../proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md) + [`../research/2026-06-18-outside-review-runtime-observation-followup.md`](../research/2026-06-18-outside-review-runtime-observation-followup.md) §2.4, §3.1
- [`../../MANIFESTO.md`](../../MANIFESTO.md) §4.3 (line 190), §4.4 (line 208)
- [`0002-cutover-continuous-sync.md`](0002-cutover-continuous-sync.md)
