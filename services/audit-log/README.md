# `services/audit-log/`

**Status:** DEFERRED — not started; no consumer today.

## Purpose

Cross-service audit log aggregation + retention.

## Decision (2026-09-05)

Deferred. Per-service audit already covers what the platform relies on: policy decisions
are audit-immutable in their own table, architecture-registry appends `status_change`
entries into candidates' `evidence_refs`, and telemetry-ingestion writes audit events. A
cross-service aggregator is speculative ahead of demand — revisit only when a concrete
need appears (a compliance/retention requirement, or a unified audit view in the
dashboard). Operator-ratified in the legibility initiative (`docs/plans/2026-09-05-legibility-review-and-plan.md`).

## Source

Partial (per-service audit today)

## When this slot populates

When the source has stabilized AND the operator approves migration. See [`../../docs/migration/README.md`](../../docs/migration/README.md).
