---
title: The memory
description: What an agent-memory store is, why you'd set one up, and how it behaves — the small set of durable things it carries across sessions, projects, and machines, recalled automatically the next time they matter.
---

The memory is a store that lets an agent carry a few durable things forward instead of starting blank every time. When you work with an agent, most of what it knows lasts only until the session ends; the next one begins from zero. A memory store keeps the small set of things worth surviving that reset — a [correction](/explanation/shared-language/#correction) you gave, a decision you made, the current state of a project. Each is saved once and [recalled](/explanation/shared-language/#recall) automatically whenever it's relevant again, in any session, any project, on any of your machines.

The words in **bold-linked** text throughout these pages are defined in [Shared language](/explanation/shared-language/). Read that once and the rest reads plainly.

## Do you need this?

You need a memory store if any of these is a cost you're tired of paying:

- You re-explain the same context — your stack, your conventions, how you like things — at the start of every session.
- You correct the agent on something, and a week later it makes the same mistake because the correction is gone.
- You want work on one machine to be visible when you sit down at another.

That recurring cost has a name — [friction](/explanation/shared-language/#friction) — and ending it is the entire reason the store exists. If none of the above bothers you, you don't need one. If they do, memory turns each of those repeated costs into a [one-time learning](/explanation/shared-language/#one-time-learning): paid once, then carried forward on its own.

## What it holds

The store is a collection of [records](/explanation/shared-language/#record). A record is one small, durable thing — a piece of feedback, a decision, a fact, a project's state — kept as a few words plus a [fingerprint](/explanation/shared-language/#fingerprint) of their meaning and a few [labels](/explanation/shared-language/#label). The agent writes records in response to what happens and reads them back when they matter:

| Moment | What the store does |
|---|---|
| A session starts | The most relevant records for the current project are recalled automatically into the agent's context |
| You correct the agent | The correction is saved immediately, as a record the agent operates under from then on |
| A decision or deliverable lands | The agent writes a record snapshotting what changed |
| The agent needs past context mid-task | It recalls by *meaning*, not by keyword — the right record surfaces even if the words differ |

Every record carries labels: whose it is, which projects it belongs to, who wrote it. Those labels are what let one shared store stay sorted by project while being reachable identically from every machine you work on.

## Decisions you'll make setting one up

Standing up a store comes down to a few choices. Each has a plain default.

| Choice | What it means | The plain default |
|---|---|---|
| **Self-host or hosted** | Run the store yourself, or point at a shared hosted one | Point at the hosted one — no server to run. Self-host when you want the data on infrastructure you control. |
| **One machine or several** | Whether the same memory should reach you across devices | The store draws no machine boundary. Give every machine the same key and they all reach the same memory. |
| **Where the shared key goes** | The key is what routes a machine to your memory | Set the *same* key on every machine. A missing or mismatched key means an error or a silently empty store. |

The one choice the store can't make for you is the last one: every machine must carry the same key. That's the whole of your setup responsibility — the [scope](/explanation/shared-language/#scope) model does the rest.

## How it behaves once it's running

Almost nothing is asked of you day to day. Once the store is wired in, the writing and recalling happen on their own. At the start of a session you'll see a block of recalled memories — past decisions, prior feedback, current state. Your part is to recognize what's there and to flag anything durable that should be saved. The agent writes; you notice.

The store keeps the durable things and overwrites them in place as they change — it is not a transcript of everything said. It's tuned for one person with thousands of memories, which is what keeps it small and fast.

## Going deeper

- [Why the memory is built this way](/explanation/why-memory-is-built-this-way/) — the reasons behind the shape: why it stays light, never bloats, and works across every machine.
- [The memory MCP](/explanation/memory-mcp/) — what accumulates in a running store, how project labels scope it, and how to keep it healthy.
- [Memory (component)](/systems/memory/) — how the store is wired, how to run it, and how to verify it.

## Related

- [Shared language](/explanation/shared-language/) — the words these pages use, defined once.
- [The observer](/explanation/the-observer/) — whose recurring-pattern memos are written into this same memory.
- [What Tapestry is](/start/what-stays-on-track/) — the other mechanisms that turn recurring friction into structure.
