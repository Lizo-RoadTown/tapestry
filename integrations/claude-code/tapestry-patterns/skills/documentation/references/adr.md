# Architecture Decision Records (ADRs)

> Source: [adr.github.io](https://adr.github.io/), originally [Michael Nygard, 2011](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

An ADR is a short markdown document capturing **one architectural decision**:
what was decided, why, and what follows. ADRs are written **at the moment of
decision**, committed alongside the code that implements them, and never
edited once accepted.

## When to write an ADR

- Choosing a database, framework, language, deployment target
- Choosing a data format or wire protocol
- Adopting a coding pattern across the codebase
- Removing or migrating away from a previous choice
- Anything where, six months from now, someone will ask "why did we do this?"

## When NOT to write an ADR

- Bug fixes, refactors, minor cleanup
- Stylistic choices already covered by a style guide
- Decisions that are obvious or fully constrained by existing choices

## Template

```markdown
# ADR-NNNN: <Short title in title case>

- **Status**: Proposed | Accepted | Rejected | Superseded by ADR-MMMM
- **Date**: YYYY-MM-DD
- **Deciders**: <names or roles>

## Context

What is the situation that requires a decision? What forces are at play
(technical, organizational, social, project)? Keep this objective — describe
the problem, not the solution.

## Decision

What did we decide to do? Phrased actively: "We will use X". One paragraph.
If the decision is multi-part, use a bulleted list.

## Consequences

What becomes easier as a result? What becomes harder? What new risks did
we accept? What other decisions are now constrained?

## Alternatives considered

(Optional, but valuable.) What else did we consider, and why didn't we pick
those? One line each.
```

## Numbering and naming

- Number ADRs sequentially: `0001-use-postgres.md`, `0002-deploy-on-fly.md`, …
- Keep numbers padded so they sort lexically
- Use lowercase-kebab-case in filenames
- Title in the file uses Title Case

## Status lifecycle

```
Proposed ──► Accepted ──► (sometime later) Superseded by ADR-NNNN
              │
              └──► Rejected
```

- **Proposed**: written, but the team hasn't agreed yet
- **Accepted**: in force; the codebase reflects this decision
- **Rejected**: written for posterity; we considered and decided against
- **Superseded**: a later ADR replaces this one. Link to it. **Don't delete.**

## Folder layout

```
docs/
└── adr/
    ├── 0001-use-postgres.md
    ├── 0002-deploy-on-fly.md
    ├── 0003-use-supabase-auth.md
    └── README.md         # Optional index
```

## Anti-patterns

- **Editing accepted ADRs**: write a new ADR that supersedes the old one
- **Vague titles**: "Database choice" → "Use Postgres for primary storage"
- **Long context, no decision**: ADRs are decision records, not essays
- **Writing them weeks after the fact**: the value is in capturing the
  rationale *while it's fresh*. Late ADRs are reconstructions
- **One giant ADR for many decisions**: split them. One decision per file
- **No `Consequences` section**: this is the most valuable part — write it

## Example

```markdown
# ADR-0001: Use Postgres for primary storage

- **Status**: Accepted
- **Date**: 2026-01-15
- **Deciders**: Liz Osborn

## Context

The system needs a single source of truth for extracted couplings, user
accounts, and audit history. We expect ~10M rows over the next year, with
heavy relational queries (joins across entities, relationships, and review
state).

## Decision

We will use Postgres (via Supabase) as the primary storage. All persistent
state goes through it. We will not introduce a separate document store
unless a concrete need arises that Postgres can't serve.

## Consequences

- Easier: relational queries, transactions, RLS for tenant isolation
- Harder: full-text search at scale (we'll add pgvector + extensions as
  needed)
- Constraint: Supabase tier limits — see ADR-0007 for our plan if we
  outgrow it

## Alternatives considered

- MongoDB: poorer fit for our heavily relational data model
- DynamoDB: lock-in to AWS; we want portability
- SQLite: not multi-tenant friendly at our expected scale
```

## Tooling

- [adr-tools](https://github.com/npryce/adr-tools) — bash CLI for managing ADRs
- The `new_adr.sh` script in this skill creates a new ADR from a template
