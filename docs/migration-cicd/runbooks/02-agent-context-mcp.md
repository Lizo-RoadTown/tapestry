# Step 02 — agent-context (loom-memory MCP)

**Owner:** Liz (operator)
**Source repo:** the-loom
**Source path:** `services/agent-context/`
**Destination:** `tapestry/services/agent-context/`
**Decision:** [x] Lift  (verbatim; schema forklift per [ADR-0003](../../adr/0003-shared-postgres-schema-source-of-truth.md))
**Status:** approved (operator 2026-06-20 "step 2 is approved") — code lifted; next gate is `approved → staging-deployed`, which needs operator Render actions (staging service + DB snapshot + secrets). Production stays gated.
**ADR:** [ADR-0002](../../adr/0002-cutover-continuous-sync.md) (cutover), [ADR-0003](../../adr/0003-shared-postgres-schema-source-of-truth.md) (schema source-of-truth)

> **⚠️ CORE DIRECTIVE 1 — highest blast radius in the system.** This service hosts the loom-memory MCP that EVERY session in EVERY repo depends on. A bad cutover breaks all agents everywhere. This runbook's whole design goal is to make the change a **near-no-op for consumers** and **instantly reversible**.

## The safety design (why this is low-risk despite being the MCP)

The change is a **re-source of ONE service**, not a parallel fleet cutover:

- **Same Render service name** (`loom-agent-context`) → **same URL** (`…onrender.com/mcp/memory/`) → **every consumer `.mcp.json` is unchanged** (zero fleet-wide edit, no plugin-session-binding churn).
- **Same database** (`loom-postgres`) → **no data moves** (the records stay put; ADR-0002 dual-write/replay is therefore minimized — see Risk R3).
- **Same JWT keys** (copied, not rotated) → existing tokens stay valid.
- **The ONLY thing that changes:** which repo Render builds the service from (`the-loom` → `tapestry`). At first the code is byte-identical (Lift), so a rollback is "point Render back at the-loom and redeploy."

## Pre-flight checklist

- [ ] Source code grep'd; all callers of the MCP enumerated (every `.mcp.json` in the fleet + the engine's `Make_Skills/.mcp.json:5`)
- [ ] Source env vars enumerated + current Render values captured (`LOOM_JWT_PRIVATE_KEY`, `LOOM_JWT_PUBLIC_KEY`, `LOOM_DB_URL`, `LOOM_SELF_HOST_TENANT_ID` default, OTEL group)
- [ ] No source cron jobs (agent-context has none; the cron is self-observer = Step 7-adjacent)
- [ ] Destination `tapestry/services/agent-context/` collision-checked (currently README-only)
- [ ] No in-flight the-loom PR touching `services/agent-context/`
- [ ] Memory recall for `feedback_*` on agent-context / MCP / cold-start
- [ ] **Decide the Render blueprint-ownership handover** (per research: `fromDatabase` can't bind cross-blueprint → use connection-string-as-secret; ensure only ONE blueprint deploys `loom-agent-context`)

## Pre-step capability snapshot

- **MCP transport:** `mcp_http.py` mounts streamable HTTP at `/mcp/memory/` (TokenVerifier = `loom_auth.LoomTokenVerifier`); self-host middleware sets `SELF_HOST_TENANT_ID` when no Bearer.
- **REST (B1):** `POST /v1/write`, `POST /v1/read` (`main.py:210-267`) — used by the self-observer synthesis memo.
- **Token issuer:** mints RS256 JWTs (holds `LOOM_JWT_PRIVATE_KEY`).
- **DB tables:** `records` (memory; `001_init_memory.sql`, 266 lines, pgvector; 209 rows under SELF_HOST_TENANT_ID per the clean tenant audit). Read+write, RLS by tenant.
- **External:** none outbound critical (it IS the dependency).
- **Health:** `/health` 200; `plan: starter` (no cold start) — preserve this.

## Change plan

- **Added in Tapestry:** `services/agent-context/` (verbatim lift), `infra/migrations/001_init_memory.sql` (forklift), a `tapestry/infra/deploy/render.yaml` entry for `loom-agent-context` (same name) referencing the DB via **connection-string secret** + `packages/auth` import.
- **Source files frozen (no edits):** `the-loom/services/agent-context/*` once parity-verified.
- **Migration path during overlap:** there is no two-instance overlap by design — staging runs under a DISTINCT name against a DB copy; production is an atomic re-source of the single `loom-agent-context` (the-loom blueprint stops deploying it, tapestry blueprint takes it over).

## Risk register

| Risk | P | Impact | Mitigation |
|---|---|---|---|
| R1 — MCP down during re-source (CORE DIRECTIVE 1) | M | **Critical** | Atomic re-source (no DNS/name change); rollback = re-point Render to the-loom + redeploy (byte-identical code); keep `plan: starter` |
| R2 — two blueprints both deploy `loom-agent-context` → fight | M | High | Mechanical one-blueprint invariant: set the-loom service `autoDeploy:false` (or remove from the-loom render.yaml) BEFORE tapestry blueprint owns it |
| R3 — records written during the switch window are lost | L | High | Window is seconds (re-source, same DB); the DB never moves, so no replay needed — but verify write-path continuity post-switch (write a probe record, read it back) |
| R4 — `LOOM_DB_URL` via `fromDatabase` silently makes a NEW empty DB | M | **Critical** | Per research: do NOT use `fromDatabase` cross-blueprint. Set the raw connection string as a `sync:false` secret. Verify row count = 209 post-deploy BEFORE accepting |
| R5 — JWT key/tenant constant drift | L | High | Copy `LOOM_JWT_*` byte-identical; `SELF_HOST_TENANT_ID` must equal `auth_bridge.py:97` (`1d8ec1b3-…`) or RLS returns empty |
| R6 — in-flight sessions pinned to old host | L | Low | URL unchanged → non-issue (the reason to preserve the name) |

## Test matrix

- [x] Unit — destination (port the-loom's agent-context tests)
- [x] Contract — MCP handshake + `/v1/write|read` wire-compat vs source
- [x] Integration — staging against a `loom-postgres` snapshot/copy
- [x] Parity — `memory_recall`/`memory_read` return identical rows source vs staging
- [ ] Smoke — prod canary: one `memory_write` + `memory_recall` round-trip from a real session
- [x] Regression — a consuming repo's SessionStart `memory_recall` still resolves

## Staging deploy

1. Branch: `migration/02-agent-context-mcp`
2. Render staging service: `tapestry-agent-context-staging` (DISTINCT name; never collides with prod)
3. Env vars (check existing first): copy `LOOM_JWT_*`, OTEL group; set `LOOM_DB_URL` to a **read replica or restored snapshot** of loom-postgres (NOT prod write)
4. Migrations: apply `001_init_memory.sql` to the staging DB
5. Deploy: tapestry blueprint, staging service only

## Parity check (go/no-go) — ≥1h or N requests

- [ ] `memory_read`/`recall` body diff < 0.1% (excl. UUIDs/timestamps) vs source
- [ ] MCP handshake succeeds from a real client
- [ ] Latency p95 within 20% of source
- [ ] Row count matches (209 baseline)
- [ ] `/v1/write` + `/v1/read` round-trip identical

**Go:** all green → operator authorizes prod. **No-go:** any red → back to `approved`.

## Production rollout

- **Style:** [x] cutover (atomic re-source of `loom-agent-context`; same name/URL/DB)
- **Sequence:** (1) set the-loom `loom-agent-context` `autoDeploy:false` (R2); (2) tapestry blueprint deploys `loom-agent-context` from `tapestry/services/agent-context/` against the connection-string secret; (3) `/health` 200 + probe `memory_write`→`memory_recall` round-trip + row count = 209; (4) accept.
- **Rollback trigger:** MCP `/health` not 200 within 5min; any `memory_recall` failure from a live session; row count ≠ 209.
- **Rollback command:** re-enable the-loom `loom-agent-context` autoDeploy + redeploy the-loom version (code byte-identical → instant, lossless; DB untouched).

## Sign-off

- [x] Operator: Liz @ 2026-06-20 (proposed → approved)
- [x] Tapestry-agent: code lift complete @ 2026-06-20
- [ ] Operator: prod authorization (parity-verified → prod-rolling) — PENDING
- [ ] Source steward (loom-agent): ____ @ ____

## Post-deployment monitoring

- **24h:** MCP error rate, `/health`, `memory_*` success rate, latency → Grafana
- **7d:** memory write/read incident review across consuming repos
- Alerts: MCP-down = P0 page (per MANIFESTO Pillar 2)

## Source prototype retirement (only after 7d clean)

- [ ] the-loom `services/agent-context/` tagged `migrated-02`
- [ ] the-loom blueprint no longer declares `loom-agent-context` (tapestry owns it)
- [ ] the-loom source path frozen read-only
- [ ] (DB is shared/unchanged — NOT retired here; it's the same `loom-postgres`)

---

**Status note:** this runbook is `proposed`. It does not authorize any deploy. The `proposed → approved` gate needs operator + Tapestry-agent sign-off; every later gate (staging, parity, prod) is separately gated. Nothing touches production until you walk it through these gates.
