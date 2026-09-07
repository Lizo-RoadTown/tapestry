---
title: Set up a new project
description: Step-by-step checklist to wire a new project so the agent in it gets the full discipline stack from day one.
---

This is the procedural how-to for setting up a new project that plugs into the Tapestry platform. Follow it top to bottom in a fresh repo and you'll have the full discipline stack wired correctly from day one.

For the concepts behind these steps, read [The discipline stack](/explanation/discipline-stack/) first. For recovery from failures, see [Recover from common failures](/how-to/recover-from-common-failures/).

> **Shortcut:** `tapestry onboard --slug <your-project-id> --registry-url <url>` performs the steps below in one command — it registers the project and writes `.env`, `.mcp.json`, `.project-intelligence/`, `.claude/settings.json`, and a starter `CLAUDE.md`. This page is the manual walkthrough: useful to understand what onboarding does, or to wire a project by hand.

## Prerequisites

- Claude Code installed and working.
- `node` available (for plugin marketplace install).
- The `tapestry` marketplace added to your Claude Code: `/plugin marketplace add Lizo-RoadTown/tapestry`. Confirm by running `/plugin marketplace list`. (Both `tapestry-discipline` and `tapestry-patterns` ship from this one marketplace.)

## Step 1 — Pick a stable project ID

The project ID becomes the `LOOM_PROJECT_ID` env var (the registry-assigned id when you use `tapestry init`) and the tag on every memory you write.

Conventions:

- kebab-case
- Append `-dev` if you anticipate spawning an `-app` instance later (a separate Claude Code agent for a deployed user-facing surface). One existing example consuming project uses this pattern: a `-dev` ID for the research/developer-facing instance and a planned `-app` ID for the eventual user-facing app.
- Single-instance projects don't need the suffix.

Examples: `example-project-dev`, `summer-2026-hub`, `your-project-dev`.

## Step 2 — Install the `tapestry-discipline` plugin

In any Claude Code session:

```
/plugin marketplace add Lizo-RoadTown/tapestry
/plugin install tapestry-discipline@tapestry
```

This installs to your machine's plugin cache at `~/.claude/plugins/cache/tapestry/tapestry-discipline/<version>/`. It is now AVAILABLE on your machine. It is NOT YET enabled in any specific project.

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
    "your-guard@your-marketplace": true
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
      "url": "https://your-memory-host.example.com/mcp/memory/",
      "headers": {
        "Authorization": "Bearer ${TAPESTRY_MEMORY_API_KEY}"
      }
    }
  }
}
```

The `Authorization` header is required — the memory server returns 401 without it. Set `TAPESTRY_MEMORY_API_KEY` in your environment; the `${...}` ref reads it. If you have other MCP servers (Supabase, Render, project-specific ones), declare them alongside `loom-memory`.

`.mcp.json` is typically gitignored if it contains secrets (e.g., API tokens in headers). If it only contains URLs, it can be committed.

## Step 5 — Set `LOOM_PROJECT_ID` in `.env`

Create `.env` at your project root with at minimum:

```
LOOM_PROJECT_ID=your-project-id
```

If you want OTel telemetry to flow to the same Grafana stack as the other projects on this platform, copy the OTel block from an existing project's `.env` (the platform operator can share these). Same applies for `OPENAI_API_KEY` and any other shared credentials.

`.env` MUST be in `.gitignore`. Confirm before any commit.

## Step 6 — Create `.project-intelligence/`

This directory holds the per-project agent configuration, written **flat** — no per-project-id subdirectory (that's what `tapestry init` produces). Minimal v1 structure:

```
.project-intelligence/
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

For working examples of these JSON configs, see an example consuming project's `.project-intelligence/` directory on GitHub.

## Step 7 — Architecture snapshots (nothing to add)

The `tapestry-discipline` plugin's SessionStart hook captures a structural snapshot at session start by running the **canonical** snapshot script from the `tapestry-patterns` plugin (resolved from the plugin and run with `--repo-root`). You do **not** need to add any per-repo snapshot script. Installing `tapestry-patterns` is the only requirement — if that plugin isn't installed, the hook logs `patterns_scripts_unresolved` and skips the snapshot; the agent otherwise works.

## Step 8 — Write a `CLAUDE.md` at the project root

This is the per-project context Claude Code auto-loads. It should explain:

- What this project IS (one paragraph).
- Who the agent IS in this project (researcher / developer / operator).
- Memory hierarchy (point at the loom-memory MCP).
- Where to read (skills, docs, .project-intelligence).
- Discipline rules (restate the ones the plugin enforces, for clarity).
- Token discipline conventions.
- Tone.

See an example consuming project's `CLAUDE.md` for a worked example.

## Step 9 — Register with the Project Registry

The Tapestry platform includes a Project Registry service that tracks every consuming project, so cross-project queries (which projects use skill X? which opted into observability lane Y?) can find yours.

The `tapestry` CLI ships today: `tapestry init --slug <your-project-id> --registry-url <url>` — or `tapestry onboard`, which wraps it — **registers the project and performs Steps 3–8 in one command.** Registration is mandatory: `init` aborts and writes nothing if it can't reach a registry, so pass `--registry-url` or set `TAPESTRY_REGISTRY_URL`. To register by hand instead, `POST` your project to `<registry-url>/projects`.

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
- You don't need any architecture-snapshot scripts in your repo — the SessionStart hook runs the canonical script from the `tapestry-patterns` plugin directly.

The point of the platform is that the heavy infrastructure is deployed once — your own backend — and consuming projects get the benefits with a small wiring layer per project.
