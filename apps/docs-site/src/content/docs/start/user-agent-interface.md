---
title: User-agent interfaces
description: A recurring coordination surface where operator intent, agent behavior, project structure, memory, and correction activity meet. Interfaces occur inside projects. Tapestry watches them as one signal about coordination health.
---

A user-agent interface is a recurring coordination surface inside a project. Operator intent, agent behavior, project structure, memory, and correction activity meet there. Tapestry watches interfaces as one signal about coordination health.

## Examples

- You and a code-review agent working in this repo
- You and a research subagent dispatched from a planner
- Two agents passing context across a tool call
- A dashboard surface where your corrections shape what it shows

## Interface lifecycle

| State | Meaning |
|---|---|
| **Active** | In regular use; behavior is predictable |
| **Emerging** | Forming; not yet predictable |
| **Changing** | In flux; participants or expectations shifting |
| **Degraded** | Failing intermittently; coordination breaking down |
| **Stabilized** | Converged; corrections have stopped |

## What the observer tracks per interface

Purpose, participating agents, operator expectations, memory dependencies, architecture dependencies, runtime signals, friction signals, correction history, candidate durable structures.

Today's observer tracks a subset (skills invoked, recurring patterns from the upskilling report, cross-repo signal-rule output).

## Related

- [Project shape](/start/project-shape/)
- [The observer](/explanation/the-observer/)
- [The signal hierarchy](/explanation/signal-hierarchy/)
