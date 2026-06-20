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

## Template

When adding a row, copy this:

```markdown
| `<source-repo>/<path>` | `tapestry/<slot>/<path>` | <Decision> | Pending | <one-line context> |
```

## Migration log (when imports start happening)

| Date | Migrating PR | What | Outcome |
|---|---|---|---|
| 2026-06-20 | Step 1 (branch `tapestry-step-1-auth-consolidation`) | `packages/auth/` lift + `infra/migrations/000_init_platform.sql` | Merged to main (PR #4, `0625054`) |
| 2026-06-20 | Step 2 (branch `migration/02-agent-context-mcp`) | `services/agent-context/` lift + `infra/migrations/001_init_memory.sql` + staging render.yaml | Code imported; runbook `approved`; staging deploy = operator Render action; prod gated |
