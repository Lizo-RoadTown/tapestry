# 0002 — cutover continuous-sync for live-produced candidates/decisions

**Date:** 2026-06-18 (proposed) · 2026-06-19 (accepted)
**Status:** **Accepted** (direction + per-table decisions + checklist + hard rule). The runbook *mechanics* in "Preconditions before execution" below are required-design items that must close before the FIRST split-write step runs — they do not block ratification of this ADR's direction.
**Operator decision:** Ratified 2026-06-19 by operator after outside-reviewer edits (loom-memory `tapestry_agent_outside_review_response_to_adrs_0001_0002_2026_06_19`, "yes") + Tapestry-agent's 3-reviewer feasibility check.

## Context

The migration runs over multiple weeks under parallel-build. During that window legacy the-loom keeps producing new state: the self-observer cron emits candidates every 6h, the A3 dispatch trigger fires on promotions (`architecture-registry/main.py:234`), and `policy_decisions` accrue. The readiness plan defines a one-time `pg_dump | pg_restore` + a 14-day dual-write for memory `records`, but does NOT define how rows created in the-loom *after* a table's cutover snapshot reconcile into Tapestry (reconciliation gap G2). Without a mechanism, new rows are silently stranded in the legacy DB.

This ADR extends — not restates — the readiness-plan §7 Q1 one-time snapshot. (NB: §7 Q1 referenced a file named `0002-data-migration-cutover-strategy.md`; this ADR supersedes/renames that to `0002-cutover-continuous-sync.md`, same four tables, focused on the post-snapshot continuous-sync gap.)

## Decision (ratified)

Before any migration step that splits live writes for a table, that step's runbook MUST specify a reconciliation mechanism. **Default: short cutover freeze + replay/export. Do NOT overbuild change-data-capture (CDC) at this scale.**

### Per-table mechanism (resolved)

| Table | Mechanism | Notes |
|---|---|---|
| `candidates` + `policy_decisions` | **Freeze + replay/export** | Low write rate. Freeze the whole write surface (see Preconditions #1), snapshot, restore, replay window-rows, switch writers, verify counts, unfreeze against Tapestry. |
| `records` (memory) | **Dual-write, 14-day max** | Session-critical; can't be frozen without disrupting active work. End condition: 14 days → parity verify → cut legacy write path. |
| `projects` (project_registry) | **Freeze + controlled import** | Contains identity mappings, project IDs, machine registrations, tenant resolution. Must NOT be casually dual-written — a bad split mislabels the whole platform. Verify IDs. |
| Telemetry | **Explicit cutover timestamp; no perfect historical replay required in v1** | Record `last legacy telemetry timestamp` + `first Tapestry telemetry timestamp`. Telemetry tolerates some loss; candidates/policy/memory do not. **BUT** the Tapestry Postgres rollup must **start cleanly** — a clean rollup start is a *precondition* for §6.5 Decision 2's "rollup before runtime-observation/decomposition active" gate and for self-host parity (runtime-observation followup §1.6 / proposal:239). "Tolerates loss" ≠ "may ship a degraded rollup." |

### Hard rule (ratification-binding)

> The `parity-verified → prod-rolling` runbook gate gains a **required artifact**: a freeze/replay/dual-write subsection for every split-write table. This **augments** (does not parallel) migration-cicd contract assertion #5 (source frozen at the same transition). A step lacking this subsection may not enter `prod-rolling`.

## Preconditions before execution (required design — close before the FIRST split-write step)

The outside-review sketch ("pause cron + disable promotion dispatch") is naive against the actual code. Tapestry-agent's feasibility reviewers PROBE'd three holes; each runbook must resolve them:

1. **The freeze surface is the whole candidate write path, not just the cron.** Writers: the cron, the registry `POST /candidates` (`architecture-registry/main.py:98`), interactive/agent PATCHes (`main.py:194`), and the bridge ack-receiver (`main.py:321`). Freezing "the cron" alone leaves three live writers.
2. **"Freeze the self-observer cron" is an IaC commit + deploy, NOT a dashboard toggle.** The cron is declared at `the-loom/render.yaml:283-293` (`autoDeploy:true`); render.yaml's own note (lines 330-335) warns dashboard-created changes drift from IaC. Freeze = comment-out/gate the block + deploy; unfreeze = a second commit. The freeze window MUST include deploy-propagation time.
3. **"Pause promotion dispatch" requires code, and replay can re-fire it.** The A3 auto-trigger at `architecture-registry/main.py:234` fires on ANY PATCH setting `status='promotion_requested'` for a skill candidate — not just operator clicks. Operator restraint is insufficient. AND there is **no candidates-table idempotency table** (the bridge idempotency table is Make_Skills-receiver-side, not the registry path); the only dedup is the engine's 409. Therefore replay MUST either preserve original `candidate_id`s (so `promotion_id` is stable and the engine 409 holds) OR pause the `main.py:234` trigger during replay and re-PATCH after. Verify the engine's 409 keying before relying on it.

## Consequences

- Closes G2 (no silently-stranded rows during cutover).
- Keeps migration reversible (freeze+replay is auditable/undoable; CDC is not, at this team size).
- Adds a required runbook subsection to every split-write step (ties to the migration-cicd runbook state machine — no parallel process).

### Required verification checklist (every split-write table)

```text
- row count before snapshot
- row count after import
- max created_at before freeze
- rows created during freeze window
- replay count
- duplicate/idempotency check (verify engine 409 keying; preserve candidate_id)
- writer switched confirmation (ALL writers per Precondition #1)
- rollback point
```

## Related
- loom-memory: `tapestry_agent_outside_review_response_to_adrs_0001_0002_2026_06_19`, `tapestry_agent_adr_review_synthesis_2026_06_18`, `tapestry_decision_adr_0001_0002_ratified_2026_06_19`, `tenant_id_audit_clean_all_under_self_host_2026_06_19` (clean tenant envelope inherited)
- Readiness plan: [`../plans/2026-06-18-tapestry-migration-readiness-and-execution.md`](../plans/2026-06-18-tapestry-migration-readiness-and-execution.md) §7 Q1
- Doctrine: [`../migration-cicd/04-runbook-template.md`](../migration-cicd/04-runbook-template.md) + [`../migration-cicd/README.md`](../migration-cicd/README.md) (assertion #5)
- §6.5 Decision 2 (telemetry pacing): [`../plans/2026-06-18-unified-integration-understanding.md`](../plans/2026-06-18-unified-integration-understanding.md)
