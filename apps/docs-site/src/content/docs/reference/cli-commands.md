---
title: CLI commands
description: Reference for the tapestry command-line interface — every subcommand and its flags.
---

The `tapestry` CLI (`pip install tapestry-cli`) onboards projects, opens the Observatory, scaffolds plugins, and deploys services. It is stdlib-only. Run `tapestry <command> --help` for the flags on any command.

```text
tapestry <command> [options]
```

| Command | What it does |
|---|---|
| `onboard` | Onboard the current directory and write `.claude/settings.json` (recommended path). |
| `init` | Onboard the current directory as a consuming project without touching `.claude/settings.json`. |
| `observatory` | Open the Observatory console in a browser. |
| `make-plugin` | Scaffold a personalized Claude Code plugin to publish to your own marketplace. |
| `deploy` | Create a Render service for the current repo via the Render API. |
| `version` | Print the CLI version and platform info. |

## `tapestry onboard`

Onboards the current directory and writes `.claude/settings.json` (enabling the discipline + patterns plugins), along with `.env`, `.mcp.json`, and `.project-intelligence/`. This is the recommended entry point for a new project.

## `tapestry init`

The granular variant of `onboard`: writes `.env`, `.mcp.json`, and `.project-intelligence/` but does **not** touch `.claude/settings.json`. Use it when you manage plugin enablement yourself.

## `tapestry observatory`

Opens the Observatory console in the default browser.

## `tapestry make-plugin`

Scaffolds a personalized Claude Code plugin — its marketplace manifest, plugin manifest, and directory shape — so you can publish your own agents/skills to your own marketplace. See [Create your own plugin](/how-to/create-your-own-plugin/).

## `tapestry deploy`

Creates a Render service for the current repo via Render's REST API. Reads a committed spec (`deploy/render-service.json` by default) and resolves the repo URL from `git origin`. Idempotent: if a service with the same name already exists, it stops without creating a duplicate. See [Deploy a service to Render](/how-to/deploy-a-service/) for the walkthrough.

| Flag | Meaning |
|---|---|
| `--spec PATH` | Deploy spec JSON (default `deploy/render-service.json`). |
| `--name NAME` | Render service name. |
| `--type TYPE` | Service type: `web`, `cron`, `worker`, or `private`. |
| `--plan PLAN` | Render plan (e.g. `starter`, `free`). |
| `--region REGION` | Region (default `oregon`). |
| `--branch BRANCH` | Git branch (default `main`). |
| `--root DIR` | `rootDir` within the repo. |
| `--runtime RUNTIME` | Runtime (default `python`). |
| `--build CMD` | Build command. |
| `--start CMD` | Start command. |
| `--health-check-path PATH` | Health check path (web services only). |
| `--schedule EXPR` | Cron schedule (cron services). |
| `--repo URL` | Repo URL (default: resolved from `git origin`). |
| `--owner-id ID` | Render owner/workspace id. |
| `--owner-name NAME` | Resolve the owner id by name. |
| `--env-group NAME` | Existing env group to attach. |
| `--auto-deploy yes\|no` | Auto-deploy on push (default `yes`). |
| `--set KEY=VALUE` | Plain env var (repeatable). |
| `--secret KEY` | Secret env var name; the value is read from your environment (repeatable). |
| `--api-key KEY` | Render API key (default: `RENDER_API_KEY` env var). |
| `--dry-run` | Print the request that would be sent and make no API calls (needs no API key; secret values are masked). |

## `tapestry version`

Prints the installed CLI version and Python/platform info.
