---
name: open-source-documentation
description: Maintain documentation for an open-source project so contributors can onboard, design decisions are auditable, and per-section docs stay current. Defines the docs/ tree (concepts / how-to / reference / decisions / proposals), the ADR pattern for design decisions, when to update what, and the dual-mode discipline (every doc explains both self-host and hosted modes). Use when authoring or updating any file under docs/, or when a design choice is made that should be tracked.
---

# Open-source documentation

Documentation for Make_Skills is **load-bearing for contribution** — without it, the open-source pillar of the platform fails. This skill defines the structure, the discipline, and what goes where.

## The four-axis docs tree

Inspired by [Diataxis](https://diataxis.fr/) (concepts / how-to / reference / explanation) but adapted with an explicit **decisions** axis that tracks why-we-chose-what over time. The tree:

```
docs/
├── README.md               Entry point — TOC + "if you do nothing else, read these 3 docs"
├── concepts/               WHY — the architecture, the principles, the mental models
│   ├── README.md
│   ├── architecture.md     (or link to root ARCHITECTURE.md — single source of truth)
│   ├── two-mode.md         The dual-mode commitment in plain language for newcomers
│   └── pillars.md          Pillar 0/1/2/3 explained for someone who just landed
├── how-to/                 STEP-BY-STEP — recipes that work end-to-end
│   ├── README.md
│   ├── self-host-quick-start.md
│   ├── deploy-to-render.md (link to platform/RENDER.md or move it here)
│   ├── add-a-skill.md
│   └── add-a-subagent.md
├── reference/              EXACT — interfaces, schemas, env vars
│   ├── README.md
│   ├── api-endpoints.md
│   ├── env-vars.md
│   ├── skill-format.md     SKILL.md frontmatter fields
│   └── tenant-model.md     tenant_id semantics in both modes
├── decisions/              WHY-WE-CHOSE — Architecture Decision Records (ADRs)
│   ├── README.md           Index + how to write a new ADR
│   ├── 000-adr-template.md
│   ├── 001-license-apache-2.md
│   ├── 002-two-mode-commitment.md
│   └── ... (numbered, immutable, append-only)
├── proposals/              WHAT-WE-MIGHT-DO — design proposals before they become decisions
│   ├── README.md
│   ├── byo-claude-code-via-mcp.md
│   └── ...
└── per-pillar/             MIRROR OF SITE STRUCTURE — section-specific docs
    ├── pillar-1-build-agents/
    ├── pillar-2-make-skills/
    └── pillar-3-observability/
```

Each top-level folder has a README.md that's the table of contents PLUS a one-paragraph "what's in here, when to read it."

## The ADR pattern (core to this skill)

Architecture Decision Records track *why* something is the way it is, not *what* it is. They're append-only — once committed, an ADR is amended only by a NEW ADR that supersedes it (with a `Supersedes: ADR-NNN` field).

### When to write an ADR

- A choice between two or more genuine alternatives was made (license, auth provider, tenant routing, etc.)
- The decision affects multiple modules or contributors
- "Why didn't they just do X?" is likely to come up later

### When NOT to write an ADR

- Implementation details with no real fork (e.g., "we chose `psycopg` over `pg8000`" — this is just an import)
- Decisions that change frequently (UI styling, copy)
- Things that are downstream of an existing ADR (don't restate, link)

### ADR template

See [`decisions/000-adr-template.md`](../../docs/decisions/000-adr-template.md) for the canonical form. Fields:

- **Title** — verb phrase. "Adopt Apache 2.0", not "Licensing Discussion"
- **Status** — Proposed / Accepted / Deprecated / Superseded by ADR-NNN
- **Context** — what's the question, what's the constraint
- **Decision** — what we picked
- **Consequences** — positive AND negative; this is the section to be honest in
- **Alternatives considered** — what we didn't pick and why

### Numbering

Sequential, four-digit, never reused. `001-license-apache-2.md`, `002-two-mode-commitment.md`, `003-...`. New ADRs get the next number.

## The two-mode discipline (every doc)

Per the 2026-04-28 commitment in [`ARCHITECTURE.md`](../../ARCHITECTURE.md): every doc explains the topic in BOTH deployment modes. Either:

- **Two parallel sections** ("In self-host…" / "In hosted multitenant…")
- **A "mode notes" callout box** at the bottom flagging differences
- **A table** with mode columns

A doc that only explains one mode is incomplete and gets blocked at review.

## Per-section docs

Each pillar (1, 2, 3) has its own subtree under `docs/per-pillar/`. The site's `/docs/<pillar>` page renders this subtree. Per-pillar docs are TARGETED to users of that pillar — Pillar 1 docs are for people building agents; Pillar 3 docs are for people setting up observability. Cross-references are explicit links, not implied context.

## Update rules (when does an existing doc need a refresh?)

| Trigger | Update |
|---------|--------|
| New endpoint added to FastAPI | `docs/reference/api-endpoints.md` + the relevant per-pillar doc |
| New env var | `docs/reference/env-vars.md` + `.env.template` |
| New skill ships | `skills/README.md` table + (if non-trivial) a `how-to/add-a-<thing>.md` example |
| New subagent ships | `subagents/README.md` table + `how-to/add-a-subagent.md` if format changes |
| Architecture choice made | New ADR under `docs/decisions/` |
| Architecture choice reversed | NEW ADR (don't edit the old one) marked `Supersedes: ADR-NNN` |
| New pillar feature | `docs/per-pillar/pillar-N/...` |
| Mode behavior diverges | Update `docs/concepts/two-mode.md` AND the affected reference docs |

## The "freshness" check (agents, follow this)

When updating docs:

1. **Probe** — read the existing doc fully before editing. Don't blindly append.
2. **Decide** — is this a small fix (status, link, typo)? Apply directly. A new substantial section? Consider whether it belongs in this doc or a new one.
3. **Act** — make the smallest change that resolves the staleness.
4. **Report** — note in the commit message which docs changed and why. The commit log becomes the doc-change audit trail.

## Anti-patterns to reject in PRs

- A new feature lands without docs in the same PR
- A doc explains only one mode
- An ADR is amended in-place after acceptance (use a superseding ADR instead)
- Per-pillar docs reference internals of other pillars without an explicit cross-link
- A "how-to" that doesn't actually work end-to-end on a fresh checkout
- Docs that explain WHAT the code does (the code already does that) without explaining WHY

## Eventually: MkDocs site

Long-term, `docs/` becomes a published site (MkDocs Material is the common pick — what Microsoft uses). `mkdocs.yml` at repo root, GitHub Actions builds + publishes to GitHub Pages. Cross-link the rendered site from `web/`'s `/docs` route as an iframe (or fetch markdown and render in-app).

For now: markdown in repo, rendered by GitHub's native viewer, sufficient. The per-pillar pages on the live site can fetch from the api's `/docs/<path>` endpoint (TBD) when we want them inline.

## See also

- [`agentic-skill-design`](../agentic-skill-design/SKILL.md) — the operating discipline this skill complements (one is for code, this is for words)
- [`documentation`](../documentation/SKILL.md) — the older documentation skill for individual documents (READMEs, ADRs in other repos); this open-source-documentation skill is the META skill for the project's whole docs system
- [`ARCHITECTURE.md`](../../ARCHITECTURE.md) — the layered model
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — what contributors must do

## Pair with the public stack

The Make_Skills-specific tree + dual-mode discipline is yours. Mechanics of OSS hygiene are better delegated:

- **`antigravity-bundle-oss-maintainer:documentation-templates`** — current README / CONTRIBUTING / SECURITY templates
- **`antigravity-bundle-oss-maintainer:create-pr`** — PR description format
- **`antigravity-bundle-oss-maintainer:commit`** — commit message format
- **`antigravity-bundle-oss-maintainer:changelog-automation`** — CHANGELOG.md
- **`antigravity-bundle-oss-maintainer:receiving-code-review`** + **`requesting-code-review`** — review hygiene for OSS contributors
- **`elements-of-style:writing-clearly-and-concisely`** — prose quality across the whole docs/ tree
