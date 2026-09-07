# Strategic plan — deploy outward + docs-site accuracy audit (2026-09-06)

After a long build session (8 PRs merged, observer live, memory fixed, plugins bumped), everything is **validated on tapestry but not yet pushed outward**, and the docs site has not been reconciled against what changed. This plan sequences the remaining work into four workstreams with explicit dependencies.

## Where things stand (grounded)

- **Merged to main:** #163 agentic review, #164 observer dedup, #165 roadmap agent + ADR-0004, #166 policy migration, #167 change-trail, #168 keeping-in-sync, #169 registry cold-start retry.
- **Open:** #170 (periodic upskilling + `gh pr merge` detection, `tapestry-discipline 0.1.20`); stale #125.
- **Plugins:** `tapestry-patterns 0.1.6` on main; `tapestry-discipline 0.1.20` pending in #170. Only THIS machine has been updated (catch-up + project scope); other machines/projects have not.
- **Published library:** `tapestry-cli 0.1.5` — never published to PyPI (needs a `tapestry-cli-v*` GitHub Release to trigger `publish-cli.yml`).
- **Docs site:** `apps/docs-site` — 36 docs across explanation (8), how-to (10), systems (6), start (5), observatory (3), reference (3). Not audited against this session's changes.

## Workstream A — Land + deploy the plugins

Sequence (each gates the next):
1. **Merge #170** → `tapestry-discipline 0.1.20` reaches main.
2. **Verify the marketplace is coherent** — `scripts/check_plugin_versions.py` green (patterns 0.1.6, discipline 0.1.20).
3. **Per-machine update** — on each machine that runs Claude Code (this one is done; the **laptop** is not): `scripts/catch-up-machine.ps1` + `--scope project` for any project-scoped installs + **restart**. Plugins are a pull, not a push (see `docs/maintenance/keeping-in-sync.md`).
4. **Decide CLI publish** (optional, separate) — if `tapestry-cli` should be pip-installable, cut a `tapestry-cli-v0.1.5` GitHub Release. Not required for plugin consumers.

## Workstream B — Docs-site accuracy audit (the thorough pass)

**Goal:** every page in `apps/docs-site` reflects the CURRENT system, verified against code — not aspirational or stale.

**Highest staleness risk after this session:**
- `systems/` (memory, observer, registry, telemetry, observatory, docs-mcp) — policy now migrated, architecture-registry migrated, self-observer live + registry-driven.
- `explanation/plugins`, `explanation/discipline-stack` — must mention the new agents/skills (`roadmap-maintenance`, `changelog-entry`) and versions (patterns 0.1.6, discipline 0.1.20), the change-trail system.
- `how-to/set-up-*` — plugin names/versions, setup steps, the observer turn-on, Render runtime (Python not Docker).
- `reference/platform-dependencies`, `reference/load-bearing-files` — current fleet + which services are load-bearing vs free (per the Render audit).
- `explanation/the-observer` — the observer is live now; behavior + cold-start retry.

**Method — a few agents, one per category cluster, each grounded in code:**
- Agent 1: `systems/` (6) — verify each against the actual service in `services/` + migration state.
- Agent 2: `explanation/` (8) — concepts + the plugin/skill/agent inventory + shared-language glossary.
- Agent 3: `how-to/` (10) — every procedure runnable as written; plugin/version/runtime accuracy.
- Agent 4: `start/` (5) + `reference/` (3) + `observatory/` (3) — onboarding path + precise facts.

Each agent is **read-only**, returns a per-file findings list (accurate / stale-with-fix / broken-link / missing), cites the code that proves each claim, and does NOT edit. A synthesis pass consolidates into one prioritized fix list. Fixes then land as a scoped docs PR (or a small batch), reviewed before merge. Deploy to the live docs site (Vercel) follows the merge.

## Workstream C — Fleet rollout + roadmap reconciliation

- **ROADMAP.md reconciliation** — stale (lists migrated services as "not ready"). Run `tapestry-patterns:roadmap-maintenance` after the plugin update lands.
- **Fleet rollout (#12)** — template the agentic code-review + change-trail into `tapestry init` so new/other projects get them by default. Gated on the tapestry dogfood (now satisfied). This is its own design+build effort.

## Workstream D — Parked engineering follow-ups

- **Memory REST `/v1/*` self-host fallback** — observer got `memory 401`; the REST surface lacks the MCP path's self-host fallback (server-side `agent-context` change).
- **Discipline SessionStart memory-reachability probe** — the expired-token outage went undetected 9 days.
- **Pre-existing test failures** — `test_scope.py` (3) + `test_observer.py` (2) fail on clean main; unrelated to this session but real.
- **Render orphan cleanup** — finish killing `make-skills-db`, PgHero, `lp-web` (see `render_service_keep_kill_map_2026_09_06`).

## Recommended order

1. **Merge #170** (unblocks the plugin deploy + is tonight's last open piece).
2. **Docs-site audit (Workstream B)** — the big, parallelizable, high-value pass; produces a fix list.
3. **Land docs fixes** + **reconcile ROADMAP** (Workstream C first half).
4. **Per-machine plugin update** (Workstream A step 3) — including the laptop.
5. Then the larger, separate efforts: **fleet rollout (#12)**, **CLI publish**, **parked follow-ups (D)** — each on its own.

Dependency note: B (docs audit) does not depend on A (plugin deploy) — they can run in parallel. C's roadmap reconciliation wants the plugin update first.
