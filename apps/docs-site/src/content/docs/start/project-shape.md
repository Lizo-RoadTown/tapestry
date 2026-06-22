---
title: Project shape
description: The substrate that user-agent interfaces live on. A project has a shape — observable structure that exists independent of any single file — and that shape changes over time. Shape change is one of the strongest evidence sources for how user-agent interfaces are evolving.
---

The substrate on which user-agent interfaces live. Read [user-agent interface](/start/user-agent-interface/) first — that's the primary object of observation. This page is the substrate that primary object exists on.

## Definition

**Project shape** is the observable structure of a project over time.

Shape is not a single file or a single repository. Shape is the accumulated pattern of all of these together:

- architecture (services, packages, boundaries)
- repositories (which code lives where, how it's split)
- memory (what the agent has learned about this project)
- agents (which agents work in it, what they specialize in)
- workflows (how work moves through the project)
- skills (which capabilities are available to invoke by name)
- friction (what keeps tripping the operator, what corrections keep firing)
- corrections (the operator's binding rules captured as memory)
- dependencies (what this project relies on, what relies on it)
- runtime behavior (what actually runs, how often, what fails)

Shape is the thing you'd describe if someone asked you "what kind of project is this, and what's it like to work in?" The answer is rarely a single sentence about the codebase. It's a feel for the boundaries, the patterns, the recurring problems, the working agreements.

## Shape can change without code changing

A project that doesn't ship a single commit can still change shape:

- A correction the operator gives once becomes a binding rule in memory. The agent now behaves differently in that project. Shape changed.
- A pattern recurs three times across sessions. The observer surfaces it as a candidate. Shape is moving toward needing new structure.
- An external dependency releases a breaking change in their MCP. The project's wiring assumes the old contract. Shape is drifting from assumed shape.
- The operator stops correcting a behavior the agent has learned to do correctly. Shape stabilized.

The codebase is one input to shape. It is not shape itself.

## The four shape verbs

Projects do one of four things at any given time:

| Verb | What it means | What it produces |
|---|---|---|
| **Drift** | Shape moves away from what the operator + agent think it is | Memos that say one thing while code does another; runbooks that no longer match; assumptions encoded in plugins that don't hold |
| **Stabilize** | Shape converges on a coherent form the operator + agent agree on | Patterns become candidates become skills; corrections stop firing; the project's "house style" becomes legible |
| **Fragment** | Shape splits into incoherent pieces that don't share assumptions | One service uses pattern A, another uses pattern B for the same problem; memory entries contradict each other; subagents lose context across handoffs |
| **Cohere** | Shape consolidates — fragmented pieces converge | Duplicate logic collapses into a shared library; competing patterns reconcile into one canonical home; agents share understanding |

Every Tapestry-detectable event is some signal about one of these four motions.

## Why this concept is load-bearing

Project shape is the **substrate** layer in Tapestry's architectural hierarchy. The primary object of observation is the [user-agent interface](/start/user-agent-interface/); interfaces live inside projects; projects have shape. Shape change is one of the strongest evidence sources for *interface change*.

Once you have *project shape* as a primitive — sitting beneath user-agent interface and above all the lower-level Tapestry concepts — every other Tapestry concept describes one face of it:

- **Memory** is the agent's accumulated understanding of the shape. The substrate the observer reads from and writes to.
- **Observability** is the API for asking what the current shape is and what it's doing right now.
- **Observer** is the component that watches shape change over time and decides what's worth surfacing.
- **Candidate registry** is the holding tank for shape changes that haven't earned durable structure yet.
- **Policy** is the gate that decides when a candidate has earned durable structure.
- **Skill compiler** is what turns "this candidate earned structure" into a reusable, callable thing.
- **Upskilling** is the entire feedback loop: shape changes → observer notices → candidates accumulate → policy gates → structure crystallizes.
- **Project portfolio** is the same loop applied to many projects, where shape signals can compound across them.

If you read a Tapestry doc and find yourself confused about what level it's on, ask: *which face of project shape is this describing?* Usually that resolves it.

## The questions Tapestry exists to answer

State questions ("what is the project right now?") are secondary. Tapestry is built around trajectory questions — all of them ultimately about *interfaces*, with shape as the evidence:

- How is this project's shape changing — and which user-agent interfaces is that change affecting?
- What's drifting — and which interface is becoming misaligned with operator intent?
- What's stabilizing — and which interface is about to earn durable structure?
- What pattern is forming that hasn't been named yet — at which coordination surface?
- What recurring friction wants to become a skill — and which interface generates that friction?
- What's about to need new structure — to support which interface?
- Which projects in the fleet have similar shape — and therefore expose similar interfaces that can share intelligence?

If you find yourself building or documenting something that doesn't help answer one of those questions, it's probably orthogonal to Tapestry's actual purpose.

## Related

- [User-agent interface](/start/user-agent-interface/) — the primary object; shape is the substrate it lives on
- [What Tapestry is not](/start/what-tapestry-is-not/) — anchoring against false analogies (LangSmith, Grafana, AgentOps)
- [The observer](/explanation/the-observer/) — the component that watches shape change as evidence of interface change
- [How the platform upskills itself](/explanation/upskilling/) — the feedback loop from shape change to durable structure
- [Sharing intelligence across projects](/explanation/sharing-intelligence-across-projects/) — shape signals compounding across the fleet
