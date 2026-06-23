---
title: Quickstart — VS Code
description: 4-step setup for a new Tapestry-consuming project in VS Code. Uses the Claude Code extension + the `loom onboard` CLI to bootstrap configuration in one command.
---

Get a new project wired into Tapestry in about 5 minutes.

## Prerequisites

- VS Code installed
- The [Claude Code extension](https://marketplace.visualstudio.com/items?itemName=Anthropic.claude-code) installed in VS Code
- `loom-cli` installed: `pip install loom-cli` (or run it from the tapestry monorepo via `python -m loom_cli`)

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
loom onboard my-project-name
```

This single command writes:

- `.env` with `LOOM_PROJECT_ID=my-project-name` + shared OTel + API-key blocks
- `.mcp.json` declaring the `loom-memory` MCP server
- `.project-intelligence/my-project-name/` with `agent-profile.json`, `project-context.json`, `observatory-config.json`
- `.claude/settings.json` enabling both tapestry plugins

It also registers the project with the Project Registry if it's reachable.

**4. Reload VS Code:** `Cmd+Shift+P` → `Developer: Reload Window`.

## Verify it worked

Open the Claude Code chat panel and start a new session. You should see:

- An auto-recall block at the top of the conversation showing past memories tagged for this project (empty on first session — that's normal)
- A `[loom-discipline] Discipline check: PROBE files before asserting ...` line at the top of every one of your messages

If neither appears, see [Recover from common failures](/how-to/recover-from-common-failures/).

## What `loom onboard` does NOT do

- Install the Claude Code extension itself (do that from the VS Code marketplace)
- Run the plugin installs (those happen inside Claude Code chat — step 2 above)
- Reload VS Code (manual — step 4 above)
- Write `CLAUDE.md` (recommended but project-specific; author it yourself)
- Add `scripts/architecture_snapshot.py` wrappers (optional; the SessionStart hook silently skips the snapshot if they're absent)

For the comprehensive walkthrough including those items, see [Set up a new project](/how-to/set-up-a-new-project/).

## Notes

- **Runtime emission strings**: the discipline reminder you'll see in your chat says `[loom-discipline]` — that's the runtime label, distinct from the install name `tapestry-discipline`. Both are correct.
- **Re-running `loom onboard`**: idempotent. It merges into existing files rather than overwriting. Safe to re-run if you want to ensure the configuration is current.
- **Other IDEs**: per-IDE quickstart pages are coming. The underlying setup (run `loom onboard`, install the two plugins, reload) is the same across IDEs; what differs is how you reach the Claude Code chat panel + how you reload.
