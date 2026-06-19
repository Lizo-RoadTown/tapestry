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

## Empty (2026-06-12 spawn)

No imports yet. Add a row when scoping a migration. **The ratified migration order (per the readiness plan §5 + v1 roadmap §5) is auth → agent-context → project-registry → engine → templates+CLI → web-dashboard → architecture-registry+policy → telemetry — NOT policy-first.** The single blocker before any import is PR-prep-2 (loom-side URL externalization). First import is `packages/auth/` + `services/agent-context/` once PR-prep-2 lands and Liz says go.

## Template

When adding a row, copy this:

```markdown
| `<source-repo>/<path>` | `tapestry/<slot>/<path>` | <Decision> | Pending | <one-line context> |
```

## Migration log (when imports start happening)

| Date | Migrating PR | What | Outcome |
|---|---|---|---|
| (empty) | | | |
