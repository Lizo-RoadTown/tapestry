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
