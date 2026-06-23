---
title: Observatory lenses
description: The Observatory is not a single dashboard. It is a surface that holds multiple lenses, each exposing a different facet of the same underlying patterns. Memory, architecture, coordination, observer, and cross-project lenses each ask different questions of the same data.
---

The Observatory is one surface. The lenses are how the operator *looks* at it. Different lenses expose different patterns from the same underlying interpretations.

## What a lens is

A lens is a structured view over the platform's stored patterns that:

- **Foregrounds one dimension** (memory writes, architecture diffs, coordination friction, observer findings, cross-project recurrence).
- **Hides everything else** by default, so the dimension being studied isn't drowned out.
- **Composes with other lenses** as overlays when the operator wants to study an intersection.
- **Is implemented as a component** of the Observatory dashboard — not a separate app.

A lens is not a dashboard tab. A dashboard tab is one way to deliver a lens; lenses can also be rendered as overlays on a single canvas, exposed as filters on a list view, or returned as data via the docs MCP.

## Planned lenses

These are the lens classes currently on the roadmap. Each has its own concept page when it ships.

| Lens | The question it answers | What it foregrounds |
|---|---|---|
| **Memory lens** | What does this project remember? What's reinforced? What's been written and never re-read? | Memory rows by scope, tag, reinforcement count, recency, last-read timestamp |
| **Architecture lens** | What's the current shape? What changed? What drifted? | Architecture snapshots, diffs between snapshots, drift-watcher findings, candidate categories |
| **Coordination lens** | Where is the user and agent getting stuck together? Where is coordination smooth? | Correction events, repeated prompts, abandoned actions, friction clusters around specific files or topics |
| **Observer lens** | What is the observer currently interpreting? What's its confidence? What's it uncertain about? | Active intent hypotheses, candidate findings awaiting promotion, observer-confidence histograms |
| **Cross-project lens** | What patterns recur across multiple projects? What's becoming a *capability* vs staying an *instance*? | Candidate recurrences across projects, promotion-eligibility scoring, capability-vs-instance classification |

## Why one canonical dashboard misses the point

If the Observatory tried to be a single canonical dashboard, it would have to pick a primary axis. Whichever axis it picked would be wrong for half the operator's questions:

- A memory-axis dashboard makes drift invisible.
- An architecture-axis dashboard makes coordination friction invisible.
- A coordination-axis dashboard makes cross-project recurrence invisible.

Lenses solve this by letting the operator load the axis their current question needs, then compose overlays when they want to study an intersection ("show me the memory writes that happened in the same week as the architecture drift the observer flagged with high confidence").

## How lenses are built

Every lens follows the same shape:

1. **Query.** A typed query against the pattern store (architecture-registry, candidate-registry, memory, observer findings). The query expresses the lens's foregrounded dimension as parameters.
2. **Aggregation.** Patterns grouped, ranked, or time-bucketed in whatever way makes the dimension legible.
3. **Render.** A surface in the Observatory (card, list, timeline, overlay, diff view) — chosen for the dimension, not standardized across lenses.
4. **Drill-down.** Each rendered item links back to the underlying signals + interpretation + supporting evidence, so the operator can audit any finding.

## Lens composition

Two lenses overlay when the operator wants to study where dimensions intersect. The implementation is intersection at the query layer (both queries filter the same pattern store; the overlay shows only patterns that satisfy both), with the rendering chosen by whichever dimension the operator marked as primary.

Composition is bounded: not every pair of lenses overlays meaningfully. The Observatory surfaces the meaningful compositions; the rest stay one-at-a-time.

## How this composes with the rest of the platform

- **[Project Intelligence vs Observatory](/explanation/project-intelligence-vs-observatory/)** explains where the Observatory sits: it's the platform-level surface, distinct from per-project Project Intelligence and from the Observer that produces the patterns lenses display.
- **[Signal → Interpretation → Pattern](/explanation/signal-interpretation-pattern/)** is what flows *into* a lens. Lenses operate at the pattern layer; they don't show raw signals.
- **[The observer](/explanation/the-observer/)** is the component that produces the patterns each lens reads.
- **[The signal hierarchy](/explanation/signal-hierarchy/)** explains why lenses live at the patterns level and not at the events level (events would drown the lens; patterns are the right granularity).

## The shortest version

```
The Observatory is the surface.
Lenses are how you look at it.
A lens picks one dimension; overlays compose dimensions.
No single dashboard does this.
```
