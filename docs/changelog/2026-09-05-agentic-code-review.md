---
date: 2026-09-05
kind: chore
area: .github/workflows
prs: [163]
adrs: []
memory: []
supersedes:
---

# Advisory agentic code review (Phase 0 dogfood)

**What:** Added `.github/workflows/agentic-review.yml` — two advisory jobs on each non-draft PR: a correctness/reuse/simplify/efficiency review (`anthropics/claude-code-action@v1`) and a diff-aware security review (`anthropics/claude-code-security-review`, pinned to a SHA). Both post comments only; neither approves, requests changes, nor blocks merge. Documented in `docs/how-to/agentic-code-review.md`.

**Why it matters:** A second reviewer on every PR that defers to deterministic CI (lint/types/tests/plugin-version stay the required checks). Phase 0 = TAPESTRY repo only; templating into `tapestry init` is a later phase.

**Follow-ups / gates:** Operator sets the `ANTHROPIC_API_KEY` repo secret (`gh secret set ANTHROPIC_API_KEY --repo Lizo-RoadTown/tapestry`); without it the jobs no-op (advisory, never blocks).
