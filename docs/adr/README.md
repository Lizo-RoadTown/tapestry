# Architectural Decision Records

ADRs as Tapestry decisions land. Format: `NNNN-short-slug.md`, sequential numbering.

## When to add an ADR

- A decision that affects multiple services or apps
- A decision that reverses an earlier prototype choice
- A naming or boundary decision worth preserving for future agents reading this repo
- A migration decision that's load-bearing (e.g., "we Lifted X, not Refactored, because of Y")

## ADR template

```markdown
# NNNN — <short-slug>

**Date:** YYYY-MM-DD
**Status:** Proposed / Accepted / Superseded by NNNN
**Operator decision:** <who approved + when>

## Context

Why this decision is being made. What's the current situation? What's the pressure?

## Decision

The decision itself, plainly stated.

## Consequences

What does this make easier? What does this make harder? What other decisions does this lock in or rule out?

## Related

- Linked proposals
- Linked memory writes (loom-memory keys)
- Linked PRs
```

## Initial state (2026-06-12)

No ADRs yet. The architecture documented in [`../architecture/UMBRELLA.md`](../architecture/UMBRELLA.md) is the starting baseline; ADRs record changes from there.
