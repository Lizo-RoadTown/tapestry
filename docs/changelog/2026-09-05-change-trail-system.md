---
date: 2026-09-05
kind: chore
area: docs/changelog
prs: []
adrs: []
memory: []
supersedes:
---

# Change trail system

**What:** Added the change trail — `docs/changelog/` (one file per notable change, with frontmatter linking PRs/ADRs/memory + an index), the `tapestry-patterns:changelog-entry` skill (the procedure for writing entries), and an advisory CI check (`scripts/check_changelog.py` + `.github/workflows/changelog-check.yml`) that flags a runtime-touching PR with no entry. Seeded with this session's shipped work.

**Why it matters:** Capability history had been living only in commit messages and drifting out of view (stale roadmap, migration details buried in commit bodies). The trail is the durable, skimmable index over ADRs / import-map / memory — so "what changed and where it lives now" is easy to follow.

**Follow-ups / gates:** The CI check is advisory (not a required merge gate); opt out of an entry with `[skip changelog]` in the commit subject (first line).
