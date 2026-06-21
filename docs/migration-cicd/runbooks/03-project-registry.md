# Step 03 — project-registry

**Owner:** Liz (operator)
**Source repo:** the-loom · **Source path:** `services/project-registry/`
**Destination:** `tapestry/services/project-registry/`
**Decision:** [x] Lift (verbatim; schema forklift per [ADR-0003](../../adr/0003-shared-postgres-schema-source-of-truth.md))
**Status:** proposed — code lifted (no deploy). Same re-source pattern as [Step 2](02-agent-context-mcp.md); **lower blast radius** (CRUD service, not the memory MCP).

## Capability snapshot
- `loom-project-registry` (Render, `plan: free`) — CRUD for `projects` / `repos` / `machines`; tenant-scoped (RLS). Reads `LOOM_DB_URL` (loom-postgres) + `LOOM_JWT_PUBLIC_KEY` (verify) via the `auth_bridge`→`loom_auth` shim. `/health`.
- Consumers: `loom-cli`/`tapestry init`, self-observer (`project_id` lookups), dashboard.
- **NOT in this lift:** the net-new tenant **signup endpoint** (roadmap §5 Step 3) — deferred to a follow-up.

## Change plan
- Added in Tapestry: `services/project-registry/` (verbatim Lift), `infra/migrations/002_init_projects.sql` (forklift), a staging entry in `infra/deploy/render.yaml`.
- Source frozen (no edits) once parity-verified.

## Risk register (abridged — see Step 2 for the shared re-source pattern)
| Risk | P | Impact | Mitigation |
|---|---|---|---|
| `fromDatabase` spawns empty DB | M | High | connection-string-as-secret, NOT `fromDatabase` |
| two blueprints fight over `loom-project-registry` | M | Med | the-loom `autoDeploy:false` before tapestry owns it |
| `project_id` UUID drift breaks self-observer | L | Med | same DB reused → IDs stable; verify post-cutover |

## Staging deploy (fresh empty DB, like Step 2)
1. New Render Postgres (or reuse the Step-2 staging DB — same `loom-postgres` schema set).
2. Apply: `psql "<external url>" -f infra/migrations/002_init_projects.sql`.
3. New web service `tapestry-project-registry-staging` from **tapestry** repo, rootDir `services/project-registry`, `LOOM_DB_URL` = staging internal url, `PYTHON_VERSION=3.12`.
4. Deploy → `/health` 200.

## Parity / smoke (go/no-go)
```bash
curl -fsS https://<staging>/health
# create a project (self-host), then read it back — confirm round-trip + tenant scoping
# (exact endpoints per main.py; Tapestry-agent runs the precise calls when staging is up)
```
- [ ] `/health` 200
- [ ] create→read round-trip on a project
- [ ] tenant scoping correct (self-host → SELF_HOST_TENANT_ID)

## Production rollout
Re-source `loom-project-registry` (preserve name/URL/DB): the-loom `autoDeploy:false` → tapestry deploys `loom-project-registry` from `services/project-registry` against the real loom-postgres connection-string secret → verify `/health` + a project read. **Rollback** = revert source to the-loom (byte-identical, lossless).

## Sign-off
- [ ] Operator @ ____  · [ ] Tapestry-agent @ ____  · [ ] loom-agent (the-loom handover) @ ____

## Retirement (after 7d clean)
- [ ] the-loom `services/project-registry/` tagged `migrated-03`; the-loom blueprint no longer declares `loom-project-registry`; source frozen read-only.
