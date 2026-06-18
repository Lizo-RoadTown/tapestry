# Runtime observation + auto-promotion: deferred to Tapestry

**Date:** 2026-06-18
**Status:** Ready for outside-agent review. Converged position across four independent verifications.
**Triggered by:** Operator asked whether the self-observer should be watching runtimes + telemetry (it isn't today; it scans static frontmatter on a 6h cron). The natural follow-up — "build a runtime-observer in the-loom now" — was challenged by parallel audits.

## Controlling rules (binding for this proposal)

1. **Tapestry is the canonical product system.** The-loom + Make_Skills are legacy source repos per `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13`.
2. **Don't invest in legacy-source infrastructure that has to migrate.** Per rule 1, every prototype change must declare an import path; building net-new architecture in the-loom doubles the work.
3. **PROBE before asserting.** Cite file:line. The discipline applied throughout this proposal per `feedback_verify_lifecycle_state_count_and_who_writes_status_before_asserting_2026_06_16`.
4. **One pattern, one canonical home.** Per `feedback_one_pattern_one_canonical_home_not_per_repo_copies_2026_06_13` — don't build two observers when one will do.

## Audit context — four independent verifications

This proposal is the synthesis of four parallel audits run 2026-06-17/18:

| Source | Scope | Key finding |
|---|---|---|
| MS-agent fleet audit (`msagent_fleet_audit_synthesis_complete_2026_06_18`) | 4 parallel research agents on Render fleet, memory + observer, UI, telemetry + migration | Observer EMITS but nothing AUTOMATICALLY CONSUMES; 8/9 candidate kinds have no destination handlers; default-agent path emits zero telemetry |
| Critical evaluator of MS-agent's Path B proposal | Attack the proposal | Two fatal flaws: `build_agent()` wrap is category error; Loki-vs-Postgres tradeoff inverted |
| Alternative architectures researcher | 9 alternative patterns scored | Path B was right *direction* but its substrate (Postgres) and home (Tapestry, not the-loom) are wrong |
| Risk surfacer | 12 hidden assumptions in Path B | Self-host blind (Loki = Grafana Cloud only); taxonomy contract break; loop still doesn't close |
| Loom-agent platform audit (`docs/research/2026-06-17-platform-state-audit.md` in the-loom, verified by independent subagent) | 9-service Render fleet, dispatch-promotion gap, memory schema gaps | D2: don't build observer-auto-promotion in the-loom. D3: don't fix dispatch-promotion gap in the-loom. Migrate as gaps; close in Tapestry from day one |

**All four converged on the same position** despite running independently with different prompts.

## What the observer is observing today (PROBE-grounded)

`the-loom/services/self-observer/` is a Render cron (`crn-d8n2q4ernols73d7upbg`, every 6h, plan: starter).

- **Static file scanning** via GitHub API across 4 hardcoded repos (`config.py:44-80`): `claude-skills-marketplace/plugins/liz-patterns`, `Make_Skills/{subagents, core/runtime/subagents, adapters/*}`, `the-loom/{adapters/.../{skills,agents}, skills_private}`, `docs-agent/{skills, agents}`.
- **Shape-classification** via three signal sets (`signal_rules.py:189-271`): agent / inline_tool / skill. Emits candidate when verdict differs from current directory location at confidence ≥ 0.3 (`config.py:164`).
- **Orphan detection** at `signal_rules.py:208-216` queries `TelemetryClient.invocations_30d()` — but the data source is broken because telemetry-ingestion only writes to Loki via stdout (`the-loom/services/telemetry-ingestion/skill_usage_handler.py:68-87`); no Postgres persistence + no read API. So the orphan check is degraded today.

**Effective state:** the observer reliably catches frontmatter+description shape drift. It does not observe runtime invocation patterns, telemetry events, cross-session signals, or session-end upskilling reports.

**40 candidates in production** (per `session_state_self_observer_loop_closed_input_side_2026_06_13`): 21 docs-agent, 16 Make_Skills, 2 claude-skills-marketplace, 1 the-loom. By kind: 34 agent / 5 inline_tool / 1 skill (demotion).

## My original Path B proposal + its fatal flaws

**Path B (as I proposed):** Add a sibling `runtime-observer` cron service in the-loom that reads Loki, emits `kind=orphan / hot_path / degrading` candidates, writes memory synthesis memos. Simultaneously fix `core/runtime/agent.py:116-127` so `build_agent()` wraps `builtin_tools` with telemetry.

**Why this was wrong (verified by 3 independent evaluators + Loom-agent's audit):**

### Fatal flaw 1: `builtin_tools` wrap is a category error

`Make_Skills/core/runtime/agent.py:116-127` shows the default agent's `builtin_tools` are `query_db` + 3 roadmap tools (`update_roadmap_status`, `add_roadmap_item`, `roadmap_overview`). These are langchain `@tool`-decorated functions, **not compiled skills**. Telemetry lives in `Make_Skills/core/skill_making/compiler.py:86-133` and fires only inside `_run` closures produced by `compile_skill_to_tool`. The default agent never goes through `compile_skill_to_tool`. So "wrap builtin_tools with telemetry" would:

- Emit `skill_id=<fake>` events that pollute the loom-side stream
- Break the `skill_id → student_skills` foreign-key assumption
- Require a different telemetry channel than `compile_skill_to_tool` uses, since `_emit_telemetry` needs `skill_id: UUID` + `source_tenant_id` (`compiler.py:178-179`)

The right instrumentation point if default-agent telemetry is needed at all: **emit one event per agent TURN at the FastAPI route level in `Make_Skills/services/api/main.py:260-286`**, not per tool call.

### Fatal flaw 2: Self-host blind

Path B reads from Grafana Cloud Loki. Self-host operators don't have Grafana Cloud. Per `project_two_mode_commitment`, every change must consider both modes. Self-host fallbacks today: structured logs go to stdout only (`the-loom/services/telemetry-ingestion/skill_usage_handler.py:87`). For self-host, runtime-observer would need to read from local Postgres — which doesn't exist for telemetry data.

### Serious flaw 1: Sibling cron duplicates infrastructure that has to migrate

Two crons (`self-observer` + `runtime-observer`) means duplicated `render.yaml` entries with `TELEMETRY_QUERY_URL` + `LOOM_MEMORY_URL` + `ARCHITECTURE_REGISTRY_URL` + `MEMORY_WRITE_AUTH`. The honest version is one service with two scan modes. **And per the canonical-Tapestry framing, neither belongs in the-loom long-term** — both eventually migrate to `tapestry/services/`.

### Serious flaw 2: Taxonomy contract break

`the-loom/services/architecture-registry/models.py:32-42` defines exactly 9 candidate kinds: `skill, inline_tool, external_tool, architecture_pattern, service, machine_support, process, agent, orchestration`. **None of `orphan`, `hot_path`, `degrading` exist.** Path B either extends the enum (cross-service contract change requiring migration + receiver-side parsers + dashboard updates) or repurposes existing kinds (semantically wrong — `candidate_type` is "what should this become?", not "what observation fired?"). The proposal didn't pick.

### Critical flaw: Loop still doesn't close

Per `bridge_closed_end_to_end_2026_06_13`, only `kind=skill` has a destination handler. The other 8 kinds ack-defer with no handler. **Even with a perfect runtime-observer, automatic promotion still hits a wall** unless destination handlers ship for at least `kind=agent` (34/40 of production candidates).

### Loom-agent's parallel call

Independently from Loom-agent's `docs/research/2026-06-17-platform-state-audit.md` (verified at `docs/research/2026-06-17-platform-state-audit-verification.md`):

> **D2:** Don't build observer-driven auto-promotion in the-loom. Lives more cleanly in Tapestry's policy daemon.
> **D3:** Don't fix the dispatch-promotion gap in the-loom. Close it in Tapestry from day one.

Same conclusion via different reasoning.

## Converged position

**Defer all architectural work to Tapestry. Do the cheap synthesis-memo extension now.**

### What lands now (this week, the-loom side)

**Single PR: extend `the-loom/services/self-observer/main.py` to call `memory_write` after each scan run.** Estimated ~50 LOC.

- New module mirroring `candidate_client.py` pattern: `memory_client.py`
- After `_run_once_async` completes its candidate emission loop, build a synthesis with:
  - Top N candidates ranked by confidence
  - Kind distribution + recent drift
  - Suggested next operator action (specific candidates worth promoting now, conditioned on destination-handler availability per kind)
- `memory_write` with stable name `self_observer_synthesis_latest` (idempotent overwrite, NOT append-only) to prevent SessionStart `memory_recall` flooding per risk surfacer's concern #5
- `record_type='project'` with `actor='self-observer'` (distinct from interactive `claude-code` actor)
- Skip-on-empty: if no candidates emitted this run, skip the memory_write to prevent placeholder churn

Every agent's SessionStart `memory_recall` then surfaces "self-observer state" automatically without dashboard visits.

**Plus Loom-agent's A1-A3 housekeeping** (per their `feedback_mcp_is_canonical_not_optional` updated 2026-06-18):
- **A1** (operator's call): pick cold-start strategy — bump `loom-agent-context` to starter ($7/mo) OR keep free + declare keep-warm cron in `render.yaml` so IaC matches reality
- **A2:** delete `loom-mcp-memory-server` orphan from `render.yaml` (verified zero callers; `.mcp.json:5` points at `loom-agent-context.onrender.com/mcp/memory/` directly)
- **A3:** ✅ already done — `feedback_mcp_is_canonical_not_optional` memory updated with current state

### What defers to Tapestry (Phase 6 and adjacent work)

| Capability | Tapestry destination (provisional) | Why deferred |
|---|---|---|
| Runtime-observer service (reads telemetry, emits hot_path/orphan/degrading signals) | `tapestry/services/project-observatory/` (the 24-line Phase-0 stub today) | Phase 6 IS this content; building in the-loom is duplicate work |
| Telemetry Postgres rollup (the substrate runtime-observer queries) | `tapestry/services/telemetry-ingestion/` migration includes the rollup schema | Self-host requires Postgres; Loki-as-store is Grafana-Cloud-locked |
| Auto-promotion / dispatch-promotion automation | `tapestry/services/policy/` daemon variant | Per Loom-agent D2; product question, not hygiene |
| Destination handlers for 8 ack-deferred kinds (`agent`, `inline_tool`, `architecture_pattern`, `service`, `machine_support`, `process`, `orchestration`, `external_tool`) | `tapestry/services/skill-making/` extensions | Loop closure requires these; without them auto-promotion pollutes state regardless of trigger |
| Default-agent telemetry instrumentation (at agent-turn edge, NOT builtin_tools wrap) | `tapestry/engine/agency-to-structure/` | The right instrumentation point is the agent turn, but the wrong place to build it is in `Make_Skills/services/api/main.py` since that's legacy-source |
| Memory schema redesign (hierarchical scopes, provenance chains, etc.) | `tapestry/services/agent-context/` Step 2 schema | Per Loom-agent D1; Tapestry redoes it from scratch |

### Explicitly NOT doing

- Building `runtime-observer` as a sibling cron service in the-loom
- Wrapping `builtin_tools` in `Make_Skills/core/runtime/agent.py:build_agent()`
- Extending the 9-kind candidate enum at `the-loom/services/architecture-registry/models.py:32-42`
- Adding Loki-based queries to the self-observer's degraded orphan-detection path
- Memory schema changes in the-loom

## Open questions for outside-agent review

1. **Cold-start strategy (A1) — operator's call between two options.** Is there a third option the audit missed? E.g., is there a Render auto-scale or per-route warm-pool feature that didn't surface?

2. **Memory write idempotency.** The proposed `self_observer_synthesis_latest` uses overwrite-by-stable-name to prevent flooding. Loom-memory MCP at `the-loom/services/agent-context/storage.py:151-233` accepts upsert by `name` — confirm via PROBE. If the MCP appends rather than upserts, we need a different mechanism (delete-prior + write-new).

3. **Default-agent traffic share is unknown.** Risk surfacer's #10: "If 95% of traffic is per-(tenant, agent_id), the default-agent telemetry gap is cosmetic. If 50% is default, it's load-bearing." We don't have a Render log measurement. **Should this proposal require a 7-day traffic sample before committing to the Tapestry-side instrumentation work?**

4. **Tapestry timing.** This proposal defers ~6 capabilities to Tapestry. Per `tapestry/docs/proposals/2026-06-13-v1-scope-and-roadmap.md`, none of those are in v1 scope. **Are we accepting "no auto-promotion until Tapestry v1 ships" as the answer?** Loom-agent's stance (D2/D3) implies yes; outside agent should confirm or contest.

5. **`loom-keep-warm` cron is undeclared in `render.yaml` but actively running.** Loom-agent's audit found this. If A1 picks option (b) — keep free, declare the cron — what's the exact yaml diff? Does any existing render.yaml NOTE need correction?

6. **The orphan `loom-mcp-memory-server` deletion (A2).** Render API confirms this service exists and is on free tier. Is there a deploy hook, CDN, or other plumbing pointed at the URL that the audit didn't surface? Verification needed before deleting.

7. **`feedback_one_pattern_one_canonical_home_not_per_repo_copies_2026_06_13` consistency check.** The synthesis memo would create a *new* canonical channel for observer outputs (alongside the architecture-registry candidates table). Two channels for the same observer = does this violate "ONE canonical home"? Or are these distinct enough (operator-actionable rows vs. agent-readable synthesis)? Outside agent's judgment.

## Related

- `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13` — the binding rule this proposal applies
- `feedback_one_pattern_one_canonical_home_not_per_repo_copies_2026_06_13` — relevant to question 7
- `bridge_closed_end_to_end_2026_06_13` — proves `kind=skill` path works; reverse-implies 8 other kinds don't
- `session_state_self_observer_loop_closed_input_side_2026_06_13` — input side state; consumer side is what this proposal addresses
- `msagent_fleet_audit_synthesis_complete_2026_06_18` — MS-agent's audit synthesis (source for §"Audit context")
- `feedback_mcp_is_canonical_not_optional` (updated 2026-06-18) — Loom-agent's A3 with current cold-start state
- `lesson_self_observer_gap_revealed_by_skill_mislabel_audit_2026_06_13` — the meta-rule that built the existing self-observer; relevant because runtime-observer would be the next instance of the same rule applied
- `feedback_verify_lifecycle_state_count_and_who_writes_status_before_asserting_2026_06_16` — discipline applied throughout
- The-loom audit + verification: `the-loom/docs/research/2026-06-17-platform-state-audit.md` and `the-loom/docs/research/2026-06-17-platform-state-audit-verification.md`

## Outside-agent review checklist

The reviewing agent should evaluate this proposal against:

- [ ] Does the converged position contradict any binding feedback memory we missed?
- [ ] Is the "fatal flaw 1" analysis (`builtin_tools` category error) correct? PROBE `Make_Skills/core/runtime/agent.py:116-127` + `Make_Skills/core/skill_making/compiler.py:86-133`.
- [ ] Is the "fatal flaw 2" analysis (self-host blind) correct? PROBE `the-loom/services/telemetry-ingestion/skill_usage_handler.py:68-87` + assess self-host fallback options.
- [ ] Are the 7 open questions in §Open questions actually open, or are some resolvable from existing source-of-truth?
- [ ] Is the ~50 LOC memory_write extension the right cheap-thing-now, or is even that too much investment in legacy source code?
- [ ] Is the Tapestry deferral schedule realistic, or does the operator need at least one of the deferred capabilities before Tapestry v1 ships?
