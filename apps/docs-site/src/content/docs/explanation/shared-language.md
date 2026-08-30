---
title: Shared language
description: The eight words the memory pages use, defined once in plain terms — friction, record, correction, one-time learning, recall, scope, fingerprint, and label. The canonical glossary the other pages link to instead of re-defining.
---

The memory pages all lean on the same handful of words. This page defines them once, in plain terms, so you can read the rest without guessing what a word means. Every other page links here rather than redefining them.

If you are setting up your first memory store, read this top to bottom once. The eight words below are the whole vocabulary; nothing else on the memory pages assumes knowledge you won't find here.

## The words

### Friction

The repeated cost of working with an agent that forgets: re-explaining the same context, watching it repeat a mistake, losing a correction by the next session. Memory exists to end friction.

It is the thing you are trying to get rid of. If you have never worked with an agent that remembers, friction is the background hum you may not have noticed yet — every session starting from zero. The rest of these words describe how a memory store removes it.

### Record

One memory. A few words worth keeping, a *fingerprint* of their meaning, and a few *labels*.

A record is the unit the store holds. Not a whole conversation, not a file — one small, durable thing: a correction you gave, a decision you made, a fact about a project. The store is a collection of these.

### Correction

When you tell the agent it got something wrong. Saved as a record, it becomes standing guidance it follows from then on.

A correction is the highest-value kind of record. You give it once — "no, we use pnpm here, not npm" — and because it is saved, the agent follows it in every session afterward instead of making you say it again.

### One-time learning

A cost you'd otherwise pay every session, paid once instead: a correction saved once is guidance forever.

This is the shape of the whole payoff. Without memory, the same explanation is a cost you pay every time you sit down. With memory, you pay it once. That conversion — a repeating cost turned into a single one — is what the store is for.

### Recall

The system surfacing the right records by *meaning*, not keyword, the moment they're relevant — automatically.

You do not search for a record by remembering its exact words. When something you once saved becomes relevant again, recall brings it back on its own, matching by what it *means*. This is why the store is useful even when you have forgotten what is in it.

### Scope

Who or what a record belongs to: **you** (a hard wall — never another person's memory), a **project** (a soft sort — a filter, not a barrier), and **machine** (deliberately none — same key, same memory everywhere).

Scope is the answer to "who sees this record?" There are three parts, and they behave differently on purpose:

- **You** is a hard wall. Your records are yours; the store will not hand another person's memory to you or yours to them.
- **Project** is a soft sort. Within your own records, project labels sort things by project — a filter you can lift, not a wall. A record can even belong to two projects at once.
- **Machine** is deliberately absent. There is no "which machine" boundary. Your laptop, your desktop, and a scheduled job all reach the same memory, because reaching it from everywhere is the point.

### Fingerprint

The 384-number stand-in for what a record's words *mean*, so recall can match by meaning instead of exact words.

When a record is saved, a small model on your own machine reads its words and produces 384 numbers that stand for their meaning. That is the fingerprint. Recall compares fingerprints to find records close in meaning, which is how it can surface the right one even when your words this time differ from the words you saved.

### Label

The marks on a record — whose it is, which projects, who wrote it, when — that keep one shared store sorted.

Labels are the bookkeeping on each record. They are what make one shared store usable: because every record carries who it belongs to and which projects it touches, the store can stay sorted by owner and project even though everything lives in one place.

## Related

- [The memory](/explanation/the-memory/) — the concept, in brief, using these words.
- [Why the memory is built this way](/explanation/why-memory-is-built-this-way/) — the reasons behind the shape, using these words.
- [The memory MCP](/explanation/memory-mcp/) — what accumulates in a running store and how to keep it healthy.
