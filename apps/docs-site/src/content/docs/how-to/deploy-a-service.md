---
title: Deploy a service to Render
description: Create a Render service for the current repo from the terminal with tapestry deploy, instead of clicking through the dashboard.
---

`tapestry deploy` creates a Render service for the current repo in one command — repo link, branch, build/start commands, plan, and the shared env group — using Render's REST API. It removes the per-project dashboard clicking that setting up a new service otherwise takes.

This guide covers the imperative, per-project path. For the platform's own multi-service stack (staging, the observability services), use the declarative `render.yaml` Blueprint instead — see [Set up Render](/how-to/set-up-render/) and the decision record [ADR 0005](https://github.com/Lizo-RoadTown/tapestry/blob/main/docs/adr/0005-deploy-imperative-cli-vs-blueprint.md) for when to use which.

## Before you start

1. **A Render API key.** Generate one at Render dashboard → avatar → Account Settings → API Keys, then export it:

   ```bash
   export RENDER_API_KEY=rnd_...
   ```

   (Or pass `--api-key` on the command.)

2. **The GitHub ↔ Render connection.** Render's GitHub App must already be authorized for the repo you are deploying. This is a one-time dashboard step; there is no API for it. If you have deployed any service from this repo before, it is already done.

3. **The CLI installed.** `pip install tapestry-cli` (or run from `packages/cli/`).

## Step 1 — preview with `--dry-run`

Always preview first. `--dry-run` prints the exact request body that would be sent and makes **no** API calls — it needs no API key:

```bash
tapestry deploy --name my-service --type web \
  --build "pip install -r requirements.txt" \
  --start "uvicorn main:app --host 0.0.0.0 --port $PORT" \
  --dry-run
```

Secret values are masked (`"***"`) in dry-run output, so you can paste it safely.

## Step 2 — create the service

Drop `--dry-run` to send it:

```bash
tapestry deploy --name my-service --type web \
  --build "pip install -r requirements.txt" \
  --start "uvicorn main:app --host 0.0.0.0 --port $PORT" \
  --plan starter --region oregon \
  --env-group tapestry-shared-secrets
```

What it does, in order:

1. Loads the deploy spec (`deploy/render-service.json` by default; flags override it).
2. Resolves the repo URL from `git origin` (unless `--repo` is given).
3. Resolves the Render owner id via `GET /v1/owners` (unless `--owner-id` / `--owner-name` is given).
4. **Idempotency:** checks `GET /v1/services?name=<name>` — if a service with that exact name already exists, it stops without creating a duplicate.
5. Creates the service (`POST /v1/services`) with the repo link, branch, auto-deploy, and build/start commands.
6. Attaches the named env group, if you passed `--env-group`.
7. Prints the new service's URL.

## Committing a spec instead of passing flags

Repeated flags belong in a committed spec so the deploy is reproducible. Create `deploy/render-service.json`:

```json
{
  "name": "my-service",
  "type": "web",
  "runtime": "python",
  "plan": "starter",
  "region": "oregon",
  "build": "pip install -r requirements.txt",
  "start": "uvicorn main:app --host 0.0.0.0 --port $PORT",
  "healthCheckPath": "/health",
  "envGroup": "tapestry-shared-secrets"
}
```

Then just run `tapestry deploy` (flags still override the spec when you need a one-off change).

## Secrets

- `--set KEY=VALUE` — a plain (non-secret) env var, repeatable.
- `--secret KEY` — a secret env var whose **value is read from your own environment** by that name at deploy time, repeatable. The name is committed; the value never is. In `--dry-run` output the value is masked.

For secrets shared across services, prefer the env group (`--env-group tapestry-shared-secrets`) over per-service `--secret`.

## Supported service types

`--type` accepts `web`, `cron`, `worker`, and `private`. Static sites are not supported by this command (they need a `publishPath` and have no start command) — create those from the Render dashboard or a Blueprint.

Cron services also need `--schedule` (a cron expression).

## If it fails

- **`error: no Render API key`** — export `RENDER_API_KEY` or pass `--api-key`. (Not needed for `--dry-run`.)
- **Owner could not be resolved / multiple owners** — pass `--owner-id` (or `--owner-name`) to disambiguate.
- **The service already exists** — that is the idempotency guard, not an error; the command stops rather than duplicating. Rename with `--name` or manage the existing service in the dashboard.
- **Build/deploy fails on Render after creation** — that is a Render-side build issue, not the CLI; check the service's logs in the Render dashboard.

## See also

- [CLI commands reference](/reference/cli-commands/) — every `tapestry` subcommand and flag.
- [Set up Render](/how-to/set-up-render/) — the account setup, env groups, and the declarative Blueprint path.
