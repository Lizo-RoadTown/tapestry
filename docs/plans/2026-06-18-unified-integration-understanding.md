# Tapestry unified-integration understanding

**Date:** 2026-06-18
**Author:** Tapestry-agent (Opus 4.8)
**Status:** Reviewed (adversarial evaluator pass applied 2026-06-18: 4 should-fix corrections folded in — A3 label, docs-agent already-consolidated, timeline caveat, C4 double-mis-cite) — pending outside-reviewer + operator (Liz) ratification
**Purpose:** The single consolidated answer to "what is the unified task, and how do we accomplish it without drift." Produced from a 4-researcher + 1-reconciler fan-out + drift-watcher oversight (see loom-memory `tapestry_agent_systematic_planning_kickoff_2026_06_18`).

## How this doc relates to the existing corpus

This **extends**, it does not replace. It builds on and points back to:

- [`2026-06-13-v1-scope-and-roadmap.md`](../proposals/2026-06-13-v1-scope-and-roadmap.md) — v1 SKU/auth/billing/topology (settled)
- [`2026-06-18-tapestry-migration-readiness-and-execution.md`](2026-06-18-tapestry-migration-readiness-and-execution.md) — the-loom + Make_Skills migration sequence (Steps 1–8), readiness YELLOW
- [`migration-cicd/`](../migration-cicd/) — the binding runbook/toolkit/testing doctrine (8 contract assertions)
- [`migration/legacy-repo-inventory.md`](../migration/legacy-repo-inventory.md) + `what-to-keep.md` / `what-to-retire.md` — the per-repo audit this doc's §2 extends
- [`UMBRELLA.md`](../architecture/UMBRELLA.md) + [`MANIFESTO.md`](../../MANIFESTO.md) — the architecture (NOTE: §5 below flags UMBRELLA as the stalest binding doc; it needs a correction pass)

**This phase produces NO code and NO migration PRs.** It is understand-and-decide only. Binding throughout: Tapestry is canonical; parallel-build (no pausing/migrating source without operator approval per CORE DIRECTIVE 2); PROBE + cite; one pattern/name/home; no marketing voice.

---

## §1. The task in one paragraph

Tapestry is the canonical product-system monorepo for a single-operator "project-intelligence" platform whose differentiator is one loop — **agency becomes structure** (observe → surface candidate → policy-decide → compile → use → measure → observe again). It is **built in parallel** with two live legacy-source prototypes (`the-loom` = services + dashboard + discipline plugin; `Make_Skills` = engine + compiler + adapters), which keep being built and migrate piece-by-piece only when each piece stabilizes and the operator approves it. The concrete near-term task is the v1 migration: ship **PR-prep-2** (externalize ~10–14 hardcoded `loom-*.onrender.com` URLs — the single blocker), then execute Steps 1–8 against the migration-cicd doctrine, yielding a v1 product in ~6–8 weeks (a *capacity estimate, not a deadline* — parallel-build pace per the binding memo; readiness plan §1.5). All runtime-observation / observation-decomposer / auto-promotion architecture defers to Tapestry. The destination owner is **Tapestry-agent (spawned 2026-06-18)**. The unified task additionally — and this is what no prior doc covered — must (a) disposition the **broader fleet** beyond the-loom + Make_Skills, (b) keep the **live crons/services/plugins/agents** current and coherent across the multi-week parallel-build, and (c) run a **multi-party operating model** (Tapestry-agent + loom-agent + ms-agent + self-observer + outside reviewer + operator + drift-watcher) that catches drift early.

---

## §2. Ecosystem disposition (extends `legacy-repo-inventory.md`)

Every "once part of the project" repo beyond the already-planned the-loom + Make_Skills. **Disposition is a plan, not an action.** Confidence + the operator question are carried so nothing is silently committed.

| Repo | Nature (PROBE-cited) | Disposition | Destination / mechanism | Conf. | Operator question |
|---|---|---|---|---|---|
| **docs-agent** | Loom-aware doc-specialist repo; its 16 skills + 7 agents were **already consolidated** into the `liz-patterns` plugin (commit `afc2f16`); `skills/`+`agents/` dirs now empty (`docs-agent/CLAUDE.md:37,43`). **Absent from every migration doc.** | ATTACH + (future) adapter | Skills/agents already in the plugin (Pillar 1 done); the only open piece is the empty agent persona Liz will author | med | Does the docs-agent persona become a Tapestry adapter, or stay a standalone published agent? |
| **loom-platform** | Consumer prototype seed (CLAUDE.md fleet table; absorption "deferred") | DECISION DEFERRED → likely ATTACH or RETIRE | TBD — operator scopes | low | Still "deferred" — does it integrate, attach, or retire? |
| **claude-skills-marketplace** | Public plugin marketplace; hosts `liz-patterns`, `loom-discipline` (via lizo-loom), `onboarding-psychologist`, `ai-agents-architect` | ATTACH (distribution surface) | Stays the publish target; Tapestry CI publishes INTO it (discipline plugin Step 8) | high | — |
| **classroom-hub-starter** | Classroom hub seed; Next.js + `.mcp.json` + embedded assistant | TEMPLATE-SOURCE | `templates/classroom-project/` | high | Hub-starter vs Make_Skills classroom default-seed — which is canonical? |
| **web-starter** | Next.js + Auth.js + Postgres template, loom-wired | TEMPLATE-SOURCE → then RETIRE | `templates/software-project/` + `packages/cli/init` | high | — |
| **ux-starter** | Framework-agnostic app template, loom-wired. **No slot in UMBRELLA template table.** | TEMPLATE-SOURCE → then RETIRE | Fold into `software-project` OR new `templates/app-project/` | med | Does ux-starter need its own template kind, or fold into software-project? |
| **project-starter** | Multi-variant day-1 scaffolding | TEMPLATE-SOURCE → then RETIRE | Placeholder conventions → `templates/*` + `packages/cli` | high | — |
| **claude-project-starter** | Byte-identical project-starter README clone | RETIRE/ARCHIVE (duplicate) | — | med | Abandoned fork of project-starter? Safe to archive? |
| **web-project-starter** | project-starter clone | RETIRE/ARCHIVE (duplicate) | — | med | Stale duplicate? |
| **paper-explainer** | Unconfigured starter clone; remote = `Lizo-RoadTown/project-starter` | RETIRE/ARCHIVE or OUT-OF-SCOPE | — | med | Abandoned scaffold or not-yet-started project? |
| **Summer 2026 Hub** | Live classroom consumer (IME 4020W); reference build for classroom-hub-starter | ATTACH (consumer) + patterns→template | Stays project-specific; patterns → `templates/classroom-project/` | high | — |
| **SDE_Extraction** | Research consumer, 16 bundled skills | ATTACH (consumer) + patterns→template | Patterns → `templates/research-project/` | high | — |
| **humancensys-app** | Next.js + Auth.js consumer at humancensys.com; `AGENTS.md` | ATTACH (consumer) + TEMPLATE-SOURCE | Wires to Tapestry `services/` via `packages/sdk`; Auth.js patterns → `apps/` + software template | med | Reference `apps/` consumer, or fully-external customer integration? |
| **humancensys** | Jekyll marketing site for the LLC | ATTACH (marketing) or OUT-OF-SCOPE | At most links to `apps/docs-site/` | med | Is the company marketing site in-scope at all? |
| **Pretend-Agents** | Vendored `langchain-ai/deepagents` checkout (remote confirms) | ATTACH (eval dependency) or OUT-OF-SCOPE | If `eval-deep-research` / `deep-research` depend on `deep_research_bench`: vendor reference; else out-of-scope | low | Is deepagents a real eval/runtime dependency or an idle clone? |
| curation-dev, proves-*, Knowrg, Lizo-RoadTown(.github.io), and NASA/PROVES/AMP/physics/coursework dirs | Unrelated (no loom/skill refs) | OUT-OF-SCOPE | — | high | — |

*(Confidence = researcher inference from the cited file(s); every disposition is operator-to-confirm, not decided here.)*

**Three findings the existing fleet table misses:** (1) **docs-agent** is absent from all migration docs though its skills/agents were already folded into the `liz-patterns` plugin (commit `afc2f16`) — its repo disposition and empty agent persona are still unaddressed; (2) **three near-duplicate starter clones** (`claude-project-starter`, `web-project-starter`, `paper-explainer`) are archival candidates, not separate sources; (3) **ux-starter has no destination slot** in the template taxonomy.

---

## §3. Live runtime + agent integration map

What is deployed/running, and how each stays coherent during the parallel-build. **PROBE correction up front:** several items the readiness plan listed as "in flight" have **landed** — the dispatch auto-trigger (A3, commit `63cf1ea`) is live (`the-loom/services/architecture-registry/main.py:234-235`), the self-observer synthesis memo is live (`synthesis.py` + `memory_client.py`, `main.py:187-199` writes `self_observer_synthesis_latest`), and cold-start is reconciled (`render.yaml:80` `plan: starter`, keep-warm cron retired). Also: **there are TWO observers** — the server-side `self-observer` cron (repo scanner) and a client-side `observer.py` inside the loom-discipline plugin (per-session transcript scanner).

| Live piece | Disposition | "Keep up to date" requires during build |
|---|---|---|
| **loom-agent-context** (memory MCP + JWT issuer) | KEEP-UPDATED → MIGRATE (Step 2, critical path) | The one piece whose drift breaks **every session everywhere**. Keep on `starter` (no cold start); keep URL stable; memory-schema changes additive-only until Tapestry redoes schema |
| **loom-architecture-registry** (40 candidates) | KEEP-UPDATED → MIGRATE (Step 7) | Don't change the 9-kind enum; keep A3 dispatch firing; URL env-overridable for cutover |
| **loom-telemetry-ingestion** | KEEP-UPDATED → MIGRATE (Step 7a); Tapestry must ADD Postgres rollup + read API | Keep ingest alive; do NOT invest in a query API loom-side (net-new Tapestry work) |
| **loom-project-registry** | KEEP-UPDATED → MIGRATE (Step 3) | Keep project_id UUIDs stable — hardcoded in self-observer config |
| **loom-self-observer** (cron, every 6h) | KEEP-UPDATED → MIGRATE → `tapestry/services/…` (see C4 below) | Keep scan-target list current as repos move; keep synthesis-memo write working (agents' SessionStart visibility). Runtime-observer expansion is Tapestry, not here |
| **make-skills-api** | KEEP-UPDATED → MIGRATE (Step 4) | Keep `LOOM_SKILL_BRIDGE_SECRET` synced both sides; keep `tenant_id_mapping` rows intact across any DB move |
| **loom-policy** (deployed, inert) | KEEP-UPDATED → MIGRATE (Step 7); build daemon variant in Tapestry | No active upkeep; don't build the policy daemon loom-side |
| **loom-project-observatory** (23-line stub) | MIGRATE as Phase-6 shell; build runtime-observer in Tapestry | Empty shell; nothing to keep current |
| **loom-mcp-memory-server** (orphan stub, 0 callers) | RETIRE | Delete from render.yaml (housekeeping A2) |
| **loom-keep-warm** cron | RETIRE (done) | Ensure it isn't re-created |
| **loom-memory MCP endpoint** | ATTACH now / migrates WITH agent-context | URL is the contract (CORE DIRECTIVE 1); stable until Step 2 env-swap |
| **loom-discipline** plugin (@lizo-loom v0.1.13) + in-plugin `observer.py` | KEEP-UPDATED → MIGRATE (Step 8, last) → `integrations/claude-code/` | Keep installed per-machine; keep registry/memory URLs env-overridable |
| **liz-patterns** plugin (@lizo-skills) | ATTACH (stays in marketplace) | Canonical home for reusable agents/skills; future compiled-skill output lands here. Not a migration target |
| **Tapestry-agent** | PERMANENT (already in scope) | Stays informed via memory recall + synthesis memo |
| **loom-agent / ms-agent** | ATTACH (transitional); retire when repos archive | Own PR-prep-2 (loom URLs) and engine-URL work respectively |
| **agentic-upskilling** | = the self-observer cron (doc pointer in liz-patterns) | Doc pointer must follow the cron to its Tapestry home post-migration |
| **drift-watcher / architecture-analyst** | ATTACH (live in plugins) | Pattern-only; no infra upkeep |
| **security-review-agent** | NOT FOUND as a deployed artifact | Likely the future Tapestry risk-classifier role; operator to confirm |

### What breaks/goes stale if NOT kept current (the operator's core worry), by blast radius

1. **loom-agent-context / loom-memory MCP** — drift breaks every session (CORE DIRECTIVE 1). On `starter` now; risk is a future deploy reverting to free.
2. **`tenant_id_mapping` rows** — if the engine DB is moved/reset, every tenant → `source_tenant_id=None` and **all telemetry silently turns off, no error**. Quietest high-impact risk.
3. **PR-prep-2 URLs (NOT STARTED)** — the single named blocker; without externalization Step-2 atomic cutover is impossible.
4. **`LOOM_SKILL_BRIDGE_SECRET` desync** — breaks the only end-to-end-closed path (`kind=skill`); A3 dispatch dead-ends.
5. **project_id UUIDs** hardcoded in self-observer config — reissue → mislabeled/dropped candidates.
6. **loom-discipline per-machine install** — one machine still runs the retired make-skills-discipline subset (writes local JSONL only, never reaches the central registry).
7. **Render MCP bearer token committed** in `the-loom/.mcp.json:11` — live secret in repo; flag for rotation (not staleness, but surfaced here).

---

## §4. Multi-party operating model + drift control

**Design principle: do not invent a parallel process.** The migration-cicd runbook state machine is the spine; this is the who-does-what overlay + the drift-catch layer.

### Decision rights (Propose → Review → Decide)

Ownership default is **by source-repo provenance**; `packages/{auth,ui,shared-types}/`, `apps/docs-site/`, `infra/` are shared (Tapestry-agent proposes).

| Decision class | Proposes | Reviews | Decides |
|---|---|---|---|
| Naming / naming-corrections | provenance owner | Tapestry-agent, outside reviewer | Tapestry-agent (routine); operator (contract-facing) |
| Schema source-of-truth | provenance owner | Tapestry-agent + other steward | **operator** (ADR required) |
| What migrates when (sequencing) | Tapestry-agent | loom-agent + ms-agent (source-stability veto) | operator (authorizes each step) |
| **Fleet disposition (attach/migrate/retire)** | Tapestry-agent (this doc) | stewards + observer signal | **operator** (the §2 questions) |
| ADR ratification | concern-raiser | Tapestry-agent + outside reviewer (adversary) | operator ratifies; Tapestry-agent merges |
| Agent spawning | Tapestry-agent | operator | operator |
| Spawn a drift-watcher | proposer self-authorizes on D2 trigger | — | proposer |
| Gate transitions | Tapestry-agent runs gate | per runbook §3 | mostly operator; `parity-verified→prod-rolling` standing-authorized |

### Memory protocol (current without spam)

- `tapestry_<slot>_<topic>_<date>` — slot working notes (decision moments only, not progress pings)
- `tapestry_decision_<topic>` — durable ratified decision (written by Tapestry-agent after operator ratifies; superseded-not-deleted)
- `tapestry_agent_<topic>_<date>` — cross-party coordination anchors (one per phase, not per step)
- `drift_watcher_<scope>_<date>` / `…_HALT_<date>` — drift concerns (drift-watcher only)
- `self_observer_synthesis_latest` — rolling observer synthesis (overwritten each cycle)

**Keeping each party current by pull, not push:** observer only emits; outside reviewer reads two surfaces on entry (latest `tapestry_agent_*` anchor + the plan's open-decisions section); operator reads three (MASTER_CHECKLIST + ratification queue + HALT surface); stewards get it via SessionStart recall. Research/eval output lands in plan docs on disk, **not** memory.

### Cadence + checkpoints

Async, event-triggered (no calendar syncs). A sync fires when: a runbook gate needs a non-automated approver; a `drift_watcher_*` concern is written; a cross-fleet schema/UUID/tenant decision surfaces; or the operator/outside reviewer asks "where are we" (answered from MASTER_CHECKLIST). **Tapestry-agent updates MASTER_CHECKLIST Part 1 at every state transition and commits it** so state survives session death.

### Drift control

- **Drift-watcher** spawns (background, read-only) for any execution window meeting all of D2: >5 sequential cross-file/cross-repo edits + bound by binding rules + >20 min. Practically, every migration step that reaches `approved` gets one. It surfaces via `memory_write`; stops at `monitoring`/`aborted`.
- **Outside reviewer** reviews *plans and decisions* (at `proposed→approved`, before any `tapestry_decision_*`, and as drift second-opinion). It does **not** watch execution — that's the drift-watcher. Clean split.
- **HALT conditions:** a `*_HALT_*` memo; `*** CONCRETE-RULE VIOLATION DETECTED ***` at SessionStart; an unfixable contract-assertion violation (drift-catcher red, untested rollback on a one-way step); the same piece a live writer in BOTH source and Tapestry; or a steward's source-stability veto while a lift proceeds.

---

## §5. Reconciliation: contradictions, gaps, staleness to resolve

The corpus has accumulated real inconsistencies. **The deepest structural risk: UMBRELLA, MANIFESTO §4.3, and the v1 roadmap disagree on service topology, and CLAUDE.md routes every new agent to UMBRELLA as authoritative — so the stalest doc has the most authority.** Fix that first.

### Contradictions (with the winner)

| # | Conflict | Winner | Action |
|---|---|---|---|
| C1 | Tapestry-agent "defer" (roadmap §7-E) vs "SPAWN NOW" (feedback memo) | **SPAWN NOW** (later operator directive; already spawned) | Patch roadmap §7-E to note supersession |
| C2 | candidate-registry separate service (UMBRELLA:47-48) vs merged into architecture-registry (roadmap §3) | **MERGED** | Correct UMBRELLA; delete/redirect the `services/candidate-registry/` slot |
| C3 | project-observatory "mature" (UMBRELLA:46, what-to-keep) vs 23-line stub (PROBE) | **STUB** | Correct UMBRELLA + what-to-keep |
| C4 | self-observer → dedicated dir (MANIFESTO §4.3) vs absorbed by project-observatory (readiness plan:89) — **plan mis-cites BOTH MANIFESTO §4.3 and the binding memo** (neither maps self-observer into project-observatory) | **UNDECIDED** | Needs an ADR (see G6) |
| C5 | discipline plugin two flavors `{loom,make-skills}` vs one (make-skills-discipline retired 2026-06-14) | **ONE (loom)** | Fix the `{loom,make-skills}` notation in roadmap §5 + plan Step 8 |
| C6 | "PR-prep-2 is the blocker / Tapestry-agent gated" vs agent already spawned | spawn ≠ start-work | State explicitly: the agent is spawned but work-gated on PR-prep-2 |
| C7 | telemetry-ingestion "out of v1" (2026-06-13 memo) vs Step 7a in-scope w/ rollup | **IN v1 (Step 7a)** | Mark the memo's exclusion stale |

### Gaps (no doc covers)

- **G1 — broader-fleet disposition** — addressed by §2 of this doc (was the central hole).
- **G2 — continuous candidate/decision sync during the weeks-long cutover.** A one-time `pg_dump` + 14-day memory dual-write is defined, but new rows the live self-observer + A4 dispatch keep producing in the-loom *during* Steps 1–7 have no reconciliation plan. **Real data-coherence hole — needs an ADR.**
- **G3 — multi-party operating model** — addressed by §4 of this doc.
- **G4 — migration-toolkit + workflows don't exist.** The binding doctrine ("every step maps to a runbook gated by the drift-catcher") has zero executable substrate yet (all "designed, not implemented"). **PR-prep-3 (ship `packages/migration-toolkit/` v0.1.0) must be scheduled before any per-step runbook.**
- **G5 — tenant_id correctness audit never run** (`SELECT COUNT(*), tenant_id FROM records GROUP BY tenant_id`). Named prerequisite; ungated. Assign + run.
- **G6 — `engine/local-observer/` orphaned.** Path A candidates (half the loop) have no migration source/owner in any table. Possible silent drop. Resolve with C4 in one observer-topology ADR.

### Staleness to patch

UMBRELLA bounded-contexts table (C2/C3/C4); roadmap §7-E (C1) + §4 telemetry exclusion (C7); `what-to-keep.md:7`; `import-map.md` (still empty, guesses policy-first when the plan is auth/agent-context-first); MASTER_CHECKLIST Part 2 (PR-prep-1 still shown unchecked though DONE); co-author tag drift (Opus 4.7 vs 4.8).

---

## §6. Decision points for the operator (explicit — not decided here)

1. **Fleet dispositions** — the open questions in §2 (docs-agent persona; loom-platform deferred call; ux-starter slot; humancensys-app reference-vs-external; the 3 duplicate starters → archive; Pretend-Agents eval dependency; humancensys marketing site in/out).
2. **Q4 telemetry pacing** — Step 4 vs Step 7a (Tapestry-agent's first owned ADR; must be seeded).
3. **Observer topology (C4/G6)** — where self-observer (static scan), local-observer (Path A), and runtime-observer (signals) each land, given project-observatory is the contested shared destination.
4. **G2 continuous-sync strategy** — how live-produced candidates/decisions reconcile across cutover.
5. **Accept "no auto-promotion until Tapestry v1 ships"** — the deferral pushes ~10 capabilities to Tapestry, none in v1.
6. **Templates source** — `Make_Skills/templates/` doesn't exist on disk; locate or author.
7. **Render MCP token rotation** — committed secret in `the-loom/.mcp.json`.
8. **Operating-model ratification** — §4's filled gaps (fleet-disposition rights, drift-watcher spawn authority, outside-reviewer role) are design choices pending sign-off → `tapestry_decision_operating_model_*`.

---

## §7. Immediate next actions (no migration; understand/prepare only)

1. **Patch the stale binding docs** (C1–C3, C5, C7 + staleness list) so UMBRELLA stops being the stalest-yet-most-authoritative doc. One small docs PR. (Tapestry-agent owns; doc-only, safe under CORE DIRECTIVE 2.) **This doc-patch PR itself wants operator review before merge** — some corrections (e.g. C2's "delete the candidate-registry slot") touch structure, not just prose.
2. **Open two ADR stubs:** `00xx-observer-topology` (C4/G6) and `00xx-cutover-continuous-sync` (G2). Draft, route to outside reviewer + operator.
3. **Surface §6 to the operator + outside reviewer** as explicit decision points.
4. **Schedule PR-prep-3** (migration-toolkit v0.1.0) into the readiness-plan §8 sprint (G4).
5. **Assign + run the tenant_id audit** (G5) — loom-agent + operator.
6. PR-prep-2 (loom URL externalization) remains the migration blocker — loom-agent's, unchanged.

---

## §8. What this phase explicitly did NOT do

- No code, no migration PRs, no source-repo changes (CORE DIRECTIVE 2 honored; parallel-build intact).
- No re-deciding settled questions (SKU/auth/billing/sequence/migration-cicd doctrine build on, not re-plan).
- No new parallel process — the runbook state machine remains the spine.
- No fleet repo dispositioned as an *action* — §2 is a plan awaiting operator ratification.

## Related
- loom-memory: `tapestry_agent_spawned_and_oriented_2026_06_18`, `tapestry_agent_systematic_planning_kickoff_2026_06_18`, `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13`, `feedback_tapestry_parallel_build_not_pause_and_migrate_2026_06_12`, `msagent_fleet_audit_synthesis_complete_2026_06_18`
- Drift-watcher baseline: `drift_watcher_tapestry_unified_planning_baseline_2026_06_18`
