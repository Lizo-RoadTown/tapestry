# Extended migration audit — what `Make_Skills` and `the-loom` carry that the migration plan doesn't enumerate

**Status:** OPERATOR-RATIFIABLE — 4 parallel research subagents + adversarial evaluator + corrections applied.

**Authored by:** loom-agent (operator-directed 2026-06-22).

**Purpose:** the existing tapestry migration plan ([`2026-06-18-tapestry-migration-readiness-and-execution.md`](2026-06-18-tapestry-migration-readiness-and-execution.md)) covers Steps 1–8 at the service-and-package level. The audit revealed **subordinate content** — sub-modules, dependent docs, infrastructure configs, fixtures, runbooks — that the headline steps name implicitly but don't enumerate. This document is the operator-ratifiable list of EVERYTHING worth lifting that isn't already on the headline plan, baselined against current state.

---

## §0 — Migration state at audit time (2026-06-22)

Per [MASTER_CHECKLIST.md:104-107](../../MASTER_CHECKLIST.md):

| Step | Status |
|---|---|
| Step 1 — auth consolidation | **MERGED to main 2026-06-20** (PR #4, `0625054`) |
| Step 2 — agent-context MCP | **PROD CUTOVER COMPLETE 2026-06-21**, `loom-agent-context` now runs from tapestry |
| Step 3 — project-registry | **PROD CUTOVER COMPLETE 2026-06-21**, `loom-project-registry` now runs from tapestry |
| Step 4 — engine | **CODE-LIFT COMPLETE 2026-06-21** (PR #9); no prod cutover owed (`make-skills-api` is a different app's host) |
| Step 5 — templates + CLI | **IN PROGRESS** (CLI lifted 2026-06-21; templates pending) |
| Step 6 (web-dashboard), Step 7 (architecture-registry + policy + telemetry), Step 7a, Step 8 (loom-discipline + self-observer) | **QUEUED** |
| PR-prep-3 — `packages/migration-toolkit/` v0.1.0 | **DOC + scaffolding shipped, executable code pending** ([MASTER_CHECKLIST.md:103](../../MASTER_CHECKLIST.md)) |

Tapestry on-disk inventory the audit uses as ground truth: `services/{agent-context, architecture-registry, audit-log, candidate-registry, policy, project-observatory, project-registry, skill-making, telemetry-ingestion}` · `packages/{auth, cli, schemas, sdk, shared-types, ui}` · `engine/{adapters, agency-to-structure, local-observer, skill-compiler}` · `apps/{admin-console, docs-site, web-dashboard}` · plus top-level `scripts/`, `deprecated/`, `templates/`, `integrations/`, `infra/`.

---

## How to read this document

- **§1 (Five tier-1 must-lifts)** — Items where Step 7/8 will produce incomplete or wrong results without them.
- **§2 (Tier-2: should-lift)** — High-utility candidates that compound value when present but won't break Steps 5–8 if deferred.
- **§3 (Tier-3 / provenance-only)** — Documentation provenance worth preserving in `tapestry/docs/`; safe to keep as GitHub blob links if lift cost is high.
- **§4 (Explicit retire list)** — Things the audit flagged that should be left in source repos (already deprecated, superseded, or stub-only).
- **§5 (Cross-cutting concerns)** — Themes that span multiple items + decisions needed.
- **§6 (Open questions for operator)** — Ratification gates before this becomes execution.
- **§7 (How this plan becomes execution)** — Conversion to MASTER_CHECKLIST entries.
- **Appendix A (Adversarial eval findings)** — Embedded in this doc so the synthesis ↔ eval ↔ corrections trail is preserved.

Every row in §§1–4 cites a path. Operator + future-agents PROBE the cited paths before acting.

---

## §1 — Five tier-1 must-lifts

### 1.1 The Make_Skills observability stack (Grafana dashboards + Loki + Promtail + the operator runbook)

**Source:**
- `Make_Skills/platform/deploy/grafana/dashboards/dev-experience.json`
- `Make_Skills/platform/deploy/grafana/provisioning/{dashboards,datasources}/*.yml`
- `Make_Skills/platform/deploy/loki-config.yml`
- `Make_Skills/platform/deploy/promtail-config.yml`
- `Make_Skills/docs/runbooks/dev-experience-observability.md`
- ALSO: `the-loom/infra/grafana/dashboards/loom-phase1-observability.json` + `the-loom/docs/runbooks/grafana-dashboard-rebuild.md` (loom-side complement)

**Why this is tier-1:** Tapestry's migration-cicd doctrine talks extensively about observability + drift-catching but ships zero concrete observability assets. The discipline plugin (Step 8) emits OTLP logs about hook events with no place to land them on Tapestry's side. Step 7 (telemetry-ingestion) lifts a sink with no display. `what-to-keep.md:11` names the dashboards as keepers but the keep-list doesn't enumerate the Loki + Promtail + provisioning yaml + the runbook — that's the genuine novel gap this surfaces.

**Destination:**
- `tapestry/infra/grafana/dashboards/` (both dashboards as a pair)
- `tapestry/infra/grafana/provisioning/{dashboards,datasources}/`
- `tapestry/infra/docker/loki/` + `tapestry/infra/docker/promtail/`
- `tapestry/docs/runbooks/dev-experience-observability.md` + `grafana-dashboard-rebuild.md` (**create `tapestry/docs/runbooks/` — directory does not yet exist**)

**Effort:** ~6 config files + 2 runbooks; half-day to lift + smoke. Pair with Step 7 (telemetry-ingestion).

### 1.2 Make_Skills `core/auth/*` — the `TenantContext` + pgcrypto BYO-key surface that Step 1 didn't lift

**Source:**
- `Make_Skills/core/auth/auth.py` — `TenantContext` class; JWT/SELF_HOST_TENANT_ID resolver
- `Make_Skills/core/auth/secrets.py` — pgcrypto-encrypted tenant-scoped BYO-API-key storage (`pgp_sym_encrypt` via `app.secrets_key` GUC)
- `Make_Skills/core/auth/tenant_context.py` — `current_tenant` ContextVar (the async-boundary chokepoint)
- `Make_Skills/core/db/db.py` — `tenant_conn()` async pool helper with transactional `SET LOCAL app.tenant_id`

**Why this is tier-1 — corrected framing:** Step 1 lifted the canonical loom-side `loom_auth` package (per [MASTER_CHECKLIST.md:102](../../MASTER_CHECKLIST.md), PR-prep-2b consolidated the 4 duplicate `auth_bridge.py` copies in the-loom into one canonical lib in 2026-06-19; Step 1 then lifted THAT to `tapestry/packages/auth/python/loom_auth/`). The `loom_auth` package is the canonical TWO-MODE JWT verifier (self-host fallback + hosted RS256). What it does NOT include: the `TenantContext` class surface, the pgcrypto BYO-key store, the `current_tenant` ContextVar, the RLS-correct `tenant_conn()`. These four are the Make_Skills-side platform primitives that have no loom-side equivalent. Without them, Tapestry will either re-implement them poorly or leave services to manually manage tenant context.

**Destination:** `tapestry/packages/auth/python/loom_auth/` (alongside the existing shim) — or split `secrets.py` to its own `packages/secrets/` (operator decides, see §5). `tenant_conn()` may belong in `tapestry/packages/sdk/python/db.py` (currently scaffold-only — see §6 open question 2).

**Effort:** ~4 files, ~350 LOC; care needed because these are referenced widely in Make_Skills. Half-day plus the audit of every existing Step-1 import path.

### 1.3 The four living architecture docs that explain the agent-side mechanics

**Source (all `the-loom/docs/architecture/`):**
- `database-shape-and-layers.md` — the only place the layered request-flow + RLS + ownership rules are written for an agent reading cold
- `how-agents-use-memory.md` — the only walkthrough of the agent's loop with the memory store
- `project-scoping-pattern-b.md` — the "one Registry row + multiple project_tags" pattern for multi-scope repos
- `assessment-protocol.md` — snapshot + functionality/efficiency measurement protocol

**Why this is tier-1:** Tapestry's `docs/architecture/` currently has one file (`UMBRELLA.md`). These four are the load-bearing companions that explain how the umbrella concepts actually work in code. `what-to-keep.md:13` mentions `docs/proposals/` for provenance but does NOT mention `docs/architecture/` — that's the gap. Without them, a new operator reading Tapestry cold has the WHAT but not the HOW.

**Destination:** `tapestry/docs/architecture/` (drop-in; update repo-relative paths to point at Tapestry's eventual structure).

**Effort:** ~4 files; mostly editorial (update internal links). Half-day.

### 1.4 URL repointing across migrated services (operationally critical, easy to miss)

**Source — hardcoded URLs that need repointing after migration:**
- `the-loom/services/self-observer/main.py` and clients — hardcodes architecture-registry URL
- `the-loom/adapters/claude-code/loom-discipline/scripts/observer.py` — hardcodes architecture-registry URL
- `the-loom/adapters/claude-code/loom-discipline/scripts/stop_audit.py` — same
- `the-loom/adapters/claude-code/loom-discipline/scripts/_observability.py` — hardcodes OTLP exporter URL
- `Make_Skills/core/runtime/agent.py` (likely) — hardcodes engine + memory URLs

**Why this is tier-1:** PR-prep-2a (source-side externalization) is DONE per [MASTER_CHECKLIST.md:101](../../MASTER_CHECKLIST.md). The destination-side flip is the actual remaining work and is NOT named in the existing plan. Step 7 cannot ship without it — a service that boots pointing at the wrong host is wrong even when the code is right. Step 8 (loom-discipline migration) has the same problem in 3+ scripts.

**Destination:** N/A — this is a sub-step within each affected service's cutover. Each service must verify its `TAPESTRY_*_URL → LOOM_*_URL → hardcoded default` env-precedence chain works against the new host BEFORE cutover.

**Effort:** small per-service (1 commit each) but easy to miss if not enumerated as a checklist item. Add to each Step 6/7/8 runbook.

### 1.5 Recursive-skill loop provenance documents

**Source (all `the-loom/docs/`):**
- `docs/proposals/2026-05-25-platform-data-model.md` — the 13-platform-object v3 spec; load-bearing source of every bounded context
- `docs/proposals/2026-05-25-agency-optimizer-pattern.md` — the "platform owns capability, project owns instance" pattern
- `docs/proposals/make-skills-engine-vs-consumer-scope.md` — the doc that justifies "engine = tapestry, consumer = humancensys-app"
- `docs/proposals/2026-06-12-promotion-categorization.md` — the 9-kind candidate taxonomy authority (cited by `infra/migrations/005`/`006`)
- `docs/research/2026-06-16-candidate-lifecycle-verified.md` — verified-by-PROBE audit of the actual 7-state candidate lifecycle vs claimed 5-state

**Why this is tier-1 — corrected framing:** This is provenance preservation, not active-blocker work. But Tapestry's UMBRELLA.md, MANIFESTO, and Step-7 work (architecture-registry + policy) all reference these documents implicitly. The candidate-lifecycle-verified doc is the only PROBE'd ground truth on policy-service inertness — Step 7 imports the policy service and will inherit the same inertness unless this doc travels with it to flag the design decision.

**Destination:** `tapestry/docs/proposals/` + `tapestry/docs/research/`.

**Effort:** five-file lift; trivial editorial. One hour.

---

## §2 — Tier-2 should-lift

High utility, won't break Steps 1–8 if deferred to a follow-up cycle. Grouped by destination.

### 2.1 Subagents (deep-research topology + roadmap-maintenance + schema-migrator + architecture-analyst)

**Source (Make_Skills):**
- `subagents/planner/` — deep-research topology, planner role
- `subagents/researcher/` — deep-research topology, researcher role
- `subagents/researcher-coordinator/` — outer-loop orchestrator
- `subagents/roadmap-maintenance/` — agent self-maintenance of `ROADMAP.md`
- `subagents/schema-migrator/` — plain-English → idempotent migration

**Plus the one already-Step-8-included** `the-loom/adapters/claude-code/loom-discipline/agents/architecture-analyst.md` — flag explicitly so Step 8 doesn't drop the `agents/` subdirectory.

**Status:** Each named in `what-to-keep.md:24` as "4 named subagent definitions" (count is wrong — there are 5; minor entry for `naming-corrections.md`). **Tapestry has no `engine/subagents/` or `engine/agents/` directory yet** — operator decides between `engine/subagents/`, `engine/agents/`, or `integrations/claude-code/subagents/`. See §6 open question 1.

**Blockers per subagent:**
- `roadmap-maintenance` is blocked on exposing in-process `@tool`-decorated tools (`update_roadmap_status`, `add_roadmap_item`, `roadmap_overview`) as MCP first. Pairs with `Make_Skills/services/admin/roadmap/{file,tools}.py` — both should migrate together as a single MCP server. **Demote `services/admin/roadmap/` from tier-3 to tier-2 here** (per eval finding 3.4).
- `schema-migrator` is hard-coded to `Make_Skills/platform/api/migrations.py` + Drizzle TS schema. Needs generalization pass before useful.

### 2.2 Make_Skills core-runtime modules + observability seed

**Source (`Make_Skills/core/`):**
- `runtime/agent.py` — `build_agent()` integration with `deepagents` + PostgresSaver
- `runtime/runtime.py` — per-`(tenant, agent_id)` instantiation; skill cache; provider client cache
- `orchestration/subagents.py` — in-process dispatch module
- `providers/model_registry.py` — multi-provider LangChain resolver (anthropic/openai/google/huggingface/together/groq/ollama)
- `tools/db.py` — read-only Postgres SQL tool for the agent
- **`observability/` (added per eval finding 3.1)** — Make_Skills' own observability module; pairs naturally with §1.1's Grafana stack. Probe contents before lifting.

**Destination:** `tapestry/engine/agency-to-structure/` (currently README-only) for the runtime modules. `tapestry/packages/sdk/python/providers/` for the provider registry. `tapestry/packages/sdk/python/tools/` for the SQL tool. `tapestry/packages/sdk/python/observability/` for the observability module (or merge into telemetry-ingestion).

### 2.3 Operational tools from the-loom's scripts/

**Source (`the-loom/scripts/`):**
- `audit_concrete_rules.py` — fleet audit script for concrete-rule invariants (the Layer 8 enforcement)
- `memory_snapshot.py` — snapshots loom-memory store shape to `docs/memory-snapshots/<UTC>.json`
- `mint_loom_token.py` — dev-mode JWT minter for the loom-memory MCP
- `apply_migration.py` — runs SQL files against the DB
- `backfill_projects.py` — registers projects-in-memory-but-not-in-Registry; codifies the umbrella+sub-tag pattern (Pattern B)

**Destination — corrected per eval finding 3.2 + 6.2:** Tapestry has a top-level `tapestry/scripts/` directory. Per-service `scripts/` subdirs (e.g., `services/policy/scripts/`) don't exist as a convention yet. Default to the top-level `tapestry/scripts/` for these; operator can refactor per-service later if a convention emerges. Specifically:

- `tapestry/scripts/audit_concrete_rules.py` (pair with §2.4)
- `tapestry/scripts/memory_snapshot.py`
- `tapestry/scripts/mint_token.py` ← `mint_loom_token.py`
- `tapestry/scripts/apply_migration.py`
- `tapestry/scripts/backfill_projects.py`

### 2.4 The 2 the-loom-unique skills

**Source (the-loom):**
- `skills_private/concrete-rule/` — methodology for protecting system invariants via defense-in-depth
- `skills_private/periodic-architectural-checkin/` — structured pause for auditing drift

**Destination:** `tapestry/integrations/claude-code/skills/` (or promote to a `tapestry-patterns` plugin entry, operator's call).

**Why:** Both are explicitly flagged in `the-loom/skills/README.md` as queued for future migration / promotion review (verify line numbers when lifting; eval finding 1.6 noted the README is at `skills/`, not `skills_private/`). Pair operationally with §2.3's `audit_concrete_rules.py` (the runner for the methodology).

### 2.5 The default-seed contract (adapters already renamed in tapestry)

**Source (Make_Skills):**
- `adapters/default-seed-contract.md`
- `adapters/development/default-seed/` + `README.md`
- `adapters/classroom/default-seed/` + `README.md`
- `adapters/research-project/default-seed/` + `README.md`

**Status — corrected per eval finding 1.4:** The three seeds are in the plan (Step 5: templates+CLI). The CONTRACT document binding them is NOT explicitly listed. **The adapter directories in tapestry are already renamed** (`engine/adapters/{classroom,development,operations,research}` — no `-project` suffix), so no adapters naming-corrections work needed. **Templates DO still have `-project` suffix** (`templates/{classroom-project,operations-project,research-project,software-project}`) — that's the only place the naming-corrections entry applies.

**Destination:** `tapestry/engine/adapters/default-seed-contract.md`.

### 2.6 Make_Skills deploy + dependency manifests

**Source (Make_Skills):**
- `platform/deploy/Dockerfile` — Python 3.12-slim canonical
- `platform/deploy/docker-compose.yml` — 3-service local stack (postgres + api + ui)
- `platform/deploy/.env.template`
- `render.yaml` — engine-side Blueprint (Tapestry's render.yaml only covers loom-side services)

**Status — corrected per eval finding 2.4:** `Make_Skills/platform/requirements.txt` is NOT needed as a separate lift — `tapestry/services/skill-making/python/requirements.txt` already exists (verified).

**Destination:**
- `tapestry/infra/docker/Dockerfile`
- `tapestry/infra/docker/docker-compose.yml`
- `tapestry/infra/docker/.env.template`
- Add a `make-skills-api`-equivalent block (or whatever the post-migration deploy shape is) to `tapestry/infra/deploy/render.yaml`

### 2.7 Runbooks (create the `tapestry/docs/runbooks/` directory)

**Source:**
- `Make_Skills/docs/runbooks/render-deploy.md` — Render Blueprint deploy walkthrough
- `Make_Skills/docs/runbooks/dev-experience-observability.md` — already in §1.1
- `Make_Skills/platform/REMOTE_ACCESS.md` — Tailscale remote-access guide
- `the-loom/docs/runbooks/grafana-dashboard-rebuild.md` — already in §1.1
- `the-loom/docs/runbooks/mcp-drop-investigation.md` — open investigation
- `the-loom/docs/howto/onboard-a-project.md` — manual `tapestry init` flow (CLI is the spec; this is the prose)

**Destination:** `tapestry/docs/runbooks/` (create the directory; add a brief README explaining the convention — one runbook = one operational task; named `<verb>-<noun>.md`).

### 2.8 Self-observer sub-modules (Step 8 currently lists "self-observer" as one bullet)

**Source (`the-loom/services/self-observer/`):**
- `signal_rules.py` — agent/tool/skill/orphan classifier rules (tested in `test_signal_rules.py`)
- `synthesis.py` — entry → candidate body composition (tested in `test_synthesis.py`)
- `github_scanner.py` — frontmatter parse + excludes
- `telemetry_client.py` — currently stub; will hit observatory when read API exists
- `memory_client.py` + `candidate_client.py` — loom-memory + architecture-registry callouts
- `README.md` — flow diagram (the only one); preserve verbatim
- `tests/` — judgment-heavy logic with non-trivial coverage

**Recommendation:** Treat Step 8 as a multi-bullet checklist for the self-observer side. Each sub-module has independent test coverage; lifting as one bullet risks losing per-module testability.

### 2.9 Step 8's loom-discipline completeness checklist

**Source (`the-loom/adapters/claude-code/loom-discipline/`):**
- `agents/architecture-analyst.md` — the subagent that produces narrative reports
- `commands/architecture-report.md` — the `/architecture-report` slash command
- `skills/loom-discipline/SKILL.md` — the plugin-embedded skill
- `tests/` — coverage for observer, pre-tool-use, scope, stop-audit-upskilling

**Plus URL repointing — see §1.4 (promoted from cross-cutting concern to tier-1).**

**Recommendation:** Treat Step 8 as five sub-tasks, not one — directory + commands + skill + tests + URL repointing.

### 2.10 Bridge wire-contract verification script

**Status — corrected per eval finding 1.3:** PROBE confirms `tapestry/services/skill-making/python/skill_making/tests/{conftest.py, test_hmac_verify.py, test_models_schema_invariants.py, test_telemetry_collector.py}` are ALL present — they DID ship with Step 4. **Only `Make_Skills/scripts/verify_bridge_receiver.py` is the genuine gap.**

**Destination:** `tapestry/services/skill-making/scripts/verify_bridge_receiver.py` (create the scripts/ subdir).

### 2.11 Make_Skills top-level prose docs (added per eval finding 3.3)

**Source (Make_Skills top-level):**
- `ARCHITECTURE.md` — load-bearing architecture overview
- `CONTRIBUTING.md` — contribution norms
- `ROADMAP.md` — Make_Skills's own roadmap
- `AGENTS.md` — cross-IDE discovery file (Codex, Cursor, ChatGPT)
- `CHANGELOG.md` — version history
- `MCP.md` — cross-client MCP setup snippets
- `README.md`

**Why surfaced as tier-2:** Make_Skills's top-level `ARCHITECTURE.md` is the kind of "load-bearing prose doc" §1.3 says the plan misses. Tapestry has `MANIFESTO.md` + `README.md` + `ROADMAP.md` + `MASTER_CHECKLIST.md` + `CLAUDE.md` at top level, but no `ARCHITECTURE.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `AGENTS.md` — each is a candidate.

**Destination:** Tapestry root for `ARCHITECTURE.md`, `CONTRIBUTING.md`, `AGENTS.md`. Operator decides on `CHANGELOG.md` (might want to start fresh for Tapestry). `MCP.md` → `tapestry/docs/runbooks/mcp-clients.md` per §2.7.

---

## §3 — Tier-3 / provenance-only

Reference value; safe to leave in source repos with a GitHub blob link rather than lift. Listed for completeness.

| Path | Tier-3 reason |
|---|---|
| `Make_Skills/docs/decisions/002-two-mode-commitment.md` | ADR-style constitutional doc; lift if `tapestry/docs/adr/` standardizes on per-decision files |
| `Make_Skills/docs/proposals/2026-05-25-make-skills-engine-data-model.md` | Provenance for the engine data model |
| `Make_Skills/docs/proposals/2026-05-25-make-skills-engine-mvp-repo-layout.md` | Historical context for the repo layout choice |
| `Make_Skills/docs/proposals/application-vs-dev-tooling-scope.md` | Founding scope doc |
| `Make_Skills/docs/runbooks/power-up-docker-cloud-ollama.md` | Docker Cloud + Ollama BYO endpoint setup |
| `Make_Skills/services/admin/{fileviewer,mcp_inspector,provider_inspector,sessions}.py` | Useful for the eventual web-dashboard; defer until dashboard surfaces these endpoints. (`roadmap/` promoted to tier-2 §2.1.) |
| `Make_Skills/scripts/sync-references.{sh,ps1}` | Vendoring helper; obsolete if vendored via git submodules |
| `Make_Skills/scripts/sync-upstream.{sh,ps1}` | Anthropic-skills refresh helper |
| `Make_Skills/deepagents.toml` | Canonical deepagents config — useful as reference |
| `the-loom/docs/architecture/2026-05-31-five-module-platform.md` | The five-module decomposition narrative |
| `the-loom/docs/plans/2026-06-14-infrastructure-map.md` | Simon-style nearly-decomposable-system map |
| `the-loom/docs/plans/2026-05-25-the-loom-roadmap-v2.md` | Historical roadmap |
| `the-loom/docs/research/2026-06-17-platform-state-audit{,-verification}.md` | Audit + verification artifacts for the A1/A2/A3 work |
| `the-loom/docs/superpowers/plans/2026-06-18-runtime-observation-followup-execution{,-EVAL}.md` | Just committed to the-loom main 2026-06-22 (`38f2808`); link rather than re-lift |
| `the-loom/docs/superpowers/specs/2026-06-12-architecture-snapshot-multiservice-design.md` | Design for multi-service snapshot script |
| `the-loom/docs/history.md` | Historical context |

---

## §4 — Explicit retire list

Items the audit flagged as actively-deletable, already-superseded, or already in a `deprecated/` dir.

| Path | Reason |
|---|---|
| `Make_Skills/{chatgpt,copilot,vs_code}/` | README-only stubs; `tapestry/integrations/` already covers these |
| `Make_Skills/scripts/smoke-test-llamaparse.py` | One-off; not load-bearing |
| `Make_Skills/platform/api/` | Empty (code already lifted into `services/api/` and `core/`) |
| `Make_Skills/deprecated/lancedb-memory/` (verified per eval finding 3.5) | Already in Make_Skills's own `deprecated/` dir; do not re-lift; document the framing was already there |
| `Make_Skills/docs/_archive/`, `inspiration/`, `_pdfs/` | Historical archive; don't lift |
| `Make_Skills/docs/runbooks/memory-mcp-local.md` | Superseded by loom's pgvector MCP; LanceDB deprecated upstream |
| `the-loom/scripts/loom_init.py` | Backwards-compat shim; obsolete once Tapestry CLI publishes |
| `the-loom/scripts/new-loom-project.ps1` | Pre-CLI manual workflow; superseded by `tapestry init` |
| `the-loom/scripts/architecture_{snapshot,diff}.py` (thin wrappers) | Per their own docstring, slated for removal once loom-discipline invokes canonical directly |
| `the-loom/skills/` | Empty by design; README documents the migration to tapestry-patterns plugin |
| `the-loom/docs/INTER_AGENT_DIALOGUE.md` | Already marked for retirement in `legacy-repo-inventory.md` |
| `the-loom/docs/architecture-snapshots/` (as content) | Auto-generated; retain in source repo for audit history but don't lift files |
| `the-loom/docs/memory-snapshots/` (as content) | Same — auto-generated artifact dir |
| `the-loom/docs/architecture/UMBRELLA.md` | Stub pointing at tapestry's UMBRELLA; superseded |
| `the-loom/platform/memory/` | Empty stub |
| `the-loom/mcp/` | Already decommissioned per A2 plan |

---

## §5 — Cross-cutting concerns

### 5.1 Subagent destination (decision needed before Step 8)

Multiple §2.1 items name subagents; tapestry has no `engine/subagents/` or `engine/agents/` directory. Three plausible destinations:

- `tapestry/engine/subagents/` — fits if subagents are part of the engine's runtime
- `tapestry/engine/agents/` — fits if "agent" is the more general framing
- `tapestry/integrations/claude-code/subagents/` — fits if subagents are Claude-Code-specific

This is an **ADR-shaped decision** that should land before Step 8 ships, not after. Recommend ADR-0004.

### 5.2 The "runbooks/" directory pattern

§1.1, §2.7 require `tapestry/docs/runbooks/` (does not yet exist). First lift creates the directory + adds a brief README explaining the convention.

### 5.3 The `Make_Skills/core/` lift strategy: incremental vs big-bang

The audit surfaced multiple `Make_Skills/core/` modules that are platform-shaped but live in Make_Skills (§1.2, §2.2). Two operator decisions:

1. **Big-bang core lift** — one PR lifts all of `core/` into tapestry's packages/sdk + engine + auth. Faster; higher coordination cost.
2. **Incremental per-service** — each service lift pulls its `core/` dependencies. Slower but lower-risk per step.

Recommendation: **incremental for auth (§1.2)** because the surface is widely-referenced and benefits from per-touch consideration; **big-bang for the runtime modules (§2.2)** because they belong together in `engine/agency-to-structure/`.

### 5.4 Tests-must-travel-with-code is currently satisfied per Step 4 (good news) but flag for Step 8

Per eval finding 1.3, Step 4 DID lift the bridge tests alongside code. **For Step 8, explicitly enumerate the per-module tests in the migration checklist** so the same discipline carries through.

### 5.5 The `tapestry/scripts/` vs `services/*/scripts/` convention

Per eval finding 3.2, Tapestry has a top-level `scripts/` directory used for the architecture-snapshot wrappers. Per-service `scripts/` subdirs don't yet exist. §2.3 destinations default to the top-level `tapestry/scripts/`; operator can refactor per-service later if a convention emerges.

---

## §6 — Open questions for the operator

Before this plan becomes execution-authority:

1. **§5.1** — Where do subagents live? `engine/subagents/`, `engine/agents/`, or `integrations/claude-code/subagents/`? (Drives Step 8 and §2.1.)
2. **§1.2** — Should `packages/sdk/python/` get created as part of §1.2's `tenant_conn()` lift, or stay scaffold-only?
3. **§2.1** — Roadmap-maintenance MCP-wrapping: do it alongside the lift, or defer?
4. **§5.3** — Big-bang or incremental for Make_Skills `core/`?
5. **§2.6** — `make-skills-api`-equivalent in `tapestry/infra/deploy/render.yaml`: what's the post-migration deploy shape for the engine service (now that the make-skills-api isn't a migration target)?
6. **§2.11** — Which top-level Make_Skills docs lift to tapestry root vs `docs/`? (Specifically `CHANGELOG.md` and whether to start fresh for Tapestry.)

---

## §7 — How this plan becomes execution

This is **discovery + recommendations**, not execution authority. After operator ratifies §1–5 and resolves §6:

- §1 items → checklist in `MASTER_CHECKLIST.md` Part 1 (active work)
- §2 items → queued in `MASTER_CHECKLIST.md` Part 2
- §4 items → single retirement PR
- Existing migration plan Steps 5/6/7/7a/8 get updated with sub-checklists pulling in the relevant §1–§2 items
- URL repointing (§1.4) becomes a sub-step in EACH affected step's runbook, before cutover

---

## Appendix A — Adversarial evaluator findings (2026-06-22)

The synthesis above was reviewed by an adversarial evaluator subagent. 8 high-impact findings, 12 medium, 6 low. Recommendation: APPLY-WITH-EDITS. The corrections were applied in this document and are summarized below for traceability.

**Corrections applied:**
- **Finding 1.1**: 003+005+006 migration trio + the promotion-categorization proposal removed from tier-1; folded into §1.5 (provenance) and called out as a Step-7 sub-checklist footnote (the existing plan's §5 Step 7 already lists migrations 003 + 004 — adding 005/006 is sub-step work, not novel discovery).
- **Finding 1.2**: §1.2 (was §1.3) auth framing corrected: `loom_auth` was the consolidated canonical loom-side library, NOT a downstream consumer of Make_Skills. Make_Skills `core/auth/*` carries TenantContext + pgcrypto BYO surface as parallel implementation that `loom_auth` does not have.
- **Finding 1.3**: §2.10 corrected: bridge tests DID ship with Step 4 (verified). Only `verify_bridge_receiver.py` is the genuine gap.
- **Finding 1.4**: §2.5 corrected: adapters already renamed in tapestry (`engine/adapters/research/`). Only templates retain the `-project` suffix.
- **Finding 1.5/1.6**: §3 `AGENTS.md` source corrected to `Make_Skills/AGENTS.md`; the-loom doesn't have one.
- **Finding 2.1**: §1.1 (Grafana stack) explicitly acknowledges `what-to-keep.md:11` names the dashboards; gap is Loki+Promtail+provisioning+runbook.
- **Finding 2.2**: §1.3 (architecture docs) explicitly notes `what-to-keep.md:13` mentions proposals/ but not architecture/.
- **Finding 3.1**: `Make_Skills/core/observability/` added to §2.2.
- **Finding 3.2**: §2.3 destinations corrected to default to `tapestry/scripts/` top-level dir (tapestry already has it).
- **Finding 3.3**: New §2.11 added for Make_Skills top-level docs (ARCHITECTURE.md, CONTRIBUTING.md, ROADMAP.md, AGENTS.md, CHANGELOG.md).
- **Finding 3.4**: `services/admin/roadmap/` promoted from tier-3 to tier-2 (§2.1), to pair with the roadmap-maintenance subagent's MCP-wrapping blocker.
- **Finding 3.5**: §4 explicitly notes `Make_Skills/deprecated/lancedb-memory/` is already in deprecated dir; verified.
- **Finding 4.1**: Migration trio demoted (see Finding 1.1).
- **Finding 4.2**: §1.5 (was tier-1.5) reframed as "provenance preservation" with corrected urgency claim ("Step 7 will absolutely proceed without these").
- **Finding 5.1**: URL repointing promoted to §1.4 (tier-1).
- **Finding 5.2**: PR-prep-3 acknowledged in §0 migration-state-at-audit-time preamble.
- **Finding 6.1**: §1.2 destination clarified to `packages/auth/python/loom_auth/` with `packages/sdk/python/` flagged as open question §6.2.
- **Finding 6.2**: §2.3 destinations defaulted to `tapestry/scripts/` top-level.
- **Finding 7.1**: §6 "Source audits (raw)" section removed; ground-truth framing dropped. The 4 source audits' substance is fully reflected in §§1-4; raw outputs are recoverable from the agent IDs `afc51bc2…`, `ab241ab2…`, `a62df633…`, `af3d1c8d…` in this session's transcript if needed.
- **Finding 7.3**: Open question #4 (verify-and-backfill Step 4 tests) dropped from §6 — already resolved per Finding 1.3.
- **Finding 8.1**: New §0 "Migration state at audit time" added; each tier-1 item re-evaluated against current state.
- **Finding 8.2**: `legacy-repo-inventory.md` cross-reference acknowledged in §0 baseline.
- **Finding 8.3**: §1.2 + §2.2 destinations call out that `engine/agency-to-structure/` is README-only scaffold (verified) before recommending it as destination.

**Findings explicitly NOT applied:**
- **Finding 8.4** (run an architecture snapshot of tapestry as audit ground truth): noted but not actioned in this draft. Future iteration could add a tapestry-snapshot diff layer; this audit's ground truth is the four subagent reports + PROBE'd file paths.

---

**Authored by:** loom-agent, 2026-06-22.
**Ratification required from:** operator (§6 open questions) + Tapestry-agent (cross-agent boundary — they own the destination repo and need to know what's queued).
