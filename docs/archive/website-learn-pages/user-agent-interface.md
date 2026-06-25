---
title: User-agent interfaces
description: A recurring place inside a project where you and an agent coordinate — and one of the signals Tapestry watches to tell whether that coordination is healthy.
---

A user-agent interface is a recurring coordination surface inside a project — a place where your intent, the agent's behavior, the project's structure, memory, and your corrections all meet. You and a code-review agent working in this repo is an interface. So is you and a research subagent dispatched from a planner, or two agents passing context across a tool call. Tapestry watches interfaces as one signal about whether coordination is holding up.

## Why it matters

Most failures in agent-assisted work aren't the agent's fault or yours in isolation — they happen at the interface between you. When that surface frays, intent stops flowing cleanly: corrections get forgotten, framing drifts, the agent assumes things it shouldn't. Watching interfaces lets Tapestry catch that fraying as a pattern instead of as one bad session.

## How it works

Each interface moves through recognizable states. The observer tracks where each one sits.

| State | Meaning |
|---|---|
| **Active** | In regular use; behavior is predictable |
| **Emerging** | Forming; not yet predictable |
| **Changing** | In flux; participants or expectations shifting |
| **Degraded** | Failing intermittently; coordination breaking down |
| **Stabilized** | Converged; corrections have stopped |

Today's observer tracks a subset of what an interface involves — which skills you invoked, recurring patterns from the upskilling report, cross-repo signals. The fuller picture (operator expectations, memory and architecture dependencies, correction history) is the target, not all wired yet.

## What you do

Nothing directly. Interfaces are observed as a side effect of normal work. You feel one degrade when coordination gets rough — the same correction keeps coming back, or the agent stops tracking what you meant.

## What it's not

- **Not a piece of code.** An interface is a coordination surface, not a file or an API.
- **Not a single agent.** It's the meeting point between participants, including you.
- **Not fully instrumented yet.** The observer reads a subset today.

## Going deeper

- [The Observer component](/systems/observer/) — what the observer actually reads per interface and how it runs.

## Related

- [Project shape](/start/project-shape/)
- [The observer](/explanation/the-observer/)
- [The signal hierarchy](/explanation/signal-hierarchy/)
