---
date: 2026-09-05
kind: migration
area: services/policy
prs: [166]
adrs: []
memory: [policy_service_migrated_pr166_2026_09_05]
supersedes:
---

# Policy service migrated from the-loom (Refactor, code-only)

**What:** Migrated `services/policy/` — the audit-of-record for candidate decisions (approve / reject / hold / demote, plus a per-candidate policy-state aggregate) — from the retired the-loom repo into Tapestry, mirroring the architecture-registry migration. Added `infra/migrations/004_init_policy.sql` (kept at slot 004, idempotent no-op replay against the live loom-postgres, audit-immutable via an omitted UPDATE RLS policy) and a disabled `loom-policy` repoint block in `render.yaml`.

**Why it matters:** Closes one of the largest "not migrated" gaps. The service is SOFT/pure-audit (records decisions, exposes policy-state, does not call architecture-registry). Two Tapestry-specific adaptations were load-bearing: the cross-service enum test was repointed `003` → `007_init_candidates.sql`, and the tenant-id invariant was rewritten from the-loom's hardcoded `1d8ec1b3` to Tapestry's fail-closed-to-nil semantics. 12/12 tests; adversarial verify pass returned SHIP.

**Follow-ups / gates:** Not cut over — code only. Operator repoints the live `loom-policy` Render service per `services/policy/README.md` "Cutover" (verify live CHECK constraints, column widths, and tenant continuity first). PR #166 awaiting merge.
