---
title: Why the memory is built this way
description: The reasons behind the shape of the memory store — why it stays light, why it never bloats, why recall is cheap, and how user, project, and machine scope differ. The design choices, tied to the goals they serve.
---

The other memory pages tell you what the store holds and how to run it. This one tells you *why it has the shape it has*, so if you stand up your own you can make the same trade-offs on purpose.

One honest thing first, because it shapes the rest: this design wasn't lifted from a single blueprint. It started from ideas in one of NVIDIA's agentic architectures, kept little of it, passed through a working version built on LanceDB, and borrowed structure from the deepagents pattern. What it is now is the result of trial and error against one goal — **keep memory light, keep it from bloating, keep recall good enough to not be frustrating, across every machine.**

## Why it matters

Memory is the floor the rest of the platform stands on. The observer, the discipline hooks, the cross-agent channel — none of them mean anything if the memory underneath is slow, bloated, or trapped on one machine. So the shape of this one store isn't a side detail; almost every choice in it is that one goal applied to a smaller piece.

## How it works

A memory is one card: a few **words** worth remembering, a short **fingerprint** (384 numbers standing for what the words *mean*), and a few **labels** (whose it is, which projects, who wrote it, when). The store is a box of these cards. Every design choice serves one of four needs:

| The need | What serves it | Why it works |
|---|---|---|
| **Stay light** | Small fingerprints, made locally by a small model; cards are plain text | A memory is a few words plus 384 numbers — cheap to store, and made on your own machine with no per-write fee and no internet |
| **Never bloat** | A card's name *is* its identity; deletes mark rather than erase | Resaving a name replaces that card instead of stacking a copy — the store stays the size of what you know, not how often you wrote it down |
| **Recall good-enough** | Search by meaning; everything on one card; a prebuilt shortcut for finding the closest | One query does "yours → this project → closest in meaning" in a single pass, and stays fast whether there are fifty memories or fifty thousand |
| **Work across machines** | One shared box, reached with a shared key | Every device presents the same key and lands in the same box, so the same recall works everywhere |

Two of those choices are worth a closer look because they're the counterintuitive ones.

**A memory's name is its address.** Save a memory under a name that already exists and it *overwrites* — it does not add a second card. Without this, every revision would pile up near-duplicates and the box would fill with slightly-different versions of the same thought. With it, the store holds one card per idea however many times you revise it. That single rule is most of why it never bloats.

**Everything the search needs is on the one card.** The words, the fingerprint, and the labels live together in one table, so a single lookup filters *and* ranks in one step. If the fingerprints lived in a separate specialized database, every recall would query two stores and stitch the answers together — slower, and one more thing to run. Keeping them together is why recall is one fast step.

### The scope model: two walls and one deliberately left out

Every card carries three labels that answer three different questions — whose it is, which projects, and which agent wrote it. From those, the three "scopes" people ask about fall out, and the surprising part is that **two are walls and the third is a wall the design leaves out on purpose:**

- **User scope is a hard wall.** Your memories sit under one owner-label, and the store itself refuses to return a card that isn't yours — enforced on every read and write, below the app.
- **Project scope is a soft sort.** Inside your own memories, project labels sort cards by project. It's a helpful filter, not a barrier — a memory can carry two project labels, and cross-project recall is allowed. A genuine wall *between* projects needs a separate owner-label, the same hard wall used between people.
- **Machine scope doesn't exist — and that's the point.** There is no "which machine" label at all. Your laptop, your desktop, a scheduled job — different machines, same shared key, so they all land in the same box. Machine isn't a boundary the store draws; it's the boundary it *refuses* to draw, because reaching the same memory from every machine is the reason the store exists in the first place.

```mermaid
flowchart LR
    L[Laptop] --> K{Same shared key}
    D[Desktop] --> K
    C[Scheduled job] --> K
    K --> B[(One shared box<br/>your memories)]
```

One caution follows directly: because the shared key is what routes a machine to your box, every machine must carry the *same* key. A missing or mismatched key is turned away with an error; a machine pointed at a *different* box lands there and quietly finds it empty. Either way the fix is the same — set the one key, identically, everywhere.

## What you do

Nothing, for the shape itself. The store runs as one always-on service; the agent writes and recalls memories automatically. Your only job is the one thing the design can't do for you: keep every machine on the same key.

## What it's not

- **Not a chat log.** It keeps a small number of durable, named memories, overwritten in place — not every message.
- **Not a second brain you file into by hand.** The agent writes memories in response to events; you recognize and flag, you don't curate.
- **Not a big-data system.** It's tuned for one person with thousands of memories — that's *why* it's small and fast. A public multi-tenant service would make different choices, and should.
- **Not built from one architecture.** It's a trial-and-error shape tested against "light, doesn't bloat, recalls well enough." The reasons on this page are the real design, not the name of any framework.

## Roads not taken

- **A separate vector database for the fingerprints** — rejected because it splits each memory across two stores and makes every recall a two-step join. One card, one query.
- **On-machine files (the earlier LanceDB version)** — a working version stored memory in files, and it was ported away from for the founding reason: files live on *one* machine, and the whole point was one shared memory across all of them.
- **Splitting memories into several tables by kind** — rejected because recall almost always wants the closest memories regardless of kind; one table with a "kind" label on each card keeps recall simple.

## Going deeper

- [Memory (component)](/systems/memory/) — how the store is wired, how to run it, and how to verify it.
- [The memory MCP](/explanation/memory-mcp/) — what accumulates, how project tags scope it, and how to keep it healthy.

## Related

- [The memory](/explanation/the-memory/) — the concept, in brief, if you want the shorter version first.
- [The observer](/explanation/the-observer/) — whose synthesis memos are just more cards in this same box.
