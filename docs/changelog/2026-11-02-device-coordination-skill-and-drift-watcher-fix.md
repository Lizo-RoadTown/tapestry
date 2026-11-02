---
date: 2026-11-02
kind: feature
area: integrations/claude-code/tapestry-patterns
prs: [174]
adrs: []
memory: [coord-poppytart-catchup-2026-11-02, drift-watch-poppytart-catchup-2026-11-02, proposal-cross-device-coordination-artifact-2026-09-13]
supersedes: 2026-09-14-device-coordination-skill.md
---

# device-coordination skill + drift-watcher memory-binding fix (tapestry-patterns 0.1.8)

**What:** Lands the `tapestry-patterns:device-coordination` skill (originally PR #174, long stuck DIRTY because its 0.1.7 collided with main's own 0.1.7 from #181) rebased onto current main at **0.1.8**, and bundles a one-line fix to the `drift-watcher` agent.

- **device-coordination skill** — a `PROBE → DECIDE → ACT → RECORD` protocol for changes on a repo shared across the operator's machines (shared-vs-per-machine table, PROBE commands, sequence-behind-mid-work stop conditions, `coord-<device>-<date>` handshake template, anti-patterns drawn from real incidents).
- **drift-watcher memory-binding fix** — the agent granted `mcp__loom-memory__memory_*`, but the live server is plugin-namespaced `mcp__plugin_tapestry-discipline_loom-memory__memory_*`. The name mismatch meant every drift-watcher spawn had **no memory tools bound** and was mute on its designated `memory_write` channel (it had to hand findings back through the primary). Corrected the `tools:` grant to the plugin-namespaced names. Surfaced by `drift-watch-poppytart-catchup-2026-11-02`.
- Version bumped 0.1.7 → 0.1.8 in both `marketplace.json` and `plugin.json` (the `plugin-version-check.yml` guard requires they match).

**Why it matters:** Cross-device coordination becomes an invocable protocol (pairs with `docs/maintenance/keeping-in-sync.md` + `scripts/catch-up-machine.ps1`), and the drift-watcher can actually record its own concerns instead of depending on the primary to relay them.

**Follow-ups / gates:** Propagate 0.1.8 — each machine runs `scripts/catch-up-machine.ps1` + restart before the skill is invocable and the drift-watcher fix is live there. The drift-watcher tool grant now couples to the discipline plugin's server name (`tapestry-discipline:loom-memory`); if that server is ever renamed, update the grant in lockstep.
