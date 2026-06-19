# 0002 — cutover continuous-sync for live-produced candidates/decisions

**Date:** 2026-06-18
**Status:** Proposed — seeded by Tapestry-agent per outside-reviewer guidance; pending operator ratification
**Operator decision:** Not yet ratified. Outside reviewer (2026-06-18): "Must have an ADR before migration steps that split live writes. Non-negotiable." Operator "generally agrees."

## Context

The migration runs over multiple weeks under parallel-build. During that window the legacy the-loom keeps producing **new state**: the self-observer cron emits candidates every 6h, the A3 dispatch trigger fires on promotions, and `policy_decisions` keep accruing. The readiness plan defines a one-time `pg_dump | pg_restore` for the candidates/policy tables and a 14-day dual-write window for memory `records` — but it does **not** define how rows created in the-loom *after* a table's cutover snapshot get reconciled into Tapestry (reconciliation gap G2).

If Step 2 (agent-context) or Step 7 (architecture-registry/policy) imports a snapshot while the legacy writers keep running, new rows are silently stranded in the legacy DB. This is a real data-coherence hole that must be closed before any step that splits live writes.

## Decision (proposed — to ratify)

Before any migration step that splits live writes for a given table, that step's runbook must specify a reconciliation mechanism. **Preferred default for this stage (per outside reviewer): a short cutover freeze for promotion/candidate writes + replay/export of any rows created during the migration window. Do NOT overbuild change-data-capture yet.**

Mechanism menu (pick per table, simplest that's safe):
1. **Cutover freeze window** — pause the legacy writer (cron / dispatch) for the cutover, snapshot, switch, unfreeze against Tapestry. Best for the candidates/policy path (low write rate, 6h cron).
2. **Replay/export queue** — capture rows created during the window, replay into Tapestry post-switch.
3. **Dual-write** — only where a freeze is unacceptable (e.g. agent-context memory records — already planned as a 14-day dual-write).
4. **CDC** — explicitly deferred; not justified at this scale.

## Open sub-questions for the ratification pass

1. Per-table choice: candidates/policy (freeze+replay preferred) vs memory records (dual-write already planned) vs project_registry.
2. Who pauses the self-observer cron during a freeze, and the max acceptable freeze duration.
3. Idempotency on replay (the bridge already has an idempotency table; reuse the pattern).

## Consequences

- Closes G2 (no silently-stranded rows during cutover).
- Keeps the migration reversible: a freeze+replay is auditable and undoable; CDC is not, at this team size.
- Adds a required runbook subsection to every split-write step (ties to the migration-cicd runbook state machine — no parallel process).

## Related
- Plan: [`../plans/2026-06-18-unified-integration-understanding.md`](../plans/2026-06-18-unified-integration-understanding.md) §5 (G2)
- Readiness plan: [`../plans/2026-06-18-tapestry-migration-readiness-and-execution.md`](../plans/2026-06-18-tapestry-migration-readiness-and-execution.md) §7 Q1 (one-time pg_dump baseline this extends)
- Doctrine: [`../migration-cicd/04-runbook-template.md`](../migration-cicd/04-runbook-template.md) (the state machine these subsections attach to)
- loom-memory: `tapestry_agent_unified_understanding_synthesis_2026_06_18`
