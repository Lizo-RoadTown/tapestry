# Runtime observation + auto-promotion: deferred to Tapestry

**Date:** 2026-06-18 (v2 revised same day after outside review + Loom-agent's correction)
**Status:** v2 — outside review and Loom-agent audit aligned. Five fixes + decomposition map integrated. Durable architectural record lives at [`tapestry/docs/research/2026-06-18-outside-review-runtime-observation-followup.md`](../research/2026-06-18-outside-review-runtime-observation-followup.md); this proposal is the operator-facing wrapper.
**Triggered by:** Operator asked whether the self-observer should be watching runtimes + telemetry (it isn't today; it scans static frontmatter on a 6h cron). The natural follow-up — "build a runtime-observer in the-loom now" — was challenged by parallel audits.

**Canonical source:** the [followup artifact](../research/2026-06-18-outside-review-runtime-observation-followup.md) is the durable form. This proposal aligns with it; if they diverge, the followup wins.

## Controlling rules (binding for this proposal)

1. **Tapestry is the canonical product system.** The-loom + Make_Skills are legacy source repos per `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13`.
2. **Don't invest in legacy-source infrastructure that has to migrate.** Per rule 1, every prototype change must declare an import path; building net-new architecture in the-loom doubles the work.
3. **PROBE before asserting.** Cite file:line. The discipline applied throughout this proposal per `feedback_verify_lifecycle_state_count_and_who_writes_status_before_asserting_2026_06_16`.
4. **One pattern, one canonical home.** Per `feedback_one_pattern_one_canonical_home_not_per_repo_copies_2026_06_13` — don't build two observers when one will do.

## Audit context — corrected accounting

**Earlier framing claimed "four independent verifications converged." That overclaimed.** Four of the five inputs were MS-agent-dispatched audits binding to the same `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13` rule. Only Loom-agent's audit was actually independent. The first outside reviewer + Loom-agent's audit + Liz's external reviewer's followup form the actual independent set.

| Source | Independence | Scope | Key finding |
|---|---|---|---|
| MS-agent fleet audit (`msagent_fleet_audit_synthesis_complete_2026_06_18`) | Self-dispatched | 4 parallel research agents on Render fleet, memory + observer, UI, telemetry + migration | Observer EMITS but nothing AUTOMATICALLY CONSUMES; 8/9 candidate kinds have no destination handlers; default-agent path emits zero telemetry |
| MS-agent's 3 sub-evaluators (critic / alternatives / risk surfacer) | Self-dispatched | Attack + alternatives + hidden assumptions in v1 Path B | Two fatal flaws: `build_agent()` wrap is category error; Loki-vs-Postgres tradeoff inverted; self-host blind |
| **Loom-agent platform audit** (`the-loom/docs/research/2026-06-17-platform-state-audit.md`, verified at `…-verification.md`) | **Independent** | 9-service Render fleet, dispatch-promotion gap, memory schema gaps | **A3 (line 405): FIX dispatch-promotion gap IN-PLACE in the-loom (~1h); D2/D3 are housekeeping items (keep-warm claim correction + service-ID typo). §B (lines 408-412) names the actual Tapestry deferral list — memory schema, dashboard redesign, project-observatory build-out, telemetry-ingestion query API — and dispatch-promotion is explicitly NOT in it.** |
| **First outside reviewer** (`tapestry/docs/research/2026-06-18-outside-review-of-runtime-observation-proposal.md`) | **Independent** | Review of v1 proposal | Accept-with-fixes. Spine sound; five fixes needed. |
| **Liz's external reviewer followup** (consolidated at `tapestry/docs/research/2026-06-18-outside-review-runtime-observation-followup.md`) | **Independent** | Three architectural sub-questions Loom-agent raised | Decomposition map needed; automation = policy-bounded cascade; falsification = `actionable_backlog_count` metric |

**Actual converged position:** runtime-observer + auto-promotion architecture defers to Tapestry. Dispatch-promotion mechanics fix lands NOW in the-loom (per Loom-agent's actual A3).

## What the observer is observing today (PROBE-grounded)

`the-loom/services/self-observer/` is a Render cron (every 6h, plan: starter).

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

### Loom-agent's parallel call — corrected attribution (Fix 1 from outside review followup §1.2)

**The v1 of this proposal mis-cited Loom-agent's audit.** Their actual recommendations from `the-loom/docs/research/2026-06-17-platform-state-audit.md`:

- **A3 (line 405, verbatim):** *"Close dispatch-promotion gap per `2026-06-16-candidate-lifecycle-verified.md` Option B (in-service auto-trigger at PATCH time)... ~1 hour code + tests"* — **FIX IN-PLACE in the-loom, NOT defer.**
- **D2 (line 422):** "correct any keep-warm-dropped claim in render.yaml or memory" (housekeeping memory correction)
- **D3 (line 423):** "record the service-ID typo: the cited service ID is telemetry-ingestion, not agent-context" (housekeeping memory correction)

The "Don't fix in the-loom; close in Tapestry" framing v1 attributed to D3 doesn't exist in the audit. Loom-agent's actual §B (DON'T FIX in the-loom, lines 408-412) names memory schema, dashboard redesign, project-observatory build-out, telemetry-ingestion query API — dispatch-promotion is explicitly NOT in that list.

**Correct framing:** Independent audits confirm the `builtin_tools` telemetry flaw, self-host telemetry flaw, and taxonomy issue. Loom-agent did NOT independently recommend deferring the dispatch-promotion gap; Loom-agent recommended fixing it IN the-loom (~1 hour, in-service auto-trigger). The convergence around deferral applies to runtime-observer + auto-promotion ARCHITECTURE, NOT to the dispatch-promotion MECHANICS gap.

This correction is load-bearing: the v1 proposal's "what lands now" omitted A4 (dispatch fix) as a result of the miscitation. Adding it back below.

## The missing piece — Observation → Decomposition map (added per outside reviewer §2)

**The fatal flaw is not automatic updating. The fatal flaw is promoting observed behavior AS ONE THING when it's always a mix.** Most repeated behavior is `trigger + deterministic steps + judgment step + side effect + report`. Asking "is this an agent or skill or tool?" is the wrong question. The right question is:

> When repeated behavior appears, how does the system decide which **parts** become what?

### Core rule

**A repeated behavior is not promoted as a whole. It is decomposed into artifact candidates.**

| Part of the observed pattern | Becomes |
|---|---|
| Event-triggered parts | Plugin / hook |
| Deterministic parts | Tool |
| Judgment parts (situational reasoning) | Skill |
| Judgment parts (ongoing responsibility across calls) | Agent |
| Multi-step sequences | Workflow |
| Cross-component coordination | Orchestration |
| Side effects + durable shared need | Service |
| Approval / risk rules | Policy |
| Stable facts / preferences | Memory / lesson |

### Worked example

**Observation:** Plugin keeps firing because session-end upskilling reports are missing.

**Wrong answer (v1 framing):** Promote the whole pattern as one agent.

**Right answer (decomposition):** 6 distinct artifact candidates from one observation:
- Plugin candidate: Stop-hook checker (detects whether report ran)
- Tool candidate: transcript-to-upskilling-report generator
- Workflow candidate: session-end upskilling pass
- Policy candidate: substantive sessions require a report before closure
- Agent candidate: promotion-review agent — only if repeated judgment remains
- Telemetry signal: missing-upskilling-report

Each gets its own lifecycle, evidence threshold, and automation ceiling.

### Semantic separation — no schema change needed in the-loom

| Field | Meaning | Where it lives |
|---|---|---|
| `candidate_kind` | "What this may become" | Existing 9-value enum at `the-loom/services/architecture-registry/models.py:32-42`; semantically correct as-is |
| `observation_kind` | "Why it was noticed" | NEW enum to be introduced in Tapestry: `runtime_usage`, `frontmatter_drift`, `repeated_failure`, `cross_project_recurrence`, etc. |
| `observation.signals[]` | The specific evidence: `hot_path`, `orphaned`, `degrading`, `deterministic_substep`, `judgment_required`, `permission_required`, `repeated_manual_step`, `stable_output` | Array of typed signals |

**The-loom side gets a 1-line docstring fix only.** At `the-loom/services/self-observer/candidate_client.py:30`, the comment using `candidate_type=process` to encode "orphaned" gets labeled as a SEMANTIC PLACEHOLDER until Tapestry introduces first-class `observation_kind`. No schema migration in the-loom. Full split happens in Tapestry only.

### Skill vs agent disambiguation (per outside reviewer §3.1)

This is the exact category drift the loop is supposed to prevent. The disambiguation rule:

- **Skill** if scope is bounded to a single call site
- **Agent** if scope is ongoing responsibility across calls

Without this rule the decomposer makes the same mistake the existing observer makes today.

### Suggested Tapestry component

**`tapestry/engine/observation-decomposer/`** OR `tapestry/services/candidate-decomposer/` (open Q8).

Responsibilities:
1. Accept observation signals from plugins, runtime telemetry, session-end reports, memory writes, tool calls
2. Identify repeated behavior across observations
3. Split into deterministic / judgment / event-triggered / infrastructure / governance parts
4. Emit one or more artifact candidates
5. Attach evidence + recommended automation level
6. Send candidates to architecture-registry
7. **NEVER activate live behavior directly**

### Correct Tapestry product framing

Don't call the future system "auto-promotion." Replace with:

> **Automatic observation and decomposition.**
> **Policy-gated promotion.**
> **Staged activation.**
> **Measured reuse.**
> **Rollback if wrong.**

A system can only be called "auto-promotion" once it has observation, decomposition, policy, staging, activation, telemetry, AND rollback.

## Converged position

**Defer the runtime-observer + observation-decomposer + auto-promotion architecture to Tapestry. Land the dispatch-promotion mechanics fix + synthesis-memo extension + housekeeping NOW in the-loom (per Loom-agent's actual A3 + outside reviewer's §1.3 fix).**

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

**Critical framing (per outside reviewer):** This synthesis memo is a **generated read-model for agents at session start.** It is explicitly:
- NOT the source of truth (the `candidates` table is)
- NOT an auto-promotion path (no activation triggers)
- NOT a decomposition (today's self-observer still emits single-kind candidates; full decomposition is Tapestry work)
- ONLY a visibility patch

Source-of-truth channels remain: candidates table at architecture-registry, policy_decisions, audit log, telemetry/event store.

**A4. Close the dispatch-promotion automation gap** (per Loom-agent's actual A3 + outside reviewer §1.3):

In `the-loom/services/architecture-registry/main.py:206-211`, after the PATCH that sets `status='promotion_requested'`, fire-and-forget `promote_dispatcher.dispatch_promotion`. Add kind-aware filter (skill only, until other handlers exist per `bridge_closed_end_to_end_2026_06_13`). ~1h code + tests. Implementation survives Tapestry migration unchanged.

**Why this matters:** without A4, every operator Promote click on a skill candidate dead-ends at `promotion_requested` for the duration of the Tapestry deferral. Synthesis memo gives agents context; A4 makes operator clicks actually deliver. Complementary, not duplicative.

**Plus operator-go housekeeping** (per Loom-agent's audit + their `ms_agent_runtime_observation_decisions_landed_2026_06_18` follow-up):
- **A1** (operator's call, in flight): cold-start strategy — bump `loom-agent-context` to starter ($7/mo) AND atomically delete the dashboard-created `loom-keep-warm` cron AND reconcile `render.yaml:80` literal + `render.yaml:336+` NOTE to match
- **A2** (in flight): decommission `loom-mcp-memory-server` orphan — verified zero callers in three independent PROBE passes
- **1-line docstring fix** at `the-loom/services/self-observer/candidate_client.py:30` — label the `process=orphan` semantic squat as placeholder until Tapestry introduces first-class `observation_kind`

Per Loom-agent's follow-up memo, plan creation for these is in flight. By the time this revision merges, A1/A2/A4 may already be executed; this proposal documents the intent + the architectural commitments.

### What defers to Tapestry (Phase 6 and adjacent work)

| Capability | Tapestry destination (provisional) | Why deferred |
|---|---|---|
| **Observation-Decomposer** — splits repeated behavior into a SET of decomposed candidates per the 9-artifact map (NEW per outside reviewer) | `tapestry/engine/observation-decomposer/` (provisional name; open question Q8) | Required for safe auto-update; cannot ship without it because "promote the whole behavior" is the named fatal flaw |
| Runtime event store + Postgres telemetry rollup + read API (the substrate the decomposer queries) | `tapestry/services/telemetry-ingestion/` migration includes the rollup schema | Self-host requires Postgres; Loki-as-store is Grafana-Cloud-locked. **Tapestry's telemetry-ingestion MUST include this for self-host parity post-migration.** |
| Runtime-observer (computes observation signals like `hot_path`, `orphaned`, `degrading`) | `tapestry/services/project-observatory/` (the 24-line Phase-0 stub today) | Phase 6 IS this content; building in the-loom is duplicate work. Note: this is NOT the decomposer — the observer COMPUTES signals; the decomposer consumes them. |
| Policy daemon — gated promotion with policy-bounded cascade (per outside reviewer §3.1) | `tapestry/services/policy/` daemon variant | Today's policy service is fully inert. Daemon variant fires transitions per evidence thresholds + automation-level ceiling. |
| Destination handlers for the other 8 candidate kinds (`agent`, `inline_tool`, `external_tool`, `architecture_pattern`, `service`, `machine_support`, `process`, `orchestration`) | `tapestry/services/skill-making/` extensions (NB: needs to expand beyond `skill-making` to handle all kinds; module rename probable) | Loop closure requires these; without them auto-promotion pollutes state regardless of trigger |
| Default-agent telemetry instrumentation (at agent-turn edge, NOT builtin_tools wrap) | `tapestry/engine/agency-to-structure/` | The right instrumentation point is the agent turn, but the wrong place to build it is `Make_Skills/services/api/main.py` since that's legacy-source. **Pending Q3 measurement** before committing to the work. |
| Memory schema redesign (hierarchical scopes, provenance chains, four-tier visibility, memory_class taxonomy) | `tapestry/services/agent-context/` Step 2 schema | Per Loom-agent's §B; Tapestry redoes it from scratch |
| First-class `observation_kind` enum + `observations[].signals[]` array (per outside reviewer §3.2) | `tapestry/services/architecture-registry/` schema | Untangles today's `process=orphan` conflation cleanly in Tapestry |
| `actionable_backlog_count` metric (per outside reviewer §3.3) | `tapestry/services/policy/` daemon | The deferral's falsification tripwire lives in the daemon that watches the candidate stream |
| Staged activation infrastructure + rollback infrastructure | TBD — likely `tapestry/services/policy/` adjacent | Required by the policy-bounded cascade; without rollback "auto-update" can't be safely shipped |

### Explicitly NOT doing

- Building `runtime-observer` as a sibling cron service in the-loom
- Wrapping `builtin_tools` in `Make_Skills/core/runtime/agent.py:build_agent()` (category error — those aren't compiled skills)
- Extending the 9-kind candidate enum at `the-loom/services/architecture-registry/models.py:32-42` (no schema change needed — observation signals go in the existing `signals: dict[str, Any]` field at `models.py:93`)
- Adding Loki-based queries to the self-observer's degraded orphan-detection path (the failure mode is the v1 stub at `telemetry_client.py:22-35` returning `None`, not Loki — see Fix 4 framing)
- Memory schema changes in the-loom (Tapestry redoes it from scratch)
- **Promoting observed behavior "as a whole" — every observed pattern must decompose into a SET of candidates, never one** (binding per outside reviewer's central correction)
- Building anything called "auto-promotion" before it has observation + decomposition + policy + staging + activation + telemetry + rollback (per outside reviewer's product framing)

## Hidden risks + falsification tripwires (per outside reviewer §1.6)

Beyond the "NOT doing" list of rejected options, these are unresolved exposures that need explicit handling:

- **Self-host telemetry parity post-migration.** If Tapestry's `services/telemetry-ingestion/` also ships log-only, the self-host blind flaw persists at a different repo. **Requirement on Tapestry:** telemetry-ingestion MUST include Postgres rollup + read API for self-host parity.
- **Synthesis-memo write + MCP cold-start interaction.** If the 6h cron fires while `loom-agent-context` is cold (per A1 free tier today), and `memory_client.py` has a default httpx 5s timeout, the write fails silently. **Spec:** ≥30s timeout + 1 retry after 5s.
- **`agentic-upskilling` plugin agent points at the current self-observer.** Post-migration, the pointer needs to follow to Tapestry's location.
- **`process=orphan` semantic squat** at `the-loom/services/self-observer/candidate_client.py:30` — addressed by the 1-line docstring fix above.
- **Falsification tripwire for the deferral itself** (per outside reviewer §3.3):

### `actionable_backlog_count` — the single tripwire metric

```text
actionable_backlog_count =
  count of candidates that are stable OR promotion_requested
  AND have a supported destination handler
  AND have not reached their next lifecycle step
```

Raw candidate count rises because the observer is doing its job — that's not failure. Real failure is *"the system found things it knows how to handle, but they're not moving."*

| Threshold | Meaning |
|---|---|
| GREEN | `actionable_backlog_count <= 5` |
| YELLOW | `> 5` for 2 consecutive scans |
| RED | `> 10` OR any skill candidate `promotion_requested` for `> 24h` OR Promote click creates no dispatch event within 5 minutes |

The synthesis memo should surface these counters:

```text
actionable_backlog_count
stuck_promotion_requested_count
oldest_stuck_candidate_age
dispatch_success_count_since_last_scan
dispatch_failure_count_since_last_scan
unsupported_candidate_count_by_kind
```

Plus a one-line health flag: `Deferral health: GREEN/YELLOW/RED — Reason: <why>`.

### Three sub-component caveats blocking the Tapestry build

Per Loom-agent's follow-up `ms_agent_runtime_observation_decisions_landed_2026_06_18`, these need their own Tapestry design pass BEFORE the observation-decomposer + policy daemon can ship:

1. **Risk classifier is undefined.** The automation cascade's Level 4 gate ("low/medium risk AND handler exists") requires a risk classifier no one has specified. Too permissive → unsafe auto-staging; too restrictive → cascade collapses.
2. **`actionable_backlog_count` blind spot for non-skill kinds.** Requires "supported destination handler" to count. Today only `kind=skill` has a handler. So it measures stuck skill candidates only. **Add sibling threshold:** `unsupported_candidate_count_by_kind` exceeding 20 for any non-skill kind held in `promotion_requested` for `>7 days` = RED. Otherwise the deferral can quietly fail for 8 of 9 kinds.
3. **Judgment-substep → skill-vs-agent split is underspecified** — exactly the category drift the loop is supposed to prevent. Minimum disambiguation: **skill if scope is bounded to a single call site; agent if scope is ongoing responsibility across calls.** Without this rule the decomposer makes the same mistake the observer makes today.

These are flagged in the durable artifact §3 and inherited here.

## Outside reviewer's resolutions on three open questions (per durable artifact §3)

### Automation transitions: policy-bounded cascade

```text
candidate artifact
  ↓
risk classification
  ↓
policy determines max_auto_level
  ↓
candidate progresses automatically until it reaches that ceiling
  ↓
anything above the ceiling requires approval
```

| Level | Action | Default behavior |
|---|---|---|
| 0 | Observe | Auto |
| 1 | Create candidate | Auto |
| 2 | Decompose into artifact candidates | Auto |
| 3 | Draft artifact | Auto |
| 4 | Stage inactive artifact | Auto only if low/medium risk AND handler exists |
| 5 | Activate low-risk read-only / warning behavior | Policy-gated; can be auto for approved classes |
| 6 | Activate write/network/shell/db behavior | Manual/security approval |
| 7 | Cross-project / default availability | Manual approval |

Transition firing — evidence-thresholded, not vibes:

```text
frequency >= threshold
stability >= threshold
confidence >= threshold
handler exists
tests pass
risk class acceptable
no missing permissions
rollback path exists
```

**Critical:** applies **per decomposed artifact**, not per original observed pattern. A single observation may generate plugin candidate auto-staged to Level 4, tool candidate drafted only, agent candidate spec-drafted only, policy candidate drafted with approval required. Heterogeneity is the point.

### `observation_kind` / `candidate_kind` retrofit timing: 1-line docstring fix in the-loom + full schema split in Tapestry

Already integrated above (decomposition map section + "What lands now" docstring fix). The reviewer's verdict: do NOT do a full schema split in the-loom; do the cheap docstring relabel only; defer real split to Tapestry.

### Falsification tripwire: `actionable_backlog_count`

Already integrated above in Hidden risks section.

## Final actionable set (per durable artifact §4)

### Proceed now (the-loom side)

| Item | Path | Effort | Status |
|---|---|---|---|
| Self-observer synthesis memo extension | `the-loom/services/self-observer/` | ~50 LOC | pending operator go |
| Dispatch-promotion fix at PATCH time | `the-loom/services/architecture-registry/main.py:206-211` | ~1h code + tests | in flight per Loom-agent's follow-up |
| A1 housekeeping (cold-start strategy) | `the-loom/render.yaml` + Render dashboard | 15 min | in flight |
| A2 housekeeping (orphan service deletion) | `the-loom/render.yaml` + Render delete | 10 min | in flight |
| 1-line docstring fix on `process=orphan` squat | `the-loom/services/self-observer/candidate_client.py:30` | 1 min | in flight |

### Defer to Tapestry (architectural commitments)

See the "What defers to Tapestry" table above — 10 capabilities total, with the observation-decomposer as the new first row.

### The clean Tapestry control model

```text
Observation signals are NOT candidate kinds.
Repeated behavior decomposes into artifact candidates.
Automation progresses only up to the max level allowed by:
  - policy
  - risk
  - evidence
  - handler availability
  - tests
```

## Open questions for outside-agent review

### Closed via PROBE in this revision (per durable artifact §1.4)

- **Q2 (memory upsert idempotency)** — CLOSED. `the-loom/services/agent-context/mcp_server.py:105-108` defines `_id_from_name(name) → name.strip()`; `storage.py:207-232` does atomic upsert by id. `self_observer_synthesis_latest` stable-name idempotency works as proposed.
- **Q3 (default-agent traffic share)** — CLOSED-with-action. Answerable via a 30-min Render log query against `make-skills-api`, NOT a 7-day sample. Convert to a measurement requirement before committing to Tapestry-side default-agent instrumentation.
- **Q5 (loom-keep-warm yaml diff)** — CLOSED. Per Loom-agent's A1 decision (now in flight), strategy is bump-to-starter + delete cron, atomic. yaml NOTE at `render.yaml:336+` reconciles to match. No "option b" yaml needed.
- **Q6 (orphan service deletion safety)** — CLOSED. Verified zero callers in audit (lines 137-138, 344) + independent verification (line 33) + Loom-agent's re-PROBE finding only `render.yaml:107-124` declaration + stub self-references.
- **Q7 (one-canonical-home for synthesis memo)** — CLOSED. The candidate table and `self_observer_synthesis_latest` serve different audiences (operator-actionable rows in dashboard vs. agent-readable SessionStart narrative). Different projections of the same observation, not duplicate patterns. Not a Pillar-1 violation.

### Remaining open

1. **Cold-start strategy (A1)** — Operator's call. Plan in flight per Loom-agent's follow-up.
2. **Tapestry timing.** This proposal defers ~10 capabilities to Tapestry. Per `tapestry/docs/proposals/2026-06-13-v1-scope-and-roadmap.md`, none of those are in v1 scope. **Are we accepting "no auto-promotion until Tapestry v1 ships"?** Outside agent confirm or contest.
3. **(NEW) Where does the Observation-Decomposer live in Tapestry?** Provisional `tapestry/engine/observation-decomposer/`; alternative `tapestry/services/candidate-decomposer/`. Engine (compute) or service (durable infrastructure)?
4. **(NEW) Risk classifier specification.** The Level 4 cascade gate ("low/medium risk AND handler exists") requires a risk classifier. Without specifying it, the cascade either collapses to "stop at Level 3" or risks unsafe auto-staging. Tapestry-agent design pass needed before the policy daemon can ship.
5. **(NEW) Non-skill threshold for falsification tripwire.** `actionable_backlog_count` is blind to non-skill kinds today. The proposed sibling threshold (`unsupported_candidate_count_by_kind > 20 for >7d → RED`) needs confirmation.

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

## Outside-agent review checklist (v2)

- [ ] Does the corrected attribution of Loom-agent's audit hold (their actual A3 = fix dispatch-in-place; D2/D3 = housekeeping)? Cross-check `the-loom/docs/research/2026-06-17-platform-state-audit.md:405,422,423`.
- [ ] Is the decomposition map (§"The missing piece") correct? Are any of the 9 artifact types missing or wrongly split?
- [ ] Are the 8 automation levels right, or is there over/under-granularity?
- [ ] Does kind-vs-signal separation (existing `candidate_type` enum stays at 9; observation signals go in existing `signals: dict[str, Any]` at `models.py:93`) survive the use cases?
- [ ] Where does Observation-Decomposer live in Tapestry — `engine/` or `services/`? (Q3)
- [ ] Risk classifier specification: when can Tapestry-agent design this? (Q4)
- [ ] `actionable_backlog_count` non-skill blind spot — is the sibling threshold (`unsupported_candidate_count_by_kind`) calibrated right? (Q5)
- [ ] Three sub-component caveats (risk classifier, non-skill threshold, skill-vs-agent disambiguation) — agree these block the Tapestry build?
- [ ] Is the dispatch-promotion fix (A4) genuinely ~1h or is there hidden scope?
- [ ] Final actionable set tables match operator-go reality?

## Revision history

- **v1** (2026-06-18 morning) — initial proposal. Path B rejected, 6 capabilities deferred, 7 open questions, "four independent verifications converged" framing.
- **v2** (2026-06-18 evening, this version) — applied 5 fixes from outside review + Loom-agent's correction:
  1. Citation correction: Loom-agent's A3 says FIX dispatch-promotion in-place (NOT defer). D2/D3 are housekeeping items, not architecture deferrals. "Four independent verifications" was overclaim — only Loom-agent's audit and the outside reviewers were independent.
  2. Added A4 (dispatch-promotion fix at PATCH time) to "What lands now".
  3. Closed 5 of 7 open questions via PROBE (Q2/Q3/Q5/Q6/Q7); added 3 new open questions (decomposer location, risk classifier, non-skill threshold).
  4. Sharpened orphan-detection framing: the v1 stub at `telemetry_client.py:22-35` returns `None`, not a Loki edge issue.
  5. Added hidden risks + falsification tripwire (`actionable_backlog_count`) + three sub-component caveats blocking Tapestry build.
  - PLUS architectural addition: §"The missing piece — Observation → Decomposition map" per outside reviewer §2. Repeated behavior decomposes into a SET of candidates; never one. Tapestry control model: `Automatic observation and decomposition / Policy-gated promotion / Staged activation / Measured reuse / Rollback if wrong`.
  - PLUS §"Outside reviewer's resolutions on three open questions" per durable artifact §3 (policy-bounded cascade, retrofit timing, falsification tripwire).
  - Linked durable artifact at top — that's the canonical version; this proposal is the operator-facing wrapper.
