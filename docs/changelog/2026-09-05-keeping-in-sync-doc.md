---
date: 2026-09-05
kind: chore
area: docs/maintenance
prs: []
adrs: []
memory: [propagation_checklist_2026_09_05_session_changes]
supersedes:
---

# Keeping-in-sync maintenance checklist

**What:** Added `docs/maintenance/keeping-in-sync.md` — the living checklist of what to propagate after a change (plugin bumps → per-machine catch-up + restart; new machine → env-ref config; migration → cutover; runtime PR → changelog entry; credential rotation → one place) and the standing drift points to check periodically.

**Why it matters:** Plugin installs are per-machine and credentials live in machine-wide/per-repo config, so a bump or rotation isn't done when it merges — it's done when every machine and consumer has it. This turns that propagation from tribal knowledge into a checklist, prompted by the loom-memory outage (a machine-wide expired token unnoticed for 9 days).

**Follow-ups / gates:** none — it's a doc. Keep it updated when a new drift point appears.
