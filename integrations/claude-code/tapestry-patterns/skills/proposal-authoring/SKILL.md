---
name: proposal-authoring
description: Author a design proposal in Make_Skills's house style — fixed section layout, project tone (state what is, not what it isn't), two-mode notes, open questions, references. Use when starting a new file under docs/proposals/, when transcribing a research synthesis into a proposal, or when reviewing a draft proposal for tone and structure compliance. Captures the template observed across 8+ existing proposals.
---

# Proposal authoring

Make_Skills design proposals follow a strict structural shape. Every proposal in `docs/proposals/` has the same sections in the same order. The body adapts; the structure does not. This skill captures the template, the tone discipline, and the references-to-include — so authoring proposal #9 takes 10 minutes of judgment instead of 30 minutes of judgment plus boilerplate.

The promotion criteria — done 7+ times same shape, mechanical core, ~30 min/run — were captured in [`docs/plans/2026-04-29-orchestration-catalog.md`](../../docs/plans/2026-04-29-orchestration-catalog.md) (score 80, second-highest capture).

## When to use this skill

**Use when:**
- Starting a new file under `docs/proposals/<slug>.md`
- Transcribing a research synthesis (from [`subagents/researcher-coordinator`](../../subagents/researcher-coordinator/AGENTS.md)) into a proposal
- Reviewing a draft proposal for tone or structural compliance

**Don't use when:**
- Writing an Architecture Decision Record (ADR) — those live at `docs/decisions/NNN-<slug>.md` and have a separate, lighter format (Status / Context / Decision / Consequences). Proposals become ADRs after acceptance; the proposal stays in `docs/proposals/` as historical context.
- Writing a runbook (`docs/runbooks/`)
- Writing test-run notes (`docs/test-runs/`)
- Writing a user-facing public doc (`web/content/docs/`)

## 1. PROBE — gather what's already decided

Before authoring, read:

- The conversation that surfaced the proposal (what was the user wrestling with?)
- Any existing proposals on adjacent topics (linked via `docs/proposals/README.md`)
- The roadmap row this proposal closes (`ROADMAP.md`)
- Memory: `recall("design preferences")`, `recall("architecture decisions")`
- The relevant feedback memories — especially [`feedback_documentation_tone.md`](../../C:/Users/Liz/.claude/projects/c--Users-Liz-Make-Skills/memory/feedback_documentation_tone.md)

If the proposal will use research from [`subagents/researcher-coordinator`](../../subagents/researcher-coordinator/AGENTS.md), the synthesis output drops directly into the "Decision" or "Insight" section.

## 2. STRUCTURE — the canonical section layout

Every proposal has these sections in this order. Don't skip any. If a section genuinely doesn't apply, write "n/a" with one sentence explaining why.

```markdown
# Proposal: <One-line title that names the thing>

**Status:** Open — <why open: needs decision on X / blocked on Y / ready to execute>
**Authors:** Liz, agent-assisted
**Date:** YYYY-MM-DD

## Problem

<2-4 paragraphs. What's broken or missing TODAY. Specific symptoms,
not abstract concerns. Quote the user's framing if there's a
representative line.>

## Insight (or "Goal")

<The thing that became clear about how to approach this. One paragraph
or a short bulleted list.>

## Decision: <one-line summary of the chosen path>

<The architectural / design choice. Lead with the choice, then the
reasoning. If the proposal is comparing options, present the matrix
here. The "Decision" line gets carved into an ADR later.>

### Adopt from <option A>
- <specific element>: <reason>

### Adopt from <option B>
- <specific element>: <reason>

### Reject from all options
- <specific element>: <reason>

## Schema changes (or "Code sketches")

<SQL, Python, or TypeScript fragments that show the shape of the
implementation. Not full implementation — enough that a reviewer can
spot architectural mistakes. Schema migrations get fenced ```sql
blocks; code goes in fenced ```python or ```typescript blocks.>

## Implementation phases

<A table or numbered list. Each phase is independently shippable, has
clear inputs/outputs, and names what blocks downstream. Effort
estimates in days/weeks, not specific dates.>

| Phase | Scope | Output | Blocks |
|-------|-------|--------|--------|
| **P1: ...** | ... | ... | All later phases |
| **P2: ...** | ... | ... | ... |

## Two-mode notes

<For Make_Skills specifically: how does this look in self-host vs
hosted-multitenant? Per the two-mode commitment (ADR-002), every
proposal that touches user data or runtime config addresses both.>

| Mode | What changes |
|------|--------------|
| **Self-host** | ... |
| **Hosted-multitenant** | ... |

## Open questions

<Numbered list of decisions the user has to make for the next phase.
Each question should be ANSWERABLE — either yes/no or "pick one of A/B/C
with these tradeoffs." Vague open questions ("how do we feel about X?")
are demotivating; concrete ones are actionable.>

1. <Question>?
2. <Question>?

## What this implies for the next action

<One paragraph. The single most likely next concrete step. Names a
file, a phase, or a follow-up proposal.>

## Sources

<Bulleted list of links: prior proposals, research syntheses, relevant
file paths in the repo, external docs / blog posts. The user (or a
future reviewer) should be able to retrace the thinking from this list.>
```

## 3. TONE — the project's house rules

From [`feedback_documentation_tone.md`](../../C:/Users/Liz/.claude/projects/c--Users-Liz-Make-Skills/memory/feedback_documentation_tone.md):

| Anti-pattern | Replace with |
|--------------|--------------|
| "Real X, not just Y" | Just describe X |
| "The unlock for…" | What the thing does |
| "We're shipping…" | What ships |
| "Not a chatbot — a real…" | Cut the contrast; describe what it is |
| "This isn't marketing speak" | Cut the meta-comment; the writing speaks |
| "Conversation language carryover" — "as we discussed earlier", "you mentioned" | Stand-alone declarative sentences |

Default to: **noun + verb + object**. "X does Y." Then stop.

When in doubt, ask: would this sentence be in the proposal if someone built this without ever talking to me about it? If the sentence only justifies a decision we made, cut it. If it states a fact about what the thing is, keep it.

## 4. ACT — drafting

Workflow:

1. **Copy the template above** into a new file `docs/proposals/<slug>.md`. Slug is kebab-case, descriptive, matches the topic (`pillar-0-tenant-abstraction`, `byo-personal-ollama`, `sidebar-architecture`).
2. **Fill in the Problem and Date first** — these are the easy facts. Quote the user's words for Problem framing if there's a representative line.
3. **Decision section drives everything below** — name the path, then justify it. The sections that follow (schema, phases, two-mode, open questions) are downstream of this choice.
4. **Schema/code sketches are optional but high-leverage** — even a 5-line SQL fragment forces concreteness and catches design mistakes.
5. **Two-mode notes are required** — Make_Skills's commitment from ADR-002. Even if a proposal is "self-host only," explicitly note that ("hosted-multitenant: n/a — this proposal targets the local-development experience").
6. **Open questions calibrate effort** — 0-1 = ready to ship; 5+ = needs more discussion before code.
7. **Update `docs/proposals/README.md`** to link the new proposal in the index.
8. **Sources section is the audit trail** — link prior proposals, the orchestration catalog, the test runs, the conversation date.

## 5. STOP CONDITIONS

Stop and ask the user only when:

- The Decision section has multiple competing options and the choice is genuinely a values call (not a technical one)
- An Open question can't be left to "future you" — its answer changes the rest of the proposal
- The Two-mode notes section reveals an architectural conflict that needs resolution before the proposal can land

For everything else: write the draft, save it, surface the open questions, let the user respond.

## 6. REPORT — single concise summary

After writing the proposal, return:

```
Proposal: docs/proposals/<slug>.md
Decision: <one-line summary of the chosen path>
Open questions: <count, listed by topic>
Next: <the concrete follow-up — usually an implementation PR or a follow-on proposal>
```

That's the entire response. The proposal file holds the detail; the report points at it.

## House rules — common mistakes the project keeps catching

These show up in PR reviews:

1. **No "Status: Approved" without an ADR.** Proposals stay "Open" until an ADR is written. The ADR is the decision; the proposal is the design space.
2. **No emojis in proposals.** The project's tone memory bans them. Use plain text.
3. **No first-person plural.** "We chose…" → "The chosen path is…". Future maintainers reading the proposal don't share "we" with the original authors.
4. **No motivational language.** "This is going to be amazing for users" is not a sentence in a Make_Skills proposal. State what the change does; the value is implicit.
5. **No section pyramid.** Sections are flat (level-2 headings everywhere). Sub-sections only when truly needed (e.g., comparing options A/B/C).
6. **Don't skip the Two-mode section** even when it feels redundant. Skipping it is how regressions in the two-mode commitment slip in.
7. **Sources at the bottom, not inline footnotes.** Every external link goes in the Sources section. Inline cross-refs to other proposals/docs are fine.

## Memory loop

After authoring a proposal:

- Save the slug → topic mapping in memory if the topic is novel for the project (most proposal topics ARE novel; ROADMAP.md is the canonical index).
- If the user pushes back on a structural element (e.g., "the Implementation phases section was too granular here"), capture as a feedback memory and update this skill's body.
- The orchestration catalog tracks proposal count; bump it after each new proposal so the next planning pass has accurate frequency data.

## Reference

- [Orchestration catalog](../../docs/plans/2026-04-29-orchestration-catalog.md) — the score-80 capture this skill fulfills
- [`feedback_documentation_tone.md`](../../C:/Users/Liz/.claude/projects/c--Users-Liz-Make-Skills/memory/feedback_documentation_tone.md) — the tone discipline
- [`subagents/researcher-coordinator`](../../subagents/researcher-coordinator/AGENTS.md) — the upstream skill that produces synthesis-ready content for the Decision section
- Existing proposals as worked examples:
  - [`pillar-0-tenant-abstraction.md`](../../docs/proposals/pillar-0-tenant-abstraction.md) — the canonical "synthesized from research" shape
  - [`sidebar-architecture.md`](../../docs/proposals/sidebar-architecture.md) — the canonical "user-friction-driven" shape
  - [`byo-personal-ollama.md`](../../docs/proposals/byo-personal-ollama.md) — the canonical "feature-staging" shape (P1 / P2 phases)
- [`docs/proposals/README.md`](../../docs/proposals/README.md) — the index every new proposal links into

## Pair with the public stack

Proposals are upstream of ADRs and benefit from research + prose passes:

- **`antigravity-bundle-architecture-design:architecture-decision-records`** — accepted proposals become ADRs; this skill plus that one is the full lifecycle
- **`academic-research-skills:ars-plan`** — when the proposal needs a Socratic planning pass before writing
- **`academic-research-skills:ars-lit-review`** — for proposals that depend on prior research (the "References" section becomes load-bearing)
- **`elements-of-style:writing-clearly-and-concisely`** — prose-quality pass; matches the project's "state what is, not what it isn't" tone rule
- **`superpowers:brainstorming`** — for proposals where the option set is genuinely open, before locking the Decision section
