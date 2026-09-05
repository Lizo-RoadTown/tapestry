---
date: 2026-09-05
kind: feature
area: integrations/claude-code/tapestry-patterns
prs: [165]
adrs: [0004]
memory: [legibility_initiative_session_2026_09_05_prs_164_165]
supersedes:
---

# roadmap-maintenance agent + agent-home decision (ADR-0004)

**What:** Added the `tapestry-patterns:roadmap-maintenance` agent — it keeps `ROADMAP.md` current by making one evidence-verified edit per invocation (flip a status, append a row), under preserved decision rules (verify evidence, exact-match the row, respect human edits, minimal diff). ADR-0004 settles that reusable agents live in the `tapestry-patterns` plugin as Claude Code agents, superseding the `engine/agents/ (PROVISIONAL)` framing carried in the retired sources (engine has no runtime). Deep research needs no new port (absorbed into the bundled `deep-research` workflow + `deep-research-pattern` skill + `eval-deep-research` agent). tapestry-patterns bumped 0.1.4 → 0.1.5.

**Why it matters:** The roadmap kept going stale because nothing owned keeping it true; this agent does. ADR-0004 gives every reusable agent ONE consistent home and invocation surface.

**Follow-ups / gates:** ROADMAP.md is currently stale (lists migrated capabilities as "not ready"); reconciling it is the agent's first job, runnable after `plugin update tapestry-patterns@tapestry` + restart.
