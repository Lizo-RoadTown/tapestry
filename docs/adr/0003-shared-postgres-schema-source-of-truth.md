# 0003 — shared Postgres schema: source-of-truth + forklift-vs-redesign

**Date:** 2026-06-20
**Status:** Proposed — pending operator ratification
**Operator decision:** Not yet ratified. Drafted after the 2026-06-20 researcher + evaluator pass on the re-homing approach; operator directive: "safest, most efficient, time-tested, best-practices… don't want catastrophe down the road" (`feedback_operator_wants_safest_best_practice_not_shortcuts_2026_06_20`).

## Context

Every migration step (2–7) needs a clear answer to: **who owns the canonical schema, and do we forklift the proven schemas or redesign them now?** This was named in the readiness plan §4 as Tapestry-agent's *first* commit (`source-of-truth-for-shared-postgres-schemas`) — it governs Steps 2–7 — but it was never written (ADR slots 0001/0002 went to observer-topology / cutover).

The 2026-06-20 evaluator identified the load-bearing risk: the instant a Tapestry service points at the live `loom-postgres`, "forklift over redesign" is decided **silently and permanently**, with no governance and no forcing-function to ever clean it up — foreclosing the planned memory-schema redesign (plan §6.7) and re-importing legacy coupling (violates `docs/migration/README.md:7` + MANIFESTO Part 7). This ADR makes that decision **explicit, governed, and reversible-into-redesign** instead of silent.

The schemas in scope: `records` (memory), `candidates`, `policy_decisions`, `projects`, `tenant_id_mapping` + `tenants` (platform). The tenant audit (`tenant_id_audit_clean_all_under_self_host_2026_06_19`) confirmed these are clean and correct in production.

## Decision (proposed)

1. **Tapestry's `infra/migrations/` is the canonical source-of-truth for all platform/shared schemas going forward.** Tapestry owns the migration sequence; the legacy `the-loom/infra/migrations/` + `Make_Skills/core/db/migrations.py` freeze at parity and are retired (per MANIFESTO Part 7). The schema-of-record lives in Tapestry's migration files **even while the live bytes temporarily remain in `loom-postgres`** during the transition — so ownership is governed here, not implied by where the database happens to sit.

2. **v1 = faithful FORKLIFT of the existing, proven schemas. No redesign during migration.** The schemas work and are audited-clean; combining a platform migration with a schema redesign is two risky changes at once — the catastrophe path. Best practice is sequential: reach parity on the known-good schema first. (000_init_platform.sql already follows this — a documented forklift.)

3. **Redesign is a SEPARATE, deliberate, POST-PARITY step — each its own ADR.** The first named redesign is the **memory-schema enrichment** (hierarchical scopes, provenance chains, four-tier visibility, reinforcement model, `memory_class` taxonomy) per plan §6.7 / the platform audit. This is the forcing-function the evaluator asked for: forklift is explicitly time-boxed and tracked toward redesign, not silent-and-forever.

4. **Naming carried during transition must be committed to a rename, not deferred indefinitely.** Where `loom-*` / `loom_auth` / `loom-postgres` names are carried for handover continuity, each gets a `naming-corrections.md` entry + a runbook trigger. Carrying legacy names is a *transition* state only.

## Consequences

- **Neutralizes the "silent forklift" risk:** the schema-of-record is Tapestry's governed migration files from day one, regardless of which physical DB holds the bytes.
- Clean ownership: one canonical migration sequence (Tapestry's); legacy frozen at parity.
- No simultaneous migrate+redesign — the safe, time-tested order.
- Redesigns become visible, tracked future ADRs (memory-schema first) rather than being foreclosed.
- Slightly more ceremony (forklift now, redesign later as separate ADRs) — accepted in exchange for not risking a combined change.

## What this ADR does NOT cover (separate decisions)

- **Deployment topology / DB-connection mechanism** (connection-string-as-secret; the "only one fleet writes the DB at a time" invariant; Render service-name preservation) — belongs to a deployment/cutover runbook under [ADR-0002](0002-cutover-continuous-sync.md), not here.
- The actual cutover sequencing per table — ADR-0002.

## Related
- Readiness plan §4 (named this as commit #1), §6.7 (memory-schema redesign): [`../plans/2026-06-18-tapestry-migration-readiness-and-execution.md`](../plans/2026-06-18-tapestry-migration-readiness-and-execution.md)
- [`0002-cutover-continuous-sync.md`](0002-cutover-continuous-sync.md) · [`../migration/README.md`](../migration/README.md) · [`../../MANIFESTO.md`](../../MANIFESTO.md) Part 7
- loom-memory: `tapestry_agent_rehoming_research_eval_findings_2026_06_20`, `tenant_id_audit_clean_all_under_self_host_2026_06_19`, `decision_tenant_id_mapping_option_b_2026_06_12`
- First application: [`../../infra/migrations/000_init_platform.sql`](../../infra/migrations/000_init_platform.sql) (Step 1)
