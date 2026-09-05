# Change trail

One file per notable change, so the history of *what* changed, *when*, *why*, and *where it now lives* is easy to follow without reading every commit message or reconstructing it from git.

This exists because capability state kept drifting out of view: the roadmap went stale, a migration's key detail (a renamed file, a widened column) lived only in a commit body, and whether a capability was migrated / absorbed / deferred was hard to trace. The change trail is the durable, skimmable record that fixes that.

## What gets an entry

Write an entry when a change is worth finding again later:

- **migration** — a service/capability moved from a legacy repo into Tapestry (Lift/Refactor/Rewrite), or a cutover happened
- **feature** — a new capability, agent, skill, workflow, or endpoint
- **fix** — a bug fix worth remembering (especially silent-failure classes)
- **decision** — a choice recorded as an ADR, or a scope call (absorbed / deferred / retired)
- **version** — a plugin or package version bump that consumers act on
- **chore** — infrastructure/tooling that changes how work is done (CI checks, scripts)

Skip trivial changes (typo fixes, comment-only edits, formatting). If you're unsure, a one-line entry is cheap; a lost trail is expensive.

## What does NOT belong here

- Per-migration source→destination mapping → that's [`../migration/import-map.md`](../migration/import-map.md) (the change trail *links* to it; it doesn't duplicate it).
- The decision's full reasoning → that's an ADR under [`../adr/`](../adr/) (link it).
- Roadmap status → that's [`../../ROADMAP.md`](../../ROADMAP.md) (the `roadmap-maintenance` agent keeps it current).
- Durable cross-session context → loom-memory (link the memory `name`).

The change trail is the *index* over those; it points at them, it doesn't replace them.

## Entry format

One file per change: `docs/changelog/YYYY-MM-DD-<kebab-slug>.md`. Frontmatter + a short body.

```markdown
---
date: 2026-09-05
kind: migration            # migration | feature | fix | decision | version | chore
area: services/policy      # the primary path/subsystem touched
prs: [166]                 # PR numbers (empty list if none yet)
adrs: [0004]               # related ADR numbers (omit or [] if none)
memory: [policy_service_migrated_pr166_2026_09_05]  # loom-memory names (omit if none)
supersedes:                # a prior changelog slug this replaces, or omit
---

# <One-line title: what changed>

**What:** 1–3 sentences. The change, plainly.

**Why it matters:** the consequence — what this unblocks, fixes, or makes findable.

**Follow-ups / gates:** anything left (a cutover step, an operator action), or "none".
```

## How to write one

Invoke the `tapestry-patterns:changelog-entry` skill — it carries the procedure (when an entry is warranted, the template, what to link, the tone). At the end of substantive work, write the entry in the same PR as the change, so the trail lands atomically with what it describes.

## Enforcement (advisory)

`.github/workflows/changelog-check.yml` runs `scripts/check_changelog.py` on every PR. If the PR touches runtime (`services/`, `engine/`, `infra/migrations/`, `apps/`, `packages/`, `integrations/`) but adds no `docs/changelog/` entry, the check flags it. It is **advisory** — it is not a required merge gate, and a change that genuinely needs no entry opts out with `[skip changelog]` in the commit subject (first line). Humans own merge.

## Index

Newest first. (Older history predating the trail lives in `import-map.md` and git.)

| Date | Kind | Change | PRs |
|---|---|---|---|
| 2026-09-05 | migration | [Policy service migrated from the-loom](2026-09-05-policy-service-migration.md) | #166 |
| 2026-09-05 | feature | [roadmap-maintenance agent + agent-home ADR](2026-09-05-roadmap-maintenance-agent.md) | #165 |
| 2026-09-05 | fix | [self-observer dedup repair + stub-slot labels](2026-09-05-self-observer-dedup-fix.md) | #164 |
| 2026-09-05 | chore | [Advisory agentic code review (Phase 0)](2026-09-05-agentic-code-review.md) | #163 |
| 2026-09-05 | chore | [Change trail system](2026-09-05-change-trail-system.md) | this PR |
