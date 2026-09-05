# Legibility initiative — reviews, evaluations, and a plan (2026-09-05)

**Status:** For operator decision. Nothing here is built. Three read-only research
agents produced Parts A–C; Part D is the synthesized design. Pick from the action
menu at the end; each item is a separate go/no-go.

**Why this exists:** the loom-*-named services made an intact, partial migration look
lost. The audit confirms **nothing was silently deleted without a trail** — but the
trail was scattered across ADRs, MASTER_CHECKLIST, memory, config headers, and git,
which is functionally the same as losing it. This initiative finishes the migration
and makes features/versions/migrations legible so the fear can't recur.

---

## Part A — Retired-capability audit (what the old observer watched, and where it went)

The old self-observer scanned 4 repos / 10 path-groups (`the-loom/services/self-observer/config.py:44-80`). Every one traced. **Net: nothing vanished without a trail; six items are live decisions**, two of them genuinely load-bearing with no current substitute.

**Already absorbed — no action:** `loom-discipline` skill + `architecture-analyst` agent → `tapestry-discipline/`; all three Make_Skills adapters (classroom/development/research) → `engine/adapters/` + `templates/`; the whole docs-agent/liz-patterns library → `tapestry-patterns/`; `core/runtime/subagents/` was empty; the observer service itself → `services/self-observer/` (PR #157).

**Live decisions:**
1. **`concrete-rule`** — methodology protecting invariants whose silent absence kills a capability (the codified defense for CORE DIRECTIVE 1). **Lifted to `integrations/claude-code/skills/concrete-rule/` but NOT wired into any plugin and NOT in the observer's scan paths.** This is the closest thing to "carried in but half-wired." **→ Promote into a plugin (recommended — load-bearing).**
2. **`periodic-architectural-checkin`** — the human-facing goal-vs-drift pause (counterpart to the automated observer). Same lifted-but-unwired state. **→ Promote to a plugin** (complements, doesn't duplicate, `architecture-report`).
3. **`roadmap-maintenance`** (you named it) — the only autonomous "keep the durable roadmap honest" agent. **Needed, missing, blocked** on writing ADR-0004 + MCP-wrapping its roadmap tools. No substitute today.
4. **Deep-research executable topology** (`planner` + `researcher` + `researcher-coordinator`) — methodology absorbed into `deep-research-pattern`, but the runnable subagents were deferred pending **ADR-0004, which was never written** (decisions stop at 0003). Decide: write ADR-0004 to pick a home, or accept methodology-only.
5. **`schema-migrator`** — needed but hard-coded to Make_Skills paths; a **rewrite, not a lift**. Lower urgency.
6. **Observer coverage regression** — the restored observer scans only `tapestry-patterns/{skills,agents}` + `engine` + marketplace; it does NOT watch `integrations/claude-code/skills/` or the discipline plugin. Promoting #1/#2 into `tapestry-patterns` re-covers them automatically; otherwise add their paths to `services/self-observer/config.py`.

**Highest weight: `concrete-rule` and `roadmap-maintenance`** — real function, no current substitute.

---

## Part B — Unmigrated / unstarted services

Migration is a code-home + blueprint repoint; all services share one `loom-postgres`, so data stays put. Priority:

1. **`architecture-registry` — migrate FIRST (M).** Most load-bearing of the four: both observers POST candidates to it and the dashboard reads/writes it, yet it's only the-loom-deployed. Its failures are **silent** (observers soft-fail) — the exact legibility risk. **Hazards:** tapestry has no candidates migration AND already reused migration numbers **005/006** for telemetry/signals (the-loom's candidate migrations occupy 003-006) → the lift must **renumber and reconcile against the live DB (already at the 9-kind CHECK)**, not replay fresh.
2. **`policy` — migrate SECOND, same PR-series (S).** One table, 3 endpoints; the dashboard's promote/hold/reject depends on it. Same renumber caveat (004).
3. **`candidate-registry` — do NOT build; fold into architecture-registry (~0, a decision).** Its function already lives in arch-registry; the stub advertises a phantom service. Update the stub to "absorbed." **Needs your yes.**
4. **`audit-log` — defer.** No consumer; per-service audit already covers the real requirement. Annotate stub "deferred."

**Also found — a real bug in the shipped self-observer (#157):** it queries `GET /candidates?status=open`, but `open` isn't a valid status → 422 → **dedup silently never engages** (`candidate_client.py:96-101`). Soft-fails, so nothing breaks, but dedup is off. Fix during the arch-registry work or as a quick patch.

---

## Part C — Agentic code review (research + recommendation)

**Today:** strong *in-session* discipline (`tapestry-discipline` hooks) + excellent *interactive* review skills (`/code-review`, `simplify`, `security-review`) — but **zero PR-time, structural, repeatable** agentic review, and `tapestry init` writes no `.github/` at all. The "Tapestry-agent code review" gates in `docs/migration-cicd/01-pipeline-architecture.md:141-143` are aspirational, not implemented.

**Recommendation — two layers, advisory-first:**
- Keep `tapestry-discipline` as the authoring-time layer.
- Add ONE canonical PR-time workflow using the two **Anthropic-native actions** — `claude-code-action@v1` (diff review, inline comments) + `claude-code-security-review` (diff-aware, false-positive-filtered) — **advisory only** (comments, never a blocking gate). Keep lint/types/tests + plugin-version as the deterministic required checks; humans own merge.
- **Make it structural:** ship the workflow as a template in `tapestry-patterns`/`templates/ci/`, and add a step to `tapestry init` that writes `.github/workflows/agentic-review.yml` into every project.
- Two surfaces, one reviewer: unattended advisory CI review + interactive `/code-review ultra --post` for hard PRs.
- Phase: dogfood on tapestry first → template + init-wire fleet-wide → optionally connect to the migration-cicd gates.

**Open decisions (yours):** per-PR cloud-review budget (gate to non-draft PRs?); CI auth (subscription vs API-key secret per repo); GitHub permissions (`pull-requests: write` fleet-wide + require-approval for forks, since the security action isn't injection-hardened); advisory-only vs. an eventual narrow required gate; Anthropic-native vs. adding a specialist (Greptile-class) for cross-file recall.

---

## Part D — Design: the legibility system (addresses asks 3, 4, 5)

Ties the above into a self-reinforcing "never lose the trail" system.

**D1 — Canonical change/migration log (ask 3).**
- One committed, chronological `docs/CHANGELOG.md` (or `docs/changelog/<date>-<slug>.md` entries) recording every feature / service / version / migration event: what changed, why, version, status (shipped/migrated/deferred/dropped), where code moved, what was absorbed/dropped **and the reason**. This is the "super easy to follow trail."
- A **`change-logging` skill** the agent invokes at those moments (the feature/migration analogue of the upskilling report).
- A **backfill agent** that reconstructs the log retroactively from git history + memory + MASTER_CHECKLIST + ADRs, so the trail is complete from the start (this session's migration work is the first backfill target).

**D2 — Per-feature procedures, structural (ask 4).**
- Each service/feature carries a light `PROCEDURE.md` (purpose · invariants (concrete-rule style) · how to change safely · migration status · where its log entries live).
- Promote **concrete-rule** + **periodic-architectural-checkin** (Part A) into a plugin — they're the methodology backbone.

**D3 — Review that enforces it, wired at setup (asks 4 + 5, built on Part C).**
- The `tapestry init` review workflow (Part C) + a review checklist that also asks: "changelog entry present for a feature/version/migration change?" and "procedure/invariants respected?" — so D1/D2 are enforced by review, not discipline alone.

Result: **log (D1) + procedures/invariants (D2) + review that wires into every project and checks both (D3).**

---

## Consolidated action menu (each is a separate go/no-go)

| # | Action | Source | Effort | Note |
|---|---|---|---|---|
| 1 | Migrate `architecture-registry` (renumber migrations, verify live CHECK) | B | M | Do first — load-bearing, silent-fail risk |
| 2 | Migrate `policy` (paired, same PR-series) | B | S | Dashboard depends on it |
| 3 | Fold `candidate-registry` into arch-registry; update stub | B | ~0 | Decision + stub edit |
| 4 | Mark `audit-log` deferred (annotate stub) | B | ~0 | No consumer |
| 5 | Fix self-observer `?status=open` dedup bug | B | S | Quick patch |
| 6 | Promote `concrete-rule` + `periodic-architectural-checkin` into a plugin | A | S | Load-bearing; also fixes observer coverage |
| 7 | Write ADR-0004 → decide home for the deep-research subagents (+ roadmap-maintenance, schema-migrator) | A | S (doc) | Unblocks the parked capabilities |
| 8 | Carry forward `roadmap-maintenance` (subagent + MCP-wrap its tools) | A | M | No substitute today |
| 9 | Build the change/migration log + `change-logging` skill + backfill agent (D1) | D | M | The core "trail" system |
| 10 | Per-feature `PROCEDURE.md` convention (D2) | D | S-M | |
| 11 | Agentic-review workflow, dogfood on tapestry (C/D3 Phase 0) | C | S | Advisory-only |
| 12 | Template it + `tapestry init` writes it fleet-wide (C/D3 Phase 1) | C | M | Review-in-setup |

## Open decisions for the operator
- The five code-review decisions in Part C (budget, auth, permissions, advisory-vs-gate, buy-vs-build).
- candidate-registry fold (#3) and audit-log defer (#4) — ratify.
- Where the deep-research subagents + roadmap-maintenance live (ADR-0004, #7).
- Log format for D1: single `CHANGELOG.md` vs per-entry files under `docs/changelog/`.
