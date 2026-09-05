# Import map

Per-source-piece destination + decision + status. Empty at initial spawn; populated as imports are scoped and executed.

## Schema

Each row:

| Source | Destination | Decision | Status | Notes |
|---|---|---|---|---|
| `<source-repo>/<path>` | `tapestry/<slot>/<path>` | Lift / Refactor / Rewrite / Retire | Pending / In Progress / Imported / Retired | brief context |

**Decisions:**

- **Lift** — minimal-change import
- **Refactor** — import + restructure
- **Rewrite** — fresh author; reference source
- **Retire** — don't import; mark for source archive

**Status:**

- **Pending** — operator has not yet approved this migration
- **In Progress** — migration PR is open
- **Imported** — landed in main; commit ref recorded
- **Retired** — explicitly not imported; source can archive

## Ratified order

**Migration order (readiness plan §5 + v1 roadmap §5): auth → agent-context → project-registry → engine → templates+CLI → web-dashboard → architecture-registry+policy → telemetry.** PR-prep-2a (URLs) + 2b (auth_bridge consolidation) are DONE on the-loom; Step 1 is the first import.

## Imports

| Source | Destination | Decision | Status | Notes |
|---|---|---|---|---|
| `the-loom/packages/auth/python/loom_auth/` | `tapestry/packages/auth/python/loom_auth/` | Lift | Imported (Step 1, 2026-06-20) | byte-identical copy (`cmp` verified) of the PR-prep-2b canonical (the-loom `23b3055`+`77aaabc`); `loom_auth` rename deferred |
| `Make_Skills/core/db/migrations.py:43-62,420-450` (`tenants` + `tenant_id_mapping`) | `tapestry/infra/migrations/000_init_platform.sql` | Refactor (forklift → `platform.*` schema) | Imported (Step 1, 2026-06-20) | conservative forklift, no redesign; bridge_idempotency/promoted_skills deferred to Step 4 |
| `the-loom/services/agent-context/` | `tapestry/services/agent-context/` | Lift | Imported (Step 2, 2026-06-20) | byte-identical (`cmp`); MCP host; auth shim resolves via `parents[2]/packages/auth/python`; **code only — not deployed (runbook gates pending)** |
| `the-loom/infra/migrations/001_init_memory.sql` | `tapestry/infra/migrations/001_init_memory.sql` | Lift (forklift) | Imported (Step 2, 2026-06-20) | byte-identical; `records` table (pgvector); per ADR-0003 |
| `the-loom/services/project-registry/` | `tapestry/services/project-registry/` | Lift | Imported (Step 3, 2026-06-20) | byte-identical (`cmp`); CRUD projects/repos/machines; shim `parents[2]`; **code only — not deployed**. Net-new signup endpoint deferred |
| `the-loom/infra/migrations/002_init_projects.sql` | `tapestry/infra/migrations/002_init_projects.sql` | Lift (forklift) | Imported (Step 3, 2026-06-20) | byte-identical; `projects`/`repos`/`machines` |
| `Make_Skills/core/skill_making/compiler.py` | `tapestry/engine/skill-compiler/python/skill_compiler/compiler.py` | **Refactor** | Imported (Step 4, 2026-06-21) | import paths rewritten to Tapestry layout; bodies unchanged; compile + resolution verified |
| `Make_Skills/services/skill_making/` (9 modules + tests) | `tapestry/services/skill-making/python/skill_making/` | **Refactor** | Imported (Step 4, 2026-06-21) | imports rewritten; **`hmac_verify.py`+`models.py` byte-identical** (wire contract); sys.path bootstrap; **deploy shape TBD** |
| `the-loom/loom-cli/` (`loom_cli/` + pyproject) | `tapestry/packages/cli/` | Lift | Imported (Step 5a, 2026-06-21) | byte-identical (`cmp`); stdlib-only; URL-env-driven; `tapestry_cli` resolves; not published yet |
| `project-starter/templates/_common/` + `{ui-app,agent-app}/` | `tapestry/templates/software-project/{ui,agent}/` | (Step 5b) Assemble (lift slices) | Imported (Step 5b, 2026-06-21) | **two-axis** (domain × shape, operator decision 2026-06-21); self-contained leaves; `_common` base + shape overlay; placeholder-driven; `.mcp.json` wires loom-memory at same URL |
| `classroom-hub-starter` (domain guide) + `project-starter` shapes | `tapestry/templates/classroom-project/{ui,agent}/` + `CLASSROOM_GUIDE.md` | (Step 5b) Assemble + author guide | Imported (Step 5b, 2026-06-21) | course-hub domain; `course-setup` skill + `classroom` adapter; readings/privacy rules; ref impl `summer-2026-hub` |
| `SDE_Extraction` (domain guide) + `project-starter` shapes | `tapestry/templates/research-project/{ui,agent}/` + `RESEARCH_GUIDE.md` | (Step 5b) Assemble + author guide | Imported (Step 5b, 2026-06-21) | research/synthesis domain; `research-project` adapter; `Agent Drafts/` vs `Human validated/` integrity boundary; deep-research skill set |
| (no source identified) | `tapestry/templates/operations-project/` | (Step 5b) — | **Deferred** | operator decision 2026-06-21: defer; no source repo for operations — documented slot only, not synthesized |
| `the-loom/apps/web-dashboard/` (16 tracked files) | `tapestry/apps/web-dashboard/` | Lift | Imported (Step 6, 2026-06-22) | byte-identical (`cmp`, 16/16); Next.js 15 + React 19; routes `/`,`/dashboard`,`/candidates`,`/api/health`; **code only — not deployed**. Consumes Step-7 services (architecture-registry, policy) via `NEXT_PUBLIC_LOOM_*` env (onrender defaults) → URL-repoint at deploy (audit §1.4). **README framing reconciliation owed:** lifted README L9 says "the-loom's running interface… Tapestry unrelated" — predates tapestry-as-container; operator to reconcile |
| `the-loom/services/policy/` | `tapestry/services/policy/` | **Refactor** | Imported (Step 7-policy, 2026-09-05) | Phase 5 audit-of-record (approve/reject/hold/demote + policy-state). SOFT/pure-audit (no bridge, no engine calls). auth shim `parents[2]`; test tenant-id invariant adapted to Tapestry env-fallback-to-nil (matches arch-registry); cross-service enum test repointed 003→**007**. `pytest` 12/12. **code only — not cut over** (render.yaml block disabled; repoint gate in README) |
| `the-loom/infra/migrations/004_init_policy.sql` | `tapestry/infra/migrations/004_init_policy.sql` | Lift (forklift) | Imported (Step 7-policy, 2026-09-05) | kept at **004** (free in Tapestry; single migration, nothing to consolidate); `policy_decisions` table, RLS, audit-immutable (no UPDATE policy); idempotent no-op replay vs live loom-postgres; no width ALTER needed |

## Template

When adding a row, copy this:

```markdown
| `<source-repo>/<path>` | `tapestry/<slot>/<path>` | <Decision> | Pending | <one-line context> |
```

## Migration log (when imports start happening)

| Date | Migrating PR | What | Outcome |
|---|---|---|---|
| 2026-06-20 | Step 1 (branch `tapestry-step-1-auth-consolidation`) | `packages/auth/` lift + `infra/migrations/000_init_platform.sql` | Merged to main (PR #4, `0625054`) |
| 2026-06-20 | Step 2 (PR #5/#7) | `services/agent-context/` lift + `001_init_memory.sql` + staging render.yaml | Merged; **staging deployed + parity GREEN**; prod re-source gated on operator |
| 2026-06-20 | Step 3 (PR #8) | `services/project-registry/` lift + `002_init_projects.sql` | Merged to main; no deploy |
| 2026-06-21 | Step 4 (branch `migration/04-engine`) | engine **Refactor**: `skill-compiler` + `skill-making` (import rewrites, bridge contract preserved) | Code refactored + verified; runbook `proposed`; deploy shape TBD; no deploy |
| 2026-06-21 | Step 5a (PR #12) | `packages/cli/` lift (`tapestry_cli`) | Merged to main (`fe6888f`); not published |
| 2026-06-21 | Step 5b (branch `migration/05b-software-template`) | `templates/` **two-axis** (domain × shape): software/classroom/research × {ui,agent} from `project-starter` + domain guides from `classroom-hub-starter`/`SDE_Extraction`; operations deferred | Operator chose two-axis + defer-operations; built in isolated worktree |
| 2026-06-22 | Step 6 (branch `migration/06-web-dashboard`) | `apps/web-dashboard/` lift (Next.js 15 dashboard, 16 files byte-identical) | Code lifted + cmp-verified; no deploy; URL-repoint + README-framing reconciliation flagged for operator |
| 2026-09-05 | Step 7-policy (branch `feat/migrate-policy-service`) | `services/policy/` Refactor + `004_init_policy.sql` forklift; disabled render.yaml repoint block | Code migrated + `pytest` 12/12; tenant-id invariant adapted to Tapestry fail-closed-to-nil; enum test repointed to 007; no deploy (repoint gate in README) |
