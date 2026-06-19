# 0001 — observer-topology

**Date:** 2026-06-18 (proposed) · 2026-06-19 (accepted)
**Status:** **Accepted**
**Operator decision:** Ratified 2026-06-19 by operator after: outside reviewer's edits (conveyed via loom-memory `tapestry_agent_outside_review_response_to_adrs_0001_0002_2026_06_19`, operator-endorsed "yes"), loom-agent's corpus drift-check + reaction (which walked back its own engine/ assertion), and Tapestry-agent's 3 independent adversarial reviewers (boundary / consistency / logic-feasibility). **Decomposer placement: the operator accepted `services/observation-decomposer/` (Reviewer A's boundary-rule position) on 2026-06-19, superseding the initial `engine/` endorsement.**

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
| **observation-decomposer** | splits repeated behavior into a SET of mixed artifact candidates | **`services/observation-decomposer/`** (operates on cross-project aggregate observations → cross-project-governance lineage per the boundary rule; canonical candidate state still in `architecture-registry`). See placement note below. |
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

## Decomposer placement — resolved to `services/` (boundary rule)

This was the one genuine operator/architecture call in this ADR; all three review sources (outside reviewer, loom-agent, Tapestry-agent's reviewers) agreed the corpus did NOT settle it. The operator chose **`services/observation-decomposer/`** on 2026-06-19.

**Why services/ (the chosen position, per Reviewer A):** the engine-vs-services boundary rule is *local-agency vs cross-project-governance*, not compute-vs-state. The decomposer consumes cross-project **aggregated** observations and emits governance-shaped candidates — the the-loom/services lineage (the same reason `self-observer` is a service, not engine). Canonical candidate state remains in `architecture-registry`; the decomposer is stateless compute but lives on the cross-project-governance side.

**Considered alternative — `engine/` (outside reviewer's position):** decomposition is a compute/transform like `engine/skill-compiler/`; UMBRELLA lists "observation" under the engine compute layer and `local-observer` lives in engine; the runtime-observation followup §2.4 named `engine/observation-decomposer/` first. Recorded as the minority view.

**Revisit trigger:** if, at build time, the decomposer's data dependencies turn out to be dominated by raw local-session signals rather than cross-project aggregates, reopen this placement.

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
