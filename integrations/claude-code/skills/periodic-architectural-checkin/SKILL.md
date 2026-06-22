---
name: periodic-architectural-checkin
description: Step back from active work and audit drift between current project state and the original goal. Surfaces (1) work that's happened, (2) where the work has drifted from the goal, (3) categorization / ownership gaps where no agent owns a domain, and (4) what to discuss with the operator. Use after N substantive PRs land, when scope ambiguity surfaces, when the operator says "let's check in," OR when a coordination boundary between agents is being negotiated.
---

# Periodic architectural check-in

Active development naturally drifts. Each phase finishes, the team coordinates, the next phase ships — and nobody asks "what does the operator actually see today?" This skill is the formal pause: a structured look at where we are relative to where we said we were going.

This skill was promoted from a recurring pattern. Liz asked for this check-in manually on 2026-06-12 after Phase 5 of the recursive-skill engine landed. The act of asking IS the recurrence signal — by the Path B criteria, the underlying need was already eligible for promotion.

## When to invoke

Trigger any of these:

- **The operator says "let's check in" / "step back" / "are we still on track"** — direct ask
- **N substantive PRs have merged since the last check-in** — recommend N=5 across the fleet, or 3 in a single repo
- **A coordination boundary is being negotiated between agents** — naming, ownership split, what-fits-where
- **A new repo / agent / service is being spawned** — the spawn itself is a fork in the architecture
- **The operator hands you the check-in skill explicitly** — `/checkin` or "run the check-in"

Don't invoke for routine work. Bug fixes, single-feature builds, doc renames don't need this. The check-in is for when the SHAPE of the architecture might have shifted.

## Operate as PROBE → SYNTHESIZE → REPORT → CONFIRM. Per [`agentic-skill-design`](../agentic-skill-design/SKILL.md).

## Probe

Read SMALL scope — the check-in shouldn't take more context than the work it's checking on.

| What | How |
|------|-----|
| Original goal of the project | Top of CLAUDE.md, README.md, the founding proposal doc (e.g. `docs/proposals/application-vs-dev-tooling-scope.md`) |
| Current loom-memory state | `memory_recall` with context = "where are we vs the goal" — top 5-8 results |
| Recent git log | `git log --oneline -10` for the active repo + recent inter-agent memories from other repos |
| Active deploy state | What services are running (Render MCP), what's still local, what's stubbed |
| The umbrella architecture doc | `docs/architecture/UMBRELLA.md` if it exists (in the-loom or in Tapestry) |
| Other agents' recent memories | `memory_list` filtered by project tags; look for unanswered asks |

PROBE budget: under 5 minutes of reading. If you need more, the check-in itself is drifting.

## Synthesize — four sections

### 1. Where we are vs the goal

What's been built in the time window. List by SHIPPED / IN-PROGRESS / NOT-STARTED. Each line ties to the original goal: "this builds [goal piece]" or "this doesn't trace to the goal — why is it here?"

### 2. Drift (the honest section)

The systematic gap between current activity and original intent. Specific drifts to look for:

- **Plumbing-vs-product drift** — building infrastructure that has no user-facing demonstration. "We've built 5 services; the user can't see any of them yet."
- **Phase-sequence drift** — the original sequence had N phases; have they been done in order or has the team jumped ahead/skipped?
- **Scope drift** — features that don't appear in the original goal but got built anyway
- **Coordination drift** — work happening in parallel that's stepping on the same boundary (e.g. two agents both touching the same domain)
- **Ownership drift** — work happening but no agent has formal ownership

State each drift specifically. Don't generalize.

### 3. Categorization & ownership gaps

For every concept that's being built across the fleet, ask: is it categorized?

- What kinds of things can be promoted (skills, tools, architecture patterns, services)?
- What does "per-project" vs "cross-project" mean for this kind?
- What's the criteria for promotion?
- Where does a promoted thing LAND?
- Who decides?

If any of these don't have an answer, that's a gap. List the gaps.

For every repo / service / domain in the fleet, ask: who owns it?

- Is there an agent assigned (loom-agent, MS-agent, Tapestry-agent, etc.)?
- Is there a canonical doc that names ownership?
- If two agents could claim it, has the split been ratified?

Unowned domains are gaps. List them.

### 4. What to discuss

The 1-3 questions the operator needs to answer before the team can keep going productively. Format as concrete decisions with options, not vague concerns. Use AskUserQuestion when the operator is present and the questions are decision-shaped.

## Report

A single structured message:

```
## Holistic check-in — [date]

### Drift check
[Section 1 + 2 above]

### Categorization & ownership gaps
[Section 3 above]

### What to discuss
[Section 4 above]

### Recommended next moves
[Ordered list]
```

Tone: plain, terse, direct. No marketing voice. The operator is going to act on this — make it easy to act on.

## Confirm

When the operator responds with decisions, save them as a `decision` or `project` memory in loom-memory with `project_tags` covering all relevant repos. Reference the check-in date so the next check-in can compare delta-over-time. Cross-link from `docs/architecture/UMBRELLA.md` if a decision affects the umbrella architecture.

Cross-tag the memory with EVERY project the decision affects, so future agents in any of those repos surface it via `memory_recall` on session start.

## Anti-patterns

- **Don't generalize.** "We've shipped a lot" is not a drift check. "Phase 5 shipped but Phase 6 hasn't started and the user can't see the upskilling loop yet" is.
- **Don't recommend more building.** The check-in's job is to surface what's missing, NOT to start filling it before the operator decides.
- **Don't expand scope.** A check-in shouldn't take a day. If you find yourself writing more than 800 words, you're drifting from the skill.
- **Don't skip ownership questions.** "What was built" without "who owned it" misses the structural issue.
- **Don't invoke this skill yourself just because you're between tasks.** Wait for one of the triggers above. Spurious check-ins are noise.

## Where the output goes

- The check-in MESSAGE goes to the operator in the conversation
- The DECISIONS that come out of it go to loom-memory as a `decision` record
- If the check-in surfaces a new gap that needs a doc, route to `docs/proposals/<date>-<topic>.md`
- If the check-in surfaces a recurring pattern, add to `skills_private/` (this skill itself was promoted this way)

## Related

- [[skills/agentic-skill-design]] — PROBE → DECIDE → ACT → REPORT methodology this skill follows
- [[skills_private/agentic-upskilling]] — the broader upskilling loop this check-in is one move within
- [[skills_private/lessons-learned]] — friction-as-memory; check-in is "drift-as-conversation"
- [[skills/layered-explanation]] — output formatting (ELI5 → quick ref → depth → mental model)
- `docs/architecture/UMBRELLA.md` — the doc check-ins read drift relative to
- `docs/proposals/2026-06-12-promotion-categorization.md` — the criteria framework the check-in uses for the "categorization gaps" section
