---
title: Create your own plugin
description: Tapestry ships one universal discipline plugin. When a project's shape needs more — project-specific guards, or your own memory/observer/telemetry backend — generate your own personalized plugin pointed at your own deployment and publish it to your own marketplace.
---

Tapestry ships **one universal plugin**, `tapestry-discipline`. It works for everyone with no backend: PROBE-first reminders, citation enforcement, dev-vs-runtime audit. Those hooks make no network calls.

When a project's *shape* calls for more — guards specific to this project, or wiring to **your own** memory / registry / telemetry backend — you create **your own** plugin. It points at **your** deployment and lives in **your** marketplace. This page shows how.

## Two layers

| Layer | What it is | Where it lives |
|---|---|---|
| **Universal** (`tapestry-discipline`) | Behavior only — PROBE, citation, audit. No backend. | The `tapestry` marketplace. Install once per machine. |
| **Personalized** (yours) | Project-specific guards + your own backend endpoints. | A repo + marketplace under **your** GitHub account. |

The personalized plugin *adds* to the universal one; it doesn't replace it.

## Generate it

Install the CLI if you haven't (`pipx install tapestry-cli`), then:

```bash
tapestry make-plugin my-project-guard
```

This scaffolds a self-contained plugin + single-plugin marketplace:

- `.claude-plugin/plugin.json` — the memory URL is `${LOOM_MEMORY_MCP_URL:-https://your-memory-host.example.com/mcp/memory/}`, so it reads **your** endpoint from the environment and falls back to a placeholder (never anyone else's deployment).
- `.claude-plugin/marketplace.json` — you are the owner.
- `hooks/hooks.json` + `hooks/run-python.mjs` — the hook wiring.
- `scripts/pre_tool_use.py` — a behavior-only guard stub to customize.
- `README.md` — test + publish steps.

## Customize it

Edit `scripts/pre_tool_use.py` with the guards this project actually needs (warn on edits to load-bearing files, require a test alongside a source change, block edits to a generated directory, etc.). Keep guards **behavior-only** where you can — those work for anyone with no backend.

To wire memory, point the plugin at your own deployment:

```bash
export LOOM_MEMORY_MCP_URL=https://<your-memory-host>/mcp/memory/
```

## Publish it to your own marketplace

```bash
gh repo create <your-github>/my-project-guard --public --source ./my-project-guard --push
```

Then in Claude Code:

```text
/plugin marketplace add <your-github>/my-project-guard
/plugin install my-project-guard@my-project-guard
```

## Let an agent do it

The **`plugin-authoring`** skill (in the `tapestry-patterns` plugin) drives the whole flow — it probes the project's shape, scaffolds, customizes the guards, tests, and publishes. Ask your agent to *"make a plugin for this project"* and it follows the skill end to end.

## The rules every plugin follows

- **Endpoints from your env, never hardcoded.** Use `${VAR:-placeholder}` in config and read the env in scripts. Never bake another deployment's URL, service name, or tenant id into a plugin.
- **Degrade cleanly with no backend.** The behavior hooks always work; the backend features (memory, registry, telemetry) skip cleanly when nothing is configured — no timeouts, no errors.
- **No personal identifiers** in a shipped plugin. The author is you; everything else is generic or env-driven.
- **Hooks are best-effort.** A hook never raises and never blocks the session on a network failure.
