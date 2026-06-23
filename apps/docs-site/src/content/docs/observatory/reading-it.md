---
title: Reading the Observatory
description: The console controls — the variable and overlay selectors and the chart type — the variables it tracks, the two chart types, and the interpretation panel.
---

The console at [`/observatory`](/observatory) has three parts: the controls, the chart, and the interpretation.

## Controls

| Control | What it sets |
|---|---|
| **Show** | The variable to track. |
| **overlaid with** | A second variable to compare, or *none*. |
| **as** | The view — trend (line) or relationship (scatter). |

A recommendation appears next to the controls: a scatter for two instrumented variables, a line over time otherwise.

## Variables

| Variable | State |
|---|---|
| Architecture changes | instrumented |
| Working episodes | instrumented |
| Tool activity | instrumented |
| Observer candidates | instrumented |
| Friction recurrence | not instrumented |
| Memory misses | not instrumented |
| Correction frequency | not instrumented |

A variable that is not instrumented is selectable but has no data; the chart marks it *not instrumented*.

## Chart types

- **Trend (line)** — one or two variables over time.
- **Relationship (scatter)** — each point is one day, plotting one variable against another. Available when both variables are instrumented.

## Interpretation

For the selected variables, the panel states:

1. what you are looking at,
2. why these variables relate,
3. patterns this view can expose,
4. the observer's current reading,
5. signals that are not instrumented.

## Raw events

Counters and the raw hook event stream are under [Raw events](/observatory/raw).
