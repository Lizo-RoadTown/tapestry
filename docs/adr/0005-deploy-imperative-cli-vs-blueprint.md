# 0005 — imperative `tapestry deploy` CLI alongside the declarative Blueprint

**Date:** 2026-09-27
**Status:** **Accepted**

## Context

There are two ways to create a Render service in this repo, and they serve different jobs:

- **The declarative Blueprint** — `infra/deploy/render.yaml` declares the platform's own service set (staging, the observability services) as reviewed infrastructure-as-code. Changes go through a PR; the whole stack is described in one file; `autoDeploy` and env-group wiring are versioned.
- **Per-project service creation** — onboarding a new consuming project onto Render is a repetitive manual task: click through the dashboard to create the service, connect the GitHub repo, set build/start/plan, and re-attach the shared env group. This is tedious and easy to get subtly wrong (wrong env group, forgotten health check path), and it produces nothing reviewable.

A Blueprint is the wrong tool for the second job: a one-off per-project service does not belong in the platform's own `render.yaml`, and asking each operator to hand-author a Blueprint per project reintroduces the same friction.

## Decision

Add an imperative `tapestry deploy` subcommand (`packages/cli/tapestry_cli/deploy.py`) that creates a single Render service for the current repo via Render's REST API, reading a small committed spec (`deploy/render-service.json`) with flag overrides.

The two paths coexist by role:

| Path | Use for | Shape |
|---|---|---|
| **Blueprint** (`infra/deploy/render.yaml`) | The platform's own multi-service stack | Declarative, reviewed in PRs, describes many services |
| **`tapestry deploy`** | Per-project, one-off service creation from the terminal | Imperative, one service per run, spec + flags |

Design constraints the command holds:

- **Stdlib-only** (`urllib`), matching the rest of `tapestry-cli` — no third-party runtime dependency.
- **Idempotent** — an exact-name match on `GET /v1/services?name=` stops the run rather than creating a duplicate.
- **`--dry-run`** prints the exact request body and makes no API call (needs no API key); resolved secret values are masked in that output so it is safe to paste.
- **Secrets by reference** — `--secret KEY` commits the env var name and reads its value from the operator's environment at deploy time; the value is never committed. Shared secrets go through the env group, not per-service flags.
- **Only builder-valid service types are advertised** — `web`, `cron`, `worker`, `private`. Static sites are omitted (they need a `publishPath` and have no start command); `healthCheckPath` is gated to web services.

## Consequences

- Onboarding a project onto Render becomes one command instead of a dashboard walkthrough, and the spec makes the deploy reproducible and reviewable in the project's own repo.
- Two creation paths now exist; this ADR fixes which is canonical for which job so they do not drift into overlapping use. New platform services still go in the Blueprint; per-project services use the CLI.
- The command depends on Render's REST API shapes (verified against the API reference 2026-09-25) and on the GitHub ↔ Render App connection, which remains a one-time dashboard step with no API.
- Static-site and other unsupported types fall back to the dashboard or a Blueprint; the CLI intentionally does not half-support them.

## See also

- How-to: [Deploy a service to Render](https://tapestry-khaki.vercel.app/how-to/deploy-a-service/)
- Reference: [CLI commands](https://tapestry-khaki.vercel.app/reference/cli-commands/)
- `packages/cli/tapestry_cli/deploy.py` — the implementation and its module docstring (records the verified API shapes).
