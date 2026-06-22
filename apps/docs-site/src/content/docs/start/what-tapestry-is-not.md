---
title: What Tapestry is not
description: Anchoring against false analogies. Readers reach for LangSmith, Grafana, OpenTelemetry, Airflow, AgentOps, Memory MCP, Knowledge Graph, CRM. Tapestry does pieces of several of those, but is none of them.
---

Most readers come to Tapestry with a mental model already loaded — usually one of these:

- LangSmith / AgentOps (agent tracing + eval)
- Grafana / OpenTelemetry (observability + dashboards)
- Airflow / Temporal (workflow orchestration)
- A memory MCP (cross-session memory store)
- A knowledge graph (entities + relationships)
- A CRM (records + workflows)
- Project observability (a fleet view of repos + their telemetry)

Tapestry does pieces of several of those. If you read these docs while one of those frames is loaded, you will get confused, because Tapestry will keep doing things outside that frame.

This page is the explicit anti-frame. Read it after [User-agent interface](/start/user-agent-interface/) and [Project shape](/start/project-shape/) — those name what Tapestry *is*; this page names what it *isn't*.

## The thing Tapestry actually is

**Tapestry observes the evolving coordination layer between operators and agents, and decides what part of that coordination should become durable structure.**

That's the only sentence you need.

The shorter version, focused on the loop: *observing how work evolves and deciding what should become durable structure.*

The primary object is the [user-agent interface](/start/user-agent-interface/). Projects, architecture, memory, and telemetry are evidence about how interfaces are changing. Everything else is a face of that one sentence applied to a different surface.

## What Tapestry is not

### Tapestry is not a memory system.

Memory is one signal.

It happens to be the substrate the observer reads from and writes to. It happens to be the thing the operator interacts with most directly. But the system isn't *for* memory. Memory is *how* the agent's accumulated understanding of project shape gets persisted across sessions — and shape is the actual subject.

If you treat Tapestry as a memory MCP, you'll be confused by everything to do with candidate registries, policy gates, signal hierarchies, and architecture snapshots — because none of that is about memory.

### Tapestry is not an observability system.

Observability is one signal.

It happens to expose the runtime view of project shape — what's executing right now, what's failing, what tools are being called. But "what happened?" is a state question. Tapestry's real questions are trajectory questions: *what's becoming? what's about to change shape?*

If you treat Tapestry as Grafana-for-agents, you'll be confused by everything having to do with patterns, candidates, structure formation, and the upskilling loop — because none of that fits in a dashboard of current metrics.

### Tapestry is not an upskilling engine.

Upskilling is one capability.

It happens to be the visible output of the loop: a pattern stabilizes, the observer surfaces a candidate, policy gates it, the skill compiler turns it into a callable thing. But upskilling is *what happens at the bottom of the loop*, not the loop itself. The loop is the observation of shape over time.

If you treat Tapestry as an automated training pipeline, you'll be confused by everything having to do with drift, fragmentation, coherence, and operator corrections — because those are inputs to the loop, not outputs.

### Tapestry is not a project portfolio dashboard.

A portfolio view is one application.

It happens to be where the cross-project compounding becomes visible — patterns repeating across projects, intelligence flowing between them, fleet-level health signals. But the portfolio is the same loop applied to many projects, not a fundamentally different system.

If you treat Tapestry as Linear-for-agents, you'll be confused by everything happening inside a single project — because the unit of analysis is shape, not projects-as-objects.

### Tapestry is not a coordination layer for humans and agents.

Coordination is one byproduct.

It happens to be what occurs inside one of those projects — humans correct agents, agents surface candidates, structure forms. But coordination is the work happening inside the loop, not the architecture of the loop itself.

If you treat Tapestry as Slack-for-agents, you'll be confused by everything that's about shape detection rather than message passing.

### Tapestry is not project observability.

Project telemetry is evidence.

A fleet dashboard that surfaces what's running, what's failing, and what's drifting across many projects is one *output* the platform can produce — but it's not the platform's purpose. The platform exists to understand the *user-agent interfaces* that the telemetry is exposing. Projects are containers for interfaces; project-level observability is one source of evidence about how interfaces are changing.

If you treat Tapestry as "Grafana for AI projects," you'll be confused by everything that's about *who's coordinating with whom and how* rather than *what's running and how fast.*

## The right frame

Every face above describes one view of the same underlying object: *the platform exists to observe user-agent interfaces as they evolve, and to crystallize coordination patterns into durable structure.* Project shape is the substrate those interfaces live on; everything else is evidence.

The right reading order for these docs:

1. [User-agent interface](/start/user-agent-interface/) — the primary object
2. [Project shape](/start/project-shape/) — the substrate interfaces live on
3. This page — what Tapestry is not
4. [The signal hierarchy](/explanation/signal-hierarchy/) — the evidence levels
5. [The observer](/explanation/the-observer/) — the component that watches interface evolution
6. [How the platform upskills itself](/explanation/upskilling/) — the loop from interface stabilization to durable structure
7. [The memory MCP](/explanation/memory-mcp/) — the substrate where interfaces accumulate state
8. [Sharing intelligence across projects](/explanation/sharing-intelligence-across-projects/) — the loop applied across the fleet

Read in that order and the system snaps into focus. Read in any other order and you'll keep mapping it onto something it isn't.
