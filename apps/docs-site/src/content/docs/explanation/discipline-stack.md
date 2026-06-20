---
title: The discipline stack
description: Why each piece of the Tapestry discipline stack exists — what failure mode it prevents and what it looks like when it's working.
---

The discipline stack is four cooperating pieces. This page explains what each one IS, why it exists, and what work it does behind the scenes. If you understand WHY each piece is there, you won't accidentally remove it.

For a one-page overview, see [What keeps a project on track](/start/what-stays-on-track/). For the file-by-file breakdown, see [Load-bearing files](/reference/load-bearing-files/). To set up a new project, see [Set up a new project](/how-to/set-up-a-new-project/).

## 1. The `loom-discipline` plugin

**What it is:** a Claude Code plugin published in the `lizo-loom` marketplace. Installed once per machine; enabled per-project in `.claude/settings.json`. Cached locally at `~/.claude/plugins/cache/lizo-loom/loom-discipline/<version>/`.

**Why it exists:** Claude Code by default has no memory across sessions, no PROBE-discipline reminders, no dual-mode boundary checks, and no upskilling discipline. The plugin adds all of those as hooks that fire at specific lifecycle events.

**The four hooks it installs:**

| Hook | Fires when | What it does |
|---|---|---|
| `SessionStart` | A new Claude Code conversation begins | Calls the REST endpoint `/v1/recall` on the memory MCP, fetches the top-N most relevant memories for this project, and injects them as `additionalContext` in the conversation. The agent sees its own past learnings before the first user message. |
| `UserPromptSubmit` | Every time you send a message | Injects the PROBE-discipline reminder at the top of your message (cite file:line, distinguish dev-tooling from runtime, save corrections as feedback memory). |
| `PreToolUse` (Edit/Write/MultiEdit) | Before any file edit | Runs a boundary check that, when relevant, asks the agent to confirm the edit's dual-mode semantics (self-host vs hosted-multitenant for the platform services). |
| `Stop` | The agent finishes a turn | Checks whether a substantive-work threshold was crossed (git action, many tool calls, many turns) without producing an upskilling report. If so, surfaces a loud warning. |

**What you'd lose without it:** Every behavior on this page. Memory stops getting recalled. PROBE stops getting reminded. Boundary checks stop firing. The agent reverts to default Claude Code behavior.

**A subtle related fact:** the plugin also declares the `loom-memory` MCP server in its own `plugin.json`. So enabling the plugin AUTOMATICALLY wires the memory MCP — you don't strictly need to add it separately to `.mcp.json`. Adding it to `.mcp.json` anyway is a defensible defense-in-depth: if the plugin fails to load for any reason, the MCP tools are still available.

## 2. The `loom-memory` MCP server

**What it is:** an HTTP-transport Model Context Protocol server hosted at `https://loom-agent-context.onrender.com/mcp/memory/`. Exposes six tools: `memory_recall`, `memory_read`, `memory_write`, `memory_search`, `memory_list`, `memory_delete`.

**Why it exists:** Claude Code conversations are independent — each new session starts with zero context from prior sessions. The MCP server is the cross-session memory layer. When the agent learns something durable (a project decision, a friction-as-correction moment, a fact about the codebase), it writes a memory. When the next session starts, the auto-recall hook reads those memories back in.

**It is also a cross-agent channel.** Memories written by one agent are readable by another. The `loom-agent` (working in `the-loom`), the `Make_Skills` agent, the Tapestry-agent, and your SDE-style consuming-project agent can all read each other's memories (filtered by `project_tags`, but cross-project memories surface universally).

**What you'd lose without it:** No durable memory across sessions. Friction-as-memory writes have nowhere to go. Cross-agent coordination memos can't be ferried. The agent starts every session cold.

**Critical: CORE DIRECTIVE 1.** Because the memory MCP is the canonical store, the discipline plugin enforces a rule: if `memory_recall` or `memory_write` is unavailable, the agent must HALT and report. It does NOT silently fall back to "well, I'll do my best without memory." Memory unavailability is treated as a P0 application failure, not a degraded mode.

## 3. The plugin enable in `.claude/settings.json`

**What it is:** a one-line JSON entry in your project's `.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "loom-discipline@lizo-loom": true
  }
}
```

**Why it exists:** plugins are install-once-per-machine but enable-per-project. Claude Code does NOT auto-enable installed plugins in every project — that would be invasive. Each project explicitly opts in.

**What you'd lose without it:** the plugin is installed on your machine but does not load in this project. None of the hooks fire. No memory MCP gets declared. The agent behaves like a stock Claude Code session.

**The silent-failure shape:** if your `.claude/settings.json` enables a different plugin (such as a per-project guard plugin) but does NOT enable `loom-discipline`, the agent looks superficially configured. The other plugin's hooks fire and do their work. But the discipline stack as a whole is missing. The most likely tell is: the agent doesn't recall memory at session start and you don't see the PROBE-discipline reminder line at the top of your messages.

## 4. The `LOOM_PROJECT_ID` in `.env`

**What it is:** a single environment variable in your project's gitignored `.env` file:

```
LOOM_PROJECT_ID=your-project-id
```

For SDE_Extraction the value is `sde-extraction-dev`. For `the-loom` itself the agent uses no specific LOOM_PROJECT_ID (it IS the platform). For a new project, pick a stable identifier — kebab-case, append `-dev` if the project will eventually spawn an `-app` instance for a deployed user-facing surface.

**Why it exists:** the discipline plugin (v0.1.12+) honors `LOOM_PROJECT_ID` as a scope gate for hook activation. Without it, the plugin's hooks would either run everywhere (invasive) or use path-substring matching against the cwd (fragile — fails for fully-wired projects in unexpected paths). The env var is the explicit opt-in signal.

**It also tags every memory write.** When the agent calls `memory_write` from your project, the platform tags the memory with `project_tags=["your-project-id"]`. When the next session in your project calls `memory_recall`, the platform returns memories tagged for your project PLUS universal (untagged) cross-project memories. The tag is how the memory store stays organized as it grows.

**What you'd lose without it:** hooks may no-op because there's no project ID for the scope gate. Memory writes may be untagged or default-tagged, polluting other projects' memory namespaces.

## 5. The `.project-intelligence/<project-id>/` directory

**What it is:** a per-project directory at your repo root holding JSON files that describe what the agent IS in this project.

```
.project-intelligence/
  <project-id>/
    agent-profile.json       — role: researcher / developer / operator
    project-context.json     — what this project is about
    observatory-config.json  — what events to log, what triggers candidates
    workflow-candidates/     — local longitudinal state for skill candidates
    promotion-candidates/    — outbox for items the agent thinks should become durable structure
```

**Why it exists:** the discipline plugin is generic. The same plugin runs in `the-loom`, `Make_Skills`, SDE_Extraction, and your project. Each project has different responsibilities, audiences, and concerns. The `.project-intelligence/` directory tells the plugin what specialization to apply — what's a candidate-worthy event for THIS project, what role the agent plays, what counts as a "promotion" worth surfacing.

**What you'd lose without it:** the agent loses per-project specialization. It still has the discipline (PROBE, memory, hooks), but it doesn't know it's a researcher in a research project vs an operator in a platform project. The discipline becomes generic.

## What about other plugins?

You can run the `loom-discipline` plugin alongside per-project guard plugins. SDE_Extraction does exactly this — its `.claude/settings.json` enables both `loom-discipline@lizo-loom` AND `sde-extraction-guard@lizo-skills`. The two plugins solve different problems:

- `loom-discipline` provides the general discipline stack (PROBE, memory, dual-mode, upskilling).
- `sde-extraction-guard` provides project-specific guards (a framing-clarification gate, a schema-correctness check on edits to the extraction surface).

The two are designed to coexist. Per the `sde-extraction-guard` plugin description: "Complements loom-discipline." If you create a new project that needs project-specific guards, build a similar guard plugin AND keep `loom-discipline` enabled. Do not replace one with the other.

## What about the architecture-snapshot scripts?

The `loom-discipline` plugin's `SessionStart` hook also looks for `scripts/architecture_snapshot.py` and `scripts/architecture_diff.py` in your repo. If they exist, the hook runs them to produce a structural snapshot of the repo and a diff against the prior baseline, then includes the narrative in the session-start context.

If those scripts are missing, the hook silently no-ops (it logs the absence but doesn't error). You don't get the architecture context at session start.

For consuming projects, the recommended approach is to add thin wrapper scripts under `scripts/` that dispatch to the canonical implementations in the `liz-patterns` plugin. See SDE_Extraction's PR #1 (commit 2325e67) for the pattern.

## The shape of the whole discipline

Every piece is small. A single JSON line. A single env var. A single directory of JSON configs. A handful of hook scripts. The discipline emerges from the COMBINATION — no one piece is heavy, but every piece is load-bearing.

Removing one piece doesn't crash the agent. It just removes one behavior the agent would otherwise have. And because Claude Code itself has no idea any of these behaviors were supposed to exist, the absence is silent. You only notice when you compare the agent in this project to the agent in a project that has the full stack — and even then, only if you know what you're looking for.

That's what this docs site exists to make legible.
