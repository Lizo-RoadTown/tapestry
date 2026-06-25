# Outside-review followup — runtime observation proposal

**Date:** 2026-06-18
**Status:** Durable architectural record. Consolidates the consolidated five-point critique delivered to MS-agent + the third-pair-of-eyes outside reviewer's follow-up positions on three open architectural questions.
**Audiences:** MS-agent (Make_Skills, primary recipient); Tapestry-agent (will absorb the architectural commitments); loom-agent (cross-link); future operator sessions.
**Companion records:**
- Original proposal: [`tapestry/docs/proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md`](../proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md)
- First outside review: [`tapestry/docs/research/2026-06-18-outside-review-of-runtime-observation-proposal.md`](2026-06-18-outside-review-of-runtime-observation-proposal.md)
- Loom-agent platform audit (the one the proposal mis-cited): [`the-loom/docs/research/2026-06-17-platform-state-audit.md`](https://github.com/Lizo-RoadTown/the-loom/blob/main/docs/research/2026-06-17-platform-state-audit.md)
- Cross-agent comm record (loom-memory MCP): `ms_agent_outside_review_of_runtime_observation_proposal_2026_06_18`

---

## TL;DR

**Verdict on the proposal: accept-with-fixes.** Spine is sound; five fixes plus one architectural addition required before ratification. This document is the durable form of those recommendations.

**Verdict on the three open architectural questions from loom-agent's followup:**

1. Automation transitions: use a **policy-bounded cascade** (per-kind ceiling, evidence-thresholded transitions), NOT seven separate manual gates and NOT a global Level-4 cascade.
2. `observation_kind` / `candidate_kind` retrofit timing: **small in-place docstring fix in the-loom now; full schema split in Tapestry only.** Don't migrate the legacy schema.
3. Falsification tripwire: single metric `actionable_backlog_count`, defined precisely below. Synthesis memo should surface six related counters + a one-line GREEN/YELLOW/RED health flag.

---

## 1. The MS-agent recommendation set

What the proposal authors should change before ratification.

### 1.1 What stays right in the proposal (PROBE-confirmed)

1. Don't build a new runtime-observer cron in the-loom
2. Don't wrap `Make_Skills/core/runtime/agent.py:116-127` `builtin_tools` as fake compiled skills — telemetry requires `skill_id: UUID` + `source_tenant_id` per [`Make_Skills/core/skill_making/compiler.py:178-179`](https://github.com/Lizo-RoadTown/Make_Skills/blob/main/core/skill_making/compiler.py#L178-L179)
3. Don't emit synthetic `skill_id` telemetry that violates the implicit FK to `student_skills`
4. Don't use Loki / Grafana Cloud as the only runtime-observation substrate (self-host blind per [`the-loom/services/telemetry-ingestion/skill_usage_handler.py:68-87`](https://github.com/Lizo-RoadTown/the-loom/blob/main/services/telemetry-ingestion/skill_usage_handler.py#L68-L87))
5. Don't add `orphan`, `hot_path`, or `degrading` as candidate kinds (they are observation signals, not artifact types) — taxonomy at [`the-loom/services/architecture-registry/models.py:32-42`](https://github.com/Lizo-RoadTown/the-loom/blob/main/services/architecture-registry/models.py#L32-L42) is exactly 9 values
6. Don't build permanent observer/auto-promotion architecture in legacy repos
7. Move real runtime observation + policy-gated promotion to Tapestry

### 1.2 Fix 1 — citation correction (governance issue, not wording)

The proposal's §"Loom-agent's parallel call" attributes **D2/D3** to loom-agent's audit with text loom-agent did not write.

Loom-agent's actual audit content at [`the-loom/docs/research/2026-06-17-platform-state-audit.md`](https://github.com/Lizo-RoadTown/the-loom/blob/main/docs/research/2026-06-17-platform-state-audit.md):

- **D2 (line 422)** = "correct any keep-warm-dropped claim in render.yaml or memory" (housekeeping memory correction)
- **D3 (line 423)** = "record the service-ID typo: the cited service ID is telemetry-ingestion, not agent-context" (housekeeping memory correction)
- **A3 (line 405, verbatim)** = *"Close dispatch-promotion gap per `2026-06-16-candidate-lifecycle-verified.md` Option B (in-service auto-trigger at PATCH time)... ~1 hour code + tests"* — **FIX IN-PLACE in the-loom, NOT defer**

The "Don't fix in the-loom; close in Tapestry from day one" framing the proposal attributed to D3 doesn't exist in the audit. §B (DON'T FIX in the-loom, lines 408-412) lists memory schema, dashboard redesign, project-observatory build-out, telemetry-ingestion query API — dispatch-promotion is explicitly NOT in that list.

Additionally, the "four independent verifications converged" framing overclaims. Four of the five inputs were MS-agent-dispatched audits binding to the same `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13` rule. Only loom-agent's audit was independent — and the proposal mis-cited it.

**Required revised text:**

> Independent audits confirmed the builtin_tools telemetry flaw, self-host telemetry flaw, and taxonomy issue. However, loom-agent did NOT independently recommend deferring the dispatch-promotion gap; loom-agent recommended fixing that gap IN the-loom (~1 hour, in-service auto-trigger). The convergence around deferral applies to runtime-observer + auto-promotion architecture, NOT to the dispatch-promotion mechanics gap.

### 1.3 Fix 2 — add dispatch-promotion fix to "what lands now"

The proposal's "what lands now" is: synthesis memo + A1/A2 housekeeping. Add a fourth item:

> **A4. Close the dispatch-promotion automation gap.** Per loom-agent A3: in [`the-loom/services/architecture-registry/main.py:206-211`](https://github.com/Lizo-RoadTown/the-loom/blob/main/services/architecture-registry/main.py#L206-L211), after PATCH that sets `status='promotion_requested'`, fire-and-forget `promote_dispatcher.dispatch_promotion`. Add kind-aware filter (skill only, until other handlers exist per `bridge_closed_end_to_end_2026_06_13`). ~1h code + tests. Implementation survives Tapestry migration unchanged.

**Why this matters:** without it, every operator Promote click on a skill candidate dead-ends at `promotion_requested` for the duration of the Tapestry deferral. Synthesis memo and dispatch fix are complementary, not duplicative — synthesis gives agents context; dispatch makes operator clicks deliver.

### 1.4 Fix 3 — close 5 of 7 PROBE-resolvable open questions

- **Q2 (memory upsert idempotency):** [`the-loom/services/agent-context/mcp_server.py:105-108`](https://github.com/Lizo-RoadTown/the-loom/blob/main/services/agent-context/mcp_server.py#L105-L108) defines `_id_from_name(name) → name.strip()`; [`storage.py:207-232`](https://github.com/Lizo-RoadTown/the-loom/blob/main/services/agent-context/storage.py#L207-L232) does atomic upsert by id. `self_observer_synthesis_latest` stable-name idempotency works exactly as proposed. **Close with citation.**
- **Q3 (default-agent traffic share):** answerable via a 30-min Render log query against `make-skills-api`. Not a 7-day sample. Convert to a measurement requirement before merging.
- **Q5 (loom-keep-warm yaml diff):** loom-agent's audit specifies the direction. The cron block needs to be added under `services:` in `render.yaml` with `*/10 * * * *`. Paste exact yaml.
- **Q6 (orphan service deletion safety):** verified zero callers in the audit (lines 137-138, 344) and the independent verification (line 33). Grep already done twice. Close.
- **Q7 (one-canonical-home for synthesis memo):** the candidate table and `self_observer_synthesis_latest` serve different audiences (operator-actionable rows in the dashboard vs. agent-readable SessionStart narrative). Different projections of the same observation, not duplicate patterns. Not a Pillar-1 violation. Close.

Leave open only Q1 (operator's cold-start call) and Q4 (Tapestry timing — needs Tapestry-agent input).

### 1.5 Fix 4 — sharpen the orphan-detection framing

[`the-loom/services/self-observer/telemetry_client.py:22-35`](https://github.com/Lizo-RoadTown/the-loom/blob/main/services/self-observer/telemetry_client.py#L22-L35) shows `invocations_30d` is a v1 stub returning `None` on every call. `signal_rules.classify` treats `None` as "telemetry unavailable, don't emit orphan candidates" — so the orphan branch literally never fires today, regardless of Loki state. The Loki-only framing in the proposal is incomplete: the failure mode is "intentional v1 stub awaiting wired-up observatory," not "degraded path at the Loki edge." Even if telemetry-ingestion grew a Postgres rollup + read API tomorrow, the observer wouldn't see it because the stub short-circuits to `None` before any HTTP.

### 1.6 Fix 5 — name hidden risks + falsification tripwires

The proposal's "Explicitly NOT doing" list rejects options. A complementary list of unresolved exposures needs to be added:

- **Self-host telemetry parity post-migration.** If Tapestry's `services/telemetry-ingestion/` also ships log-only, the self-host blind flaw persists at a different repo. Tapestry's telemetry-ingestion MUST include Postgres rollup + read API for self-host parity.
- **Synthesis-memo write + MCP cold-start interaction.** If the 6h cron fires while `loom-agent-context` is cold, and the new `memory_client.py` has a default httpx 5s timeout, the write fails silently. Specify ≥30s timeout + 1 retry after 5s.
- **`agentic-upskilling` plugin agent points at the current self-observer.** Post-migration, the pointer needs to follow to Tapestry's location.
- **`process=orphan` semantic squat.** [`the-loom/services/self-observer/candidate_client.py:30`](https://github.com/Lizo-RoadTown/the-loom/blob/main/services/self-observer/candidate_client.py#L30) docstring uses `candidate_type=process` to encode "this is orphaned" — a candidate_kind squatted to represent an observation_kind. One-line docstring fix before migration so the destination inherits clean labels. (See §3.2 below for the exact fix.)
- **Falsification tripwire for the deferral.** See §3.3.

---

## 2. The architectural addition — the missing decomposition map

This is the substantive addition Liz's external reviewer surfaced. Neither loom-agent's audit nor the first outside review had it.

### 2.1 Core rule

> **A repeated behavior is not promoted as a whole. It is decomposed into artifact candidates.**

The observer/decomposer must identify:

| Part of the observed pattern | Becomes |
|---|---|
| Event-triggered parts | Plugin / hook |
| Deterministic parts | Tool |
| Judgment parts (situational reasoning) | Skill |
| Judgment parts (ongoing responsibility) | Agent |
| Multi-step sequences | Workflow |
| Cross-component coordination | Orchestration |
| Side effects + durable shared need | Service |
| Approval/risk rules | Policy |
| Stable facts / preferences | Memory / lesson |

### 2.2 Worked example

**Observation:** A plugin keeps firing because session-end upskilling reports are missing.

**Wrong answer:** "Promote the whole pattern as one agent."

**Right answer — decomposition into 6 distinct artifact candidates:**

- Plugin candidate: Stop-hook checker (detects whether the report ran)
- Tool candidate: transcript-to-upskilling-report generator
- Workflow candidate: session-end upskilling pass
- Policy candidate: substantive sessions require a report before closure
- Agent candidate: promotion-review agent — only if repeated judgment remains
- Telemetry signal: missing-upskilling-report

Each gets its own lifecycle, evidence threshold, and automation ceiling.

### 2.3 Semantic separation

| Field | Meaning | Where it lives |
|---|---|---|
| `candidate_kind` | "What this may become" | Existing 9-value enum; semantically correct as-is |
| `observation_kind` | "Why it was noticed" | New enum: `runtime_usage`, `frontmatter_drift`, `repeated_failure`, `cross_project_recurrence`, etc. |
| `observation.signals[]` | The specific evidence: `hot_path`, `orphaned`, `degrading`, `deterministic_substep`, `judgment_required`, `permission_required`, `repeated_manual_step`, `stable_output` | Array of typed observation signals |

This untangles today's `process=orphan` conflation in the-loom and prevents Tapestry from inheriting it.

### 2.4 Suggested Tapestry component

**Name:** `engine/observation-decomposer/` OR `services/candidate-decomposer/`

**Responsibilities:**

1. Accept observation signals from plugins, runtime telemetry, session-end reports, memory writes, tool calls
2. Identify repeated behavior across observations
3. Split the behavior into deterministic / judgment / event-triggered / infrastructure / governance parts
4. Emit one or more artifact candidates
5. Attach evidence + recommended automation level (per §3.1 below)
6. Send candidates to the candidate / architecture registry
7. **NEVER activate live behavior directly**

### 2.5 Correct Tapestry product framing

Replace "runtime-observer + auto-promotion" with:

> **Automatic observation and decomposition.**
> **Policy-gated promotion.**
> **Staged activation.**
> **Measured reuse.**
> **Rollback if wrong.**

Don't call the future system "auto-promotion" until it has observation, decomposition, policy, staging, activation, telemetry, AND rollback.

---

## 3. Outside reviewer's resolutions on the three open questions

These are the architectural positions loom-agent asked the outside reviewer to weigh in on. The reviewer's resolutions follow.

### 3.1 Automation transitions: policy-bounded cascade

**Use a policy-bounded cascade.** Not seven separate manual gates (would kill the system) and not a global Level-4 cascade (too broad).

> **A candidate may automatically progress through levels only up to the maximum level allowed by its artifact kind, risk class, evidence quality, and permissions.**

Flow:

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

**Recommended defaults:**

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

**Transition firing — evidence-thresholded, not vibes:**

```text
frequency ≥ threshold
stability ≥ threshold
confidence ≥ threshold
handler exists
tests pass
risk class acceptable
no missing permissions
rollback path exists
```

**Critical:** this applies **per decomposed artifact**, not per original observed pattern. A single observation may generate plugin candidate → auto-stage to Level 4, tool candidate → draft only until tests exist, agent candidate → draft spec only, policy candidate → draft only with approval required. That heterogeneity is the point.

### 3.2 observation_kind / candidate_kind retrofit timing

**Small in-place label correction in the-loom now; full schema split in Tapestry only.**

**The-loom minimal fix (today, single-line docstring):**

At [`the-loom/services/self-observer/candidate_client.py:30`](https://github.com/Lizo-RoadTown/the-loom/blob/main/services/self-observer/candidate_client.py#L30), replace:

```text
candidate_type: one of 9 taxonomy values — agent / inline_tool / skill (demotion) / process (orphan).
```

with:

```text
candidate_type means "what this may become" — one of 9 values per models.py:32-42.

Note: today's code uses candidate_type=process to encode an orphan observation.
This is a SEMANTIC PLACEHOLDER until Tapestry introduces first-class observation_kind.
orphaned / hot_path / degrading are observation signals, not candidate types.
```

This prevents the migration target from inheriting corrupted language. **Do NOT do a full schema split in the-loom.** That belongs in Tapestry.

**Tapestry target schema:**

```json
{
  "candidate_kind": "inline_tool",
  "observations": [
    {
      "observation_kind": "runtime_usage",
      "signals": ["hot_path", "deterministic_substep", "stable_output"]
    }
  ]
}
```

The `candidate.kind` and `observations[].kind` axes are independent.

### 3.3 Falsification tripwire metric

**Single metric:** `actionable_backlog_count`.

**Definition:**

```text
actionable_backlog_count =
  count of candidates that are stable OR promotion_requested
  AND have a supported destination handler
  AND have not reached their next lifecycle step
```

**Why this metric and not raw candidate count:** raw candidate count rises because the observer is doing its job. That's not failure. The real failure is *"the system found things it knows how to handle, but they're not moving."*

**Recommended thresholds:**

```text
GREEN:  actionable_backlog_count <= 5
YELLOW: actionable_backlog_count > 5 for 2 consecutive scans
RED:    actionable_backlog_count > 10
        OR any skill candidate remains promotion_requested for > 24h
        OR Promote click creates no dispatch event within 5 minutes
```

**Synthesis memo should surface these counters:**

```text
actionable_backlog_count
stuck_promotion_requested_count
oldest_stuck_candidate_age
dispatch_success_count_since_last_scan
dispatch_failure_count_since_last_scan
unsupported_candidate_count_by_kind
```

**Plus one-line health flag:**

```text
Deferral health: GREEN/YELLOW/RED
Reason: <why>
```

---

## 4. Final actionable set

### 4.1 Proceed now (the-loom side)

| Item | Path | Effort | Status |
|---|---|---|---|
| Self-observer synthesis memo extension (~50 LOC) | `the-loom/services/self-observer/` | as proposed | pending operator go |
| Dispatch-promotion fix at PATCH time | `the-loom/services/architecture-registry/main.py:206-211` | ~1h code + tests | pending operator go |
| A1 housekeeping (cold-start strategy) | `the-loom/render.yaml` + Render dashboard | 15 min | pending operator decision |
| A2 housekeeping (orphan service deletion) | `the-loom/render.yaml` + Render delete | 10 min | pending operator approval |
| PROBE-close 5 of 7 open questions | proposal edits | 30 min | MS-agent task |
| Add hidden risks + tripwires | proposal edits | 30 min | MS-agent task |
| 1-line docstring fix on `process=orphan` squat | `the-loom/services/self-observer/candidate_client.py:30` | 1 min | pending operator go |

### 4.2 Defer to Tapestry (architectural commitments)

- Runtime event store
- Postgres telemetry rollup + read API (in `services/telemetry-ingestion/`)
- **Observation-decomposer component** (the missing architecture — see §2)
- Policy daemon (gated promotion with policy-bounded cascade per §3.1)
- Destination handlers for 8 remaining candidate kinds (`agent`, `inline_tool`, `external_tool`, `architecture_pattern`, `service`, `machine_support`, `process`, `orchestration`) — today only `kind=skill` has a handler
- Staged activation infrastructure
- Rollback infrastructure
- Memory schema redesign (hierarchical scopes, provenance chains, four-tier visibility, memory_class taxonomy) in `services/agent-context/`
- First-class `observation_kind` enum + `observations[].signals[]` array (per §3.2)
- `actionable_backlog_count` metric in policy daemon (per §3.3)

### 4.3 The clean Tapestry control model

```text
Observation signals are not candidate kinds.
Repeated behavior decomposes into artifact candidates.
Automation progresses only up to the max level allowed by:
  - policy
  - risk
  - evidence
  - handler availability
  - tests
```

---

## 5. Operator decisions outstanding

These are the operator's call alone. Outside reviewer's recommendation noted in italics; operator confirmation in operator's own voice required before any action.

| # | Decision | Outside reviewer's recommendation | Status |
|---|---|---|---|
| A1 | Cold-start strategy: starter ($7/mo) + delete keep-warm cron, OR keep free + declare cron in `render.yaml` | *Bump to starter; delete the cron; update render.yaml + memory* | awaiting operator go |
| A2 | Decommission `loom-mcp-memory-server` (verified zero callers) | *Approve deletion with rollback note* | awaiting operator go |
| A3 | Implement dispatch-promotion in-service auto-trigger at PATCH time | *Approve now; not optional if Promote clicks dead-end* | awaiting operator go |

---

## 6. Cross-references

- Original proposal: [`tapestry/docs/proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md`](../proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md)
- First outside review: [`tapestry/docs/research/2026-06-18-outside-review-of-runtime-observation-proposal.md`](2026-06-18-outside-review-of-runtime-observation-proposal.md)
- Loom-agent platform audit: [`the-loom/docs/research/2026-06-17-platform-state-audit.md`](https://github.com/Lizo-RoadTown/the-loom/blob/main/docs/research/2026-06-17-platform-state-audit.md)
- Loom-agent platform audit verification: [`the-loom/docs/research/2026-06-17-platform-state-audit-verification.md`](https://github.com/Lizo-RoadTown/the-loom/blob/main/docs/research/2026-06-17-platform-state-audit-verification.md)
- Candidate-lifecycle research (prior session): [`the-loom/docs/research/2026-06-16-candidate-lifecycle-verified.md`](https://github.com/Lizo-RoadTown/the-loom/blob/main/docs/research/2026-06-16-candidate-lifecycle-verified.md)
- Cross-agent comm memo (loom-memory MCP): `ms_agent_outside_review_of_runtime_observation_proposal_2026_06_18`
- Binding rule: `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13`
- Engine bridge state (kind=skill only): `bridge_closed_end_to_end_2026_06_13`

---

*End of followup.*
