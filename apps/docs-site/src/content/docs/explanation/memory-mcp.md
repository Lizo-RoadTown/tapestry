---
title: The memory MCP and your project's memory
description: What the loom-memory MCP is, what gets stored in it, how the memory for your project stays scoped and organized, and what you can do as the operator to keep it healthy.
---

The loom-memory [MCP](/explanation/shared-language/#mcp-model-context-protocol) is the cross-session, cross-agent memory store for everything on the Tapestry platform. Every Tapestry-consuming project shares one hosted instance; each project gets its own slice via the `project_tags` scoping mechanism.

This page explains what's stored there, how it gets organized, what behavior you should see from the agent when memory is wired correctly, and what you can do to keep your project's memory clean over time.

For how the MCP gets wired into your project, see [The plugins](/explanation/plugins/) and [Set up a new project](/how-to/set-up-a-new-project/).

## What the MCP is

`loom-memory` is an HTTP-transport MCP server hosted at:

```
https://your-memory-host.example.com/mcp/memory/
```

It runs as a Render web service backed by Postgres + [pgvector](/explanation/shared-language/#pgvector-and-embeddings). The Postgres rows ARE the memories. The pgvector index enables semantic search via embeddings of memory content.

It is not one-MCP-per-project — every project shares the same hosted MCP instance, and the project scoping happens at the row level via `project_tags`.

It also serves as a **cross-agent channel**. A memory written by the agent in your project is readable by agents working in other projects that share the same memory store. When those other agents write memos tagged for cross-project context, the agent in your project reads them at the next session start. This is how decisions and learnings made in one project become available to agents elsewhere.

## What ends up in memory

Six categories of content accumulate over time. You don't author these directly — the agent writes them in response to specific events. Your role is to recognize what each type is when you see it surfaced at session start, and to flag the agent when something durable should be saved.

| Type | What goes here | Triggered by |
|---|---|---|
| decision | An architectural or design choice and the reasons it was made. | A non-obvious decision the agent makes (or you make and the agent records). |
| fact | Stable information about the project (e.g., the project's Supabase URL). | The agent learns something durable about the codebase or infrastructure. |
| feedback | A correction you gave the agent. This is the highest-leverage memory type — it is how the agent gets sharper over time. | You correct the agent. The discipline plugin enforces immediate save. |
| lesson | A pattern that worked or an anti-pattern that didn't, learned by doing the work. | A session produces a generalizable learning. |
| project | The current state of the project — what landed, what's pending, who owns what. | A significant deliverable lands, or the session's understanding of project state shifts. |
| preference | An operator preference about style, tone, format, or process. Lighter than a feedback correction. | You express a preference. |
| reference | A pointer to something durable elsewhere (a doc URL, a commit SHA, a runbook). | The agent encounters an external resource worth bookmarking. |
| skill_idea | An emerging pattern worth becoming a reusable skill someday. | The upskilling audit surfaces a candidate. |
| topic | A topic placeholder that will be expanded later. | A subject comes up that warrants future exploration. |
| user | Information about you — your role, preferences, context. | The agent learns something durable about you. |

The most common in practice are `feedback`, `lesson`, `project`, and `decision`.

## How project_tags scope memory

Every memory row has an optional `project_tags` array that determines who sees it on recall.

- A memory tagged `["your-project-id"]` is scoped to a single project. It surfaces when the agent in that project calls memory recall, but not in other projects' sessions.
- A memory tagged `["project-a", "project-b"]` is dual-scoped — both projects see it. Useful for decisions or coordination memos that affect multiple projects.
- A memory with NO tags (empty or omitted) is **universal**. It surfaces in every project's recall. This scope is reserved for discipline rules that apply to all projects, not for project-specific notes.

The discipline plugin handles the tagging automatically. It reads `LOOM_PROJECT_ID` from your `.env` and applies that as the tag on any memory the agent writes during sessions in your project. If `LOOM_PROJECT_ID` is wrong or missing, memory writes land in the wrong scope — your project either pollutes other projects' memory or loses its own at next session.

## What the agent does with memory (so you know what to expect)

When the discipline stack is wired correctly, the agent's behavior around memory follows a predictable pattern:

**At the start of every session:** the SessionStart hook calls the platform's `/v1/recall` REST endpoint with the project's tag and fetches the top-N most relevant memories. These appear as `additionalContext` in the conversation before your first message. You see this as a block of accumulated context at the top of the chat — past decisions, prior feedback, current project state.

**During a substantive task:** the agent recalls memory explicitly when it judges the task is large enough to warrant the lookup. You can also tell it to: "check loom memory for what we did last session on this" is the canonical phrasing.

**When you correct the agent:** the discipline plugin's per-turn reminder enforces immediate save as a feedback memory, at the moment of correction, not deferred to end-of-session. You should see the agent acknowledge the correction AND write a memory before continuing the task.

**When a deliverable lands:** the agent writes a project memory snapshotting state. You should see this happen alongside the deliverable — a commit, a finished doc, a deployed service.

**Before answering questions about the codebase:** the agent should PROBE the actual files (grep / read) AND check memory. Memory tells what was true at a point in time; the files tell what's true now. If the agent cites memory without checking the code, that's drift — flag it.

## How to inspect memory directly

The MCP exposes a REST surface (commit `9262943`) so you can read, write, and recall without going through an agent session. Useful when you want to audit what's actually in storage.

Recall the top relevant memories for a context:

```sh
curl -X POST https://your-memory-host.example.com/v1/recall \
  -H "Content-Type: application/json" \
  -d '{"context": "what was decided about X", "n": 5, "project_tags": ["your-project-id"]}'
```

Read one memory by exact name:

```sh
curl -X POST https://your-memory-host.example.com/v1/read \
  -H "Content-Type: application/json" \
  -d '{"name": "exact_memory_name"}'
```

Write a memory directly (rarely needed — the agent usually does this for you, but useful for seeding or backfilling):

```sh
curl -X POST https://your-memory-host.example.com/v1/write \
  -H "Content-Type: application/json" \
  -d '{"name": "...", "record_type": "fact", "content": "...", "project_tags": ["your-project-id"]}'
```

In [self-host mode](/explanation/shared-language/#self-host-vs-hosted) (no Authorization header), the tenant resolves to a deterministic UUID — every consuming project lands in one tenant envelope. In hosted-multitenant mode, a Bearer JWT is required; the `tenant_id` claim drives row-level scoping.

## How to keep your project's memory healthy

Memory grows. After a few months of active work, a project may have hundreds of memories. Without maintenance, recall becomes noisy and the value compounds less.

**The lifecycles to be aware of:**

- `project` memories supersede each other. Each new session-state snapshot makes the prior one history. They aren't deleted (still useful for audit) but the most recent is canonical. You should see new `session_state_<date>` memories appear over time, with the older ones still readable for context.
- `feedback` memories accumulate. Each correction adds a binding rule the agent will operate under going forward. The set grows; nothing supersedes. The agent's discipline gets richer over time.
- `decision` memories don't get edited in place. When a decision is overturned, a NEW decision memory is written with `v2` or a similar marker, referencing the prior. Editing in place would destroy the audit trail.

**Things to do every few months:**

1. **Spot-check what's in scope.** Ask the agent: "list the most recent 20 memories tagged for this project." Read through. Anything obviously wrong? Anything superseded but the new version isn't linked?
2. **Search for outdated facts.** If a Render URL, an API key reference, or a service name changed, memories that still reference the old value will mislead future sessions. Flag them and ask the agent to write superseding memories.
3. **Look for unconnected memories.** Memories without cross-references or with broken `[[link]]` markers don't surface in recall as clusters. The agent can strengthen the linking on request.
4. **Spot-check names.** Memories named `notes` or `update_3` aren't findable. Renaming = write-with-new-name + delete-old. The agent can do this batch.

**What not to do:**

- Don't bulk-delete memories to "clean up." Most of what looks like clutter is actually audit history. Better to ask the agent to write a new `project_state_<date>` memory that supersedes a cluster of older ones — the older ones become history; the new one is canonical.
- Don't edit a memory directly to "correct" it (via the REST surface). Write a new one and mark the old as superseded. The audit trail is part of the value.

## What goes wrong when memory isn't maintained per project

| Failure mode | Symptom you'd see |
|---|---|
| `LOOM_PROJECT_ID` wrong | Memories tag for the wrong project. Recall at session start surfaces memories from a different project's context, which feels off but isn't immediately obvious. |
| `LOOM_PROJECT_ID` unset | Memories may be untagged. Universal recall pulls them everywhere — your project's specifics start polluting other projects' contexts. |
| Memories never written | The agent doesn't seem to remember anything across sessions. Each conversation starts cold. Corrections you gave last week aren't reflected this week. |
| Memories written but never recalled | The data is in storage but the agent isn't pulling it into context. Usually this is a SessionStart hook failure — see [Recover from common failures](/how-to/recover-from-common-failures/). |
| Memories with generic names | Recall finds them but they collide with similarly-named memories from other contexts. The agent can't tell them apart. |
| Memories contradicting current code | The agent cites a memory as fact when the code has changed. Flag immediately — this is drift; the agent should be PROBE-ing the code, not trusting memory blindly. |

## CORE DIRECTIVE 1: memory unavailability is a P0

If the memory MCP is unreachable — because the hosted service is down, your `.mcp.json` isn't wiring it, the plugin isn't enabled, or the network is failing — the discipline rule (enforced by the plugin's hooks) is for the agent to HALT and report rather than continue without memory. The platform's primary value proposition is cross-session memory; treating its absence as a degraded mode that's silently accepted would erode that value.

You should expect to see the agent loudly surface MCP unavailability rather than quietly working around it. If a session is going on without memory and the agent isn't flagging it, that's itself a discipline failure worth correcting.

## Related

- [Shared language](/explanation/shared-language/) — the eight words the memory pages use, defined once
- [Why the memory is built this way](/explanation/why-memory-is-built-this-way/) — the reasons behind the shape: why one table, why recall stays cheap, how user/project/machine scope differ, and why the observer's schedule shares the same service
- [The discipline stack](/explanation/discipline-stack/) — how the MCP fits with the plugins, the observer, and the recursive miscommunication-becomes-architecture loop
- [The plugins](/explanation/plugins/) — `tapestry-discipline` is what wires the MCP into your project
- [The observer](/explanation/the-observer/) — how patterns in your session activity become candidates that compound across sessions
- [Set up a new project](/how-to/set-up-a-new-project/) — get the MCP wired into a new repo
- [Recover from common failures](/how-to/recover-from-common-failures/) — when the agent stops checking memory
- [Load-bearing files](/reference/load-bearing-files/) — file-by-file reference of the MCP wiring
