# Tapestry v1 — scope, shape, and roadmap

**Date:** 2026-06-13 (revised same day per operator framing correction)
**Status:** Draft proposal, awaiting operator (Liz) arbitration
**Purpose:** Self-contained briefing document for an outside agent — describes what Tapestry is, what v1 ships, the runtime architecture, and the sequenced migration plan.

This document is the synthesis of two parallel planning sessions (one by the engine-side legacy-source steward working in `Lizo-RoadTown/Make_Skills`, one by the platform-side legacy-source steward working in `Lizo-RoadTown/the-loom`), revised by the operator's 2026-06-13 framing rule that **Tapestry is the canonical product system; the-loom and Make_Skills are legacy source repos to be migrated and retired**. Source memos are `tapestry_v1_plan_synthesized_proposal_2026_06_13`, `loom_agent_tapestry_planning_synthesis_2026_06_13`, and the binding correction `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13`.

## Controlling frame (binding for this document)

1. **Tapestry is the canonical product system.**
2. **the-loom and Make_Skills are legacy prototype/source repos.** They will be migrated into Tapestry and retired after parity.
3. **Every capability described below is a Tapestry product capability.** Some are currently prototyped in the legacy repos. That is temporary.
4. **Customers experience ONE product: Tapestry.** Not "Tapestry plus loom." The differentiation is the loop: *agency becomes structure*.
5. **No final runtime dependency on the legacy repos as separate systems.** When all useful capabilities have migrated, the legacy repos are archived or made read-only.
6. **Migration remains incremental.** No big-bang. But the destination is not optional.

---

## 1. What Tapestry is

**Tapestry is the enterprise monorepo of a project-intelligence platform that watches a coding agent work, captures the patterns it repeatedly produces, decides which deserve to become reusable structure, compiles approved patterns into runnable skills, and feeds them back to future agent runs.**

The core loop, in five steps:

1. **Observe** — a local observer reads what the agent did during a session (tool calls, memory writes, session-end self-report).
2. **Surface candidates** — repeated patterns become *candidates* in a registry (a skill, an inline tool, an architecture pattern, a service, ...). There are 9 candidate kinds.
3. **Decide** — a policy service holds promote/hold/reject decisions for each candidate. Audit-immutable.
4. **Compile** — an engine ingests promoted candidates and emits runnable artifacts (today: `SKILL.md` → `StructuredTool` via the skill-compiler).
5. **Use + measure** — the engine emits telemetry on every invocation; that feeds back into the observer and dashboard.

The agent that uses Tapestry is the same agent that helped grow it. The platform compounds.

**Today (2026-06-13) the loop closes end-to-end for `kind=skill`.** A candidate created in the dashboard can be dispatched to the engine, compiled into a runnable skill, and the registration acknowledged back. Verified at 07:09 UTC. The other 8 candidate kinds ack-defer (engine acknowledges receipt but hasn't built compilation for that kind yet).

## 2. Tapestry and the legacy source repos

Tapestry was spawned on 2026-06-12 as a skeleton — no code imported yet. Migration is incremental: prototype repos remain active during pre-migration stabilization, but the destination is not optional. Every prototype change should carry a declared import path into Tapestry.

The operator's standing rule from 2026-06-12: *"we keep building in the [prototype] repo until the new one it built fully, a lot of the information isn't yet known. I am still experimenting."* That rule governs **pace** (incremental, not big-bang). It does **not** make the prototypes permanent product boundaries. They aren't.

### Legacy source repos

| Repo | Role | Current state | Disposition |
|---|---|---|---|
| `Lizo-RoadTown/the-loom` | Legacy source for: agent-context MCP, project-registry, project-observatory, telemetry-ingestion, architecture/candidate-registry, policy, audit patterns, dashboard, Claude Code discipline plugin, scaffolder/CLI source material, auth bridge, Grafana integration, deploy config | Phases 0-5 live + deployed on Render; Phase 6 (operator dashboard) in flight | Source-stabilize → migrate per capability → freeze legacy → archive |
| `Lizo-RoadTown/Make_Skills` | Legacy source for: agency-to-structure engine, skill-compiler, bridge receiver, skill-making services, project-type adapters, default template seeds, runtime/tool telemetry | Working skill-compiler; bridge receiver shipped + smoke-verified 2026-06-13 | Source-stabilize → migrate per capability → freeze legacy → archive |
| `Lizo-RoadTown/loom-platform` | Consumer seed | Empty | Will spawn from Tapestry templates |
| `Lizo-RoadTown/claude-skills-marketplace` | Claude Code plugin distribution endpoint | Publishes `make-skills-discipline`; `loom-discipline` sourced from `the-loom/adapters/claude-code/` directly | Stays as distribution endpoint; sources move to Tapestry's `integrations/claude-code/discipline/` |
| Various consuming projects (Hub, SDE_Extraction, humancensys-app, ...) | Demand-side — projects that USE the platform | Each in own repo | Consume Tapestry via templates + SDK |

The 12-step build order (engine first, UI last) is captured in [`tapestry/ROADMAP.md`](../../ROADMAP.md). This document covers the v1 product slice that's achievable in 4-8 weeks.

## 3. The shape — runtime architecture for v1

All services below are Tapestry-owned. (`engine/` runs Tapestry's skill-compiler + bridge receiver; today's code is sourced from Make_Skills but the destination is Tapestry.)

```text
                                              External
                                              ────────
                                                                  Stripe
                                                                  WorkOS / AuthKit
                                                                  Grafana Cloud LGTM
   ┌──────────────────────────────────────────────────┐                       ▲
   │                  PUBLIC INTERNET                 │                       │
   └──────────────────────────────────────────────────┘                       │
        ▲                       ▲                    ▲                        │
        │                       │                    │                        │
   tapestry.io          docs.tapestry.io      app.tapestry.io           (forwarded)
   (marketing)          (docs)                (dashboard, Next.js)            │
        │                       │                    │                        │
        ▼                       ▼                    ▼                        │
   ┌──────────┐           ┌──────────┐        ┌──────────────┐                │
   │ apps/    │           │ apps/    │        │  apps/       │                │
   │marketing │           │  docs    │        │ web-dashboard│                │
   └──────────┘           └──────────┘        └──────┬───────┘                │
   (Vercel)               (Vercel)            (Vercel)                        │
                                                     │                        │
                                                     │ HTTPS                  │
                                                     ▼                        │
                                ┌────────────────────────────────────┐        │
                                │  api.tapestry.io   (REST gateway)  │        │
                                │  • JWT validation                  │        │
                                │  • tenant_id resolution            │        │
                                │  • injects X-Tapestry-Tenant       │        │
                                │  • routes → internal services      │        │
                                └────────────────────────────────────┘        │
                                                     │                        │
        ┌────────────────────────────┬───────────────┼───────────────┐        │
        │                            │               │               │        │
        ▼                            ▼               ▼               ▼        │
┌──────────────────┐   ┌────────────────────┐ ┌──────────┐  ┌─────────────┐   │
│ architecture-    │   │  project-          │ │  policy/ │  │ telemetry-  │   │
│  registry/       │   │   registry/        │ │          │  │ ingestion/  │   │
│ (Path A+B        │   │  (projects,        │ │ (promote │  │ (HMAC       ├───┘
│  candidates,     │   │   tenants,         │ │  / hold  │  │  /skill-    │
│  bridge dispatch │   │   memberships)     │ │  / reject│  │   used      │
│  → engine)       │   │                    │ │  / audit)│  │   receiver) │
└────────┬─────────┘   └────────────────────┘ └──────────┘  └─────────────┘
         │                       ▲
         │ POST /bridge/         │
         │  promotion-candidate  │
         │ (HMAC-signed)         │
         ▼                       │
   ┌─────────────────────┐       │
   │  engine.tapestry.io │       │
   │  (Tapestry engine/) │       │
   │  • skill-compiler   │       │
   │  • bridge receiver  │       │
   │  • adapters/        │       │
   └──────────┬──────────┘       │
              │                  │
              │ POST /skill-     │
              │  registered      │
              │ (HMAC-signed)    │
              └──────────────────┘

                          ╔════════════════════════╗
                          ║  mcp.tapestry.io       ║◄────  External MCP clients
                          ║  agent-context/        ║       (Claude Code,
                          ║  (memory MCP, NOT      ║        Cursor, Codex)
                          ║   proxied via REST     ║
                          ║   gateway — stateful)  ║
                          ╚════════════════════════╝
                                     │
                                     ▼
                          ┌───────────────────────┐
                          │  Render Postgres      │
                          │  (one DB, schemas:    │
                          │   arch_registry.*     │
                          │   policy.*            │
                          │   project_registry.*  │
                          │   agent_context.*     │
                          │   platform.* (shared, │
                          │    tenant_id_mapping) │
                          │  RLS via              │
                          │   app.tenant_id GUC)  │
                          └───────────────────────┘


             ┌──────────────────────── INPUT SIDE OF THE LOOP ───────────────────────┐
             │                                                                       │
             │   ┌─────────────────────┐                                              │
   GitHub ◄──┤   │  self-observer/     │  every 6h                                    │
   (4 repos) │   │  (Render cron)      ├───┐  signal-detection rules                  │
   skills/   │   │                     │   │  walk skills/ agents/ tools/             │
   agents/   │   │                     │   │  emit candidates of category drift       │
   tools/    │   └─────────────────────┘   ▼                                          │
             │                       POST /candidates                                 │
             │                       source_path="path_b"                             │
             │                       kind=agent/inline_tool/skill/process             │
             │                                                                       │
             │                                ▼                                       │
             │                     architecture-registry  ──►  upskilling dashboard   │
             │                     (existing service)         (operator: promote /    │
             │                                                  hold / reject)        │
             │                                                                       │
             └───────────────────────────────────────────────────────────────────────┘


             ┌──────────────────────── OUTPUT SIDE OF THE LOOP ──────────────────────┐
             │                                                                       │
             │   architecture-registry  ──►  policy  ──►  bridge dispatcher          │
             │   (candidate promoted)        (decision)   (HMAC POST)                │
             │                                                  │                    │
             │                                                  ▼                    │
             │                                            engine/skill-compiler      │
             │                                            (compiles to runnable)     │
             │                                                  │                    │
             │                                                  ▼                    │
             │                                            ack callback               │
             │                                            (status='promoted')        │
             │                                                                       │
             └───────────────────────────────────────────────────────────────────────┘

  Loop status: 2026-06-13 — both sides green for kind=skill end-to-end.
                          INPUT side observes platform's own registries.
                          OUTPUT side compiles approved candidates.
                          Other 8 kinds ack-defer until per-kind handlers ship.
```

**Five runtime services in v1**, not the skeleton's nine. Two of the skeleton slots (`candidate-registry`, `audit-log`) collapse into siblings because their data + transactions already live with another service in production.

| Service | Runtime role | Public? | Owns DB schema |
|---|---|---|---|
| `architecture-registry/` | Candidates + dispatcher + bridge handler. **Absorbs `candidate-registry/` slot** — they share a table. | Public via REST gateway | `arch_registry.*` |
| `agent-context/` | Memory MCP. Stateful — has its own subdomain because MCP is the protocol. | Public direct (mcp.tapestry.io) | `agent_context.*` |
| `project-registry/` | Tenants, projects, machine registrations. | Public via REST gateway | `project_registry.*` |
| `policy/` | Promote/hold/reject decisions. Audit-immutable. | Internal only (called by gateway after decision UI) | `policy.*` |
| `telemetry-ingestion/` | HMAC `/skill-used` receiver. Forwards to Grafana Cloud LGTM. | Internal only (engine calls it) | (no schema; forwards) |

**Skill-making** + **audit-log** ship as code packages inside `architecture-registry`'s pod (single deploy, two endpoints) until traffic justifies splitting. **Project-observatory** stays as a `services/` directory but isn't a deployed Render service in v1 — its read-side query API is unbuilt.

## 4. v1 scope — what ships, what doesn't

**Ships in v1:**
- Operator dashboard (candidates, decisions, evidence, promotion actions)
- Agent-context MCP (cross-session, cross-project memory)
- Skill-compiler (`SKILL.md` → runnable `StructuredTool` via langchain)
- Skill-making bridge (candidate → engine → compiled skill → ack), for `kind=skill`
- Multi-tenant signup + JWT auth (WorkOS AuthKit)
- Per-tenant telemetry ingest via HMAC receiver
- One templated consuming-project type (software-project)
- Cross-platform CLI for `tapestry init <project>`
- Marketing site + docs site (Vercel)

**Does NOT ship in v1:**
- Per-tenant Grafana-embedded telemetry dashboards (deferred to v2)
- Compilation handlers for the other 8 candidate kinds (architecture_pattern, inline_tool, external_tool, service, machine_support, process, agent, orchestration) — engine ack-defers them
- Admin console (separate app, future)
- `services/audit-log/` as a separate deploy (lives inside architecture-registry's pod)
- `services/project-observatory/` read-side query API (24-line stub today)
- Stripe billing UI (post-v1 acceptable; meters can be wired without UI)
- VSCode extension, Codex CLI integration, GitHub App, telemetry → raw OTel collector
- Demotion review (Step 11 of the 12-step build order)
- Classroom / research / operations adapter variants (only `development/` ships v1)

## 5. The roadmap — sequenced migration into Tapestry

Two prep PRs first (in the legacy source repos, reversible), then eight migration steps. Each migration step is its own PR, owned by a specific role, with explicit upstream dependencies. **Tapestry-agent (spawn now) is the destination owner across all steps; the legacy-source stewards (loom-agent, ms-agent) stabilize sources pre-migration.**

### Prep PRs (in legacy source repos, before Tapestry imports begin)

**PR-prep-1 — Engine telemetry collector hook** *(legacy source: Make_Skills, ~1 day, ms-agent)*
- `Make_Skills/services/skill_making/telemetry_sender.py` already exists at 160 lines with HMAC send-path + retry. The module docstring (lines 17-20) flags the missing piece as the runtime-loop emission hook, not the sender.
- This PR wires the agent loop's tool-invocation events → existing `telemetry_sender.send()` → the live `/skill-used` endpoint (currently hosted by the-loom's telemetry-ingestion service, which is the legacy source for Tapestry's `services/telemetry-ingestion/`).
- Generates real telemetry data before any Tapestry migration. The endpoint moves into Tapestry during migration; the sender continues working unchanged.

**PR-prep-2 — Loom-side defensive prep** *(legacy source: the-loom, ~1 day, loom-agent)*
- `the-loom/adapters/claude-code/loom-discipline/.claude-plugin/plugin.json` hardcodes `https://loom-agent-context.onrender.com` for the loom-memory MCP. Same URL hardcoded again in `scripts/session_start.py:77`.
- Extract to a config resolution order: `$TAPESTRY_AGENT_CONTEXT_URL` → `tapestry.config.json` → marketplace-published default. (Name uses `TAPESTRY_` not `LOOM_` because the destination is Tapestry; the legacy URL stays as the default until migration cuts over.)
- Also: extract `auth_bridge.py` (verbatim-duplicated across 4+ legacy services per `services/architecture-registry/auth_bridge.py:11-14`'s own comment threshold) into a `the-loom/packages/auth/` Python package as the pre-migration shape that `tapestry/packages/auth/` will inherit.
- Both moves reversible inside the-loom; both make the Tapestry lift mechanical.

### Migration steps (into Tapestry)

All steps are Tapestry-agent-owned (destination). The "executor" column names the legacy-source steward who carries out the migration PR. Once the capability reaches parity in Tapestry, Tapestry-agent freezes the legacy version.

| # | Description | Destination owner | Executor | Depends on | Estimated effort |
|---|---|---|---|---|---|
| 1 | **Auth consolidation.** Import `packages/auth/` into Tapestry + add `platform.tenant_id_mapping` table to shared Postgres. Establishes the gateway's JWT-validation + tenant-resolution layer. | Tapestry-agent | loom-source steward | PR-prep-2 done | M (2-3 PRs) |
| 2 | **Agent-context MCP import.** Move `services/agent-context/` source from the-loom into Tapestry. Wire `mcp.tapestry.io` subdomain (direct, NOT through REST gateway). Freeze the legacy version after smoke. | Tapestry-agent | loom-source steward | Step 1 done, PR-prep-2 URL externalization done | S (1 PR) |
| 3 | **Project-registry + signup endpoint.** Import + add tenant signup, email verify, project CRUD endpoints. | Tapestry-agent | loom-source steward | Steps 1, 2 done | M (2-3 PRs) |
| 4 | **Engine import: skill-compiler + skill-making receiver.** Move `Make_Skills/core/skill_making/` → `tapestry/engine/skill-compiler/`. Move `Make_Skills/services/skill_making/` → `tapestry/services/skill-making/`. Bridge contract preserved. Freeze the legacy versions after smoke. | Tapestry-agent | ms-source steward | Steps 1, 2 done | M (2-3 PRs) |
| 5 | **Templates + CLI.** Import `templates/software-project/` + write a minimal `packages/cli` that scaffolds new consuming projects. Replaces today's PowerShell-only scaffolder. | Tapestry-agent | ms-source steward | Steps 1-4 done | M (3-4 PRs) |
| 6 | **Web dashboard v1.** Import `apps/web-dashboard/` from the-loom. Wait until in-flight Phase 6 work is mature in the legacy source. Wire to `api.tapestry.io`. | Tapestry-agent | loom-source steward | Steps 2-4 done + Phase 6 maturity | L (4-6 PRs) |
| 7 | **Architecture-registry + policy import.** Move `services/architecture-registry/` (absorbs candidate-registry slot) + `services/policy/`. Wire `infra/deploy/render.yaml`. | Tapestry-agent | loom-source steward | Step 4 done | L (4-6 PRs) |
| 7a | **Telemetry-ingestion (w/ Postgres rollup + read API) + project-observatory import.** Q4 RATIFIED 2026-06-18: the engine lift (Step 4) is **NOT** blocked on telemetry, but the telemetry Postgres rollup **MUST land before runtime observation/decomposition is considered active** (self-host parity + the decomposer's data source). Rollup is in v1, ahead of any promotion automation. | Tapestry-agent | loom-source steward | Step 4 done | M-L (rollup is net-new) |
| 8 | **Discipline plugin → `integrations/claude-code/discipline/loom/`.** ONE flavor only — `make-skills-discipline` retired 2026-06-14 (Option A). Tapestry CI publishes to marketplace repo (distribution endpoint, not source). | Tapestry-agent | loom-source steward | Step 2 done (so URL config resolves to Tapestry MCP) | M (2-3 PRs) |

**Critical-path graph:** Step 1 blocks everything. Steps 2, 3, 4 parallel after Step 1. Steps 5, 6, 7 after Step 4. Steps 6 + 7 are the v1 ship gate. Step 8 can interleave once Step 2 is done.

**Estimated v1 ship**: 4-8 weeks of focused work from prep-PR start, assuming the two agents continue in parallel and Phase 6 dashboard work matures during that window.

## 6. Key product + technical decisions

### v1 product — Tapestry

One product, one name. The v1 surfaces (dashboard + agent-context MCP + skill-making bridge + telemetry ingest) are all Tapestry surfaces. No sub-SKUs in v1.

**Marketing lead:** the loop. *Tapestry observes agent work, captures repeated patterns, surfaces candidates, lets the operator decide, compiles approved skills, measures reuse, and feeds structure back into future work.* **Agency becomes structure.** That is the differentiation — not "another memory backend," not "another compiler," not "Tapestry plus loom."

### Customization model — hybrid

- **White-label config** (`config/tapestry.config.ts`): logo, color, copy, domain
- **Plugin API** (`packages/sdk/plugins/`): adapter hooks for project-type-specific behavior
- **Tagged stable-LTS branch as fork escape hatch**: enterprises can fork at LTS tags and bring their own infra

Customization stays outside core. Preserves the parallel-build framing (changes to consumer setups don't churn core).

### Auth — WorkOS AuthKit

SSO + SCIM free, cheaper than Clerk at scale, users live in our DB. Self-host fallback via `AUTHKIT_DISABLED=true`.

### Billing — Stripe, post-v1

Tier shape: free / $29 dev / $99 seat / Enterprise-contact. Meter on tool invocations + active-agent-months. `BILLING_ENABLED=false` in self-host. UI deferred; meters wired in v1.

### Telemetry + observability — Tapestry product capability

Telemetry-ingestion, project-observatory, agent-context memory, and Grafana integration are **Tapestry product capabilities**, not separate-system dependencies. They are currently prototyped in the-loom; during migration the-loom remains live as the source/compatibility provider — temporarily. On parity, the legacy versions freeze.

The bridge HMAC contract is the engine→ingest interface; it survives the consolidation because both endpoints will run inside Tapestry once migration completes (`engine/` POSTing to `services/telemetry-ingestion/` inside the same monorepo).

The prior framing ("telemetry stays loom-side" / "Tapestry subscribes to loom") is superseded. Customers experience ONE product: Tapestry observability is Tapestry's, not a sidecar dependency.

### Database — shared Postgres, per-service schemas

One Render Postgres instance. Per-service schemas (`arch_registry.*`, `policy.*`, `project_registry.*`, `agent_context.*`). Shared `platform.tenant_id_mapping` readable by all. Cross-service reads go through HTTP, NOT cross-schema SQL. RLS via `set_config('app.tenant_id', ...)` GUC per tenant. Unlocks per-service DB extraction later without contract change.

### Discipline plugins — hybrid disposition

Tapestry owns sources at `integrations/claude-code/discipline/{loom,make-skills}/`. The marketplace repo (`claude-skills-marketplace/plugins/`) becomes generated output, populated by a Tapestry CI step. Single source of truth in Tapestry; distribution surface unchanged for end users.

## 7. Open questions for the outside agent

The two internal agents have settled on the above. These are the points where outside perspective would be most useful:

1. **Service granularity.** v1 ships 5 deployed services + 2 in-pod sub-services. Is this the right granularity for an early-stage enterprise platform, or should v1 ship fewer-larger services (e.g., merge policy into architecture-registry too)?
2. **Tenant isolation strategy.** Shared Postgres with per-service schemas + RLS via `app.tenant_id` GUC. Is this acceptable for the enterprise buyer, or do we need per-tenant DBs for any of the v1 services (especially `agent-context`, where memory content is highest-sensitivity)?
3. **Compilation deferral for 8/9 candidate kinds.** Engine ack-defers all candidate kinds except `skill`. Is shipping v1 with one working kind defensible as MVP, or does the platform need at least 2-3 working kinds to demonstrate the loop?
4. **Telemetry / observability migration pacing.** Telemetry-ingestion + project-observatory are Tapestry product capabilities currently prototyped in the-loom. They migrate into Tapestry per the doctrine. Open question: which step in the roadmap do they move at? Today they're not in the v1 service list (Step 7 carries arch-registry + policy + render.yaml). Should they migrate as part of Step 7, or as a new Step 7a/7b, or earlier (e.g., bundled with Step 4 so the engine-side telemetry-sender PR has a Tapestry endpoint to target)?
5. **Marketing site = v1 vs v2.** Building `apps/marketing/` adds 1-2 weeks. Defer to v2 and rely on a static landing page off `app.tapestry.io`?
6. **Build order risk.** Step 1 (auth) is the universal blocker. Three agents in parallel + the operator could each propose changes to auth design simultaneously and create contradictory work. Is the team-agreement strong enough to prevent this?
7. **Engine telemetry collector — prep PR or migration PR?** The current plan does it as PR-prep-1 in Make_Skills before migration starts, generating real data. Alternative: do it as part of Step 4 once the engine is in Tapestry. Trade-off: 4-8 weeks of zero telemetry vs. ~1 day of work upfront.

## 8. What this document does NOT cover

- **The full 12-step build order** (lives in [`tapestry/ROADMAP.md`](../../ROADMAP.md))
- **Bounded-context details** for each service (lives in [`tapestry/docs/architecture/UMBRELLA.md`](../architecture/UMBRELLA.md))
- **Per-prototype-repo retirement strategy** (lives in [`tapestry/docs/migration/what-to-retire.md`](../migration/what-to-retire.md))
- **Schema-level migration mappings** (lives in [`tapestry/docs/migration/import-map.md`](../migration/import-map.md))
- **Security model details** (lives in [`tapestry/docs/security/`](../security/))

This document IS:

- The v1 product slice (what ships)
- The runtime architecture (the diagram)
- The migration sequencing (prep PRs + 7 + 8 steps)
- The open questions worth outside review

## 9. Sources

- Loom-memory record `ms_agent_tapestry_planning_kickoff_2026_06_13` — engine-side agent's planning announcement
- Loom-memory record `tapestry_v1_plan_synthesized_proposal_2026_06_13` — engine-side agent's 4-agent synthesis
- Loom-memory record `loom_agent_tapestry_planning_engagement_2026_06_13` — platform-side agent's engagement
- Loom-memory record `loom_agent_tapestry_planning_synthesis_2026_06_13` — platform-side agent's 3-agent synthesis + counter-proposal (this document is its prose form)
- Loom-memory record `bridge_closed_end_to_end_2026_06_13` — bridge smoke verification
- Loom-memory record `feedback_tapestry_parallel_build_not_pause_and_migrate_2026_06_12` — the binding operator rule

All loom-memory records readable via the MCP at `https://loom-agent-context.onrender.com/mcp/memory/`.

— Tapestry planning, 2026-06-13
