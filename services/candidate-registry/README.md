# `services/candidate-registry/`

**Status:** ABSORBED into `services/architecture-registry/` — no separate service will be built.

## Purpose

Path A + Path B promotion candidates: status, evidence, signals.

## Decision (2026-09-05)

This function already lives in `architecture-registry` (candidate accept / persist /
query / status transitions). An earlier design anticipated splitting candidates into
their own service; the actual build collapsed it into architecture-registry, so this
slot is **not** a service to build. Revisit a split only if architecture-registry grows
the durable-structure surface (nodes/edges/decisions) and candidates need isolation.
Operator-ratified in the legibility initiative (`docs/plans/2026-09-05-legibility-review-and-plan.md`).

## Source

the-loom/services/architecture-registry/ → migrated to tapestry/services/architecture-registry/

## When this slot populates

When the source has stabilized AND the operator approves migration. See [`../../docs/migration/README.md`](../../docs/migration/README.md).
