# loom-memory evolution — systematic plan (2026-11-05)

**Status:** Planning only. **Nothing is built, migrated, or executed in this pass.** All
runtime work happens on a **different machine** in a later session; this document is the
decision-ready sequence it will follow.

**Spine (the operator's constraint, carried through every decision):**
*light / no-bloat / good-enough recall / cross-machine / non-frustrating.* Every option
below is judged against this first, capability second.

**Grounding (PROBE'd, not assumed):**
- Research synthesis that this plan sequences: loom-memory `new-memory-architecture-research-2026-11-05`
  (3-agent convergence: keep Postgres+pgvector+MCP; evolve it; don't swap framework or store).
- Live schema: [`infra/migrations/001_init_memory.sql`](../../infra/migrations/001_init_memory.sql)
  (`records` table, lines 69–97; `extra JSONB` forward-compat slot, line 84; HNSW index,
  lines 120–121; RLS policies, lines 150–183; **"never edit a migration after it lands"**, line 51).
- Live storage layer: [`services/agent-context/storage.py`](../../services/agent-context/storage.py)
  (fastembed bge-small, line 68; upsert `ON CONFLICT (id)`, line 217; `<=>` cosine search +
  `ORDER BY`, lines 285–290; `_set_tenant` RLS via `set_config`, lines 129–143; `list_records`
  newest-first, line 342).
- Migration discipline: [`infra/migrations/README.md`](../../infra/migrations/README.md)
  (manual via Render PSQL console, idempotent, numeric order) +
  [`infra/migrations/APPLIED.md`](../../infra/migrations/APPLIED.md) (one row per file×DB with
  evidence; unknown = NOT APPLIED, never guessed).
- Schema governance: [`docs/adr/0003-shared-postgres-schema-source-of-truth.md`](../adr/0003-shared-postgres-schema-source-of-truth.md)
  — **point 3 (line 21) already names "memory-schema enrichment" as the FIRST named post-parity
  redesign ADR.** WS-A below is the concrete delivery of that forcing-function.
- Cutover precedent (zero-downtime, URL-preserving): loom-memory
  `tapestry_step2_prod_cutover_complete_2026_06_21` + runbook
  [`docs/migration-cicd/runbooks/02-agent-context-mcp.md`](../migration-cicd/runbooks/02-agent-context-mcp.md);
  cutover/continuous-sync governance in [`docs/adr/0002-cutover-continuous-sync.md`](../adr/0002-cutover-continuous-sync.md).
- Render inventory: loom-memory `render_service_keep_kill_map_2026_09_06` — `loom-postgres`
  (PG16, pgvector, ~$6/mo, **sacred, don't downgrade**) + `loom-agent-context` (the MCP, Starter,
  must stay warm — CORE DIRECTIVE 1) + a **separate** Render cron (self-observer, 6h).
- Decomposition/migration doctrine the DB-move must respect: loom-memory
  `proves-decomposition-architecture-main-repo-plus-independent-modules-2026-09-26`,
  `proves-decomposition-failure-modes-and-constraints-2026-09-25`,
  `proves-decomposition-run-underway-capture-doc-2026-09-26`,
  `tapestry_agent_outside_review_response_to_unified_understanding_2026_06_18`
  (automation-level policy; ADR-0001 observer topology; ADR-0002 continuous-sync).
- Tenant state is clean: loom-memory `tenant_id_audit_clean_all_under_self_host_2026_06_19`.

**CORE DIRECTIVE 1 constraint on everything here:** the loom-memory MCP is load-bearing —
every session in every repo depends on it. Any change that touches runtime must be
zero-downtime and rollbackable, using the Step-2 re-source-preserving-URL pattern as the
precedent (`tapestry_step2_prod_cutover_complete_2026_06_21`).

---

## 1. Overview + dependency graph

Five workstreams. Only **WS-A** and **WS-E** are safe to start before any irreversible
decision; the rest gate on the Supabase go/no-go (WS-B), which is itself gated on a 2-minute
verification.

```
                 ┌─────────────────────────────────────────────┐
                 │ GATE 0 (2-min check, OTHER machine):         │
                 │ does Render loom-postgres expose pg_cron /   │
                 │ pg_net? (Render dashboard → DB → Extensions) │
                 └───────────────┬─────────────────────────────┘
                                 │ (almost certainly NO → structural reason the cron is separate)
                                 ▼
  WS-A  bi-temporal supersession ─────────────► (additive, runtime, PRE-decision, SAFE NOW)
    │        migration 008 + storage.py recall           │
    │        runs on CURRENT store; carries over as-is    │
    │        to Supabase if WS-B proceeds                 │
    │                                                     │
    ▼                                                     ▼
  WS-B  Supabase migration (DECISION-GATED) ◄── needs: decision log + operator go
    │        pg_dump → Supabase Pro; re-point MCP DATABASE_URL
    │        consolidates DB + cron + (keeps FastAPI external)
    │
    ├──────────────► WS-C  self-observer INTO the DB (gated on WS-B)
    │                      pg_cron + pgmq + pg_net + Edge Function
    │                      retires the separate Render cron
    │
    └──────────────► WS-D  `mem` CLI worker set (file-shaped window)
                           read-only first; store-agnostic, so NOT gated,
                           but cheaper to wire once endpoint is stable

  WS-E  retrieval quality (hybrid BM25+vector + rerank A/B) ──► (SAFE NOW, store-agnostic,
                           highest-leverage-per-byte; do BEFORE adopting any framework)
```

**Reading the graph:**
- **WS-A and WS-E need no decision** — both are additive and reversible, both run against the
  current `loom-postgres`, both carry over unchanged if the store later moves. Start here.
- **WS-B is the hinge.** It forces the real spend/auth decisions and unlocks WS-C. Its first
  step is **GATE 0**, a free 2-minute check that confirms the premise (Render managed Postgres
  almost certainly lacks `pg_cron`/`pg_net` — the structural reason the self-observer is a
  separate Render cron today).
- **WS-C depends on WS-B** (Supabase Cron = `pg_cron` *inside* the same Postgres; can't move the
  loop into the DB until the DB can run it).
- **WS-D depends on nothing structurally** (it wraps the existing `memory_*` MCP tools) but is
  listed after WS-B because it's cheapest to build once the MCP endpoint is settled.

---

## 2. The five workstreams

### WS-A — Bi-temporal typed supersession *(DO FIRST; additive, pre-decision, safe)*

**Goal.** Give `records` an explicit notion of "what's true *now*" so recall can prefer
currently-valid rows and treat superseded ones as history, not noise. This is the
highest-evidence upgrade in the research (`new-memory-architecture-research-2026-11-05` §1A:
typed state ~99% vs retrieval 6–43% on "what's true now"; supersession → ~0% stale) and it is
the concrete delivery of the **memory-schema enrichment** that ADR-0003 (line 21) already
committed to as the first post-parity redesign. Zero new infrastructure — columns + a WHERE
clause. The Zep insight **without** the graph DB.

**Two candidate shapes — evaluate both against the never-edit-landed-migrations + idempotent
rules ([`infra/migrations/README.md`](../../infra/migrations/README.md), and line 51 of 001):**

| | Option A — typed columns | Option B — `extra` JSONB keys |
|---|---|---|
| Shape | new `008_bitemporal.sql` adds `valid_from DOUBLE PRECISION`, `invalid_at DOUBLE PRECISION NULL`, `superseded_by VARCHAR(256) NULL` | store `{"valid_from":…, "invalid_at":…, "superseded_by":…}` in existing `extra` (line 84), no DDL |
| Indexable | yes — partial btree `WHERE invalid_at IS NULL` is cheap and clean | only via the existing `records_extra_gin` (line 134), weaker for range/null filters |
| Backward-compat | **yes** — add columns with defaults; every existing row defaults to valid (`invalid_at = NULL`, `valid_from = ts`) | yes — absent keys read as valid |
| Fits "never edit landed migration" | yes — brand-new file 008, 001 untouched | yes — no migration at all |
| Recall WHERE clause | `WHERE invalid_at IS NULL` (first-class) | `WHERE NOT (extra ? 'invalid_at')` (awkward, slower) |
| No-bloat verdict | **recommended** — one small additive migration, first-class and queryable | tempting (zero DDL) but pushes semantics into a JSON blob, harder to index/reason about |

> **Recommendation to carry into the ADR:** Option A (typed columns in `008_bitemporal.sql`).
> It stays additive and idempotent (so it satisfies the same rules that make 001 safe to re-run),
> it is first-class and index-friendly, and it reads cleanly in recall. Option B is the fallback
> if the operator wants *zero* schema change this cycle; record the trade in the decision log
> either way.

**Concrete steps (OTHER machine, later):**
1. Write `infra/migrations/008_bitemporal.sql` — additive, idempotent:
   `ALTER TABLE records ADD COLUMN IF NOT EXISTS valid_from DOUBLE PRECISION NOT NULL DEFAULT 0`,
   `ADD COLUMN IF NOT EXISTS invalid_at DOUBLE PRECISION` (nullable = "still valid"),
   `ADD COLUMN IF NOT EXISTS superseded_by VARCHAR(256)`; backfill `valid_from = ts` for
   existing rows; add partial index `CREATE INDEX IF NOT EXISTS records_valid_idx ON records (tenant_id) WHERE invalid_at IS NULL`.
   (Note: next number in the series IS 008 — the series skips 003, files run 000,001,002,004–007
   per [`APPLIED.md`](../../infra/migrations/APPLIED.md).)
2. `storage.py` change: in `search()` and `list_records()` add an opt-in `only_valid: bool = True`
   that appends `invalid_at IS NULL` to `where_parts` (mirrors the existing `visibility != 'deleted'`
   pattern at line 268 / 401). Supersession write: a small helper that, on upsert of a record that
   replaces another, sets the old row's `invalid_at = now()` and `superseded_by = <new id>` inside
   the same transaction as the existing `ON CONFLICT` path (line 217).
3. Apply 008 via Render PSQL console; **record the row in `APPLIED.md`** in the same change
   (file × live loom-postgres × date × evidence).

**Who/where it runs.** OTHER machine, later session. Migration applied manually to the **live
`loom-postgres`** (or to Supabase if WS-B has already happened — the migration is store-agnostic).
Code lands in `services/agent-context/` and deploys via the existing `loom-agent-context` Render
service.

**Risk.** This is **runtime** — it touches the load-bearing MCP (CORE DIRECTIVE 1). Risks: (a) a
recall default flip that hides valid records; (b) deploy of `storage.py` while sessions are live.

**Rollback.** (a) Schema: columns are additive and nullable — leaving them unused is a no-op; a
bad index drops with `DROP INDEX`. (b) Code: `only_valid` defaults can ship **off** first
(behavior identical to today), flipped on only after verification. (c) Service: the Step-2
re-source/redeploy rollback (`tapestry_step2_prod_cutover_complete_2026_06_21`) restores the prior
image byte-identical, DB untouched.

**Test plan.**
- Migration idempotency: run `008` twice on a scratch copy → second run is a no-op (same contract
  as 001, line 49–50).
- Backfill: after apply, `SELECT count(*) FROM records WHERE valid_from = 0` → 0 (all backfilled);
  `WHERE invalid_at IS NULL` → full row count (everything defaults valid).
- Supersession round-trip: write record X; write X' that supersedes X; assert X.invalid_at set +
  X.superseded_by = X'; assert `search(only_valid=True)` returns X' not X, and
  `search(only_valid=False)` returns both.
- Regression: existing `memory_recall` / `memory_search` across repos unchanged with `only_valid`
  off; CORE DIRECTIVE 1 smoke (the session's own `memory_*` calls keep working, per the Step-2
  verification pattern).

**Decisions it forces.**
- D-A1: typed columns (Option A) vs `extra` JSONB (Option B)?
- D-A2: does recall default to `only_valid=True` (prefer current truth) or stay opt-in at first?
- D-A3: is supersession **automatic** on name-collision upsert, or an **explicit** call? (research
  warns continuous auto-consolidation is contested; manual/offline is safer — ties to WS-C.)

---

### WS-B — Supabase migration *(decision-gated; ships WITH a running decision log)*

**Goal.** Move `loom-postgres` → **Supabase Pro** to get (1) the DB **visualization** the operator
is missing (Studio Table Editor / SQL / vecs), and (2) **`pg_cron` + `pg_net` inside the same
Postgres**, which is the prerequisite for WS-C. This **consolidates** today's three Render things
(DB + separate cron + FastAPI) toward one project — only the FastAPI MCP host stays external, via
one `DATABASE_URL` change (`new-memory-architecture-research-2026-11-05` §2). The operator
explicitly wants a **decision log**; this workstream produces it alongside the migration.

**GATE 0 (gating step, free, 2 min, OTHER machine).** Confirm the premise before spending:
in the Render dashboard, open `loom-postgres` → Extensions and check for `pg_cron` / `pg_net`.
Expected: **absent** (managed Render Postgres needs `shared_preload_libraries` it doesn't expose —
the structural reason the self-observer is a separate cron today). If, surprisingly, they ARE
available, WS-C could be done in place and WS-B's urgency drops to "visualization only" — record
that fork in the decision log.

**Concrete steps (OTHER machine, later; each produces a decision-log entry):**
1. **Provision** a Supabase project, Pro plan (~$25/mo; free tier pauses after ~7d + 500MB — unfit
   for a cron-driven always-on memory). Enable `vector`, `pg_cron`, `pg_net`, `pgmq`.
2. **Schema**: apply the canonical tapestry series (`000`→`008`) to Supabase via its SQL editor.
   pgvector columns + HNSW (001, lines 73/120–121) carry over as-is. Decide RLS posture (step 4).
3. **Data move**: `pg_dump loom-postgres` → restore into Supabase. pgvector data transfers as
   native `vector` values; verify row counts match (209+ at last count, `APPLIED.md` line 19) and a
   sample `<=>` query returns the same neighbours.
4. **Auth decision (RLS vs app-auth)**: today RLS enforces tenant scope via `set_config('app.tenant_id')`
   (storage.py lines 129–143, policies 001 lines 150–183). Recommended: connect the MCP as the
   Supabase **service role** and keep the existing JWT/self-host tenant auth at the **MCP layer**
   (the `app.tenant_id` contextvar already does this) — RLS stays as defense-in-depth. Decide
   deliberately; do not let Supabase's default `anon`/`authenticated` roles silently replace the
   current model.
5. **Connection**: re-point MCP `LOOM_DB_URL`/`DATABASE_URL` to Supabase using the **session pooler
   (port 5432)** — NOT the transaction pooler (6543) — because `storage.py` holds a long-lived
   async pool (`get_pool`, lines 89–113). This is the one-line consumer-facing change; the
   `loom-agent-context.onrender.com` URL every `.mcp.json` points at **does not change**
   (same invariant as the Step-2 cutover).
6. **Cutover**: follow the Step-2 pattern (`tapestry_step2_prod_cutover_complete_2026_06_21` +
   runbook 02): short freeze on writes, point DATABASE_URL, verify `/health`, a known-record read,
   a recall, and a write round-trip against the live URL before declaring green. Keep old
   `loom-postgres` intact and un-deleted through a monitoring window (24h/7d) as the rollback.

**Who/where it runs.** OTHER machine. New infra = Supabase project (hosted). The MCP stays on
Render (`loom-agent-context`). `loom-postgres` is **kept, not deleted**, until the monitoring
window closes.

**Risk.** Highest-stakes workstream — it moves the load-bearing store. Risks: data-fidelity on
pgvector dump/restore; pooler choice breaking the long-lived async pool; auth model regression
(RLS misconfig exposing/ hiding rows); ongoing cost; a second always-paid vendor.

**Rollback.** `loom-postgres` is untouched during the window → re-point `DATABASE_URL` back to it
and redeploy = instant, lossless (same shape as the Step-2 rollback). Decision log records the
exact prior connection string so the revert is mechanical.

**Decisions it forces (these ARE the decision-log seed — see §3).**
- D-B1: Supabase Pro ~$25/mo approved? (raises steady spend from ~$6 DB to ~$25; offsets by
  retiring the separate Render cron in WS-C and is a candidate to retire the ~$14/mo staging pair
  per `render_service_keep_kill_map_2026_09_06`.)
- D-B2: RLS-as-enforcement vs app-layer-auth-with-RLS-as-defense-in-depth? (recommended: the latter.)
- D-B3: build-new vs evolve-in-place? (research verdict: **evolve in place** — same store, same
  MCP; Supabase is a host swap, not a rewrite.)
- D-B4: keep `loom-postgres` as warm standby for how long after green?
- D-B5: does this move require/trigger a new ADR under ADR-0002 (cutover) and ADR-0003 (schema
  source-of-truth)? (Yes — see §3; the physical store moving while the schema-of-record stays in
  `infra/migrations/` is exactly the ADR-0003 line-17 situation.)

---

### WS-C — Self-observer INTO the DB *(the "recursive AI in the DB"; gated on WS-B)*

**Goal.** Move the 6h self-observer loop from a **separate Render cron**
(`render_service_keep_kill_map_2026_09_06`: "tapestry" cron) **into the database** as
`pg_cron` + `pgmq` (queue) + `pg_net` (HTTP from SQL) + a Supabase **Edge Function** that does
offline **dedup / consolidate / supersede / promote**. This is the Supabase "automatic-embeddings"
pattern (trigger → pgmq → pg_cron → pg_net → Edge Function) pointed at memory maintenance — which
IS the self-observer's job (`new-memory-architecture-research-2026-11-05` §2: *"it doesn't move the
cron away from the DB — it moves the cron INTO the DB"*). It also closes the loop with WS-A:
the offline pass is what **sets `invalid_at` / `superseded_by`** on stale rows.

**Memory-SOTA caveat (bind this into the design).** Offline consolidation on a schedule is
**OK and medium-strong evidence**; **continuous LLM consolidation in the hot path is CONTESTED and
can harm** (`new-memory-architecture-research-2026-11-05` §1B). So: the loop stays **offline/batched**
(the cron cadence), never on the read/write hot path. No in-DB model inference (PostgresML/pgai/pgml
are off the table — resource contention, not on managed hosts, and pgai itself retreated to an
external worker in 2025); the LLM/embedding call is an Edge Function over `pg_net`, not in-process.

**Concrete steps (OTHER machine, later; all AFTER WS-B green):**
1. Port the existing self-observer logic (currently the Render cron) into a Supabase Edge Function:
   input = a batch of candidate rows; output = dedup/supersede/promote decisions written back via
   the service role.
2. `pg_cron` job on the Supabase Postgres (run history visible in `cron.job_run_details`) enqueues a
   maintenance batch to `pgmq`; a second scheduled step drains the queue and calls the Edge Function
   over `pg_net`.
3. The Edge Function writes supersession using the WS-A columns (`invalid_at`, `superseded_by`) —
   WS-A is therefore a **hard prerequisite** for the "supersede" verb.
4. **Retire the separate Render cron** once the in-DB loop runs clean for a window — removes one
   Render service (cost + one less thing to keep warm).

**Who/where it runs.** OTHER machine for setup. Steady-state: runs **inside Supabase** (cron +
queue + edge). No Render cron.

**Risk.** A self-modifying loop that writes back to the canonical store. Risks: a bad consolidation
pass corrupting/over-superseding good memories; runaway cron; Edge Function cost; the contested-ness
of automated consolidation itself.

**Rollback.** `pg_cron` jobs are `cron.unschedule(...)` — instant stop, loop halts, store frozen at
last state. Because consolidation only ever *sets* `invalid_at` (soft, WS-A) and never hard-deletes,
a bad pass is **reversible** by clearing `invalid_at`/`superseded_by` on the affected rows. Keep the
old Render cron **suspended, not deleted**, until the in-DB loop is trusted.

**Decisions it forces.**
- D-C1: cadence — keep 6h, or slower (consolidation is not urgent)?
- D-C2: which verbs are auto vs proposal-only? (ties to the automation-level policy in
  `tapestry_agent_outside_review_response_...`: dedup/supersede ≈ level 1–2 auto; "promote" to
  public/cross-project ≈ level 5–7, approval-gated.) Recommended: dedup/supersede auto, promote
  stays a human/queue step.
- D-C3: Edge Function model/provider for the consolidation LLM call (cost + which model).

---

### WS-D — Linux `mem` CLI worker set *(file-shaped window; incremental, store-agnostic)*

**Goal.** Add the Linux "file-feel" the operator wants as a **thin read-only CLI over the existing
`memory_*` MCP tools**, so hosted memory becomes `cat`-able / `grep`-able per machine **without**
re-platforming the canonical store to markdown (which would re-introduce the cross-machine
merge-conflict problem the hosted store exists to avoid — `new-memory-architecture-research-2026-11-05`
§3, "Rung 0"). Delivered as a **series of small worker tasks**, not a big build.

**Worker set (each a small, independently shippable deliverable):**
- **W-D1 (do first, ~50 lines):** `mem.sh` + `mem.ps1` — read-only wrappers:
  `mem ls` → `memory_list`, `mem cat <name>` → `memory_read`, `mem recall "<q>"` → `memory_recall`,
  `mem search "<q>"` → `memory_search`. Dual-shell per the repo's existing `.sh`/`.ps1` convention.
- **W-D2 (optional):** `mem grep "<pat>"` — client-side filter over `memory_list` output (you can't
  grep a 384-dim embedding, so this is lexical over returned content — honest about the limit).
- **W-D3 (optional, later):** richer file-facade (e.g. `mem edit` → write path, a read-through
  cache of records as local files). Explicitly **not** source-of-truth; a *window*, not a *mirror*.

**Non-goals (recorded so they don't creep):** no FUSE/9P DB-as-filesystem (right philosophy, wrong
cost for n=1 on Windows); no markdown-as-source-of-truth for the canonical store; WSL2 is want-not-need.

**Who/where it runs.** OTHER machine (and every machine the operator uses — that's the point). Pure
client of the MCP; **store-agnostic**, so it works against `loom-postgres` today or Supabase later —
not gated on WS-B.

**Risk.** Low. Worst case a read-only CLI returns stale/confusing output. W-D3's write path carries
the usual write risk and should reuse the server-side validation, not re-implement it.

**Rollback.** Delete the scripts — nothing server-side changes. (W-D3 writes go through the same MCP
write path, which already soft-deletes, so they're recoverable.)

**Decisions it forces.**
- D-D1: ship W-D1 read-only only, or commit to W-D3 write-facade now? (Recommended: W-D1 only this
  pass; W-D3 is a "promote at 3rd instance" candidate.)
- D-D2: where do the scripts live — `integrations/claude-code/`, a new `tools/mem/`, or the
  discipline plugin?

---

### WS-E — Retrieval quality *(cheap, highest-leverage; safe now, store-agnostic)*

**Goal.** Act on the research's headline finding — **"retrieval beats architecture"**: effort on
retrieval moved accuracy ~20pts, write/consolidation cleverness only 3–8
(`new-memory-architecture-research-2026-11-05` §1). So improve retrieval **before** adopting any
memory framework (Mem0/Letta/Zep all lose this cost-benefit test for n=1). Specifically: **hybrid
BM25 + vector + a rerank**, run as an **A/B against today's pure-vector `<=>` search**, adopt only
if it wins.

**Concrete steps (OTHER machine, later; no decision gate):**
1. Add a lexical signal: Postgres full-text (`tsvector`/`ts_rank`) or `pg_trgm` over `content` —
   both are in-DB, no new service, fits no-bloat. (Supabase or Render both support these; store-agnostic.)
2. Hybrid score: combine the existing cosine distance (`<=>`, storage.py lines 285–290) with the
   lexical rank (e.g. reciprocal-rank fusion). Optionally a small cross-encoder rerank on the top-N
   **only** (bge-reranker is the natural pair to the bge-small embedder already in use, line 46).
3. **A/B harness**: a fixed set of real recall queries scored pure-vector vs hybrid vs hybrid+rerank;
   adopt the cheapest variant that clears a chosen quality bar. Keep pure-vector as the fallback.

**Who/where it runs.** OTHER machine. Lands in `services/agent-context/storage.py`
(`search()`). Store-agnostic; works pre- or post-WS-B.

**Risk.** Low–medium. Hybrid can regress on some query shapes; rerank adds latency on the read path
(keep it top-N only). All reversible — it's a scoring change behind the same API.

**Rollback.** Feature-flag the hybrid path; default off until the A/B says it wins. Revert = flip
the flag. The pure-vector path (line 285) is never removed.

**Decisions it forces.**
- D-E1: what's the quality bar + eval set that decides "adopt"? (needs a small labelled recall set.)
- D-E2: rerank yes/no — is the extra read-path latency worth it for n=1?
- D-E3: if hybrid clearly wins, does that **close** the question of adopting Mem0/Letta/etc.?
  (Recommended framing: yes — retrieval win first, framework only if retrieval plateaus.)

---

## 3. Decision-log / ADR index skeleton

Two artifacts, both already house-conventional in this repo:

**(a) Running decision log** — new file `docs/decisions/loom-memory-evolution-log.md` (or a section
appended to this plan). One append-only entry per choice, in the ADR shape from
[`docs/adr/README.md`](../adr/README.md) lines 14–38 but lighter-weight (context / decision /
consequences / date / evidence). The operator asked specifically for this; it captures the *small*
decisions that don't each merit a full ADR (pooler port, backfill approach, cadence) so they're not
lost. Entry template:

```markdown
### DL-NNN — <one-line decision>   (YYYY-MM-DD)
- Context: <what forced it, file:line / memory key>
- Decision: <what was chosen>
- Consequences: <easier / harder / locked-in>
- Evidence: <commit / APPLIED.md row / verification output>
```

**(b) Formal ADRs** — for the load-bearing, multi-service decisions (ADR-0006+; existing series is
0001–0005, [`docs/adr/`](../adr/)). Proposed slots:

| ADR | Title | Covers | Depends on |
|---|---|---|---|
| **0006** | memory-schema enrichment: bi-temporal supersession | WS-A; the forcing-function ADR-0003 line 21 already named | — |
| **0007** | loom-memory store move to Supabase | WS-B; extends ADR-0002 (cutover) + ADR-0003 (schema-of-record stays in `infra/migrations/` even though bytes move) | 0006 landed or parallel |
| **0008** | self-observer loop into the DB (pg_cron/pgmq/pg_net/Edge) | WS-C; ties to the automation-level policy in `tapestry_agent_outside_review_response_...` | 0007 |
| *(no ADR)* | WS-D `mem` CLI | dev-tooling, not runtime/schema — decision-log entries only | — |
| *(maybe 0009)* | retrieval scoring: hybrid+rerank adopt | WS-E, **only if** adopted — the A/B result is the ADR's evidence | — |

**Decision-log seed (open items pulled from the five workstreams):**
DL-candidates = D-A1, D-A2, D-A3, D-B1…D-B5, D-C1…D-C3, D-D1, D-D2, D-E1…D-E3 (see each
workstream). GATE 0's result is DL-001.

---

## 4. Sequencing recommendation

**Safe to start now (no irreversible decision, no spend, reversible):**
1. **GATE 0** — the free 2-min Render extension check. (Confirms the WS-B/WS-C premise.)
2. **WS-A** — `008_bitemporal.sql` + `only_valid` recall, shipped with defaults **off** first.
   Additive, highest-evidence, and it's the ADR-0003 forcing-function already owed.
3. **WS-E** — retrieval A/B harness. Store-agnostic, highest-leverage-per-byte, and it settles the
   "do we need a framework?" question cheaply before any of that is considered.
4. **WS-D / W-D1** — the ~50-line read-only `mem` CLI. Store-agnostic, low-risk, delivers the
   Linux feel immediately.

**Decision-gated (needs operator go + the decision log):**
5. **WS-B** — Supabase move. Gate on D-B1 (spend) + D-B2 (auth) + GATE 0's result. This is the hinge.
6. **WS-C** — self-observer into the DB. Hard-gated on WS-B green **and** WS-A columns existing.

**Why this order fits the spine:** the three safe-now items (A, E, D-W1) each improve the system
*without* a vendor decision, a bill, or a risky store move — "good-enough, light, non-frustrating"
first. The store move (B) and the recursive loop (C) are the bigger, decision-laden steps and are
deliberately held behind an explicit log so they're chosen, not slid into.

---

## 5. Open decisions for the operator

Grouped; the **bold** ones unblock the most.

1. **D-B1 — Supabase Pro ~$25/mo: yes/no?** Unblocks WS-B and WS-C. (Offset: retires the separate
   Render cron in WS-C; candidate to retire the ~$14/mo staging pair per
   `render_service_keep_kill_map_2026_09_06`.)
2. **D-B2 — Auth model on Supabase:** service-role connect + keep app-layer tenant auth, RLS as
   defense-in-depth (recommended) — confirm?
3. **D-B3 — Evolve-in-place vs build-new:** research says evolve. Confirm so no one reaches for a
   rewrite.
4. **D-A1 — Supersession shape:** typed columns in `008` (recommended) vs `extra` JSONB.
5. **D-A2 — Recall default:** prefer currently-valid (`only_valid=True`) once verified, or stay opt-in?
6. **D-C2 — Automation levels:** dedup/supersede auto, promote approval-gated (recommended) — confirm
   against the automation-level policy.
7. **D-E1/E3 — Retrieval bar + framework question:** agree that a retrieval A/B is the gate that
   decides whether any memory framework is ever adopted?
8. **GATE 0 — run the 2-min Render extension check** (confirms the whole WS-B/WS-C premise; costs
   nothing).
9. **D-D2 / D-B4 / D-C1** — placement of `mem` scripts; how long to keep `loom-postgres` warm;
   consolidation cadence. (Lower-stakes; decision-log entries.)

---

## 6. Cross-machine handoff + record policy

The work happens on a **different machine** and the operator wants to avoid GitHub as the required
channel. Three carriers, by artifact type:

**A. This plan's text (and the decisions it generates) → loom-memory.** The plan and every decision
entry are written as loom-memory records (they already travel machine-to-machine with zero sync
effort — that's the whole reason the hosted store exists, `new-memory-architecture-research-2026-11-05`
§3). The OTHER machine reads them via `memory_recall` / the `mem` CLI at session start. **No GitHub
needed for the thinking.** Suggested record on completion of this plan:
`loom_memory_evolution_plan_2026_11_05` (type `reference`, this file's path + the §4 sequencing + §5
open decisions).

**B. The files themselves (migrations, scripts, code) → Syncthing / Tailscale / shared drive, or
Git when convenient.** Code *can* go through GitHub when the operator wants, but it isn't required to
move between the operator's own machines: a **Syncthing** folder or **Tailscale**-reachable path
carries `infra/migrations/008_bitemporal.sql`, `mem.sh/.ps1`, and the `storage.py` diff directly.
Git remains the eventual system-of-record for anything that lands in `tapestry` — but handoff ≠ merge.

**C. Once Supabase exists (post-WS-B), the DB itself is a carrier.** Supabase Studio is reachable
from any machine (browser), so the memory store — and after WS-C the consolidation loop's run history
(`cron.job_run_details`) — is inspectable cross-machine with no file sync at all. This is a *bonus*
reason WS-B helps the cross-machine spine, beyond visualization.

**Record policy — what may NOT want to be recorded, and where it goes instead:**

| Artifact | Goes to | Why |
|---|---|---|
| Plan text, open decisions, ADR drafts | **loom-memory (private)** + `docs/` in Git | durable, cross-machine, meant to persist |
| Supabase connection string / service-role key / `DATABASE_URL` | **`.gitignored` secret file / env only** — never Git, never a memory record | credential; follows the existing token-hygiene stance (`tapestry_agent_outside_review_response_...` Fix 3 — rotate, don't commit) |
| `pg_dump` output / data snapshots | **scratchpad or local secure dir**, deleted after restore | contains all memory content; not a repo artifact |
| Throwaway verification output, scratch SQL | **scratchpad** (`.../scratchpad/`), not committed | noise; not system-of-record |
| A memory record that turns out wrong/sensitive | **private + `visibility='deleted'`** (soft-delete via the MCP) | the store already soft-deletes (storage.py line 401); keeps it recoverable but out of recall |

**Rule of thumb:** *thinking* → loom-memory (private); *code/schema* → Git + a sync channel for
handoff; *secrets and raw data dumps* → gitignore / env / scratchpad, never a record and never
committed.

---

## 7. What this pass did NOT do (explicit)

No code was written, no migration applied, no service touched, no Supabase project created, nothing
deployed. This is a sequence and a set of decisions for a later session on another machine. The next
action is the **free** one: run **GATE 0** and bring D-B1/D-A1 to the operator.

## 8. Component functionality verdict (addendum — pgvectorscale / pgml / pgai / LanceDB)

From the parallel functionality deep-dive (operator asked to actually know what each piece does, not take a dismissal on faith). The memory pipeline is three jobs — **embed → store → find-fast** (fastembed-in-Python / Postgres / pgvector-HNSW today). Each tool changes one job:

| Piece | Changes | Verdict for this system |
|---|---|---|
| **pgvectorscale** | find-fast (DiskANN + compression) | **Parked.** Benefit only at ~5–10M+ vectors (you're 2–4 orders below); and it **cannot run on Render or Supabase** (needs `shared_preload_libraries`; Tiger/Timescale-Cloud only). Revisit-if: a tenant's vectors approach ~1M **and** HNSW recall/latency degrades. |
| **pgml / PostgresML** | embed+infer+train, inside the DB | **Parked (structural).** Impossible on managed Postgres; solves a round-trip you already removed by running fastembed in the Python service (`storage.py:68`). In-DB inference is bloat for one user. |
| **pgai** | — | **Nothing to adopt.** After its 2025 pivot it's an external Python embedding worker ≈ what `storage.py` already is. Cite as prior-art that your shape is current, nothing more. |
| **LanceDB** | your former local store | Left for a correct reason: it's **embedded/local**, you needed a **shared cross-machine cloud store**. The port to pgvector was right. |

**The one real connection to WS-A:** the single capability you genuinely *lost* leaving LanceDB is **automatic dataset versioning / time-travel** ("what did memory look like last Tuesday"). **WS-A's bi-temporal supersession (`valid_from` / `invalid_at`) partially re-adds exactly that** at the row level — so WS-A is not only the highest-evidence recall upgrade, it also recovers a slice of the LanceDB time-travel the port gave up. Full breakdown + sources: loom-memory `new-memory-architecture-research-2026-11-05` + the functionality agent's report (this session).

## Related

- loom-memory: `new-memory-architecture-research-2026-11-05` (the synthesis this sequences),
  `render_service_keep_kill_map_2026_09_06`, `tapestry_step2_prod_cutover_complete_2026_06_21`,
  `tapestry_agent_outside_review_response_to_unified_understanding_2026_06_18`,
  `tenant_id_audit_clean_all_under_self_host_2026_06_19`, the three `proves-decomposition-*` records.
- Code: [`infra/migrations/001_init_memory.sql`](../../infra/migrations/001_init_memory.sql),
  [`services/agent-context/storage.py`](../../services/agent-context/storage.py),
  [`infra/migrations/README.md`](../../infra/migrations/README.md),
  [`infra/migrations/APPLIED.md`](../../infra/migrations/APPLIED.md).
- Governance: [`docs/adr/0002-cutover-continuous-sync.md`](../adr/0002-cutover-continuous-sync.md),
  [`docs/adr/0003-shared-postgres-schema-source-of-truth.md`](../adr/0003-shared-postgres-schema-source-of-truth.md)
  (line 21 forcing-function), [`docs/adr/README.md`](../adr/README.md),
  [`docs/migration-cicd/runbooks/02-agent-context-mcp.md`](../migration-cicd/runbooks/02-agent-context-mcp.md),
  [`docs/migration/README.md`](../migration/README.md).
