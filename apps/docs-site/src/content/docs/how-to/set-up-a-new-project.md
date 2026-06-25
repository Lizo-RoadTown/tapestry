---
title: Set up a new project
description: Step-by-step checklist to wire a new project so the agent in it gets the full discipline stack from day one.
---

This is the procedural how-to for setting up a new project that plugs into the Tapestry platform. Follow it top to bottom in a fresh repo and you'll have the full discipline stack wired correctly from day one.

For the concepts behind these steps, read [The discipline stack](/explanation/discipline-stack/) first. For recovery from failures, see [Recover from common failures](/how-to/recover-from-common-failures/).

## Prerequisites

- Claude Code installed and working.
- `node` available (for plugin marketplace install).
- The `tapestry` marketplace added to your Claude Code: `/plugin marketplace add Lizo-RoadTown/tapestry`. Confirm by running `/plugin marketplace list`.
- (Optional, recommended) `tapestry` marketplace too, if you'll use the patterns plugin: `/plugin marketplace add Lizo-RoadTown/tapestry`.

## Step 1 — Pick a stable project ID

The project ID becomes the `LOOM_PROJECT_ID` env var, the directory name under `.project-intelligence/`, and the tag on every memory you write.

Conventions:

- kebab-case
- Append `-dev` if you anticipate spawning an `-app` instance later (a separate Claude Code agent for a deployed user-facing surface). One existing example consuming project uses this pattern: a `-dev` ID for the research/developer-facing instance and a planned `-app` ID for the eventual user-facing app.
- Single-instance projects don't need the suffix.

Examples: `sde-extraction-dev`, `summer-2026-hub`, `your-project-dev`.

## Step 2 — Install the `tapestry-discipline` plugin

In any Claude Code session:

```
/plugin marketplace add Lizo-RoadTown/tapestry
/plugin install tapestry-discipline@tapestry
```

This installs to your machine's plugin cache at `~/.claude/plugins/cache/tapestry/tapestry-discipline/<version>/`. It is now AVAILABLE on your machine. It is NOT YET enabled in any specific project. The prior `loom-discipline@lizo-loom` install command still works during the transition.

## Step 3 — Enable the plugin in your project's `.claude/settings.json`

Create `.claude/` directory in your project root if it doesn't exist. Then write `.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "tapestry-discipline@tapestry": true
  }
}
```

If you have a per-project guard plugin you also want enabled (e.g., a SDE-style guard), add it alongside:

```json
{
  "enabledPlugins": {
    "tapestry-discipline@tapestry": true,
    "your-guard@lizo-skills": true
  }
}
```

`.claude/settings.json` is shared (commit it). `.claude/settings.local.json` is local-only (gitignored by default in most setups).

## Step 4 — (Optional) Add `loom-memory` MCP to `.mcp.json` as defense-in-depth

The `tapestry-discipline` plugin already declares the `loom-memory` MCP, so enabling the plugin is sufficient to wire it. Adding it explicitly to your project's `.mcp.json` is belt-and-suspenders. If the plugin ever fails to load (cache staleness, version mismatch), the MCP tools remain available.

Create or extend `.mcp.json` at your project root:

```json
{
  "mcpServers": {
    "loom-memory": {
      "type": "http",
      "url": "https://your-memory-host.example.com/mcp/memory/"
    }
  }
}
```

If you have other MCP servers (Supabase, Render, project-specific ones), declare them alongside `loom-memory`.

`.mcp.json` is typically gitignored if it contains secrets (e.g., API tokens in headers). If it only contains URLs, it can be committed.

## Step 5 — Set `LOOM_PROJECT_ID` in `.env`

Create `.env` at your project root with at minimum:

```
LOOM_PROJECT_ID=your-project-id
```

If you want OTel telemetry to flow to the same Grafana stack as the other projects on this platform, copy the OTel block from an existing project's `.env` (the platform operator can share these). Same applies for `OPENAI_API_KEY` and any other shared credentials.

`.env` MUST be in `.gitignore`. Confirm before any commit.

## Step 6 — Create `.project-intelligence/<project-id>/`

This directory holds the per-project agent configuration. Minimal v1 structure:

```
.project-intelligence/
  <project-id>/
    agent-profile.json
    project-context.json
    observatory-config.json
```

Templates:

**`agent-profile.json`**

```json
{
  "role": "researcher | developer | operator",
  "memory_tag": ["your-project-id"],
  "discipline_rules": [
    "PROBE before asserting",
    "Cite file:line for claims",
    "Save corrections as feedback memory immediately"
  ]
}
```

**`project-context.json`**

```json
{
  "project_id": "your-project-id",
  "purpose": "One sentence on what this project is.",
  "audience": "Who uses its outputs.",
  "stage": "research | building | maintaining"
}
```

**`observatory-config.json`**

```json
{
  "log_events": ["git_action", "memory_write", "skill_invocation"],
  "candidate_triggers": ["3+ similar task executions", "operator says 'we keep doing X'"]
}
```

For working examples of these JSON configs, see [an example consuming project's `.project-intelligence/` directory on GitHub](https://github.com/Lizo-RoadTown/sde-extraction/tree/main/.project-intelligence/sde-extraction-dev).

## Step 7 — Add architecture-snapshot wrappers (recommended)

The `tapestry-discipline` plugin's SessionStart hook can run `scripts/architecture_snapshot.py` and `scripts/architecture_diff.py` to capture a structural snapshot at session start. These don't need to be your code — they can be thin wrappers that dispatch to the canonical implementations in the `tapestry-patterns` plugin.

See [the wrapper-pattern reference (consuming project PR)](https://github.com/Lizo-RoadTown/sde-extraction/commit/2325e67) for the canonical example.

If you skip this step, the SessionStart hook silently no-ops on the snapshot piece — the agent loses the architecture context at session start but otherwise works.

## Step 8 — Write a `CLAUDE.md` at the project root

This is the per-project context Claude Code auto-loads. It should explain:

- What this project IS (one paragraph).
- Who the agent IS in this project (researcher / developer / operator).
- Memory hierarchy (point at the loom-memory MCP).
- Where to read (skills, docs, .project-intelligence).
- Discipline rules (restate the ones the plugin enforces, for clarity).
- Token discipline conventions.
- Tone.

See [an example consuming project's `CLAUDE.md`](https://github.com/Lizo-RoadTown/sde-extraction/blob/main/CLAUDE.md) for a worked example.

## Step 9 — Register with the Project Registry (when it's live)

The Tapestry platform includes a Project Registry service that tracks every consuming project. Registering means future cross-project queries (which projects are using skill X? which projects opted into observability lane Y?) can find your project.

The registry endpoint is `https://your-project-registry-host.example.com/projects` (currently hosted from the platform's beta repo; the URL will change when the service migrates into Tapestry — env-var overrides are wired so consuming projects won't have to chase the rename).

When the registry has its public CLI (`tapestry init`), one command will do all of this. Until then, a `curl POST` to register is the manual step. See the Tapestry MASTER_CHECKLIST for current status.

## Step 10 — Restart Claude Code and verify

Plugin hooks bind at session start. To pick up the new plugin enable + MCP wiring, you must **fully restart Claude Code** in this repo (close the IDE window for this project; reopen). `/plugin update` does NOT hot-swap hooks.

After restart, you should see:

1. A SessionStart auto-recall block at the start of the conversation, with relevant memories tagged for your project.
2. A discipline reminder line at the top of every one of your messages: `[loom-discipline] Discipline check: PROBE files before asserting (cite file:line). Distinguish dev-tooling from runtime ...`
3. `memory_recall`, `memory_write`, etc. available when you ask the agent to use them.
4. If you ask the agent "check loom memory for what we did last session in this project," it actually does it.

If any of these don't appear, see [Recover from common failures](/how-to/recover-from-common-failures/) — the symptom-to-fix table covers each one.

## What you DON'T need to do

- You don't need to clone the platform repos to build your project. Your project is a CONSUMER of the platform, not part of it.
- You don't need to write your own discipline plugin unless you need project-specific guards beyond the general discipline.
- You don't need to set up your own memory store. The hosted `loom-memory` MCP serves all consuming projects.
- You don't need to put architecture-snapshot CODE in your repo — just the thin wrapper scripts that dispatch to the canonical scripts in `tapestry-patterns`.

The point of the platform is that the heavy infrastructure is deployed once — your own backend — and consuming projects get the benefits with a small wiring layer per project.
