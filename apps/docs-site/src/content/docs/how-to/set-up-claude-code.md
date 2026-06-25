---
title: Set up Claude Code
description: Install Claude Code, sign in, and connect the Tapestry marketplace so the discipline and patterns plugins are available in your sessions.
---

Tapestry runs inside **Claude Code** — the agent in your IDE or terminal. Without it, no hooks fire, no memory recall, no observer. This is the first prerequisite.

## Install Claude Code

Install Claude Code (the CLI, the desktop app, or an IDE extension) and sign in with your Anthropic account. Follow Anthropic's install guide for your platform.

## Connect the Tapestry marketplace

In a Claude Code session:

```text
/plugin marketplace add Lizo-RoadTown/tapestry
/plugin install tapestry-discipline@tapestry
/plugin install tapestry-patterns@tapestry
```

- **`tapestry-discipline`** — the universal discipline hooks (PROBE-first reminders, citation enforcement, write/edit audit). Works with no backend; the memory/observer/telemetry features light up only when you point them at your own deployment.
- **`tapestry-patterns`** — the reusable agents and skills available by name in every project.

The marketplace is the public repo `Lizo-RoadTown/tapestry`, so no special access is needed. (See [Set up GitHub](/how-to/set-up-github/) for the account basics.)

## Enable per project

Onboarding (`tapestry onboard`) writes `.claude/settings.json` with both plugins enabled for that project. See [Your first project](/start/your-first-project/) and the [Quickstart](/how-to/quickstart-vscode/).

## Verify

Run `/plugin list` — both plugins should show as installed. Start a fresh session in an onboarded project and you should see the discipline reminders in the context.
