# Outside review — `2026-06-18-runtime-observation-deferred-to-tapestry.md`

**Reviewer:** independent opus-4-7 subagent (third pair of eyes — neither MS-agent nor loom-agent).
**Date:** 2026-06-18.
**Method:** PROBE every load-bearing claim against source-of-truth (Make_Skills + the-loom source, Render API via memory references, prior audit + verification reports, the cited memory records). Read both loom-agent's primary audit and its verification report. Then read MS-agent's audit-synthesis memory `msagent_fleet_audit_synthesis_complete_2026_06_18`. Then critically evaluate convergence vs. confirmation-loop.
**Subject:** `c:/Users/Liz/tapestry/docs/proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md`

---

## 1. TL;DR

**Accept-with-fixes.** The two "fatal flaws" against Path B are real and well-cited. The deferral direction is right per the canonical-Tapestry framing rule. **But the proposal mis-cites loom-agent's audit on two load-bearing points** (D2/D3 attribution is wrong; A3 says the opposite of what the proposal claims) and **the "all four converged independently" framing oversells the evidence** — at least one input was MS-agent's own audit whose synthesis already absorbed Tapestry-canonical framing. Fix the citations, soften the convergence language, and close 3 of the 7 "open questions" that PROBE resolves in under 10 minutes — then ship.

---

## 2. Verified-true load-bearing claims

### 2.1 Fatal flaw 1 — `builtin_tools` is a category error. **TRUE.**

PROBE'd `c:/Users/Liz/Make_Skills/core/runtime/agent.py:110-127`:

```python
from core.tools.db import query_db
from services.admin.roadmap.tools import (
    add_roadmap_item,
    roadmap_overview,
    update_roadmap_status,
)
builtin_tools = [
    query_db,
    roadmap_overview,
    update_roadmap_status,
    add_roadmap_item,
]
# ...
agent = create_deep_agent(
    model=resolve_model(model_cfg),
    tools=builtin_tools,
    ...
)
```

These are **direct imports of langchain `@tool`-decorated functions**, NOT compiled skills. Confirmed.

PROBE'd `compiler.py:86-145` — telemetry lives inside the `_run` closure produced by `compile_skill_to_tool`. The closure carries the captured `skill_id: UUID` (line 130) and `source_tenant_id` (line 131), both required by `_emit_telemetry(...)` (lines 161-179). Specifically `compiler.py:178-179`:

```python
if source_tenant_id is None:
    return
```

— telemetry is intentionally skipped when there's no source-side UUID. The default-agent's `builtin_tools` never go through this pipeline. So "wrap `builtin_tools` with telemetry" would either:

- pollute the stream with synthetic `skill_id`s that violate the implicit FK to `student_skills`, or
- require a parallel telemetry channel with a different envelope shape.

PROBE'd `services/api/main.py:260-286` — the `chat` endpoint at the agent-turn edge. This IS the right instrumentation point if default-agent telemetry is actually wanted. The proposal's redirect is correct.

**Verdict:** the proposal's fatal flaw 1 analysis is accurate and well-cited.

### 2.2 Fatal flaw 2 — self-host blind. **TRUE.**

PROBE'd `c:/Users/Liz/the-loom/services/telemetry-ingestion/skill_usage_handler.py:68-87`:

```python
for event in batch.events:
    record = {
        "event_kind": "skill_usage",
        # ... 12 fields ...
    }
    logger.info(json.dumps(record, separators=(",", ":")))

return {
    "batch_id": str(batch.batch_id),
    "events_processed": len(batch.events),
}
```

There is **no Postgres persistence**, no read API, just a `logger.info` emit to stdout for Render's log shipper to pick up. Self-host operators don't have Grafana Cloud → the stream has no consumer. Confirmed.

**Verdict:** fatal flaw 2 is accurate.

### 2.3 Taxonomy contract — 9 exact kinds; `orphan/hot_path/degrading` absent. **TRUE.**

PROBE'd `the-loom/services/architecture-registry/models.py:32-42`:

```python
CANDIDATE_TYPE = Literal[
    "skill",                  # §4.1
    "inline_tool",            # §4.2 (renamed from 'tool' in migration 006)
    "external_tool",          # §4.3
    "architecture_pattern",   # §4.4
    "service",                # §4.5
    "machine_support",        # §4.6
    "process",                # §4.7
    "agent",                  # §4.8
    "orchestration",          # §4.9
]
```

Exactly 9 enum values. `orphan`, `hot_path`, `degrading` are **NOT** present. Confirmed.

Also confirmed: the field is named `candidate_type` (`models.py:71`) and its docstring (`models.py:71-78`) confirms the semantic — "what the candidate IS / what it should become" — not "what observation fired." Adding the runtime-observer's three kinds would require migration 007 + Pydantic Literal update + receiver-side parsers + dashboard updates (per the in-file comment at `models.py:27-30`). The proposal's framing is accurate.

### 2.4 9-kind taxonomy has only one closed handler. **TRUE for kind=skill.**

Cross-checked memory `bridge_closed_end_to_end_2026_06_13`: "Only `kind=skill` has a destination handler. The other 8 kinds ack-defer with no handler." This is also called out in the OUTPUT-side memory itself. The proposal's "critical flaw: loop still doesn't close" is correctly framed.

### 2.5 Self-observer scan paths + classification. **MATCHES.**

PROBE'd `services/self-observer/config.py:44-80` (REGISTRIES) and `signal_rules.py:189-271` (classify):

- 4 hardcoded REGISTRIES (claude-skills-marketplace plugins, Make_Skills residuals, the-loom residuals, docs-agent residuals) — exactly as the proposal describes
- Three signal sets (agent / inline_tool / skill) per `classify()`
- Confidence threshold `EMIT_THRESHOLD: float = 0.3` at `config.py:164` — matches the proposal's "≥ 0.3" claim
- Orphan detection at `signal_rules.py:208-216` — fires when `invocations_30d == 0 AND current_location_kind in ("skill", "agent")` → emits `process` candidate at confidence 0.7

All matches. The proposal correctly describes the observer's current behavior.

### 2.6 Memory MCP upsert IS by stable name (question 2 from proposal is resolvable). **TRUE.**

PROBE'd `services/agent-context/mcp_server.py:105-108`:

```python
def _id_from_name(name: str) -> str:
    """Memory name (e.g. 'feedback_documentation_tone') IS the row id.
    No filesystem extension; the protocol is name-centric."""
    return name.strip()
```

And `storage.py:207-232`:

```sql
INSERT INTO records (id, type, content, ...)
VALUES (...)
ON CONFLICT (id) DO UPDATE SET
    type = EXCLUDED.type,
    content = EXCLUDED.content,
    ...
```

Atomic upsert by `id`, where `id` is `name.strip()`. **Question 2 in the proposal IS resolved by PROBE alone.** The proposed `self_observer_synthesis_latest` stable-name idempotency works exactly as the proposal hopes. The proposal should close question 2 with a citation, not leave it open.

### 2.7 40 candidates / kind breakdown. **TRUE.**

Verified via `memory_recall` of `session_state_self_observer_loop_closed_input_side_2026_06_13`:

> Production state: 40 self_observation candidates live across 4 source repos:
> - 21 docs-agent
> - 16 Make_Skills (skills_private/, subagents/, top-level skills/, adapters/)
> - 2 claude-skills-marketplace
> - 1 the-loom
> By kind: 34 agent / 5 inline_tool / 1 skill (demotion).

Exactly matches the proposal's numbers. Confirmed.

### 2.8 Tapestry-canonical binding rule. **TRUE.**

Verified via `memory_recall` of `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13`. The rule binds. Capability mapping explicitly names `tapestry/services/project-observatory/`, `tapestry/services/telemetry-ingestion/`, `tapestry/services/policy/`, `tapestry/services/skill-making/`, `tapestry/services/agent-context/` — exactly the destinations the proposal points its deferred work at. Consistent.

---

## 3. Verified-false or overstated claims

### 3.1 "D2 / D3" attribution to loom-agent. **WRONG.**

The proposal §"Loom-agent's parallel call" (lines 72-79) quotes:

> **D2:** Don't build observer-driven auto-promotion in the-loom. Lives more cleanly in Tapestry's policy daemon.
> **D3:** Don't fix the dispatch-promotion gap in the-loom. Close it in Tapestry from day one.

PROBE'd `c:/Users/Liz/the-loom/docs/research/2026-06-17-platform-state-audit.md:419-423`. The actual D1/D2/D3 in loom-agent's audit are:

> ### D. UPDATE MEMORY (stale/wrong records)
> - D1: **`feedback_mcp_is_canonical_not_optional`** — the framing rule … is correct and load-bearing. The CONCRETE REMEDIATION section … is **false today**. …
> - D2: **Any "keep-warm dropped" claim** — render.yaml:336-341 NOTE plus any memory referencing it. Reality: still running.
> - D3: **Brief's service-ID confusion** — record that `srv-d8aj2b3bc2fs7382snqg` is `loom-telemetry-ingestion`, not `loom-agent-context`. …

**D2 and D3 are housekeeping items about stale memory records and a service-ID typo. They are NOT recommendations to defer observer/dispatch work to Tapestry.**

The proposal's attribution is **inverted**. In loom-agent's audit, the action items are A1/A2/A3, and `A3` says (verbatim, audit lines 405):

> **Close dispatch-promotion gap** per `docs/research/2026-06-16-candidate-lifecycle-verified.md` Option B (in-service auto-trigger at PATCH time): in `architecture-registry/main.py:206-211`, after PATCH that sets `status='promotion_requested'`, fire-and-forget `promote_dispatcher.dispatch_promotion`. Add kind-aware filter (skill only, until other handlers exist) | The loop dead-ends at `promotion_requested` today; engine is verified to work for kind=skill | ~1 hour code + tests

**Loom-agent's actual recommendation is to FIX the dispatch-promotion gap IN the-loom NOW, ~1 hour code + tests, not defer to Tapestry.** The proposal cites loom-agent as endorsing exactly the opposite of what loom-agent actually recommended.

The "Don't fix in the-loom" framing comes from loom-agent's §B (lines 408-412), but §B explicitly lists:

> - Memory schema hierarchical scopes, provenance chain, reinforcement model, memory_class taxonomy
> - Dashboard redesign
> - Project-observatory build-out
> - loom-telemetry-ingestion query API

Dispatch-promotion is in §A (fix now), not §B (defer). The proposal conflated them.

**Fix required:** the proposal must either (a) drop the "loom-agent D2/D3" citation block and re-source the converged-position claim, or (b) re-read loom-agent's audit and pick the actual quotes (which would weaken — not strengthen — its argument that loom-agent agrees with deferring everything).

### 3.2 "Self-host blind … broken because telemetry-ingestion only writes to Loki via stdout". **PARTIALLY MISDESCRIBED.**

The proposal §"What the observer is observing today" line 34 says:

> Orphan detection at `signal_rules.py:208-216` queries `TelemetryClient.invocations_30d()` — but the data source is broken because telemetry-ingestion only writes to Loki via stdout (`the-loom/services/telemetry-ingestion/skill_usage_handler.py:68-87`); no Postgres persistence + no read API. So the orphan check is degraded today.

Telemetry-ingestion's stdout-only behavior IS true. But the actual reason `invocations_30d` returns nothing is even simpler — PROBE'd `c:/Users/Liz/the-loom/services/self-observer/telemetry_client.py:22-35`:

```python
async def invocations_30d(self, repo: str, file_path: str) -> int | None:
    """Return invocation count over last 30 days for an entry.

    Returns:
        None if telemetry unavailable (v1 default).
        int if observatory's read API is wired (future).
    ...
    """
    # TODO(post-v1): swap for real query against telemetry_query_url
    # once project-observatory exposes /metrics or /query endpoints.
    return None
```

**`TelemetryClient.invocations_30d` is a stub that returns `None` literally on every call.** It has nothing to do with the Loki stream. Even if telemetry-ingestion grew a Postgres rollup + query API tomorrow, the observer wouldn't read it because this method short-circuits to `None` before any HTTP is attempted.

Returning `None` (not `0`) is a deliberate safe default — `signal_rules.classify` treats `None` as "telemetry unavailable, don't emit orphan candidates." So the orphan-detection branch at `signal_rules.py:208-216` literally never fires today, regardless of Loki state.

This is a more important detail than the proposal's framing implies: **runtime-observer in either the-loom or Tapestry needs the upstream telemetry rollup AND a wired-up `TelemetryClient`.** The current stub is a forward-compatible placeholder, not a degraded path. The Loki framing isn't wrong, just incomplete — the failure mode is "intentional v1 stub," not "Loki has no read API."

**Fix required:** sharpen the wording in the "What the observer is observing today" section to reflect that `invocations_30d` is a stub by design, not a degraded path that breaks at the Loki edge.

### 3.3 "All four converged on the same position despite running independently with different prompts." **OVERSTATED.**

The four inputs the proposal claims converge:

1. MS-agent fleet audit (`msagent_fleet_audit_synthesis_complete_2026_06_18`)
2. Critical evaluator of MS-agent's Path B proposal
3. Alternative architectures researcher
4. Risk surfacer
5. Loom-agent platform audit

Inputs 1–4 are all dispatched and synthesized by MS-agent. They were briefed against MS-agent's own Path B framing and bind to the `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13` rule the proposal already cites at the top.

Input 5 is loom-agent's, independent of MS-agent. But §3.1 above shows the proposal mis-cites it.

**The "convergence" is real on the surface (defer to Tapestry) but the mechanism is largely "every agent was told Tapestry is canonical, so every agent recommended Tapestry destinations."** That's not zero signal — it tells you the binding rule is internally consistent — but it's much weaker evidence than "four independent agents with different prompts reached the same architectural conclusion."

The two truly independent strands of evidence are (a) the binding rule itself and (b) the PROBE-verified fatal flaws. Both are strong. The "four-way convergence" framing implies independence the inputs don't actually have.

**Fix required:** soften §"Audit context — four independent verifications" to "the converged position holds across four audits that share the canonical-Tapestry binding rule" + spell out which of the inputs are genuinely independent of MS-agent's framing.

### 3.4 Convergence claim's third weakness: "alternative architectures researcher scored 9 patterns; Path B was right direction." **UNVERIFIABLE.**

The proposal cites "9 alternative patterns scored" with no link to that research output. The other audits' synthesis memos exist (`msagent_fleet_audit_synthesis_complete_2026_06_18`); this one apparently doesn't. Either:

- the 9-alternatives research is captured in an unsaved subagent transcript (low confidence — gone after the session ends)
- the research is in the synthesis memo above but I couldn't see the scoring breakdown
- the line is a paraphrase, not a direct citation

Recommend the proposal either link the artifact or drop the line.

---

## 4. Verified-ambiguous claims

### 4.1 "~50 LOC" memory-write extension.

The 50-LOC estimate is plausible for the synthesis-memo path described:

- `memory_client.py` mirroring `candidate_client.py` (~30 LOC for an MCP HTTP client with auth-bridge fallback)
- synthesis-builder helper in `main.py` (top-N candidate ranking + kind histogram + suggested-action one-liner)
- `_run_once_async` call-site addition

But I haven't seen the actual diff. **Resolves with:** spike the PR; if it grows past ~150 LOC, that's a signal the design is wrong and the "cheap thing now" framing breaks. The proposal should commit to a LOC ceiling and what to do if the ceiling is breached.

### 4.2 "Tapestry timing — none of those are in v1 scope."

Per `tapestry/docs/proposals/2026-06-13-v1-scope-and-roadmap.md`, the v1 steps are auth → agent-context → project-registry → engine → templates+CLI → dashboard → architecture-registry+policy → telemetry-ingestion+observatory → discipline plugins. The runtime-observer + auto-promotion the proposal defers would live in `project-observatory` (Step 7a). v1 ratifies the *migration* of telemetry-ingestion + observatory but doesn't necessarily ship Phase 6 inside that step. The proposal claims "none of those are in v1 scope" which is **plausibly true for the runtime-observer per se** but depends on what "v1 ships" means in the roadmap.

**Resolves with:** explicit confirmation from Tapestry-agent (or whoever owns the v1 roadmap) of whether Phase-6 observatory work is in v1 or v2. The proposal's question 4 asks this; it should be answered before the proposal merges.

### 4.3 "If 95% of traffic is per-(tenant, agent_id), the gap is cosmetic" (open Q3).

Risk surfacer's #10 is the right question but unanswerable from the proposal alone. The proposal's response — "should this require a 7-day traffic sample?" — is sensible. Whether the sample blocks the proposal depends on whether Tapestry will need to instrument the default-agent path before v1 ships. If yes: sample now. If no (the default-agent path is going away post-Tapestry): defer.

**Resolves with:** a quick Render log query to count `/chat` (default agent) vs `/chat/{tenant}/{agent_id}` requests over the last 24-48h. Doesn't need 7 days.

---

## 5. Logic-and-reasoning critique

### 5.1 The convergence inflation (already covered in §3.3).

The proposal leans hard on "all four converged." Once you remove the shared binding rule, the convergence shrinks to: (a) two PROBE-verified fatal flaws and (b) loom-agent's audit recommending dispatch-promotion fix IN the-loom (not deferral). That's still a strong case for the deferral direction, but a different case than the proposal makes.

### 5.2 The "deferral assumes Tapestry ships in usable timeframe" assumption is undefended.

The proposal's exposure if Tapestry slips:

- **6 months:** operator continues to click Promote manually on candidates emitted by self-observer; the ~50 LOC synthesis memo gives next-session agents context; no auto-promotion. Tolerable but increasingly annoying as candidate volume grows.
- **12 months:** the 40-candidate problem becomes a 400-candidate problem (assuming roughly current observer cadence). Manual triage breaks. The promotion-loop differentiation that justifies the v1 SKU (per `loom_agent_tapestry_planning_synthesis_2026_06_13` §C) goes unexercised at scale before customers see it.
- **Indefinite slip:** the proposal's deferral becomes "we never built auto-promotion." Different problem.

The proposal should explicitly own this risk. The ~50 LOC stopgap genuinely is the right cheap move under any timing assumption, but the proposal should commit to a tripwire (e.g., "if candidate count exceeds 100 before Tapestry Step 7a ships, revisit").

### 5.3 Question 7 — synthesis-memo + candidates table = two channels. **My judgment: NOT a violation.**

The `one_pattern_one_canonical_home` rule binds reusable *patterns* (skills, agents, tools) to one home. The candidate table and the synthesis-memo serve different audiences:

- Candidates table = operator-actionable rows in a dashboard (UI surface)
- `self_observer_synthesis_latest` memory = agent-readable narrative summary at SessionStart (context surface)

These are not duplicates of the same pattern; they are different *projections* of the same underlying observation. Analogous to a database table and the README that describes it — the README isn't a duplicate of the table.

That said: if the memory grows into something that needs its own write path, lifecycle, or schema (e.g., per-candidate-status updates), that's the signal it's becoming a parallel state store and the rule starts to bind. **For the synthesis-memo-as-summary use case, no violation.**

### 5.4 Several "open questions" should be closed before this ships.

Per loom-agent's audit + PROBE in this review:

- **Q2 (memory upsert idempotency)** — PROBE resolves it. Storage IS atomic upsert by id, where id = stable name. Close.
- **Q3 (traffic share)** — needs a 30-min Render log query, not a 7-day sample. Close after measurement.
- **Q5 (loom-keep-warm cron yaml)** — loom-agent's audit already specifies the diff implicitly (move from "claimed deleted in render.yaml:336-341" to "declared as a Render service block with `*/10 * * * *` schedule"). Cheap diff. Close.
- **Q6 (orphan service deletion safety)** — loom-agent's audit verified zero callers via grep across the repo (`audit.md:33-34, 62-64, 137-138, 344`). The verification report independently re-grepped (`verification.md:33`) and confirmed nothing references `loom-mcp-memory-server.onrender.com`. **The verification IS complete.** Close.

That leaves Q1 (cold-start third option — likely no), Q4 (Tapestry timing — needs Tapestry-agent), Q7 (one-canonical-home — my judgment above: no violation).

3 of 7 should be closed before this ships. The proposal has them open as if they're unresolved.

### 5.5 What the proposal doesn't ask.

#### 5.5.1 Operator burden under deferral.

The proposal moves runtime-observer + auto-promotion to Tapestry. Until Tapestry ships those, the operator manually clicks Promote on every candidate. With 40 candidates today and the observer running every 6h, scrubbing the queue is already a chore. Does the proposal accept that operator clicks remain the sole promotion path for the duration?

If yes: state it explicitly. If no: name the in-the-loom near-term mitigation that loom-agent's A3 already provides — closing the dispatch-promotion automation gap with ~1 hour of code that makes existing operator Promote clicks actually reach the engine. This is **fundamentally different from auto-promotion** (operator still decides; only the mechanics auto-fire after the decision) and it's the right hygiene under either timing assumption.

**Strong recommendation:** the proposal should add A3 from loom-agent's audit (close dispatch-promotion gap IN the-loom NOW) as a sibling change to the synthesis-memo extension. ~1h work; complementary; survives Tapestry migration unchanged.

#### 5.5.2 Synthesis-memo + cold-start MCP.

`feedback_mcp_is_canonical_not_optional` (updated 2026-06-18) confirms `loom-agent-context` is on **free tier** as of audit. The 6h cron fires the synthesis-write. If the MCP is cold-spun-down at that moment, what happens? PROBE'd `loom-keep-warm` schedule = `*/10 * * * *`, so 10-min margin vs ~15-min spin-down. Most cron fires hit a warm MCP. But not guaranteed.

If the synthesis-memo's `memory_write` hits cold-spinup latency (20-30s per loom-agent's audit §2 cold-probe), and the cron job's HTTP client has a short timeout (default httpx is 5s), the write fails silently, and SessionStart agents won't see fresh state. The proposal should:

- specify the timeout used by the new `memory_client.py` (recommend ≥30s read/write to absorb cold start)
- specify the retry policy (recommend 1 retry after 5s)
- consider whether the synthesis-write should ping `loom-keep-warm` first to warm the MCP

None of this is hard; the proposal just doesn't address it.

#### 5.5.3 Synthesis-memo content stability.

If the synthesis content is non-deterministic (e.g., includes a timestamp or counter-of-runs in the body), every cron fire writes a "different" content. Postgres ON CONFLICT DO UPDATE still works (re-embedding + replacing the row) — but the embedding compute happens on every write. Cost is low (fastembed BAAI/bge-small-en-v1.5 is fast), but it's a quiet design choice. The proposal should specify whether the content has timestamp-like fields or aims for deterministic stability when nothing has changed.

#### 5.5.4 Skip-on-empty interaction with the dedup.

The proposal says "Skip-on-empty: if no candidates emitted this run, skip the memory_write to prevent placeholder churn." But "no candidates emitted this run" includes the case where every candidate was deduped against open candidates (per `candidate_client.preload_dedup`). If the observer dedupes 40 candidates against an already-full set, the synthesis memo should *still update* (the existing 40 are still actionable). The skip-on-empty condition should be "no candidates currently open" not "no candidates emitted this run." Clarify.

---

## 6. Open questions that should be closed now

Per §5.4 above:

1. **Q2 (memory upsert idempotency)** — PROBE'd. Close with citation: `mcp_server.py:105-108` + `storage.py:207-232` confirm atomic upsert by id=name. Add to proposal.
2. **Q3 (default-agent traffic share)** — answerable with a 30-min Render log query against `make-skills-api`. Run before merging; report the percentage in §"Defer to Tapestry" if it tilts the urgency.
3. **Q5 (loom-keep-warm yaml diff)** — loom-agent's audit specifies the diff direction; the cron block needs to be added under `services:` in `render.yaml` with schedule `*/10 * * * *`. Cheap. The proposal can paste the exact yaml.
4. **Q6 (orphan deletion safety)** — verified twice already (loom-agent's audit + verification). Close.
5. **Q7 (one-canonical-home)** — my judgment: not a violation (§5.3). Document and close.

That leaves only Q1 (cold-start, operator's call between 2 options) and Q4 (Tapestry timing, needs Tapestry-agent input) as legitimately open.

---

## 7. Hidden risks MS-agent missed

### 7.1 The proposal's biggest hidden risk: it cites loom-agent's findings to validate its own conclusion, but the citations don't actually validate the conclusion (§3.1).

Loom-agent's audit says: "fix dispatch-promotion gap NOW in the-loom; migrate observer + auto-promotion design to Tapestry." The proposal collapses both into "defer to Tapestry." Loom-agent would not endorse this version of the proposal. **The proposal's strongest "independent corroboration" is actually fragmented support, not endorsement.**

### 7.2 Self-host customers see no observability change post-Tapestry.

Per the canonical-Tapestry framing, telemetry-ingestion migrates to Tapestry. Self-host customers in v1+ still don't have Postgres telemetry rollup unless Tapestry's `services/telemetry-ingestion/` ships with a rollup substrate. The proposal's "defer telemetry rollup to Tapestry" implicitly assumes Tapestry will do this. **What if Tapestry's telemetry-ingestion also ships log-only?** Then the "self-host blind" fatal flaw persists post-migration, just at a different repo. The proposal should either:

- name the requirement explicitly: "Tapestry's `services/telemetry-ingestion/` MUST include Postgres rollup + read API for self-host parity"
- or accept that self-host runtime-observation is permanently out of scope.

### 7.3 The 9-kind taxonomy is now contested.

The proposal correctly identifies that `orphan/hot_path/degrading` don't fit the 9-kind enum. But the 9 kinds are anchored at `docs/proposals/2026-06-12-promotion-categorization.md §4.1-§4.9` (per the in-file comment at `models.py:27-30`). When Tapestry eventually wants runtime observations, it'll face the same question. **Is the right answer to extend the taxonomy at the proposal source first, or to add a sibling `observation_kind` enum and decouple it from `candidate_type`?** This is a Tapestry-time decision but should be flagged now — the proposal currently implies the question is "for later" without naming what "later" looks like.

### 7.4 `agentic-upskilling` plugin skill is the documentation entry-point for the existing self-observer.

Per memory `liz_patterns_plugin_install_test_passed_2026_06_14`, the canonical patterns home is the `liz-patterns` plugin, and `agentic-upskilling` is listed as one of its agents. Per `lesson_self_observer_gap_revealed_by_skill_mislabel_audit_2026_06_13`, the self-observer IS the implementation behind `agentic-upskilling`. When Tapestry absorbs the observer, the agent stub in the plugin needs to point at the new location. The proposal doesn't mention this seam — it's a small thing but it's the kind of detail that becomes a "wait, this is broken" moment six months from now.

### 7.5 No tripwire for "the proposal was wrong."

What evidence would falsify the deferral? E.g., if the synthesis-memo doesn't move the needle on operator decisions after 4 weeks (operator still clicks Promote with no use of the memo), the cheap-thing-now investment is wasted. The proposal should name the success/failure signal. Default: "operator subjectively reports the memo is useful after 4 weeks." Better: "memo content appears in operator's stated reasoning on N% of Promote clicks over 4 weeks" (visible in policy decision reasons).

---

## 8. Specific edits the proposal needs before it ships

### 8.1 Section "Loom-agent's parallel call" (lines 72-79). **REWRITE.**

Replace with the actual quote from loom-agent's audit. The accurate paraphrase is:

> Loom-agent's `docs/research/2026-06-17-platform-state-audit.md` §B-§D recommends:
> - §A3 (fix NOW in the-loom): close the dispatch-promotion automation gap with ~1h of in-service auto-trigger code at PATCH time (lines 405-406)
> - §B (defer to Tapestry — migrates anyway): memory schema, dashboard redesign, project-observatory build-out, telemetry-ingestion query API (lines 408-412)
>
> The runtime-observer service this proposal originally proposed maps onto §B (project-observatory build-out). But loom-agent's A3 is sibling work that should land NOW in the-loom and is missing from this proposal — see §"What lands now" below.

This is a substantive change. It strengthens the proposal by adding the dispatch-promotion fix to "what lands now."

### 8.2 Section "Audit context — four independent verifications" (lines 14-26). **SOFTEN.**

The "all four converged on the same position despite running independently with different prompts" claim should become:

> The four MS-agent-dispatched audits all bind to the `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13` rule (which routes every "where does this belong?" question toward Tapestry destinations). Loom-agent's separately-dispatched platform audit corroborates the deferral direction for runtime-observer + auto-promotion specifically, while recommending the dispatch-promotion mechanics gap be closed in-place. The PROBE-verified fatal flaws (§"My original Path B proposal + its fatal flaws") are the strongest independent evidence; the rest is convergence under a shared binding rule.

### 8.3 Section "What lands now" (lines 86-105). **ADD A4 (loom-agent's A3).**

Add a fourth item between A2 and A3:

> **A4 (new): Close the dispatch-promotion automation gap.** Per loom-agent's A3 (`docs/research/2026-06-17-platform-state-audit.md:405`): in `the-loom/services/architecture-registry/main.py:206-211`, after a PATCH that sets `status='promotion_requested'`, fire-and-forget `promote_dispatcher.dispatch_promotion`. Add kind-aware filter (skill only, until other handlers exist per `bridge_closed_end_to_end_2026_06_13`). ~1h code + tests. **This is in-scope for "what lands now" because:** (a) loom-agent verified the engine bridge works end-to-end for kind=skill; (b) without it, every operator Promote click on a skill candidate dead-ends at `promotion_requested` and requires manual curl. The synthesis-memo and the dispatch-fix are complementary — synthesis-memo gives agents context, dispatch-fix makes operator clicks actually deliver.

### 8.4 Section "What the observer is observing today" line 34. **SHARPEN.**

Replace:

> Orphan detection at `signal_rules.py:208-216` queries `TelemetryClient.invocations_30d()` — but the data source is broken because telemetry-ingestion only writes to Loki via stdout (`the-loom/services/telemetry-ingestion/skill_usage_handler.py:68-87`); no Postgres persistence + no read API. So the orphan check is degraded today.

With:

> Orphan detection at `signal_rules.py:208-216` queries `TelemetryClient.invocations_30d()` (`telemetry_client.py:22-35`), which is a v1 stub returning `None` on every call. `signal_rules.classify` treats `None` as "telemetry unavailable, don't emit orphan candidates" — so the orphan branch never fires today. Even if upstream telemetry got a Postgres rollup + read API (telemetry-ingestion is currently log-only per `skill_usage_handler.py:68-87`), the observer's reader would still need wiring. The stub is forward-compatible by design, not a degraded path.

### 8.5 Section "Open questions" (lines 124-138). **CLOSE 5 OF 7.**

Per §6 above:

- Q2: close with citation `mcp_server.py:105-108` + `storage.py:207-232`. Atomic upsert by id=name. Confirmed.
- Q3: convert to "decision criterion: 30-min Render log measurement before committing to Tapestry-side instrumentation work. Threshold: if default-agent share > 50%, sample longer; if < 20%, defer."
- Q5: provide exact yaml diff inline or link to a draft PR.
- Q6: close with citation to loom-agent's audit §2.137-138 + verification §2.33.
- Q7: close with the my-judgment paragraph or remove the question.

Leave Q1 (operator's cold-start call) and Q4 (Tapestry timing) open. Add Q5-new: "What's the timeout + retry policy for the new `memory_client.py` to survive MCP cold-spinup?"

### 8.6 Section "What lands now" §A1 (line 102). **CHECK.**

The proposal frames A1 as "operator's call: pick cold-start strategy." Per `feedback_mcp_is_canonical_not_optional` (updated 2026-06-18), this is correct — Liz's decision. Leave as-is.

### 8.7 Add a "What this proposal does NOT solve" section.

The proposal has an "Explicitly NOT doing" list but it's framed as "things we considered and rejected." A complementary list of "things this proposal leaves unsolved" would help downstream readers:

- Auto-promotion for the 40 production candidates (operator continues manual review)
- Self-host telemetry parity (depends on Tapestry's `services/telemetry-ingestion/` shipping Postgres rollup)
- The 8 destination-handler gap (`kind=agent`, `inline_tool`, etc. — defers to Tapestry's `services/skill-making/`)
- `agentic-upskilling` plugin agent's pointer to the future Tapestry observer location

---

## 9. Net assessment

The proposal's reasoning is mostly sound, the PROBE work on the two fatal flaws is rigorous and verified, and the deferral direction is consistent with the binding `feedback_tapestry_is_canonical...` rule. **The proposal under-claims the synthesis-memo's idempotency (Q2 is closable), over-claims convergence across audits, and most importantly mis-cites loom-agent's audit on two load-bearing points** — flipping a recommendation to fix dispatch-promotion in the-loom NOW into an endorsement of deferral.

The fix is mechanical: cite loom-agent accurately, add dispatch-promotion-gap closure to "what lands now," soften the convergence claim, close the 5 PROBE-resolvable open questions, name 4-5 hidden risks. After those edits, the proposal is ready to ship.

The deeper question the proposal raises and answers correctly: **"is runtime observation a hygiene gap or a product capability?"** Hygiene goes in legacy source repos that survive only during migration; product capability lives in Tapestry. Runtime observation is product capability. The proposal is right to defer it. The proposal is also right that the cheapest near-term unlock is a synthesis-memo so future-session agents see observer state without dashboard visits.

Net: **accept-with-fixes** per §1. The fixes are bounded; the proposal's spine is sound.

---

## Appendix: PROBE citations index

**Make_Skills:**
- `Make_Skills/core/runtime/agent.py:110-127` — builtin_tools assembly + `create_deep_agent` call
- `Make_Skills/core/skill_making/compiler.py:80-145` — `_run` closure + `_emit_telemetry` call sites
- `Make_Skills/core/skill_making/compiler.py:161-179` — `_emit_telemetry` signature + skill_id/source_tenant_id requirement
- `Make_Skills/services/api/main.py:260-286` — `/chat` endpoint (proposed correct instrumentation point)

**the-loom:**
- `the-loom/services/telemetry-ingestion/skill_usage_handler.py:55-92` — stdout-only emit, no Postgres persistence
- `the-loom/services/architecture-registry/models.py:25-46` — 9-kind enum, in-file comment naming the doc anchor + migration cost
- `the-loom/services/agent-context/mcp_server.py:80-108` — `_id_from_name` and `_resolve_tenant`
- `the-loom/services/agent-context/storage.py:151-233` — `insert_records` with atomic upsert by id
- `the-loom/services/self-observer/config.py:44-80` — REGISTRIES (4 hardcoded repos)
- `the-loom/services/self-observer/config.py:155-164` — `EMIT_THRESHOLD = 0.3`
- `the-loom/services/self-observer/signal_rules.py:185-271` — `classify()` and the orphan-detection branch at 208-216
- `the-loom/services/self-observer/telemetry_client.py:22-35` — `invocations_30d` stub returning None
- `the-loom/services/self-observer/main.py:38-49, 52-63, 94-140` — _SELF_NAME_PATTERNS, `_is_self`, `_run_once_async`

**Prior audit + verification (the-loom):**
- `the-loom/docs/research/2026-06-17-platform-state-audit.md:399-425` — Recommendations §A/§B/§D
- `the-loom/docs/research/2026-06-17-platform-state-audit-verification.md:16-95` — verification PASS

**Memory records:**
- `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13` — binding rule
- `feedback_one_pattern_one_canonical_home_not_per_repo_copies_2026_06_13` — referenced in proposal Q7
- `bridge_closed_end_to_end_2026_06_13` — kind=skill loop closed; 8 other kinds ack-defer
- `session_state_self_observer_loop_closed_input_side_2026_06_13` — 40 candidates, breakdown by repo and kind
- `msagent_fleet_audit_synthesis_complete_2026_06_18` — MS-agent's 4-agent audit synthesis
- `feedback_mcp_is_canonical_not_optional` — updated 2026-06-18 with cold-start state
- `loom_agent_tapestry_planning_synthesis_2026_06_13` — capability ownership boundaries
- `liz_patterns_plugin_install_test_passed_2026_06_14` — canonical patterns home including `agentic-upskilling`
- `lesson_self_observer_gap_revealed_by_skill_mislabel_audit_2026_06_13` — the lesson that built the self-observer

---

*End of review.*
