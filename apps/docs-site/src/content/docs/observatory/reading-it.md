---
title: Reading the Observatory
description: How to read the console — the variable + overlay selectors, the chart types (line trend vs scatter relationship), the observer interpretation panel, and how blind (uninstrumented) variables are shown honestly rather than faked.
---

The console at [`/observatory`](/observatory) has three parts: the controls, the chart, and the observer's interpretation.

## The controls

| Control | What it does |
|---|---|
| **Show** | The variable on the vertical axis (the thing you're tracking). |
| **overlaid with** | A second variable to compare against — or *none*. |
| **as** | The view: **trend (line)** or **relationship (scatter)**. |

A recommendation appears next to the controls: with two real variables, a scatter shows their relationship; with one variable (or one that isn't instrumented), a line over time is the right read.

## The variables

| Variable | State | Source |
|---|---|---|
| Architecture changes | **real** | architecture snapshot diffs |
| Working episodes | **real** | hook telemetry (prompt → stop cycles) |
| Tool activity | **real** | `PreToolUse` events |
| Observer candidates | **real** | observer `obs_created` |
| Friction recurrence | *blind* | not instrumented |
| Memory misses | *blind* | not instrumented |
| Correction frequency | *blind* | not instrumented |

A **blind** variable is selectable, but it has no data yet. The chart draws it as a dashed *not instrumented* line, a scatter against it shows "can't plot a relationship — one axis has no data," and the interpretation says so. This is deliberate: the Observatory makes missing instrumentation visible instead of hiding it.

## The chart types

- **Trend (line)** — one or two variables over time. Reads as "is this going up or down."
- **Relationship (scatter)** — each point is one day, plotting one variable against another. Reads as "do these move together." Only available when both variables are real.

More view types (heatmap, timeline, flow, shape radar) are planned as the variable set and instrumentation grow.

## The interpretation panel

For whatever you've selected, the observer states:

1. **What you're looking at** — the selected variables in plain language.
2. **Why these matter together** — the question the overlay tests.
3. **Patterns this view may expose** — e.g. *architecture churn causing coordination degradation*, *memory misses following structural changes*.
4. **What the observer currently thinks** — its current read, or an honest "can't measure this yet."
5. **Blind / low-confidence** — which signals are missing.

This panel is the point of the console. The chart shows the data; the panel explains what the data can and can't tell you.

## Raw events

Counters and the unrolled hook stream live under **[Raw events](/observatory/raw)** — drill-down evidence, not the main view.
