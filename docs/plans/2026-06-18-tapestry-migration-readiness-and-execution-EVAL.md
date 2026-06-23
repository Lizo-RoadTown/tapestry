# Evaluation — Tapestry migration readiness + execution plan (2026-06-18)

**Evaluator:** independent reviewer subagent (Opus 4.7), invoked by loom-agent at operator (Liz) request
**Subject:** `c:/Users/Liz/tapestry/docs/plans/2026-06-18-tapestry-migration-readiness-and-execution.md` (819 lines, loom-agent, 2026-06-18)
**Verdict scope:** binding-rule conformance + duplication + new-work coverage + honesty + actionability + omissions

---

## §1. TL;DR

**Accept with required fixes.** The plan is solid on PROBE discipline, new-work cataloging (B1 REST endpoints, A3 trigger, B2 synthesis), and the dependency graph. It has **three load-bearing omissions** (no reference to the existing `migration-cicd/` doctrine, no stuck-candidate replay plan, no explicit parallel-build reaffirmation) and one **operator-decision conflict** (week-1 spawn recommendation contradicts the v1 plan's prior trigger condition without acknowledging the contradiction). All fixable with documentation edits, not structural rework.

---

## §2. Conflicts with binding rules

### 2.1 Parallel-build framing — NOT VIOLATED, but UNDER-EMPHASIZED

**Binding rule:** `feedback_tapestry_parallel_build_not_pause_and_migrate_2026_06_12` — "Existing 5 repos KEEP being built. No pausing. Migration happens only when Tapestry is fully built (or at least clearly ready for a given piece). **Liz is still experimenting.**"

**Plan posture:** the plan never explicitly affirms this rule. It doesn't recommend pausing — Steps 1-8 read as lift/refactor against stable source — but it also doesn't carry forward the "Liz is still experimenting" caveat anywhere. The week-2 sprint and the gantt chart (Appendix B.1) read as a hard timeline ("V1 ship gate: 2026-07-25") that does not budget for in-flight source-repo churn.

**Specifically problematic:** §8 Closing line — *"the longer source repos remain 'the place where work happens,' the more entrenched the legacy-source framing becomes"* (line 814). This pushes against the parallel-build doctrine: it implies source-repo work is itself a problem. The binding rule says source-repo work continues until Tapestry is ready *for that piece*. The Closing's framing inverts the rule's polarity.

**Required edit:** add a §1.5 or §2.0 callout that quotes the parallel-build memo verbatim and clarifies that Steps 1-8 begin only when the corresponding source-repo piece has stabilized — not on a fixed gantt cadence.

### 2.2 Tapestry-agent spawn timing — CONTRADICTS the v1 plan, but ALIGNS with the canonical-framing memo

**Tension:**
- `tapestry_v1_plan_synthesized_proposal_2026_06_13` (MS-agent's prior synthesis): *"defer. Spawn only when first non-trivial migration touches >2 slots simultaneously AND neither current agent has clean ownership."*
- `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13` (Liz, two days later): *"Tapestry-agent: SPAWN NOW."*

The new plan recommends week-1 spawn (line 221: *"Open Tapestry-agent in week 1, gated by PR-prep-2 completion"*). This **aligns with the later canonical-framing memo** and **supersedes** the v1 plan's defer-condition.

**Plan flaw:** the new plan does not flag this as a deliberate override of the prior trigger condition. It reads as if the recommendation emerged fresh, leaving an operator who only remembers the v1 plan confused about whether they were just told to do the opposite of what MS-agent said three days ago.

**Required edit:** §4 should add one sentence: *"This supersedes the v1 plan's defer-condition (`tapestry_v1_plan_synthesized_proposal_2026_06_13` §E) per Liz's 2026-06-13 directive in `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13`."*

### 2.3 Layered-explanation default — NOT VIOLATED

The plan is depth-only (no ELI5 / quick reference layers). That is acceptable for a planning artifact whose audience is two AI agents + the operator already steeped in the architecture. No edit required.

---

## §3. Duplication with prior memos

### 3.1 NOT a duplication — the new plan is a legitimate UPDATE to the v1 synthesized proposal

The new plan correctly references the v1 roadmap throughout (`v1 roadmap §5 Step N` markers in every Step section). It adds Step 7a (telemetry-ingestion + project-observatory + observation-decomposer), surfaces the B1/A3/B2 carry-over items, and adjusts the sequencing. **This is the legitimate value-add.** No re-litigation of SKU shape, auth provider, customization model, or billing — those settled choices are referenced via roadmap §6/§7 without being re-argued.

### 3.2 MAJOR GAP — the plan IGNORES the migration-cicd/ doctrine

`tapestry_migration_cicd_plan_committed_2026_06_13` records that MS-agent shipped 5 documents at `tapestry/docs/migration-cicd/` containing:
- 6 GitHub Actions workflows + parity gates + rollback procedure (`01-pipeline-architecture.md`)
- drift-catcher test + 4 mandatory test categories + golden-payload corpus (`02-testing-strategy.md`)
- `tapestry-migrate` Python package + 12 CLI commands at `packages/migration-toolkit/` (`03-migration-toolkit-design.md`)
- 8-state runbook template per migration step (`04-runbook-template.md`)
- 8 contract assertions (`README.md`)

**The new plan references `migration-cicd/` exactly ONCE** — line 89 of Table 2.3, listing the directory as one that exists. No section, step, ADR, sprint task, or done criterion in the new plan references:
- the drift-catcher test as a parity gate for Steps 2, 4, 7
- the runbook template as the artifact Tapestry-agent fills out per step
- the `tapestry-migrate` toolkit (the plan instead says "1 PR per concern" without saying which tool)
- the 8 contract assertions (especially #5 "Tapestry is canonical; source prototype is frozen at parity-verified → prod-rolling transition" — this IS the freeze criterion the new plan invents from scratch in §5 done-criteria)
- `packages/migration-toolkit/` as a destination (the plan mentions `packages/auth/`, `packages/cli/` but never the toolkit)

**This is not a contradiction — it is a load-bearing OMISSION.** The migration-cicd plan is the *operating framework* the new plan should be sequencing against. By ignoring it, the new plan implicitly proposes a parallel framework (ad-hoc per-step PRs + done criteria) when one already exists.

**Required edit:** add §0 or §5.0 referencing migration-cicd/ as the operating framework. Each Step's done-criterion should map to a runbook state-machine transition. Done-criteria for Steps 2, 4, 7 should reference drift-catcher CI gates. The toolkit (`packages/migration-toolkit/`) should be added as a PR-prep-3 or Step-1.5 deliverable.

### 3.3 NOT duplication — restating settled framing is appropriate

The new plan restates the v1 ship gate (Steps 6+7), the WorkOS recommendation, the dual-write window — but cites these as ratified prior decisions. Not duplication, scaffolding.

---

## §4. Coverage of new work this session (verified / missing / overstated)

### 4.1 VERIFIED — B1 REST endpoints

§2.1 Table row "agent-context (NEW: /v1/write + /v1/read)" cites `main.py:210-267` for B1. §6.1 carries the must-port-verbatim note. §7 Q6 surfaces the operator-decision (REST vs MCP canonical). **Correctly cataloged.**

### 4.2 VERIFIED — A3 BackgroundTasks auto-trigger

§2.1 Table row + §6.2 + §7 Q5 cover A3. The §6.2 "Tapestry-survival note" preserves the architectural decision (HTTP-endpoint vs direct storage write). §7 Q5 names this as needing ADR. Appendix B.3 mermaid diagram makes the decision visual. **Correctly cataloged AND elevated to ADR-first.**

### 4.3 VERIFIED — B2 self-observer synthesis

§2.1 Table row + §6.3 cite `memory_client.py` + `synthesis.py`. The MANIFESTO §4.3 mapping (project-observatory absorbs self-observer) is correctly applied. **Correctly cataloged.**

### 4.4 VERIFIED — Followup §3.1 sub-component caveats

§6.8 surfaces all three (risk classifier, judgment-substep skill-vs-agent rule, sibling unsupported_candidate threshold) as Step 7a-scope with ADR-each requirement. §7 Q7 confirms the slotting. **Correctly cataloged.**

### 4.5 VERIFIED — actionable_backlog_count metric

§6.8 third bullet + Step 7a outputs list (line 434). **Correctly cataloged.**

### 4.6 MISSING — drift-watcher pattern

The runtime-observation followup §3.3 introduces a drift-watcher pattern (oversight subagent that runs alongside long executions). The new plan does NOT mention this. Either it's out-of-scope for migration (in which case state that) or it should be slotted as a Step 7a or post-v1 capability.

**Required edit:** add one bullet in §6 stating "drift-watcher pattern is out-of-scope for v1 migration; lands as v2 capability in `tapestry/engine/local-observer/` or `tapestry/services/project-observatory/`" — OR rebut and add to Step 7a scope.

### 4.7 OVERSTATED — "B1's REST endpoints aren't in original v1 roadmap"

Line 28 + §6.1 frame these as net-new. They ARE new code. But the v1 roadmap §5 Step 2 simply says "lift agent-context" — it doesn't enumerate endpoints. The endpoints being added is not a roadmap-mismatch; it's a within-step refinement. The "NOT in original v1 roadmap" framing inflates novelty slightly.

**Required edit:** soften §6.1 framing from "Not in original v1 roadmap" to "Added since the v1 roadmap was authored; ports verbatim into Step 2's scope."

---

## §5. Honesty about unknowns

### 5.1 GOOD — templates location uncertainty

§2.2 Table row + §7 Q8 admit the templates source is missing (`Make_Skills/templates/` does not exist per PROBE). Names the three possibilities (other path, in `adapters/development/`, or not yet authored). Marks operator clarification as a week-1 gate. **Honest.**

### 5.2 GOOD — tenant_id audit not yet run

§4 Preparation gates table + §8 week-1 day-3-5 task explicitly call out the audit hasn't run. **Honest.**

### 5.3 PROBLEMATIC — wall-clock estimates

The plan offers very specific numbers: "4-6 weeks to Step 6, 6-8 weeks to v1 ship gate", "5-7 developer-days for Step 2", "8-12 developer-days for Step 7", "2026-07-25 ship gate" in the gantt. These are presented without an uncertainty band or basis.

**Honesty issue:** the plan has not actually scoped any of this work via task decomposition — it counts LOC and gestures. LOC count is a poor proxy for migration effort, especially when:
- Schema migration involves coordinating with live production data
- Multi-step cutover with dual-write window inherently widens calendar
- Operator is one human with finite attention; "one operator + two AI agents" is not a 3x parallelization
- The roadmap's own framing says "4-8 weeks" — the new plan tightens this to "4-6 weeks" without justification

**Required edit:** add a §8.5 "Wall-clock caveat" stating estimates are LOC-derived, do not account for operator review latency, do not budget for parallel source-repo work continuing, and should be treated as floor not ceiling. Or remove the specific date (`2026-07-25`) from the gantt.

### 5.4 PROBLEMATIC — "Operator + two AI agents working in parallel"

Used in §1 line 17 and §8 line 624. The two-agent parallelization assumes Tapestry-agent spawns + becomes productive immediately. Realistically, a spawned agent needs:
- First-session onboarding (reading MANIFESTO + roadmap + this plan + migration-cicd + history)
- Memory accumulation
- Calibration with operator

Treating Tapestry-agent as a turnkey parallel worker from day-1 of week-2 is optimistic.

**Required edit:** acknowledge ramp-up cost for Tapestry-agent (1-2 sessions before productive on owned PRs).

---

## §6. Operator-actionability findings

### 6.1 GOOD — week-1 sprint is concrete

Day-by-day breakdown, trigger-to-advance conditions per task, named executor (loom-agent vs operator vs Tapestry-agent). This passes the "checkable signal not vibe" test.

### 6.2 GOOD — done criteria per Step

Every Step in §5 has a specific done criterion (e.g., Step 2: "every consuming repo's `.mcp.json` points at `mcp.tapestry.io`"). Most are operator-checkable.

### 6.3 PROBLEMATIC — Step 7 done criterion is the recursive proof

Line 417: *"Promote click in Tapestry dashboard → Tapestry architecture-registry → Tapestry policy → Tapestry engine → kind=skill compiled → Tapestry candidate marked promoted. Same recursive proof as `bridge_closed_end_to_end_2026_06_13` but inside Tapestry."*

This is correct but assumes Step 6 (dashboard) is done before Step 7's done criterion can be checked. The dep graph (§3) says Step 6 depends on Step 4 (engine in Tapestry), not Step 7. **Re-read:** actually, Step 6 + Step 7 are parallel after Step 4. So Step 7's done criterion fires only after BOTH Step 6 and Step 7 land. The done criterion should say "needs Step 6 dashboard to be live" explicitly.

**Required edit:** Step 7 done criterion should note: "checkable only after Step 6 ships; until then, use synthetic PATCH against Tapestry architecture-registry to drive the recursion."

### 6.4 GOOD — operator decisions surfaced explicitly

Q4 (telemetry pacing), Q8 (templates location), Q1 (data-migration strategy), and the WorkOS spin-up are all named as operator gates. Not buried.

### 6.5 MISSING — what does the operator do when Tapestry-agent + loom-agent disagree?

The migration-cicd doctrine has an arbitration protocol (per `tapestry_v1_plan_synthesized_proposal_2026_06_13` "propose → counterproposal → ADR → Liz arbitrates"). The new plan doesn't reference this. Steps 2, 4, 7 are explicitly multi-agent (Tapestry-agent + loom-agent / + ms-agent). No conflict-resolution path stated.

**Required edit:** add a §0.1 or §4.1 referencing the arbitration protocol from the v1 plan §F.

---

## §7. Things the plan MISSES

### 7.1 OMISSION — Stuck-candidate replay for pre-A3 candidates

**The issue:** A3 (`63cf1ea`) fires only on PATCH-to-promotion_requested events going forward. Candidates already in `promotion_requested` status before A3 shipped do NOT auto-dispatch. The just-resolved layered-explanation candidate was a manual fix (per session context — operator had to intervene).

**The plan does not address this.** Any candidate sitting in `promotion_requested` from before A3 (commit 2026-06-18 mid-day) is silently stuck. The migration to Tapestry compounds this: the migrated data inherits the stuck rows.

**Required edit:** add §6.9 "Pre-A3 stuck-candidate sweep" — before Step 7's data migration, run a one-time backfill that lists every candidate in `promotion_requested` with `updated_at < <A3 deploy timestamp>` and either manually re-trigger or insert a replay-dispatcher task.

**Concrete query for the sweep:**
```sql
SELECT id, name, candidate_type, status, updated_at
FROM candidates
WHERE status = 'promotion_requested'
  AND candidate_type = 'skill'
  AND updated_at < '<A3 deploy timestamp UTC>';
```

### 7.2 OMISSION — Bridge cross-repo span explicitly during the weeks-3-7 window

**Cited but not designed-around.** Appendix C row "Bridge cross-repo span widens during weeks 3-7" with mitigation "Env-var flip mitigates; 4-week window only" is too thin.

Concretely: after Step 4 (engine moves to Tapestry), the the-loom architecture-registry STILL needs to dispatch to Tapestry-engine. Make_Skills's prior engine endpoint gets frozen. Any consumer (or test, or smoke) that still hits the legacy Make_Skills engine will fail silently. The plan should add a freeze-and-redirect step on the Make_Skills side parallel to Step 4 cutover.

**Required edit:** add a "Make_Skills engine freeze + redirect" sub-step to Step 4. The Make_Skills engine returns 302/410 with the Tapestry URL during a freeze window.

### 7.3 OMISSION — Discipline plugin hardcoded URL cutover affects operator's LIVE sessions

The new plan handles this in §6.4 (PR-prep-2 externalizes the URL) and §7 Q3 (plugin loader is session-start-bound). But it misses one thing:

**Operator currently has live Claude Code sessions with the plugin bound to `loom-agent-context.onrender.com`.** When PR-prep-2 ships and the operator updates the plugin, NEW sessions read the new env var. But every running session is bound to the old URL until restart. During the migration, this means:
- Operator must restart all Claude Code sessions at PR-prep-2 cutover (to pick up env-driven config)
- Operator must restart all Claude Code sessions at Step 2 cutover (to point at Tapestry MCP)
- Memory writes during in-flight sessions go to whichever MCP was bound at session-start

**Required edit:** add to §8 Day-2 PR-prep-2 task: "Operator restarts all Claude Code sessions after PR-prep-2 lands; subsequent migrations require the same restart cycle."

### 7.4 OMISSION — Make_Skills engine bridge during cutover, from MS side

The plan covers loom-side cutover (PR-prep-2). It does NOT specify what Make_Skills needs to do during the migration. From the memory `reference_make_skills_engine_bridge`: the bridge is bidirectional. If Tapestry replaces loom on the registry side, Make_Skills's bridge_receiver needs to point at Tapestry's URL.

**Required edit:** add a "PR-prep-2b" task on the Make_Skills side: externalize `LOOM_REGISTRATION_ACK_URL` + `LOOM_TELEMETRY_CALLBACK_URL` to env-driven (note: per §4 line 179 these "already are env-driven" — verify and codify).

### 7.5 OMISSION — Memory data migration: `loom_qji7` Postgres has live data, plan doesn't say what specifically happens to it

§7 Q1 + Q2 cover the question philosophically. But operationally:
- the-loom Postgres URL: `loom_qji7` (per render.yaml)
- Tapestry destination Postgres: unnamed, doesn't exist yet
- pg_dump | pg_restore is mentioned (line 301) but no specifics on: ownership, timing, cutover sync, rollback

**Required edit:** §7 Q1 should reference Tapestry-agent's ADR-0002 as the place this gets specified, and §8 week-2 should include "Tapestry Postgres provisioning" as a prereq task.

### 7.6 OMISSION — Render service naming + ownership during the dual-stack window

When Tapestry services exist alongside loom services on Render:
- Are they in the same Render workspace? (Existing: loom workspace `tea-...`)
- Same Postgres? Separate? (the plan implies separate — `Tapestry Postgres` — but doesn't confirm)
- Cost implications (running two stacks for 4-week dual-write window)

**Required edit:** add §6.10 "Render dual-stack topology" — clarifies workspace, Postgres separation, and cost expectations.

### 7.7 OMISSION — `claude-skills-marketplace` repo is not mentioned

The marketplace is the publishing channel for the discipline plugin (per CLAUDE.md). Step 8 says "Marketplace plugin publishes from Tapestry CI (not from the-loom)" but doesn't describe:
- Does the `lizo-loom` marketplace get updated, or does a new `lizo-tapestry` marketplace get created?
- What happens to existing `tapestry-discipline@tapestry` installations during cutover?
- Cross-repo CI to push from Tapestry to the marketplace repo

**Required edit:** Step 8 expand to enumerate the marketplace cutover.

### 7.8 NICE-TO-HAVE — Tapestry CI/CD doesn't exist yet

Steps 2-8 all assume Tapestry has CI for the drift-catcher, parity gates, etc. The plan does not mention spinning up GitHub Actions on the Tapestry repo. Per migration-cicd/01-pipeline-architecture.md, that's 6 workflows. They need to exist before Step 2.

**Required edit:** add "PR-prep-3 (Tapestry-agent owned): provision Tapestry GitHub Actions" between Tapestry-agent spawn and Step 1.

---

## §8. Required edits before plan is shippable

Concrete line-level changes, in priority order:

### Priority 1 — load-bearing (block-merge until done)

1. **Add §0 or §1.5 referencing the migration-cicd/ doctrine** as the operating framework. Map every Step's done-criterion to a runbook state-machine transition. (Fixes §3.2.)
2. **Add §6.9 stuck-candidate sweep** with the SQL query and a one-time backfill plan. (Fixes §7.1.)
3. **Add §4 paragraph that supersedes the v1 plan's defer-condition** with the canonical-framing memo. One sentence; cite the memo. (Fixes §2.2.)
4. **Add §0.5 "Parallel-build framing reaffirmed"** quoting `feedback_tapestry_parallel_build_not_pause_and_migrate_2026_06_12` verbatim. Revise §8 Closing line 814 to remove the framing inversion. (Fixes §2.1.)

### Priority 2 — accuracy

5. **Soften §6.1 framing** of B1 endpoints from "Not in original v1 roadmap" to "Added since the v1 roadmap was authored." (Fixes §4.7.)
6. **Add §8.5 "Wall-clock caveat"** OR remove the specific `2026-07-25` ship date from the gantt. (Fixes §5.3.)
7. **Revise Step 7 done criterion** to acknowledge dependency on Step 6 OR specify a synthetic-PATCH fallback. (Fixes §6.3.)
8. **Add Tapestry-agent ramp-up acknowledgment** in §8 week-2. (Fixes §5.4.)

### Priority 3 — completeness

9. **Add §6.10 Render dual-stack topology.** (Fixes §7.6.)
10. **Add PR-prep-2b on Make_Skills side.** (Fixes §7.4.)
11. **Add PR-prep-3 for Tapestry GitHub Actions provisioning.** (Fixes §7.8.)
12. **Expand Step 8 marketplace cutover.** (Fixes §7.7.)
13. **Add operator-restart-sessions note to PR-prep-2 + Step 2.** (Fixes §7.3.)
14. **§7 Q1 references Tapestry-agent ADR-0002 + week-2 task to provision Tapestry Postgres.** (Fixes §7.5.)
15. **Address drift-watcher pattern (in-scope vs deferred).** (Fixes §4.6.)
16. **Add §0.1 conflict-resolution protocol reference.** (Fixes §6.5.)
17. **Add "Make_Skills engine freeze + redirect" sub-step to Step 4.** (Fixes §7.2.)

---

## §9. What the plan gets right (preserved without edit)

- PROBE discipline: every claim about source-repo state is file:line-cited
- New-work cataloging: B1, A3, B2, followup §3.1 sub-components all correctly slotted
- Dependency graph (§3): clear, defensible, parallel opportunities named
- §4 trigger conditions for Tapestry-agent spawn: concrete and operator-checkable
- §6 cross-cutting concerns: the architectural decision for A3 (HTTP vs storage write path) is elevated correctly to ADR-first
- §7 Q&A surfaces the right operator decisions
- Appendix A PROBE citation index: gold-standard transparency

---

## §10. Verdict + executive summary

**Accept with the 17 required edits above (4 load-bearing, 4 accuracy, 9 completeness).** The plan is fundamentally sound — its PROBE work, new-code cataloging, and dependency analysis are strong, and its sequencing aligns with the canonical-framing memo. Its weaknesses are omission-shaped, not error-shaped: it ignores the existing `migration-cicd/` framework (the most serious gap), under-emphasizes parallel-build framing, omits stuck-candidate replay, and offers wall-clock numbers without uncertainty bands. After the load-bearing edits land, this becomes the live execution plan; the v1 roadmap remains the strategy doc above it and the migration-cicd/ docs remain the operational doctrine below it.

— Evaluator subagent, 2026-06-18
