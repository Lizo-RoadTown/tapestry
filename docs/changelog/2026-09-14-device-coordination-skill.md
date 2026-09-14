---
date: 2026-09-14
kind: feature
area: integrations/claude-code/tapestry-patterns
prs: []
adrs: []
memory: [proposal-cross-device-coordination-artifact-2026-09-13, coord-poppytart-catchup-2026-09-13]
supersedes:
---

# device-coordination skill (tapestry-patterns)

**What:** Added the `tapestry-patterns:device-coordination` skill — a `PROBE → DECIDE → ACT → RECORD` protocol for making changes on a repo shared across the operator's multiple machines (e.g. tapestry on MINIPC-T9CJY + Poppytart). It codifies what is shared-via-git vs per-machine, the PROBE commands (hostname, repo lag, plugin versions, `~/.claude.json` header shape, loom-memory reachability, `coord-*` handshake recall), when to sequence behind another device, and the requirement to write a `coord-<device>-<date>` handshake memory after any device-crossing change. Bumps tapestry-patterns 0.1.6 → 0.1.7 (marketplace.json + plugin.json).

**Why it matters:** Plugin installs and machine-wide config are per-machine, so updates on one device silently diverge or break the other (stale plugin shadow, case-duplicate registry rows, expired literal JWT, marketplace-clone staleness — all real incidents in loom-memory). This turns cross-device coordination from tribal knowledge into an invocable protocol that pairs with `docs/maintenance/keeping-in-sync.md` (the propagation checklist) and `scripts/catch-up-machine.ps1`.

**Follow-ups / gates:** (1) Propagate the 0.1.7 bump — every machine runs `scripts/catch-up-machine.ps1` + restarts before the new skill is invocable there (recorded as a handshake in loom-memory). (2) Pressure-test the skill per `superpowers:writing-skills` RED-GREEN loop — authored to spec and grounded in real incidents, but not yet subagent-tested.
