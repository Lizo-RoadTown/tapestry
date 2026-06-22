---
title: User-agent interfaces
description: A recurring coordination surface where operator intent, agent behavior, project structure, memory, and correction activity meet. Interfaces occur inside projects and workflows. Tapestry observes them as one of several signals about coordination health.
---

A user-agent interface is one observable manifestation of the coordination Tapestry reinforces. Interfaces occur inside projects and workflows; Tapestry observes them alongside other signals when tracking coordination health.

## Where interfaces sit in the picture

Tapestry is a user/agent support and reinforcement system. Its concern is the coordination between operator and agents. Memory, telemetry, observability, architecture analysis, friction analysis, and upskilling are mechanisms it uses to reinforce that coordination.

When an interface degrades, coordination is breaking down at that surface. When an interface stabilizes, coordination has settled into a pattern that may deserve durable structure. Tapestry watches interfaces because their state is informative about coordination quality.

## Definition

**A user-agent interface is a recurring coordination surface where operator intent, agent behavior, project structure, memory, and correction activity meet.**

Some examples to make this concrete:

- The interface between you and your code-review agent in this repo
- The interface between you and a research subagent dispatched from a planner
- The interface between two agents passing context to each other across a tool call
- The interface that emerges when a new dashboard surface starts being used and your corrections shape what it shows
- The interface that degrades when an MCP server starts dropping requests and the agent's behavior shifts in response

Interfaces are recurring patterns of coordination — patterns with purpose, history, expectations, and friction. They exist inside projects independently of any platform that watches them.

## What the observer looks at when it watches interfaces

The observer tracks interface state as one input to its broader picture of coordination health. The five lifecycle states it distinguishes:

| State | Meaning | Signal to coordination health |
|---|---|---|
| **Active** | Interface is in regular use; behavior is predictable | Coordination working as expected |
| **Emerging** | Interface is forming; coordination patterns are taking shape but not yet predictable | New coordination surface forming; operator and agents are still calibrating |
| **Changing** | Interface is in flux; participants, expectations, or memory attachments are shifting | Coordination is adapting — may be intentional, may be drift |
| **Degraded** | Interface is failing intermittently; coordination is breaking down | Coordination quality dropping; reinforcement needed |
| **Stabilized** | Interface has converged on a coherent form; corrections have effectively stopped | Coordination has settled; pattern may deserve durable structure |

Interface lifecycle is one of several inputs the observer uses. Memory health, telemetry signals, architecture diffs, friction patterns, and correction recurrence are other inputs.

## What each tracked interface carries

For each interface the observer tracks, it holds:

- **Purpose** — what coordination this surface supports
- **Participating agents** — which agents and operator take part
- **Operator expectations** — what "working" looks like from the operator's view
- **Memory dependencies** — which memory entries the interface relies on
- **Architecture dependencies** — which platform/repo structure supports it
- **Runtime signals** — telemetry exposing how the interface is being exercised
- **Friction signals** — where the interface is misaligned with intent
- **Correction history** — what the operator has corrected and when
- **Candidate durable structures** — what could earn promotion if the interface stabilizes

Today's observer implementation tracks a subset of this (skills invoked, recurring patterns from the upskilling report, cross-repo signal-rule output). The full set is the target shape.

## How interfaces relate to the rest of the picture

| Concept | Relationship |
|---|---|
| **Tapestry** | The support/reinforcement system; acts on interfaces from outside them |
| **User/agent coordination** | The focal phenomenon; interfaces are one observable manifestation of it |
| **Projects** | Environments where coordination occurs; expose different interfaces under different conditions |
| **Project shape** | The structural conditions a project creates for coordination; affects which interfaces emerge and how they behave |
| **Memory** | A reinforcement mechanism; also where interface state accumulates |
| **Telemetry** | A reinforcement mechanism; surfaces signals about how interfaces are being exercised |
| **Observer** | The component that watches interface lifecycle alongside other coordination signals |
| **Architecture diffs** | Often reveal interface change; more broadly reveal structural changes affecting coordination |
| **Upskilling** | What happens when a stabilized interface earns durable structure |

## Related

- [Canonical statement](/) — Tapestry as a user/agent support and reinforcement system
- [Project shape](/start/project-shape/) — environments where coordination occurs
- [What Tapestry is not](/start/what-tapestry-is-not/) — anchoring against "Tapestry is an interface observatory" and other false frames
- [The observer](/explanation/the-observer/) — the component that watches interface lifecycle as one of many coordination signals
- [The signal hierarchy](/explanation/signal-hierarchy/) — the levels of evidence the observer interprets
