---
name: design-evaluation
description: Evaluate a design question with multiple options across the dimensions that matter for the project — produces a tradeoff matrix, scores each option, and recommends a path (often a hybrid). Use when the user asks "which approach", "should we use X or Y", "compare these styles", or shares competitor screenshots and asks what to learn from them. Different from next-actions-planning — that picks WHAT to do; this picks HOW to do it.
---

# Design evaluation

Turn a fuzzy design question ("should we copy MS Foundry or Claude Console?") into a structured tradeoff matrix with a defensible recommended path. The output is a file at `docs/plans/<YYYY-MM-DD>-<topic>-design-evaluation.md` plus a 3-bullet report.

## When this applies

**Apply when:**
- Multiple options are visible and the choice isn't obvious (architecture style, UI pattern, library choice, sequencing question)
- The user shares a competitor / reference design and asks "what should we learn?"
- A proposal needs a "we evaluated X, Y, Z and chose Y because" section

**Skip when:**
- One option is clearly correct (just do it, document briefly)
- The question is "what next?" not "how?" — use [`next-actions-planning`](../next-actions-planning/SKILL.md) instead
- You're recognizing recurring work patterns — use [`orchestration-cataloging`](../orchestration-cataloging/SKILL.md) instead

## 1. PROBE — gather the option set and current state

Before evaluating, know what's actually on the table.

- **Read the conversation** for the options being compared. Quote them in the plan; don't paraphrase from memory.
- **Read the current implementation** — what's already built that constrains or enables each option? Skim `platform/`, `web/`, `subagents/`, recent ROADMAP rows.
- **Read prior evaluations** in `docs/plans/*-design-evaluation.md` — has this been litigated? Is this a follow-up?
- **Read the relevant proposal** in `docs/proposals/` if one exists — the proposal usually scopes the design space.
- **Memory probe** for revealed preferences: `recall("design preferences")`, `recall("architecture decisions")`.

For competitor / reference screenshots: enumerate the patterns you see one-by-one (don't synthesize too early). Each pattern is a candidate row in the matrix.

## 2. INVENTORY — pick the dimensions that matter

The dimensions are project-specific. Default set to consider, then prune:

| Dimension | When it matters |
|-----------|----------------|
| **User-fit** | Always. Who is the primary user, what do they know, what do they want? |
| **Two-mode-fit** | Always for Make_Skills (self-host AND hosted-multitenant from day one) |
| **Effort to build** | Always. Days vs weeks vs months. Inverse-weighted at parity |
| **Teaching value** | Make_Skills-specific — does this design explain its own concepts? |
| **Multiplayer-fit** | When the feature has any social dimension (Pillar 2/3 territory) |
| **Reversibility** | Higher weight when the choice locks in data shape (schemas, URLs, tenant model) |
| **Operational cost** | When hosted infra spend is a factor |
| **Author / contributor experience** | When open-source contributors will touch the code |
| **Migration cost** | When existing data or users would need to move |

Pick 4-7 dimensions. More than that becomes noise; fewer than 4 misses real constraints. Document why each was selected (and which were considered and dropped).

## 3. DECIDE — score and synthesize

Score each option on each dimension on a 1-5 scale (1 = bad fit, 5 = strong fit). Show the score AND the reason in the cell — never just the number.

| Option | Dim 1 | Dim 2 | Dim 3 | Total |
|--------|-------|-------|-------|-------|
| A | 4 (because…) | 2 (because…) | 5 (because…) | 11 |

Synthesize:

- **If one option dominates** (≥2 points clear of next), recommend it.
- **If two are close**, recommend a hybrid — name the *specific elements* you're taking from each. "Take A's nav structure + B's onboarding flow." Vague hybrids are worse than picking one.
- **If the matrix is too close everywhere**, name the *single dimension* whose tiebreaker should resolve it, ask the user, return.

Always include "Reject from all options" — what you're explicitly NOT taking. This is as important as what you're keeping.

## 4. ACT — write the evaluation file

`docs/plans/<YYYY-MM-DD>-<topic>-design-evaluation.md`:

```markdown
# <Topic> design evaluation — <date>

## Question
<one-sentence framing of what we're choosing between>

## Options on the table
- **A. <name>** — <2-3 sentence summary, with source/reference link>
- **B. <name>** — <…>
- **C. <name>** — <…>

## Dimensions that matter (and why)
- <dim 1>: <why it matters for this project>
- ...

## Tradeoff matrix
<the scored table>

## Recommendation
**<concrete recommendation, often hybrid>**

Adopt from A:
- <specific element>: <reason>

Adopt from B:
- <specific element>: <reason>

Reject from all:
- <specific element>: <reason>

## Why not the alternatives
- Why not pure A: <reason>
- Why not pure B: <reason>

## Open questions (if any)
- <one specific question that, if answered, would shift the recommendation>

## What this implies for the next action
<one sentence pointing to a concrete next step — usually a proposal update or a Pillar item>
```

## 5. REPORT — three bullets

```
Plan: docs/plans/<date>-<topic>-design-evaluation.md

Recommended: <hybrid name or single option> — <one-line why>

Open questions: <0-2 short questions, or "none">.
```

## Rules of thumb

- **Hybrids beat purity when no option dominates** — but a vague hybrid ("a bit of each") is worse than picking one. Name the specific elements.
- **The status quo is always an option** — keep doing what you're doing. Score it like any other option.
- **Reversibility is high-leverage** — give it 1.5× weight when the choice writes data or sets a URL. You can rebuild a UI; you can't easily migrate user-facing primary keys.
- **Don't compare alternatives to perfection** — compare them to each other.
- **The "reject from all" list is honest signal** — if you can't name what you're not taking, you haven't actually compared.

## Memory loop

After a successful evaluation:

- If the user picks something other than the recommendation, save *why* — the dimension weighting was wrong.
- If the same dimension keeps deciding evaluations the same way (e.g., "two-mode-fit" always tilts toward Anthropic-style decomposition), capture it as a project preference so future evaluations start from there.

## Reference

- [`agentic-skill-design`](../agentic-skill-design/SKILL.md) — the PROBE/DECIDE/ACT/REPORT pattern this instantiates
- [`next-actions-planning`](../next-actions-planning/SKILL.md) — the "what next" sibling
- [`orchestration-cataloging`](../orchestration-cataloging/SKILL.md) — the "what recurring patterns should I make reusable" sibling

## Pair with the public stack

The matrix is yours. Pair it with brainstorming before and ADR capture after:

- **`superpowers:brainstorming`** — run BEFORE this skill to surface the option set; this skill scores options, brainstorming generates them
- **`antigravity-bundle-architecture-design:architecture-decision-records`** — capture the chosen path as an ADR after evaluation; the matrix becomes the Context section
- **`antigravity-bundle-architecture-design:senior-architect`** — second-pair-of-eyes when the tradeoffs are load-bearing for system architecture
- **`antigravity-bundle-essentials:concise-planning`** — when the recommendation is "do A first, then B"; this skill outputs the comparison, concise-planning sequences the execution
