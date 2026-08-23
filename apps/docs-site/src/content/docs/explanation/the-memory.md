---
title: The memory
description: How Tapestry remembers across sessions, projects, and machines — the handful of durable things worth carrying forward from your work, recalled automatically the next time they're relevant.
---

The memory is how Tapestry remembers across sessions. When you work with an agent, most of what it knows lasts only until that session ends — the next one starts blank. Memory is the small set of durable things that survive the reset: a correction you gave, a decision you made, the current state of a project. Each is saved once and recalled automatically whenever it's relevant again — in any session, any project, on any of your machines.

## Why it matters

Without it, every session starts cold. You re-explain the same context, the agent repeats the same mistakes, and a correction you gave last week is gone this week. That cost is paid every session. Memory turns those repeated costs into one-time learnings — a correction saved once becomes guidance from then on.

## How it works

Memory is a set of small, named cards, each one a typed record — a piece of feedback, a decision, a fact, a project's state. The agent writes them in response to what happens, and reads them back when they matter:

| Moment | What memory does |
|---|---|
| A session starts | The most relevant cards for the current project are recalled automatically into the agent's context |
| You correct the agent | The correction is saved immediately, as a card the agent operates under from then on |
| A decision or deliverable lands | The agent writes a card snapshotting what changed |
| The agent needs past context mid-task | It recalls by *meaning*, not by keyword — the right card surfaces even if the words differ |

Every card carries labels: whose it is, which projects it belongs to, who wrote it. Those labels are what let one shared store stay sorted by project and, at the same time, be reachable identically from every machine you work on.

## What you do

Almost nothing. Once the discipline plugin is wired, the writing and recalling happen on their own. At the start of a session you'll see a block of recalled memories — past decisions, prior feedback, current state. Your job is to recognize what's there and to flag anything durable that should be saved.

## What it's not

- **Not a chat log.** It keeps the durable things, overwritten in place as they change — not every message.
- **Not a notebook you file into by hand.** The agent writes; you recognize and flag.
- **Not big-data storage.** It's tuned for one person with thousands of memories, which is what keeps it small and fast.

## Going deeper

- [Why the memory is built this way](/explanation/why-memory-is-built-this-way/) — the reasons behind the shape: why it stays light, never bloats, and works across every machine.
- [The memory MCP](/explanation/memory-mcp/) — what accumulates, how project tags scope it, and how to keep it healthy.
- [Memory (component)](/systems/memory/) — how the store is wired, how to run it, and how to verify it.

## Related

- [The observer](/explanation/the-observer/) — whose recurring-pattern memos are written into this same memory.
- [What Tapestry is](/start/what-stays-on-track/) — the other mechanisms that turn recurring friction into structure.
