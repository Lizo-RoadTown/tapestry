---
title: Observatory lenses
description: The Observatory is one surface, not one dashboard. A lens is a view that foregrounds a single dimension — memory, architecture, coordination — and hides the rest, so the thing you're studying isn't drowned out.
---

The Observatory is one surface. A lens is how you look at it. Each lens foregrounds a single dimension — what a project remembers, how its architecture drifted, where coordination got stuck — and hides everything else, so the dimension you're studying stands out instead of being buried. Want to study an intersection? Overlay two lenses.

## Why it matters

A single all-purpose dashboard has to pick one primary axis, and whichever it picks is wrong for half your questions. A memory-axis view makes drift invisible; an architecture-axis view makes coordination friction invisible. Lenses let you load the axis your current question needs, rather than squinting at one fixed layout.

## How it works

Each lens asks a different question of the same stored patterns:

| Lens | The question it answers |
|---|---|
| **Memory** | What does this project remember? What's reinforced, and what's been written but never re-read? |
| **Architecture** | What's the current shape, what changed, and what drifted? |
| **Coordination** | Where are you and the agent getting stuck together? Where is it smooth? |
| **Observer** | What is the observer interpreting right now, and how confident is it? |
| **Cross-project** | What patterns recur across projects — what's becoming a capability vs staying a one-off? |

Every lens runs the same way under the hood: a query against the pattern store, an aggregation that makes the dimension legible, a render (card, list, timeline, or overlay), and a drill-down so any finding links back to the signals and interpretation behind it.

## What you do

Pick the lens that matches your question. When you want an intersection — say, the memory writes that landed the same week as a high-confidence architecture drift — overlay two lenses. Only the meaningful pairings overlay; the Observatory surfaces those and keeps the rest one-at-a-time.

## What it's not

- **A lens is not a dashboard tab.** A tab is one way to deliver a lens; a lens can also be an overlay, a filter, or data returned via the docs MCP.
- **Not a separate app.** Each lens is a component of the Observatory, not its own deployment.
- **Not all built yet.** These are the lens classes on the roadmap; each gets its own concept page when it ships.

## Going deeper

- [Project Intelligence vs Observatory](/explanation/project-intelligence-vs-observatory/) — where the Observatory sits relative to the Observer and per-project intelligence.
- [Signal → Interpretation → Pattern](/explanation/signal-interpretation-pattern/) — what flows into a lens (lenses operate at the pattern layer, not raw signals).

## Related

- [The observer](/explanation/the-observer/) — the component that produces the patterns each lens reads.
- [The signal hierarchy](/explanation/signal-hierarchy/) — why lenses live at the patterns level, not the events level.
