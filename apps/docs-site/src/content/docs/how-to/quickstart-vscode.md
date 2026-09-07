---
title: Quickstart — VS Code
description: 4-step setup for a new Tapestry-consuming project in VS Code. Uses the Claude Code extension + the `tapestry onboard` CLI to bootstrap configuration in one command.
---

Get a new project wired into Tapestry in about 5 minutes.

## Prerequisites

- VS Code installed
- The [Claude Code extension](https://marketplace.visualstudio.com/items?itemName=Anthropic.claude-code) installed in VS Code
- `tapestry-cli` installed: `pip install tapestry-cli` (or run it from the tapestry monorepo via `python -m tapestry_cli`)

## 4 steps

**1. Open your project in VS Code.**

**2. In the Claude Code chat panel, register the marketplace + install both plugins:**

```text
/plugin marketplace add Lizo-RoadTown/tapestry
/plugin install tapestry-discipline@tapestry
/plugin install tapestry-patterns@tapestry
```

**3. In the integrated terminal (or any terminal at your project root):**

```sh
tapestry onboard --slug my-project-name --registry-url <your-project-registry-url>
```

`--slug` is required. This single command **registers the project with the Project Registry first** — this is mandatory: if no registry is reachable it aborts and writes nothing, and the default registry URL is a placeholder, so pass `--registry-url` (or set `TAPESTRY_REGISTRY_URL`). Then it writes:

- `.env` with `LOOM_PROJECT_ID` (the registry-assigned id) + the shared `OTEL_*` block
- `.mcp.json` declaring the `loom-memory` MCP server (with the `Bearer ${TAPESTRY_MEMORY_API_KEY}` header)
- `.project-intelligence/` (flat) with `agent-profile.json`, `project-context.json`, `observatory-config.json` (plus `local-skills/` + `lessons-learned/` subdirs)
- `.claude/settings.json` enabling both tapestry plugins
- a starter `CLAUDE.md` skeleton, `.gitignore`, and a `docs/` + `skills/` tree

**4. Reload VS Code:** `Cmd+Shift+P` → `Developer: Reload Window`.

## Verify it worked

Open the Claude Code chat panel and start a new session. You should see:

- An auto-recall block at the top of the conversation showing past memories tagged for this project (empty on first session — that's normal)
- A `[loom-discipline] Discipline check: PROBE files before asserting ...` line at the top of every one of your messages

If neither appears, see [Recover from common failures](/how-to/recover-from-common-failures/).

## What `tapestry onboard` does NOT do

- Install the Claude Code extension itself (do that from the VS Code marketplace)
- Run the plugin installs (those happen inside Claude Code chat — step 2 above)
- Reload VS Code (manual — step 4 above)
- Author your project-specific `CLAUDE.md` content (it seeds a starter skeleton — edit it to fit your project)
- Add per-repo snapshot scripts (not needed — the SessionStart hook runs the canonical snapshot script from the `tapestry-patterns` plugin)

For the comprehensive walkthrough including those items, see [Set up a new project](/how-to/set-up-a-new-project/).

## Notes

- **Runtime emission strings**: the discipline reminder you'll see in your chat says `[loom-discipline]` — that's the runtime label, distinct from the install name `tapestry-discipline`. Both are correct.
- **Re-running `tapestry onboard`**: idempotent. It merges into existing files rather than overwriting. Safe to re-run if you want to ensure the configuration is current.
- **Other IDEs**: per-IDE quickstart pages are coming. The underlying setup (run `tapestry onboard`, install the two plugins, reload) is the same across IDEs; what differs is how you reach the Claude Code chat panel + how you reload.
