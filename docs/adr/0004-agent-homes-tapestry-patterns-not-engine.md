# 0004 — reusable-agent homes: tapestry-patterns plugin, not engine/

**Date:** 2026-09-05
**Status:** **Accepted**
**Operator decision:** Ratified 2026-09-05 by operator ("I want the roadmap tool") as part of the legibility initiative (`docs/plans/2026-09-05-legibility-review-and-plan.md`).

## Context

Several reusable agents were promoted out of the retired `Make_Skills` /
`the-loom` sources. Each carries a header line declaring its Tapestry
destination as **`tapestry/engine/agents/<name>.md` (PROVISIONAL)** — the
framing from the 2026-06-13 skill-vs-agent conversion proposal, written before
Tapestry had any structure in place.

That destination is not reachable today: `engine/` has **no runtime**. The
deepagents runtime those subagents assumed (`load_subagents()`,
`core/runtime/agent.py`, the `@tool`-decorated Python tools under
`services/admin/`) lives in `Make_Skills` and is **not migrated** (and per
CORE DIRECTIVE 2, adding a new runtime dependency on it is forbidden). An agent
placed in `engine/agents/` would be inert.

Meanwhile the pattern has **already been resolved de facto**: the reusable
agents that shipped — `next-actions-planning`, `infrastructure-mapping`,
`lessons-learned`, `orchestration-cataloging`, `eval-deep-research`,
`web-app-scaffold`, `agentic-upskilling`, `drift-watcher` — all live in the
**`tapestry-patterns` plugin** (`integrations/claude-code/tapestry-patterns/agents/`)
as Claude Code agents, invoked via
`Agent({subagent_type: "tapestry-patterns:<name>"})`. Their source headers
still say `engine/agents/ (PROVISIONAL)`; the reality diverged and was never
written down. `next-actions-planning.md:8` even names `roadmap-maintenance` as
its peer ("Tune the roadmap (that's `roadmap-maintenance`)") — a peer that had
not yet been built.

The immediate forcing-function: the operator asked for the roadmap tool. Before
building it, its home has to be settled — and the same question governs the
remaining un-ported subagents (`roadmap-maintenance`, and the legacy
`researcher-coordinator` for deep research).

## Decision

1. **The canonical home for a reusable agent is the `tapestry-patterns`
   plugin** (`integrations/claude-code/tapestry-patterns/agents/<name>.md`),
   as a Claude Code agent invoked by `subagent_type: "tapestry-patterns:<name>"`.
   This ratifies the pattern the shipped agents already follow, and matches
   CLAUDE.md's "canonical home for reusable agents + skills + tools is the
   `tapestry-patterns` plugin" and MANIFESTO Pillar 1 (ONE name, ONE home).

2. **The `engine/agents/ (PROVISIONAL)` framing in the promoted sources is
   superseded.** It is not a target to build toward. When `engine/` gains a
   runtime, a *programmatic, non-interactive* caller (a cron, a compiler step)
   MAY reconstitute a deepagents variant there — but the interactive/agent home
   stays `tapestry-patterns`. A future engine port would be a separate ADR with
   its own justification, not the default.

3. **A Claude Code agent edits its target files directly (Read/Edit/Grep) and
   does NOT need the source's bespoke Python tools.** The `roadmap-maintenance`
   source assumed three `@tool` functions (`roadmap_overview`,
   `update_roadmap_status`, `add_roadmap_item`) because a deepagents subagent
   cannot freely touch the filesystem. A Claude Code subagent can — so the three
   tools collapse into `Read ROADMAP.md` + `Edit` under the same decision rules.
   The rules (verify evidence before flipping status, exact-match the row,
   respect human edits, one change per invocation) are preserved verbatim; only
   the mechanism changes.

4. **`roadmap-maintenance`** is built now under this decision (this ADR's PR).

5. **Deep research needs no new port.** The capability is already served by the
   bundled `deep-research` workflow (fan-out → fetch → adversarial-verify →
   synthesize), the `tapestry-patterns:deep-research-pattern` skill
   (methodology), and the `tapestry-patterns:eval-deep-research` agent (scoring
   against the DRB bench). The legacy `Make_Skills/subagents/researcher-coordinator`
   is **absorbed** into those three — it is not ported.

## Consequences

- **The roadmap tool works today** — no engine runtime required, installed with
  the `tapestry-patterns` plugin every consuming project already gets.
- **The `engine/agents/ PROVISIONAL` headers across the promoted agents are now
  known-stale.** They are left in place as historical provenance (they point at
  the source of record) but this ADR is the authority on where the agents
  actually live. New agents skip the provisional header and cite this ADR.
- **One consistent invocation surface:** every reusable agent is
  `tapestry-patterns:<name>`. No split between "engine agents" and "plugin
  agents" for operators to track.
- **Deferred:** if a non-interactive caller ever needs `roadmap-maintenance`
  (e.g. a CI step that updates the roadmap on merge), that engine/cron variant
  is a future ADR — this one does not build it.
- **Cost:** the `tapestry-patterns` plugin version bumps (0.1.4 → 0.1.5) and the
  CI plugin-version guard requires `marketplace.json` to match — both updated in
  this PR.

## What this ADR does NOT cover

- The *content* of ROADMAP.md or its reconciliation with current migration
  state — that is the agent's job once installed, not a schema/boundary decision.
- Building the engine runtime, or any deepagents port — explicitly out of scope
  and deferred to a future ADR if a programmatic caller appears.

## Related
- Plan: [`../plans/2026-09-05-legibility-review-and-plan.md`](../plans/2026-09-05-legibility-review-and-plan.md)
- Source (retired): `Make_Skills/subagents/roadmap-maintenance/AGENTS.md`, `Make_Skills/services/admin/roadmap/tools.py`
- Precedent already following this pattern: [`../../integrations/claude-code/tapestry-patterns/agents/next-actions-planning.md`](../../integrations/claude-code/tapestry-patterns/agents/next-actions-planning.md)
- Origin proposal (the superseded PROVISIONAL framing): [`../proposals/2026-06-13-skill-vs-agent-conversion-and-self-observer.md`](../proposals/2026-06-13-skill-vs-agent-conversion-and-self-observer.md)
- CLAUDE.md "Canonical patterns" section · [`../../MANIFESTO.md`](../../MANIFESTO.md) Pillar 1
