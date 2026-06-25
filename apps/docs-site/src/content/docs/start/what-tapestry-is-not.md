---
title: What Tapestry is not
description: Tapestry borrows pieces from memory tools, observability stacks, and tracing — but it is none of them. Here's what it actually is, frame by frame.
---

Tapestry helps you and your agents work together better over time — it notices what keeps happening in your projects, reinforces what works, and turns recurring patterns into durable structure. Memory, telemetry, observability, and upskilling are mechanisms it uses to do that. They are not the thing itself.

Readers often arrive with one of those mechanisms loaded as the whole picture. Each table row names the frame, then what Tapestry actually is instead.

## Why it matters

If you read Tapestry as "a memory system" or "a dashboard," you'll expect the wrong thing, look in the wrong place, and conclude it's broken when it's working as designed. The frame you arrive with decides what you go looking for.

## Frame by frame

| You might read it as… | What it actually is |
|---|---|
| A memory system (Mem0, Letta, Zep) | Memory is one mechanism. Tapestry uses it to reinforce what's worth keeping. |
| An observability stack (Grafana, OpenTelemetry) | Observability is one source of evidence about how coordination is going. |
| An agent tracing tool (LangSmith, AgentOps) | Tracing produces telemetry. Telemetry is one input among several. |
| A training pipeline | Upskilling is the step that turns a stabilized pattern into a reusable skill or rule. |
| A project dashboard | The dashboard is one surface onto the patterns — not the system behind them. |
| A workflow orchestrator (Airflow, Temporal) | Tapestry does not run your workflows. It observes them. |
| A knowledge graph | Memory accumulates state, but entities-and-relationships is not the primary structure. |
| A CRM | Not record-keeping. The point is the reinforcement loop, not the records. |

## Going deeper

- [Project intelligence](/project-intelligence) — the outcome-led version of what Tapestry accumulates and why.
- [The observer](/explanation/the-observer/) — why "observability system" is the wrong frame for the part that watches your project.

## Related

- [Project intelligence vs Observatory](/explanation/project-intelligence-vs-observatory/) — keeping the three platform nouns distinct.
- [Project shape](/start/project-shape/) — what Tapestry watches change over time.
