---
title: Project shape
description: The structural conditions a project creates for user/agent coordination. Different projects expose different interfaces, memory requirements, architectural constraints, friction patterns, and learning opportunities. Tapestry tracks project shape because shape influences the effectiveness of the coordination Tapestry exists to reinforce.
---

Projects are environments where coordination occurs. Different projects create different conditions for the user/agent coordination Tapestry reinforces. Project shape is the observable structure of those conditions over time.

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

## Why Tapestry tracks shape

Project shape is one of several things Tapestry tracks to understand the coordination it's reinforcing. Different shape produces different coordination conditions:

- A project that's all one repo with one agent has different coordination conditions than a project with five services and three subagents handing off context.
- A project whose memory entries are stable produces different coordination conditions than one where the operator is constantly correcting prior memos.
- A project whose architecture is in flux produces different coordination conditions than one that's settled.

Shape change is one of the strongest signals about coordination change. When a project's shape shifts, the coordination patterns inside it usually shift too — interfaces emerge or disappear, memory attachment points move, friction patterns change.

Other Tapestry concepts describe other faces of the same picture:

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

State questions ("what is the project right now?") are secondary. Tapestry is built around trajectory questions — all of them ultimately about the **quality and direction of user/agent coordination**, with shape as one of the strongest signals:

- How is this project's shape changing — and how is that changing the conditions for coordination?
- What's drifting — and where is coordination becoming misaligned with operator intent?
- What's stabilizing — and what coordination pattern is about to earn durable structure?
- What pattern is forming that hasn't been named yet?
- What recurring friction wants to become a skill — i.e., what coordination pattern recurs enough to deserve codification?
- What's about to need new structure — to support what coordination?
- Which projects in the fleet have similar shape — and therefore similar coordination conditions to share reinforcement signals between?

If you find yourself building or documenting something that doesn't help answer one of those questions, it's probably orthogonal to Tapestry's actual purpose.

## Related

- [Canonical statement](/) — Tapestry as a user/agent support and reinforcement system; shape is one of the conditions it tracks
- [User-agent interfaces](/start/user-agent-interface/) — one observable manifestation of coordination that emerges differently under different shape
- [What Tapestry is not](/start/what-tapestry-is-not/) — anchoring against false analogies (LangSmith, Grafana, AgentOps)
- [The observer](/explanation/the-observer/) — the component that watches shape change as one of several coordination signals
- [How the platform upskills itself](/explanation/upskilling/) — the feedback loop from coordination patterns to durable structure
- [Sharing intelligence across projects](/explanation/sharing-intelligence-across-projects/) — coordination signals compounding across the fleet
