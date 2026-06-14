# Master Checklist + Roadmap

**Purpose:** durable on-disk checklist + broader roadmap that survives session boundaries. The primary agent updates this as it works; future agents (and the drift-watcher) read it to confirm direction.

**Maintained by:** the active primary Claude Code agent.
**Read by:** future agents at session start, drift-watcher during execution, the operator any time.

---

## How to use this document

1. **Active Work** (Part 1) is the currently-in-flight task. Check off as steps land. When complete, archive to Part 4.
2. **Queued Work** (Part 2) is what's next in priority order. Lift to Part 1 when active.
3. **Discipline reminders** (Part 3) are binding rules the primary keeps drifting on. Read at session start.
4. **Archive** (Part 4) is completed work, with cross-refs to the commits/memories that landed it.

When the primary updates this document, it commits the change to tapestry repo so the state survives session crashes.

---

## Part 1 — Active Work

### CURRENT: loom-discipline / make-skills-discipline reconciliation (Option A)

**Operator directive 2026-06-14:** "A" — keep loom-discipline canonical at `lizo-loom` marketplace; retire make-skills-discipline from `lizo-skills`.

**Spawned drift-watcher:** background agent `a055617579e203f42` watching this work.

**Status:** in progress as of 2026-06-14.

#### Steps

- [x] **A1.** Revert claude-skills-marketplace commit `2c6e292` (loom-discipline addition I incorrectly made) — committed `9fecb47`, pushed
- [ ] **A2.** Bump `the-loom/.claude-plugin/marketplace.json` loom-discipline entry from v0.1.12 → v0.1.13 so `/plugin update` upgrades operator's v0.1.10 install
- [ ] **A3.** Bump `the-loom/adapters/claude-code/loom-discipline/.claude-plugin/plugin.json` from v0.1.12 → v0.1.13 to match catalog (version-drift discipline)
- [ ] **A4.** Commit + push the-loom version bumps
- [ ] **A5.** Delete `claude-skills-marketplace/plugins/make-skills-discipline/` source dir
- [ ] **A6.** Remove `make-skills-discipline` entry from `claude-skills-marketplace/.claude-plugin/marketplace.json`
- [ ] **A7.** Commit + push claude-skills-marketplace cleanup
- [ ] **A8.** Sweep **15 files** (PROBE-verified, not 13 as I initially said) replacing `make-skills-discipline@lizo-skills` → `loom-discipline@lizo-loom`:
  - [ ] `c:/Users/Liz/classroom-hub-starter/CLAUDE.md`
  - [ ] `c:/Users/Liz/claude-skills-marketplace/CLAUDE.md`
  - [ ] `c:/Users/Liz/docs-agent/CLAUDE.md`
  - [ ] `c:/Users/Liz/loom-platform/CLAUDE.md`
  - [ ] `c:/Users/Liz/Make_Skills/CLAUDE.md`
  - [ ] `c:/Users/Liz/project-starter/CLAUDE.md`
  - [ ] `c:/Users/Liz/Summer 2026 Hub/CLAUDE.md`
  - [ ] `c:/Users/Liz/tapestry/CLAUDE.md`
  - [ ] `c:/Users/Liz/the-loom/CLAUDE.md`
  - [ ] `c:/Users/Liz/ux-starter/CLAUDE.md`
  - [ ] `c:/Users/Liz/web-starter/CLAUDE.md`
  - [ ] `c:/Users/Liz/humancensys-app/AGENTS.md`
  - [ ] `c:/Users/Liz/claude-project-starter/templates/_common/CLAUDE.md` (template source!)
  - [ ] `c:/Users/Liz/project-starter/templates/_common/CLAUDE.md` (template source!)
  - [ ] `c:/Users/Liz/web-project-starter/templates/_common/CLAUDE.md` (template source!)
- [ ] **A9.** Update reconciliation-note callouts in the-loom, Make_Skills, tapestry CLAUDE.md — the "Marketplace migration deferred" notes are now wrong (Option A keeps it in lizo-loom, no migration deferred)
- [ ] **A10.** Commit + push each of 15 repos (some may share commits within the same repo)
- [ ] **A11.** Mark `feedback_discipline_plugin_reconciliation_deferred_2026_06_14` memory as RESOLVED via a follow-up memory
- [ ] **A12.** Save `loom_discipline_reconciliation_complete_option_a_2026_06_14` state snapshot (signals drift-watcher to stop)
- [ ] **A13.** Operator verifies: `/plugin marketplace update` then `/plugin update loom-discipline@lizo-loom` upgrades from 0.1.10 to 0.1.13

#### Stop conditions / abort

- If any step shows the plugin installed in BOTH `lizo-loom` AND `lizo-skills` after this work → STOP, that's a Pillar 1 violation
- If drift-watcher writes a `drift_watcher_loomdisc_concern_HALT_*` memory → STOP and surface to operator
- If sweep grep returns any `make-skills-discipline` after step A10 → not done; loop back

---

## Part 2 — Queued Work (priority order)

### Q1. Resolve the candidate cleanup pre-Tapestry migration

Per `cleanup_complete_pre_tapestry_2026_06_14` — done. State clean. Tapestry migration can begin when operator says go.

### Q2. Tapestry migration — actual work begins

Per `tapestry/docs/proposals/2026-06-13-v1-scope-and-roadmap.md` §5 (sequenced migration):

- [ ] **PR-prep-1** (Make_Skills side) — engine telemetry collector hook → existing `/skill-used` endpoint
- [ ] **PR-prep-2** (the-loom side) — externalize loom-memory MCP URL config + extract `auth_bridge.py` into `the-loom/packages/auth/`
- [ ] **Step 1** — auth consolidation into Tapestry (`packages/auth/` + `platform.tenant_id_mapping`)
- [ ] **Step 2** — agent-context MCP lift to Tapestry
- [ ] **Step 3** — project-registry + signup endpoint lift
- [ ] **Step 4** — engine lift (skill-compiler + skill-making receiver)
- [ ] **Step 5** — templates + CLI lift
- [ ] **Step 6** — web-dashboard v1 lift
- [ ] **Step 7** — architecture-registry + policy lift + render.yaml
- [ ] **Step 7a** — telemetry-ingestion + project-observatory lift
- [ ] **Step 8** — discipline plugins migrate to `tapestry/integrations/claude-code/`

### Q3. Loop-closure auto-write

Per MANIFESTO Part 4.7 — engine compile output → plugin file → git commit → push. Currently manual. Future scope.

### Q4. Per-kind handlers for the other 8 candidate kinds

Engine ack-defers all kinds except `kind=skill`. Need handlers for `agent`, `inline_tool`, `external_tool`, `architecture_pattern`, `service`, `machine_support`, `process`, `orchestration`.

### Q5. roadmap-maintenance migration into liz-patterns plugin

Blocked on exposing the in-process Make_Skills `@tool`-decorated roadmap tools (`services/admin/roadmap/tools.py:22, 69, 106`) as MCP first.

### Q6. concrete-rule + periodic-architectural-checkin (the-loom skills_private extras)

Two unique-to-the-loom entries that haven't migrated to the plugin yet. Decide per-skill whether to promote or retire.

### Q7. Drift-watcher formal promotion

Per `candidate_skill_drift_watcher_agent_pattern_2026_06_14` — write `liz-patterns/agents/drift-watcher.md` formalizing the pattern. Validated twice now (2026-06-13 cleanup + 2026-06-14 loom-discipline reconciliation).

---

## Part 3 — Discipline reminders (binding for this primary)

Rules I've drifted on this session that the discipline plugins + memory enforce — but I keep forgetting to apply consistently:

### D1. PROBE installed marketplaces before ANY plugin migration work

Per `feedback_check_installed_marketplaces_before_proposing_plugin_migration_2026_06_14`:
- `grep -n "marketplace\|extraKnownMarketplaces" C:/Users/Liz/.claude/settings.json` FIRST
- `ls C:/Users/Liz/.claude/plugins/cache/` to see installed plugins per marketplace
- For each marketplace, find its source repo + read its `.claude-plugin/marketplace.json`
- THEN propose migration

### D2. Spawn drift-watcher when work crosses multiple repos OR marketplaces

Per `feedback_drift_watcher_value_demonstrated_real_save_2026_06_14`. Trigger when ALL three:
- >5 sequential edits across multiple repos OR multiple files
- Bound by binding rules (MANIFESTO + feedback memories)
- >20 minutes wall-clock estimated

This loom-discipline reconciliation hit all three. Drift-watcher is running now.

### D3. ONE pattern, ONE name, ONE canonical home

MANIFESTO Pillar 1. Per `feedback_one_pattern_one_canonical_home_not_per_repo_copies_2026_06_13`. Applies to PATTERNS AND MARKETPLACES. Two marketplaces both publishing the same plugin name = Pillar 1 violation.

### D4. PROBE before asserting; cite file:line

Standard discipline. Every claim about what a file says needs a citation. Training-data defaults don't count.

### D5. Check `git branch --show-current` before committing

Today I committed to `revert-readme-the-loom-leak`, `bump-sentry-9`, `add-skills-to-scaffold` branches without realizing because I didn't check. ALWAYS check first when in any repo with non-trivial branch history.

### D6. Save corrections as feedback memory IMMEDIATELY

At the moment of correction. Not at session end. Use `memory_write` via the loom-memory MCP.

### D7. Operator's framing is source of truth

When operator contradicts an earlier framing, operator wins. Don't argue. Update the older framing in memory.

### D8. Mark stale memories as resolved when work changes their state

Don't let old `feedback_*_deferred` memories sit when the deferred work has been done. Write a follow-up memory referencing the resolution.

---

## Part 4 — Archive (completed work, with refs)

### 2026-06-14 — Cleanup pre-Tapestry migration

Per `cleanup_complete_pre_tapestry_2026_06_14`:
- 64 duplicate skill dirs deleted across 4 mirror repos
- 13 CLAUDE.md / AGENTS.md updated + template source fixed
- 2 stale skills/README.md corrected
- 36 obsolete candidates batch-rejected in production
- Drift-watcher caught a real drift mid-session

### 2026-06-14 — liz-patterns plugin install test

Per `liz_patterns_plugin_install_test_passed_2026_06_14`:
- Plugin install verified
- Skill invocation verified
- Agent invocation verified (`Agent({subagent_type: "liz-patterns:infrastructure-mapping", ...})`)
- Canonical-home model proven end-to-end

### 2026-06-13 — Plugin migration to canonical home

Per `canonical_patterns_home_landed_liz_patterns_plugin_2026_06_14`:
- liz-patterns plugin shipped at commit `cb11df7`
- 7 agents + 8 skills migrated from docs-agent
- Marketplace registration + README updates

### 2026-06-13 — Bridge end-to-end + self-observer ship

Per `bridge_closed_end_to_end_2026_06_13` + `session_state_self_observer_loop_closed_input_side_2026_06_13`:
- Bridge fires end-to-end for kind=skill
- Self-observer cron live at `crn-d8n2q4ernols73d7upbg`
- INPUT + OUTPUT sides of the loop both green

### 2026-06-13 — Tapestry MANIFESTO

Per commit `4199568` on tapestry main:
- 12-part binding document
- Five pillars
- Component glossary
- Agnostic-transition framing

---

## Cross-references

- `tapestry/MANIFESTO.md` — the binding constitution
- `tapestry/docs/proposals/2026-06-13-v1-scope-and-roadmap.md` — v1 roadmap with full architecture diagram
- `tapestry/docs/playbook/migration/` — 5 playbook chapters
- `feedback_*` memories — the rulebook
- `lesson_*` memories — what's been learned
- This document — operational state across sessions

When the operator wants to know "where are we" — they read this document.
When a future agent picks up cold — they read this document.
When the drift-watcher checks alignment — it reads this document.
