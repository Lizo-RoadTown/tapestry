# Telemetry substrate deployment — recommendation

**Date:** 2026-10-21
**Scope:** deploy arrangement for `services/telemetry-ingestion/` (code-complete, undeployed) replacing the live log-and-discard receiver `loom-telemetry-ingestion` built from the-loom.
**Status:** recommendation; no deploy is authorized by this document. Every gate below follows the runbook discipline established in `docs/migration-cicd/runbooks/02-agent-context-mcp.md`.

---

## Recommendation (primary, one arrangement)

**Repoint the existing `loom-telemetry-ingestion` Render service at the Tapestry repo — same name, same URL, same live `loom-postgres` — exactly as the agent-context cutover did, after (a) applying Tapestry migrations 005 + 006 to the live DB and (b) landing authenticated reads in `read_api.py`.**

Concretely:

1. **Service:** the existing Render service `loom-telemetry-ingestion` (declared today at `the-loom/render.yaml:144-164`, `autoDeploy: true` at `:153`) is re-sourced to `tapestry`, `rootDir: services/telemetry-ingestion`. Name and URL preserved → every baked consumer URL keeps working (enumerated in §3). Rollback = re-point Render back at the-loom (precedent: `docs/migration-cicd/runbooks/02-agent-context-mcp.md:15-20` and the agent-context removal note at `the-loom/render.yaml:73-85`).
2. **Database:** the live `loom-postgres` (the only production database in either blueprint — `the-loom/render.yaml:40-48`), connected via a `sync: false` raw connection-string secret, **never** `fromDatabase` (a second blueprint's `fromDatabase` spawns a new empty DB — `tapestry/infra/deploy/render.yaml:9-15`, runbook risk R4 at `02-agent-context-mcp.md:54`). This is where the schema was written to land: `infra/migrations/005_init_telemetry.sql:3` ("Telemetry read-substrate for loom-postgres") and `services/telemetry-ingestion/README.md:23`.
3. **Migrations:** apply Tapestry `005_init_telemetry.sql` then `006_init_observation_signals.sql` to `loom-postgres` manually via psql (the established convention: `the-loom/infra/migrations/README.md:21-39`); both are idempotent `CREATE IF NOT EXISTS` wrapped in `BEGIN/COMMIT` (`005:33-41`, `006:32-39`). Record the apply in a new checked-in ledger (§2).
4. **One-blueprint invariant:** before the Tapestry blueprint block is enabled, the-loom's `loom-telemetry-ingestion` block (`the-loom/render.yaml:144-164`) is removed in a the-loom PR, mirroring the agent-context precedent (`the-loom/render.yaml:73-85`; invariant stated at `tapestry/infra/deploy/render.yaml:17-19`).
5. **Blueprint block:** a gated, commented-out prod repoint block is added to `tapestry/infra/deploy/render.yaml`, following the `loom-architecture-registry` repoint pattern (`render.yaml:185-241`): same name, `autoDeploy: false`, `plan: free`, env per §4.
6. **Read auth:** required before cutover; mechanism in §5 (mirror of the memory service's REST tenant resolver, anonymous disabled for `/telemetry/*`).

Why not a new `tapestry-telemetry-ingestion` name: §3 enumerates ~10 baked consumer references across three repos plus per-machine `.env` files that would all need retargeting, including a default URL the live registry *distributes to the engine* at promotion time (`the-loom/services/architecture-registry/promote_dispatcher.py:101-105`, used at `:288-291`). The repo's own precedent is name-preservation (`02-agent-context-mcp.md:17`: "same URL → every consumer unchanged"), and the staged rename discipline (ADR-0003 point 4, `docs/adr/0003-shared-postgres-schema-source-of-truth.md:23`) treats `loom-*` names as a transition concern with its own later runbook — not something to force through a telemetry cutover.

---

## 1. Database findings

**Databases that exist:**

| Database | Declared | Role |
|---|---|---|
| `loom-postgres` (db `loom`, PG 16, oregon, plan basic-256mb) | `the-loom/render.yaml:40-48` | THE production DB. All live services use it via `fromDatabase` (`the-loom/render.yaml:132-135` registry, `:161-164` telemetry, `:200-203` arch-registry, `:244-247` policy) |
| `tapestry-agent-context-staging-db` (`dpg-d8rcol3eo5us73d7ejcg-a`) | `02-agent-context-mcp.md:71` | fresh empty staging DB for Step 2 |
| staging copies for observatory blocks | `tapestry/infra/deploy/render.yaml:61,84,116,135` (`sync:false` "STAGING copy of loom-postgres") | staging only |

Tapestry's blueprint deliberately declares **no `databases:` block** (`infra/deploy/render.yaml:11-15`). The live `loom-agent-context` (memory) was already cut over to build from Tapestry against the same `loom-postgres` (`the-loom/render.yaml:73-85`; `02-agent-context-mcp.md:8`). So the live system's data all lives in one Postgres, and the telemetry schema headers target that same DB (`005_init_telemetry.sql:3`, `README.md:23,27`). **Recommended: telemetry tables land in the live `loom-postgres`.** A separate telemetry DB would break the single-tenant-envelope assumption (§4) and give the observers a second connection to manage for no isolation benefit — RLS already isolates by tenant (`005:189-249`).

## 2. Migrations: inventory, ownership, numbering, ledger

**the-loom `infra/migrations/` (applied to live loom-postgres):**

| File | Touches | Applied evidence |
|---|---|---|
| `001_init_memory.sql` | `records` + pgvector + RLS | live memory service; 209 rows (`02-agent-context-mcp.md:37`) |
| `002_init_projects.sql` | `projects`, `repos`, `machines` | live registry uses it |
| `003_init_candidates.sql` | `candidates` (4-kind CHECK) | superseded by 005/006 alters |
| `004_init_policy.sql` | `policy_decisions` | live `loom-policy` (shipped 2026-06-12, `tapestry render.yaml:246-250`) |
| `005_alter_candidate_type.sql` | `candidates.candidate_type` CHECK → 4 new kinds | PROBE against prod in header (`005:13-17`) |
| `006_expand_candidate_type_to_9_kinds.sql` | CHECK → 9 kinds + `'tool'→'inline_tool'` data fix | PROBE against prod in header (`006:25-28`) |

**tapestry `infra/migrations/`:** `000_init_platform.sql` (platform.tenants/tenant_id_mapping — explicitly NOT applied anywhere, `000:18-19`), `001_init_memory.sql` (forklift, parity with live), `002_init_projects.sql` (parity), `004_init_policy.sql` (byte-parity no-op replay of the-loom 004, `004:16-26`), `005_init_telemetry.sql` + `006_init_observation_signals.sql` (**new tables, nothing applied to prod**), `007_init_candidates.sql` (consolidates the-loom 003+005+006 into one terminal-state no-op replay, `007:19-30`).

**Numbering reconciliation — mostly already done.** The 005/006 collision is number-only, not content: the-loom's 005/006 alter `candidates`; Tapestry's 005/006 create `telemetry_events`/`telemetry_rollup_daily`/`observation_signals`. Tapestry resolved it by renumbering candidates to 007 and documenting why the-loom's numbers cannot be reused (`007_init_candidates.sql:19-30`), and 006's header records the numbering rationale (`006:25-27`). **Ownership:** ADR-0003 already rules that Tapestry's `infra/migrations/` is the canonical series and the-loom's freezes at parity (`docs/adr/0003:17`). Nothing to re-decide; the Tapestry sequence 000–007 is the one true series going forward, and the-loom's directory is a frozen historical record.

**Applied-state ledger (the real gap).** There is no record anywhere of which file has run against which database — Tapestry's `infra/migrations/README.md:3` is still "Slot. No code yet." (stale: the directory holds eight migrations), and the-loom's README only *plans* a `_migrations` table "from a service (future)" (`the-loom/infra/migrations/README.md:43`). Minimal proposal, consistent with the manual-psql convention (`the-loom README:21-39`):

- **A checked-in ledger file `tapestry/infra/migrations/APPLIED.md`** — one table: migration file × database (loom-postgres / staging DBs) × date × who × evidence link. Zero runtime machinery; auditable in git; matches how applies actually happen (operator psql console). Seed it from the evidence above, with unknowns marked for operator confirmation.
- Rewrite `infra/migrations/README.md` to describe the real contents + the ledger rule ("no psql apply without a ledger row in the same PR").
- The `schema_migrations`/`_migrations` table stays future scope (it belongs with the "service runs migrations on startup" change the-loom README deferred); do not build it for this cutover.

## 3. Service naming: repoint vs. new name

**(a) Repoint `loom-telemetry-ingestion` (recommended).** Precedent is exact: the agent-context cutover preserved name/URL/DB and flipped only the source repo (`02-agent-context-mcp.md:15-20`; `the-loom/render.yaml:73-85`). Consequences: the-loom's `autoDeploy: true` block (`the-loom/render.yaml:153`) must be removed/disabled first or the two blueprints fight over the service (one-blueprint invariant, `tapestry/infra/deploy/render.yaml:17-19`; risk R2 pattern at `02-agent-context-mcp.md:52`). The Tapestry prod block stays commented out until the repoint gate, like the architecture-registry and policy blocks (`render.yaml:185-241, 243-293`). Rollback is the documented one-step re-point (`render.yaml:210-211`).

**(b) New `tapestry-telemetry-ingestion` name — every consumer that would need retargeting:**

| Consumer | Reference |
|---|---|
| self-observer default `TELEMETRY_QUERY_URL` (Tapestry copy) | `tapestry/services/self-observer/config.py:152-155` |
| self-observer default (legacy copy, still the deployed cron) | `the-loom/services/self-observer/config.py:113` |
| the-loom cron's declared env | `the-loom/render.yaml:308-309` |
| engine callback default the live registry **distributes** in every promotion payload | `the-loom/services/architecture-registry/promote_dispatcher.py:101-105`, used at `:288-291` (Tapestry copy identical: `services/architecture-registry/promote_dispatcher.py:104`) |
| engine-side default sender URL | `Make_Skills/services/skill_making/telemetry_sender.py:38` (+ Tapestry copy `services/skill-making/python/skill_making/telemetry_sender.py:38`) |
| hooks' `LOOM_INGEST_ENDPOINT` in every machine's `.env` | `integrations/claude-code/tapestry-discipline/scripts/_observability.py:390-398` |
| backfill tool reads the same env | `integrations/claude-code/tapestry-discipline/scripts/flush_hooks_jsonl.py:54,95` |
| tests asserting the URL | `services/architecture-registry/tests/test_promote_dispatcher.py:213`, `tests/test_bridge_contract.py:64` (both repos) |
| wire-contract doc | `services/architecture-registry/bridge_models.py:29` |

Ten-ish touchpoints across three repos plus per-machine env, including already-dispatched promotion payloads whose callback URL cannot be recalled. Option (b) is rejected; the `loom-*`→`tapestry-*` rename is a separate, later exercise under the ADR-0003 naming-transition rule (`0003:23`).

## 4. Tenant + secrets

| Var | Where it stands today | Recommended single source |
|---|---|---|
| `SELF_HOST_TENANT_ID` | Live value `1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8`: baked in the-loom's auth bridge (`the-loom/packages/auth/python/loom_auth/auth_bridge.py:97`); env-sourced in Tapestry's (`tapestry/packages/auth/python/loom_auth/auth_bridge.py:108-114`); pinned in blueprint comments (`infra/deploy/render.yaml:232-233,292-293`) and `scripts/mint_token.py:40`. Fail-closed on both telemetry paths: writes (`skill_usage_handler.py:96-97`), reads 503 (`read_api.py:89-97`). | Set once in the **`tapestry-shared-secrets` env group** (`render.yaml:28-33`) and have every Tapestry-sourced service take it from the group — exactly what the auth bridge asks for ("Pin the env in one place per deployment (a shared env group)", `auth_bridge.py:105-107`). The telemetry service, the observatory cron/web, and the repointed registry/policy then cannot drift from each other. |
| `LOOM_SKILL_BRIDGE_SECRET` | In the-loom's `loom-shared-secrets` group (`the-loom/render.yaml:63-64`), shared byte-identical with the Make_Skills engine. Verified by `bridge_hmac.py` on `/skill-used` (`services/telemetry-ingestion/bridge_hmac.py:8`). | Copy **byte-identical** (no rotation) into `tapestry-shared-secrets`, same as the JWT keys were (`render.yaml:24-26`). Rotation would require a simultaneous engine-side change — out of scope for this cutover. |
| `LOOM_HOOK_BRIDGE_SECRET` | Exists nowhere in either blueprint — it is new with this service (`services/telemetry-ingestion/main.py:41`; emitter side `_observability.py:394-399`). | Operator mints one value; set it (1) on the Render service and (2) in each machine's discipline-hooks `.env` next to `LOOM_INGEST_ENDPOINT`. Service-side home: `tapestry-shared-secrets` group, so the future observatory emitters inherit it. |

## 5. Read auth (required before cutover)

Today `/telemetry/*` reads have **no auth at all** — tenant comes from the server's own env (`read_api.py:42-58`), so anyone who finds the URL can read the whole self-host tenant's telemetry. The module's own TODO names the fix (`read_api.py:54-58`): mirror the memory service's REST resolver.

**Recommended mechanism — least new machinery:** reuse the existing `loom_auth` bearer bridge, as `services/agent-context/main.py:53-100` (`_resolve_tenant_for_rest`) already does: bearer token checked first against a shared key via constant-time `api_key_matches` (`packages/auth/python/loom_auth/auth_bridge.py:226-233`) → self-host tenant; else RS256 JWT verified with `LOOM_JWT_PUBLIC_KEY` → `tenant_id` claim (`main.py:87-100`). One deliberate difference from memory: **no anonymous path** for `/telemetry/*` — the anonymous gate exists only to protect already-deployed clients during a staged rollout (`auth_bridge.py:204-223`), and telemetry reads have zero existing clients, so they start locked (`401` on no/invalid token; keep the existing nil-tenant 503 as the last line, `read_api.py:89-97`). Writes stay on HMAC unchanged.

Files to change:

- `services/telemetry-ingestion/read_api.py` — replace `_resolve_read_tenant()` (`:78-97`) with a FastAPI dependency modeled on `agent-context/main.py:53-100`, minus the anonymous branch.
- `services/telemetry-ingestion/requirements.txt` — add `python-jose` (its absence was the deliberate Phase-0 deferral, `read_api.py:44-45`).
- New thin shim (or direct `sys.path` insert) so `loom_auth` imports from `packages/auth/python`, copying `services/agent-context/auth_bridge.py:20-40`. Guarded-import discipline per `auth_bridge.py:65-83` means no `mcp` dependency comes along.
- Env: `LOOM_JWT_PUBLIC_KEY` already in `tapestry-shared-secrets` (`render.yaml:31-32`); add a telemetry read key env (reuse the `_memory_api_key` resolution pattern, `auth_bridge.py:195-201`, under a telemetry-specific name such as `TAPESTRY_TELEMETRY_READ_KEY` so the memory key's blast radius does not widen).
- Consumers: the self-observer already sends `OBSERVER_JWT` as a Bearer when set (`services/self-observer/config.py:170-178`; declared at `render.yaml:176-177` and `the-loom/render.yaml:316-317`) — mint it with `scripts/mint_token.py` (tenant claim = `1d8ec1b3-…`, `mint_token.py:40,94`). The observatory cron reads the DB directly, not this API (`render.yaml:88-92`), so it is untouched.

## 6. Operational sequence

| # | Step | Owner |
|---|---|---|
| 1 | Land read auth (§5: `read_api.py`, `requirements.txt`, auth shim, tests) — PR | agent |
| 2 | Author `docs/migration-cicd/runbooks/05-telemetry-ingestion.md` from `04-runbook-template.md`; add the gated (commented) prod repoint block for `loom-telemetry-ingestion` to `infra/deploy/render.yaml` following the `:185-241` pattern (`plan: free`, `autoDeploy: false`, env per §4/§5) — PR | agent |
| 3 | Create `infra/migrations/APPLIED.md` ledger + rewrite the stale `infra/migrations/README.md:3` slot text — PR | agent |
| 4 | Confirm ledger unknowns against the Render dashboard; approve the runbook (`proposed → approved`) | operator |
| 5 | Apply `005_init_telemetry.sql` then `006_init_observation_signals.sql` to live `loom-postgres` via the Render PSQL console (`the-loom/infra/migrations/README.md:37-39`); both idempotent | operator (agent verifies tables exist + RLS forced, updates ledger) |
| 6 | Provision env on the Render service: `LOOM_DB_URL` (raw internal string, sync:false), `SELF_HOST_TENANT_ID=1d8ec1b3-…`, copy `LOOM_SKILL_BRIDGE_SECRET`, mint `LOOM_HOOK_BRIDGE_SECRET`, `LOOM_JWT_PUBLIC_KEY`, telemetry read key; mint `OBSERVER_JWT` (`scripts/mint_token.py`) | operator |
| 7 | the-loom PR removing the `loom-telemetry-ingestion` block (`the-loom/render.yaml:144-164`), agent-context-style tombstone comment; merge = one-blueprint satisfied | agent authors; operator merges |
| 8 | Repoint the Render service's repo the-loom → tapestry, rootDir `services/telemetry-ingestion`; deploy | operator (dashboard action) |
| 9 | Post-cutover smoke: `/health` 200; HMAC-signed `POST /hook-events` lands a row; unauthenticated `GET /telemetry/invocations` → 401; authed GET returns the probe row under tenant `1d8ec1b3…` | agent |
| 10 | Turn on emitters: set `LOOM_INGEST_ENDPOINT` + `LOOM_HOOK_BRIDGE_SECRET` in each machine's hooks `.env` (`_observability.py:390-396`); run `flush_hooks_jsonl.py` backfill (idempotent uuid5 dedup, `services/telemetry-ingestion/README.md:43`); set `OBSERVER_JWT` on the self-observer cron | operator (agent runs the backfill + verifies counts) |
| 11 | 7-day monitoring window, then tag the-loom `services/telemetry-ingestion/` migrated/frozen (retirement checklist pattern, `02-agent-context-mcp.md:134-139`) | agent proposes; operator signs off |

No changes are needed to the engine callback distribution, the self-observer defaults, or any `.mcp.json` — that is the point of preserving the name.

## Decisions for Liz

Only the consequence-bearing choices; recommended option first.

1. **Service identity (irreversibility):** **Repoint `loom-telemetry-ingestion` in place (recommended)** — same name/URL/DB, rollback is one dashboard re-point; the alternative (new `tapestry-telemetry-ingestion`) forces retargeting ~10 baked references across three repos plus every machine's `.env`, including callback URLs already distributed to the engine.
2. **Data location:** **Telemetry tables land in the live `loom-postgres` (recommended)** — it is what 005/006 were written for and keeps one tenant envelope; the alternative (a separate telemetry Postgres) adds a second database to pay for and manage, and splits the observers' reads for no isolation gain (RLS already isolates).
3. **Money:** **`plan: free` (recommended, $0)** — follows the fleet rule that only the MCP needs guaranteed warm (`the-loom/render.yaml:320-331`); cold-start drops are recoverable via the idempotent `flush_hooks_jsonl` backfill. Alternative: `starter` ($7/mo) eliminates the cold-start loss window entirely — upgrade later if observed loss matters.
4. **Read-auth posture (security):** **Auth required on all `/telemetry/*` reads from day one, no anonymous path (recommended)** — there are no existing read clients to break, so the staged-rollout anonymous gate the memory service needed does not apply here. Alternative: mirror memory's anonymous-ON default, which leaves the telemetry store world-readable until a later flip.
5. **Secrets (security):** **Copy `LOOM_SKILL_BRIDGE_SECRET` byte-identical (no rotation) and mint a brand-new `LOOM_HOOK_BRIDGE_SECRET` (recommended)** — rotation of the skill secret would require a simultaneous Make_Skills engine change mid-cutover; the hook secret has no history, so it starts fresh. Alternative: rotate both now, at the cost of coordinating the engine side in the same window.
