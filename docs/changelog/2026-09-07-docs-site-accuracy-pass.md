---
date: 2026-09-07
kind: chore
area: apps/docs-site
prs: []
adrs: []
memory: [docs_keep_the_vision_fix_the_tense_2026_09_07]
supersedes:
---

# Docs-site accuracy pass — reconcile 18 pages with the code

**What:** Applied the fixes from the four-agent docs audit (`docs/plans/2026-09-06-docs-site-audit-findings.md`) across the `systems/`, `how-to/`, `explanation/`, `reference/`, and `start/` pages, plus the stale `services/self-observer/README.md`. Corrected the `loom-*` service names (`loom-agent-context`, `loom-architecture-registry`, `loom-postgres`, `tapestry-self-observer-cron`), real env-var names, the flat `.project-intelligence/` layout, the canonical env-ref `.mcp.json` block, the broken `tapestry onboard --slug` command, the Render Blueprint reality (reuses `loom-postgres`, `infra/deploy/` path), the snapshot mechanism (canonical from the plugin, not per-repo wrappers), CORE DIRECTIVE 3, the 10 record types, and the OTel `loom-discipline` default.

**Why it matters:** The docs had drifted from the system as it migrated — several setup commands failed as written, and the capability pages overstated maturity. The capability pages (registry, observatory, observer) now **keep the vision but separate live-today from designed** (per the operator's "keep the vision, fix the tense" principle); pure factual errors were fixed outright.

**Follow-ups / gates:** none — deploy the docs site (Vercel) after merge. The engine-deploy + fleet-rollout work remains separate and unstarted by design.
