---
title: The Observatory
description: The console where you watch coordination between you and your agents over time — what's changing in a project, what the observer sees, where friction appears, and whether things are trending better or worse. It lives at /observatory.
---

The Observatory is the console where you watch coordination between you and your agents, across projects and over time. It lives at [`/observatory`](/observatory), and it shows how a project's shape is changing, what the observer sees, where coordination friction appears, whether memory is helping or failing, and which way things are trending.

It answers *trajectory* questions — is coordination getting smoother or rougher, is anything stabilizing into a pattern worth keeping — rather than point-in-time status like "is the API up right now," which belongs in an operational dashboard.

## How it reads

The console models telemetry as variables over time. You pick a variable to **Show**, optionally **overlay** a second to compare it against, and choose how to view the result:

| Control | What it sets |
|---|---|
| **Show** | The variable to track |
| **overlaid with** | A second variable to compare, or none |
| **as** | Trend (a line over time) or relationship (a scatter, one point per day) |

For whatever you select, an interpretation panel states what you're looking at, why the variables relate, what patterns the view can expose, the observer's current reading, and which signals aren't instrumented yet.

## The variables

| Variable | State |
|---|---|
| Architecture changes | instrumented |
| Working episodes | instrumented |
| Tool activity | instrumented |
| Observer candidates | instrumented |
| Friction recurrence | not instrumented |
| Memory misses | not instrumented |
| Correction frequency | not instrumented |

A variable that isn't instrumented is still selectable, but has no data — the chart marks it *not instrumented*.

## Lenses

You look at the same patterns through different lenses — memory, architecture, coordination, observer, cross-project — each foregrounding one dimension and hiding the rest, so the thing you're studying isn't drowned out.

## What you do

Open it and pick the variable that matches your question. The Observatory is your own deployment; the [public demo](https://tapestry-khaki.vercel.app/observatory) runs on sample data as a read-only reference. To open it, run it locally, or feed it live data, see [Run the Observatory](/observatory/run-it/) and [The Observatory feed](/observatory/feed/).

## Related

- [First Observatory visit](/start/first-observatory-visit/) — what a brand-new project looks like.
- [The observer](/explanation/the-observer/) — what produces the patterns you're looking at.
