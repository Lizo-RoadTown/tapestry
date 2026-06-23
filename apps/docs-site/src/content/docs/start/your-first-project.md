---
title: Your first project
description: What `tapestry onboard` actually did, what files appeared in your repo, and what to expect when you start your first Claude Code session. Run this page after the Quickstart and before Verify it worked.
---

You ran `tapestry onboard my-project`. Here's what landed and what comes next.

## Files written

`tapestry onboard` is idempotent and writes (or merges into) four files:

| File | What it holds | Why |
|---|---|---|
| `.env` | `LOOM_PROJECT_ID=my-project` + shared OTel + API-key blocks | The project's identity tag — everything memory and telemetry scope by this. |
| `.mcp.json` | The `loom-memory` MCP server declaration | Wires the [Memory](/systems/memory/) MCP into every Claude Code session in this repo. |
| `.project-intelligence/my-project/` | `agent-profile.json`, `project-context.json`, `observatory-config.json` | Per-project intelligence files the Observer + Observatory read. |
| `.claude/settings.json` | Both `tapestry-discipline` + `tapestry-patterns` plugins enabled | So the discipline plugin auto-loads its hooks and `tapestry-patterns` auto-loads its agents + skills. |

It also registers your project with the Project Registry if the registry is reachable. If it isn't, the local files still write — registration retries on the next `tapestry onboard` run.

## What changes in Claude Code

Open the chat panel and start a fresh session. Three things are now different from a bare project:

**1. The session header includes an auto-recall block.** It lists memory records tagged for `my-project`. On first session this block is empty — that's expected; it fills in as you accumulate corrections, decisions, and observer findings over time.

**2. Every prompt you send gets a `[loom-discipline] Discipline check:` reminder line injected as additional context.** That's the discipline plugin's `UserPromptSubmit` hook firing — it injects PROBE-before-asserting + cite file:line + dev-tooling-vs-runtime + save-friction-as-memory rules into the agent's working context.

**3. Hook events emit to two destinations.** Local `~/.claude/logs/hooks.jsonl` always (source of truth). Grafana Cloud via OTel if `OTEL_EXPORTER_OTLP_*` env vars are set in your `.env`. See [Telemetry](/systems/telemetry/) for the wiring.

## What's NOT installed by onboarding

Onboarding makes your project **observable**. It does not install the **Observatory** — the Observatory is a platform-level surface that already exists. Onboarding wires your project *into* it.

See [Project Intelligence vs Observatory](/explanation/project-intelligence-vs-observatory/) for why the distinction matters.

## What to do next

1. [Verify it worked](/start/verify-it-worked/) — four quick checks that the wiring landed.
2. [First Observatory visit](/start/first-observatory-visit/) — open the dashboard and learn what to look for.
3. (Optional) Write a `CLAUDE.md` in your project root. Onboarding does not author one — it's project-specific. See an example at [the-loom's CLAUDE.md](https://github.com/Lizo-RoadTown/the-loom/blob/main/CLAUDE.md).

## Related

- [Quickstart — VS Code](/how-to/quickstart-vscode/) — the 4-step setup that got you here
- [Set up a new project (comprehensive)](/how-to/set-up-a-new-project/) — what to do beyond onboarding for projects that want CLAUDE.md, snapshot scripts, custom hooks
- [Names you'll see in these docs](/start/names-you-will-see/) — `tapestry-discipline`, `tapestry-patterns`, `loom-memory`, `loom-agent-context`, etc.
