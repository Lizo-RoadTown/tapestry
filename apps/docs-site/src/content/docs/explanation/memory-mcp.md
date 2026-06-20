---
title: The memory MCP and your project's memory
description: What the loom-memory MCP is, the six tools it exposes, how project_tags scope memory per project, and how to maintain your project's memory over time.
---

The `loom-memory` MCP is the canonical cross-session, cross-agent memory store for everything in the Tapestry platform. Every Tapestry-consuming project shares ONE hosted instance of it. Your project gets its own slice of that store via the `project_tags` scoping mechanism.

This page explains what the MCP is, what tools it exposes, how memory scoping works, and how to maintain your project's memory so it stays useful (not bloated, not stale, not silently wrong).

For how the MCP gets wired into your project, see [The plugins](/explanation/plugins/) and [Set up a new project](/how-to/set-up-a-new-project/).

## What the MCP is

`loom-memory` is an HTTP-transport MCP server hosted at:

```
https://loom-agent-context.onrender.com/mcp/memory/
```

It runs as a Render web service backed by Postgres + pgvector. The Postgres rows ARE the memories. The pgvector index enables semantic search via embeddings of memory content.

It's the platform's canonical memory layer. It's NOT one-MCP-per-project — every project shares the same hosted MCP instance, and the project scoping happens at the row level via `project_tags`.

It's also a **cross-agent channel**. When you write a memory from your project, the loom-agent (working in `the-loom`) and the Make_Skills agent and the Tapestry-agent can all read it via universal recall. When they write memos tagged for cross-project context, your project's agent reads them at the next session start.

## The six tools

| Tool | Purpose |
|---|---|
| `memory_recall(context, n=5, project_tags?)` | Semantic search returning top-N memories most relevant to the given context. Default scope: all of your memories cross-project. Scope to a specific project via `project_tags`. **This is what fires automatically at SessionStart.** |
| `memory_read(name)` | Fetch one memory by exact name. Returns the full body. |
| `memory_write(name, record_type, content, project_tags?, why?, actor?)` | Upsert a memory row. If a memory with the same `name` exists, it's replaced. |
| `memory_search(query, ...)` | Lexical search across memory content. Use when you know roughly what to grep for. |
| `memory_list(record_type?)` | Index entries (names only, no bodies) for browsing what exists. |
| `memory_delete(name)` | Hard delete by name. Use sparingly — most "deletion" should be replacing content with a "this is wrong, see X" pointer. |

The agent calls these via the MCP HTTP transport at session-relevant moments. You can also call them by asking the agent: "memory_recall for X", "memory_write that down as a feedback memory", etc.

## How project_tags scope memory

Every memory row has an optional `project_tags` array. The platform uses this for the recall scoping logic:

- A memory with `project_tags: ["sde-extraction-dev"]` is a SDE-Extraction-scoped memory. It surfaces when the SDE agent calls `memory_recall` with no filter (cross-project default) OR explicitly with `project_tags=["sde-extraction-dev"]`.
- A memory with `project_tags: ["the-loom", "tapestry"]` is dual-scoped. It surfaces for the loom-agent and the Tapestry-agent.
- A memory with NO `project_tags` (empty array or omitted) is **universal** — it surfaces in EVERY project's recall. Use sparingly; this is the right scope for discipline rules that apply to all projects (e.g., the PROBE rule itself).

When you set up your project, you decide what `LOOM_PROJECT_ID` to use. From then on, every memory you write should be tagged with that project ID UNLESS the memory is genuinely universal (then no tags) or genuinely cross-project (then multiple tags listing each).

The discipline plugin handles the tagging automatically when the agent calls `memory_write` — it reads `LOOM_PROJECT_ID` from `.env` and applies the tag.

## What memories to write

The platform has six record types. Each has a slightly different shape and recall behavior:

| Type | When to use |
|---|---|
| `decision` | An architectural or design choice was made and the reasons matter. Capture immediately when the choice is made, not later. |
| `fact` | Stable information you'll want to recall later (e.g., "the project's Supabase URL is X"). Different from a decision because it's not a choice, just a true statement. |
| `feedback` | The operator corrected you. Capture IMMEDIATELY at the moment of correction. This is the highest-leverage memory type — it's how the agent gets sharper over time. |
| `lesson` | You learned something from doing the work. Pattern that worked, anti-pattern that didn't. |
| `project` | Current state of the project — what landed, what's pending, who owns what. Often supersedes prior project memories of the same name. |
| `preference` | Operator preference about style, tone, format, or process. Lighter than a `feedback` correction. |
| `reference` | A pointer to something durable elsewhere (a doc URL, a commit SHA, a runbook). |
| `skill_idea` | An emerging pattern worth becoming a skill someday. Surfaced by the upskilling audit. |
| `topic` | A topic placeholder you'll later expand. |
| `user` | Information about the operator themself (preferences, role, context). |

The most common and important types in practice: `feedback` (when corrected), `lesson` (when you learn), `project` (current state snapshots), `decision` (architectural choices).

## When to write a memory

**Always:**

- The operator corrects you on something. Save a `feedback` memory IMMEDIATELY, before continuing the task. Defer-until-end-of-session = lose the moment, get vague memory.
- A significant deliverable lands (a PR, a deployed service, a finished docs site). Save a `project` memory snapshotting the current state.
- An architectural decision is made (use X library, deploy to Y, structure data as Z). Save a `decision` memory with the WHY at the moment the choice is made.
- You learned a pattern through doing the work. Save a `lesson` memory.

**Sometimes:**

- You PROBE'd something and learned non-obvious information about the codebase that's worth recalling next session. `fact` memory.
- You noticed an emerging pattern that could become a reusable skill. `skill_idea` memory.

**Rarely or never:**

- Restating something that's already obvious from the code or docs. The memory exists for things that AREN'T in the code.
- Logging routine actions ("I ran the tests, they passed"). Memory is not a transcript.
- Anything that becomes stale quickly (current commit SHA, open browser tabs, what you're thinking about right now). Memory is for things with shelf life.

## When to recall

**Always at session start:** the discipline plugin's SessionStart hook does this automatically via `/v1/recall`. You don't have to call `memory_recall` manually — the top-N relevant memories appear in your conversation's initial context.

**At the start of a substantive task:** explicitly call `memory_recall(context="...")` with a description of what you're about to do. This pulls in past memories specific to the task.

**When the operator says "check memory":** they're saying "your context is missing something I know is in memory — go look." Always honor.

**When the operator references prior work you don't remember:** `memory_recall` before guessing.

**Before making claims about the codebase, plus PROBE the files.** Memory tells you what was true at a point in time; the files tell you what's true now. Both matter.

## Memory naming conventions

The name field is the primary key for `memory_read` and `memory_write`. Pick names that future-you (or another agent) can guess.

Good name shapes:

- `<type>_<topic>_<date>` for time-bound work: `feedback_consolidating_modules_check_per_service_deps_2026_06_19`
- `<type>_<topic>` for evergreen rules: `feedback_cite_files_not_memory`
- `<project>_state_<date>` for session snapshots: `session_state_2026_06_20_sde_diagnosis_fixes_and_tapestry_docs_site`
- `<agent>_<topic>_<date>` for cross-agent memos: `loom_agent_built_tapestry_docs_site_v1_2026_06_20`

Bad name shapes:

- Generic names that collide (`notes`, `decisions`, `memo`)
- Names without enough specificity to disambiguate (`fix`, `update`, `note_2026_06_20`)
- Names that include transient state (`current_branch_name`, `latest_pr_number`)

## How to maintain memory over time

Memory grows. After a few months of active work, a project may have hundreds of memories. Without maintenance, recall becomes noisy and the operator (or agent) starts ignoring it.

**The natural lifecycle:**

- **`project` memories supersede.** When a new `session_state_<date>` memory is written, prior session-state memories become history. They're not deleted (they're still useful for audit), but the most recent supersedes. The `Related` section at the bottom of the new memory points back at the prior one for trail.
- **`feedback` memories accumulate.** Each correction adds a binding rule. They don't supersede — they stack. The agent's discipline gets richer over time.
- **`decision` memories don't get edited.** When a decision is overturned, write a NEW decision memory (`decision_<topic>_v2_<date>`) that supersedes the prior. Reference the prior. Never edit a decision memory in place.

**Active maintenance tasks (do every few months):**

1. **Recall in your project's scope.** `memory_recall(context="recent state", project_tags=["your-project-id"], n=20)`. Read through the top 20. Anything that's clearly wrong now? Anything that's been superseded but the new version doesn't point at it?
2. **Search for outdated facts.** `memory_search(query="<old_render_url>")` — finds memories that reference a thing that no longer exists. Update or supersede.
3. **Look for unconnected memories.** Memories without a `Related` section, or with broken `[[reference]]` links. Strengthen the linking so recall surfaces clusters.
4. **Spot-check naming.** Memories with generic names (`notes`, `update_3`) won't be findable by future you. Rename via write-with-new-name + delete-old.

**Don't:**

- Don't bulk-delete memories to "clean up." Most "clutter" is actually history. Better to write a `project_state_<date>` memory that supersedes a cluster of old ones — the cluster becomes history; the new one is canonical.
- Don't edit a memory in place to "correct" it. Write a new one and mark the old as superseded. The audit trail matters.

## What goes wrong if memory isn't maintained per project

| Failure mode | Symptom |
|---|---|
| LOOM_PROJECT_ID is wrong | Memories tag for the wrong project. Cross-project recall surfaces the wrong memories at session start. |
| LOOM_PROJECT_ID is unset | Memories may be untagged. Universal recall surfaces them everywhere — pollutes other projects' contexts. |
| Memories never written | Each session starts cold. The agent re-learns the same things every time. Discipline doesn't compound. |
| Memories written but never recalled | The agent has the data but isn't checking. CLAUDE.md should remind it; the plugin's hooks should enforce it. |
| Memories written with generic names | Recall finds them but you can't tell them apart. Names like `update` and `notes` collide and become useless. |
| Memories that contradict the code | Memory says one thing; the code says another. Discipline rule: PROBE the code before trusting the memory. |

## How to access memory directly (no agent)

The MCP exposes a REST surface for non-MCP clients (added in commit `9262943`):

```sh
# Recall
curl -X POST https://loom-agent-context.onrender.com/v1/recall \
  -H "Content-Type: application/json" \
  -d '{"context": "what is X?", "n": 5, "project_tags": ["your-project-id"]}'

# Read one by name
curl -X POST https://loom-agent-context.onrender.com/v1/read \
  -H "Content-Type: application/json" \
  -d '{"name": "exact_memory_name"}'

# Write one
curl -X POST https://loom-agent-context.onrender.com/v1/write \
  -H "Content-Type: application/json" \
  -d '{"name": "...", "record_type": "fact", "content": "...", "project_tags": ["your-project-id"]}'
```

For self-host mode (no Authorization header), the tenant resolves to the deterministic UUID `1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8` — every consuming project lands in this single tenant envelope for the self-host deployment. For hosted-multitenant mode, a Bearer JWT is required; the `tenant_id` claim drives row-level scoping.

## CORE DIRECTIVE 1: memory unavailability is a P0

If `memory_recall` or `memory_write` is unavailable in the agent's session — because the MCP server is down, the agent's `.mcp.json` isn't wiring it, the plugin isn't enabled, or the network is failing — the discipline rule (enforced by the plugin's hooks) is to **HALT and report**. Do not silently fall back to "I'll do my best without memory." Memory unavailability is treated as a P0 application failure.

This is intentionally aggressive. The platform's primary value proposition is cross-session, cross-agent memory. Treating its absence as a degraded mode that's acceptable would erode that value silently.

## Related

- [The discipline stack](/explanation/discipline-stack/) — how MCP fits with plugins and per-project config
- [The plugins](/explanation/plugins/) — `loom-discipline` is what wires the MCP into your project
- [Set up a new project](/how-to/set-up-a-new-project/) — get the MCP wired into a new repo
- [Recover from common failures](/how-to/recover-from-common-failures/) — when MCP tools don't appear in your tool list
- [Load-bearing files](/reference/load-bearing-files/) — file-by-file reference of the MCP wiring
