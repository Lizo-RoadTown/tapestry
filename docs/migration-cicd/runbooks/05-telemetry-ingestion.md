# Step 05 — telemetry-ingestion (the event store cutover, A1→A5)

**Owner:** Liz (operator)
**Source repo:** the-loom (deployed log-only build)
**Source path:** `services/telemetry-ingestion/`
**Destination:** `tapestry/services/telemetry-ingestion/` (already the newer code)
**Decision:** [x] Refactor (authenticated reads added; then repoint — the adopted arrangement, [2026-10-21-telemetry-deployment-recommendation.md](../../plans/2026-10-21-telemetry-deployment-recommendation.md), all five options recommended + adopted)
**Status:** **proposed** — A1 PR adds read auth + tests + the gated render block + this runbook + the migrations ledger. Nothing deploys from that PR.
**References:** master plan workstream A ([2026-10-21-master-plan-personal-loop.md](../../plans/2026-10-21-master-plan-personal-loop.md)); manifest components pl-002/pl-003; modeled on [02-agent-context-mcp.md](02-agent-context-mcp.md).

> This cutover turns the fleet's telemetry from verified-logged-DISCARDED into stored-and-readable. It is the gate for wires X1, X2, and X4 and the prerequisite for milestone M1.

## The safety design

Same shape as the agent-context cutover (02):

- **Same Render service name** (`loom-telemetry-ingestion`) → same URL → the engine's /skill-used callback target and the hooks' future `LOOM_INGEST_ENDPOINT` need no coordination.
- **Same database** (live `loom-postgres`) → additive migrations only (005/006 create NEW tables; nothing existing is touched).
- **The only change at cutover:** which repo Render builds from. Rollback = re-point back to the-loom (one dashboard action).
- The legacy build never wrote the DB, so there is no data to migrate and no replay question — only a loss window during the switch, bounded by the hooks' local `hooks.jsonl` buffer + `flush_hooks_jsonl.py` backfill.

## Pre-cutover checks (agent, before asking Liz to act)

- [ ] A1 PR merged; CI leg `telemetry-ingestion` green on main.
- [ ] `infra/migrations/APPLIED.md` exists and reflects reality.
- [ ] No in-flight the-loom PR touching `services/telemetry-ingestion/`.
- [ ] The the-loom cleanup PR (removing `the-loom/render.yaml:144-164`) authored and ready to merge.

## Operator steps

### A2 — apply the migrations (manual psql, per the fleet convention)

1. Render dashboard → loom-postgres → PSQL console.
2. Paste `infra/migrations/005_init_telemetry.sql`, run; then `006_init_observation_signals.sql`, run. Both are idempotent.
3. Tell the agent; it verifies the tables + forced RLS exist and records both rows in `infra/migrations/APPLIED.md` with evidence.

### A3 — provision env on the `loom-telemetry-ingestion` service

| Variable | Value |
|---|---|
| `LOOM_DB_URL` | raw internal connection string of live loom-postgres (never `fromDatabase`) |
| `SELF_HOST_TENANT_ID` | `1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8` (must match writer/reader/cron) |
| `LOOM_SKILL_BRIDGE_SECRET` | COPY byte-identical from the engine pair (no rotation now) |
| `LOOM_HOOK_BRIDGE_SECRET` | mint NEW (`python -c "import secrets; print(secrets.token_hex(32))"`); the hook emitter gets the same value as `LOOM_HOOK_BRIDGE_SECRET` on each machine |
| `TAPESTRY_TELEMETRY_READ_KEY` | mint NEW; goes to read clients only (self-observer may instead use `OBSERVER_JWT` minted via `scripts/mint_token.py`) |
| `LOOM_JWT_PUBLIC_KEY` | from `tapestry-shared-secrets` (fromGroup already in the block) |

### A4 — one-blueprint, then repoint

1. Merge the the-loom cleanup PR (removes its telemetry block → one-blueprint invariant satisfied).
2. Render dashboard → `loom-telemetry-ingestion` → change source repo the-loom → tapestry, rootDir `services/telemetry-ingestion`, branch main → deploy.
3. Uncomment the gated block in `infra/deploy/render.yaml` in a small PR (the record that tapestry now owns the service).

## Post-cutover smoke (agent, A5)

- [ ] `GET /health` 200.
- [ ] POST a signed probe hook event (`LOOM_HOOK_BRIDGE_SECRET`) → 202 with `events_processed: 1`.
- [ ] `GET /telemetry/invocations` for the probe's artifact_ref **with the read key** → 200, `known: true`.
- [ ] Same GET **without credentials** → 401 (read auth live).
- [ ] Re-POST the identical probe → dedup (no double count).
- [ ] Set `LOOM_INGEST_ENDPOINT` on this machine (wire X1) and run one real session; event arrives.
- [ ] Run `flush_hooks_jsonl.py` backfill for the accumulated local buffer; counts rise; duplicates excluded.
- [ ] Record outcomes in `docs/test-runs/` + memory.

## Rollback

Re-point the Render service's repo back to the-loom and redeploy (one dashboard action). The DB keeps whatever was stored; the hooks fall back to local-buffer-only, exactly today's behavior.

## Risk register (delta from 02's)

| Risk | P | Impact | Mitigation |
|---|---|---|---|
| Migrations collide with the-loom's series | — | none at the schema level | numbering-only collision; tables are disjoint; ledger records both series (see APPLIED.md) |
| Read routes exposed unauthenticated | L | High | no anonymous path exists in this build; smoke asserts 401 |
| `SELF_HOST_TENANT_ID` drift between writer/reader/cron | M | High (silent empty reads) | single value in A3 table; smoke's probe-write→authed-read catches drift immediately |
| Free-plan cold start drops sender pushes | M | Low | hooks keep the local jsonl buffer; backfill is idempotent (uuid5 + ON CONFLICT) |
