---
title: Set up Render (platform owner only)
description: Step-by-step walkthrough for provisioning Tapestry's backend services on Render — managed Postgres + the FastAPI services declared in the-loom's render.yaml Blueprint. Consuming projects don't need this; the platform owner runs it once.
---

This walkthrough is for the **platform owner** standing up Tapestry's backend. Consuming projects don't need Render — they connect to the platform owner's deployment via `.mcp.json`. See [Platform dependencies](/reference/platform-dependencies/) for who needs what.

Estimated time: 20–40 minutes for first provisioning, mostly waiting on builds.

## What you'll provision

The Render side hosts five Python web services plus one Postgres instance plus one cron, declared in `the-loom/render.yaml` (the platform's Blueprint file). The Blueprint is the source of truth — Render reads it and provisions everything declaratively.

| Resource | Purpose | Source |
|---|---|---|
| `loom-postgres` (managed Postgres) | Backing store for memory records, project registry, candidate registry | [the-loom/render.yaml](https://github.com/Lizo-RoadTown/the-loom/blob/main/render.yaml) |
| `loom-agent-context` (web service) | The Memory MCP — `memory_read/write/recall/list/search/delete` over HTTP + MCP | [the-loom/services/agent-context/](https://github.com/Lizo-RoadTown/the-loom/tree/main/services/agent-context) |
| `loom-architecture-registry` | Candidate + Architecture registry endpoints | [the-loom/services/architecture-registry/](https://github.com/Lizo-RoadTown/the-loom/tree/main/services/architecture-registry) |
| `loom-policy` | Promotion policy evaluator | [the-loom/services/policy/](https://github.com/Lizo-RoadTown/the-loom/tree/main/services/policy) |
| `loom-project-registry` | Project + repo + machine registration | [the-loom/services/project-registry/](https://github.com/Lizo-RoadTown/the-loom/tree/main/services/project-registry) |
| `loom-self-observer` (cron) | 6-hour scan that interprets signals into candidates | [the-loom/services/self-observer/](https://github.com/Lizo-RoadTown/the-loom/tree/main/services/self-observer) |

## Prerequisites

- A [Render account](https://render.com/) (free tier is enough to start; the platform-owner deployment may need a paid plan once traffic grows — see [Render's pricing](https://render.com/pricing))
- A [GitHub account](https://github.com/) that can read `Lizo-RoadTown/the-loom` (the public repo holding the Blueprint)
- A Grafana Cloud account with OTel credentials in hand — see [Set up Grafana Cloud + OTel](/how-to/set-up-grafana-cloud/) first; the Render services need `OTEL_EXPORTER_OTLP_*` env vars at provisioning time

## Step 1 — Sign up + sign in

1. Open [render.com](https://render.com/) and create an account if you don't have one. The Render docs' [Getting Started](https://render.com/docs) page covers the basics.
2. After signup, you land at [dashboard.render.com](https://dashboard.render.com/). Bookmark it — every later step happens here.

## Step 2 — Connect the GitHub repo

Render reads the Blueprint directly from a connected GitHub repo. You need to authorize Render to access `Lizo-RoadTown/the-loom`.

1. In the dashboard, click your profile (top-right) → **Account Settings** → **GitHub** → **Configure**.
2. Authorize Render against `Lizo-RoadTown` (your fork, or the upstream if you're the upstream owner).

If you're standing up your own deployment, fork `the-loom` first and edit the `render.yaml` service names if you want a different namespace.

## Step 3 — Validate the Blueprint locally (optional but recommended)

Render provides a CLI for Blueprint validation. Per the [Blueprint spec](https://render.com/docs/blueprint-spec), the command (requires CLI v2.7.0+):

```sh
brew install render          # or: curl -fsSL https://render.com/download-cli/linux | sh
render login
render validate the-loom/render.yaml
```

If the file is valid, the command exits 0. If not, it prints the schema errors so you can fix them before pushing.

## Step 4 — Provision the Blueprint

1. In the Render dashboard, click **New** (top-right) → **Blueprint**. Render's [Infrastructure as Code](https://render.com/docs/infrastructure-as-code) page documents this workflow.
2. Select the connected `Lizo-RoadTown/the-loom` repo.
3. Render reads `render.yaml` at the repo root and previews what it will create — five web services + one Postgres + one cron, matching the table above.
4. Click **Apply**.

Render builds each service in parallel. First builds take 3–8 minutes per service (the Postgres comes up faster, services have to install pip dependencies). Subsequent deploys are incremental.

## Step 5 — Set the required env vars

The Blueprint declares which env vars each service needs but does not set their values (secrets are operator-supplied). Per [the-loom's render.yaml comments](https://github.com/Lizo-RoadTown/the-loom/blob/main/render.yaml), you need to set these in the dashboard.

### Shared across services — `loom-shared-secrets` env group

1. In the dashboard, click **Environment Groups** (left sidebar) → **New Environment Group** → name it `loom-shared-secrets`.
2. Add these key-value pairs:

   | Key | Source |
   |---|---|
   | `OTEL_EXPORTER_OTLP_ENDPOINT` | from [Grafana Cloud setup](/how-to/set-up-grafana-cloud/) |
   | `OTEL_EXPORTER_OTLP_HEADERS` | from [Grafana Cloud setup](/how-to/set-up-grafana-cloud/) |
   | `LOOM_JWT_PUBLIC_KEY` | RSA public key (PEM) — every service verifies tokens with it |

3. Attach the env group to each web service: open the service → **Environment** → **Link Environment Group** → select `loom-shared-secrets`.

### Per-service secrets

A few keys must be set on individual services (not shared):

| Service | Key | Purpose |
|---|---|---|
| `loom-agent-context` | `LOOM_JWT_PRIVATE_KEY` | RSA private key — only this service signs tokens |
| `loom-project-observatory` (if deployed) | `GRAFANA_CLOUD_API_URL` | Server-side Grafana query endpoint |
| `loom-project-observatory` (if deployed) | `GRAFANA_CLOUD_API_TOKEN` | Auth for the query endpoint |

Set these per-service: open the service → **Environment** → **Add Environment Variable**.

## Step 6 — Verify deployment

Each service must show **Live** in the dashboard. Then check the health endpoints (every Python service in `the-loom/services/*/main.py` exposes `/health`):

```sh
curl https://loom-agent-context.onrender.com/health
curl https://loom-architecture-registry.onrender.com/health
curl https://loom-policy.onrender.com/health
curl https://loom-project-registry.onrender.com/health
```

Each should return `{"status": "ok", "service": "<name>"}`.

For the cron, open [`loom-self-observer`](https://dashboard.render.com/) in the dashboard and check the **Logs** tab. The first run executes within 6 hours of deployment (or you can manually trigger it via **Manual Deploy** → **Trigger Job**).

## Step 7 — Confirm the Memory MCP is reachable

From a Claude Code session in any test project:

1. Create or update the project's `.mcp.json`:

   ```json
   {
     "mcpServers": {
       "loom-memory": {
         "transport": {
           "type": "http",
           "url": "https://loom-agent-context.onrender.com/mcp/memory/"
         }
       }
     }
   }
   ```

2. Restart Claude Code.
3. In a session, call `memory_list` — should return without error.

If you see `MCP UNREACHABLE: HTTP 404`, the service is still cold-starting (free-tier services sleep after 15 minutes of no traffic). Wait 30–60 seconds and retry. If persistent, see [Memory troubleshoot](/systems/memory/#troubleshoot).

## Cost notes

Render's free tier covers small projects but the platform's services have constraints:

- Free-tier web services sleep after 15 minutes idle (~60s cold-start when traffic resumes). For the Memory MCP this is a real UX cost — every fresh session hits a cold start. The platform owner typically upgrades `loom-agent-context` to a paid plan (starter or above) once consumers are active.
- Managed Postgres has its own pricing tiers; the free tier is fine for early use.
- The cron schedule (every 6h) is well within free-tier limits.

See [Render pricing](https://render.com/pricing) for current rates.

## Operator-only actions that need the dashboard (not the MCP)

Some Render operations are NOT available via the Render MCP — only the dashboard:

- Plan changes (free → starter etc.) — operator does in dashboard
- Service deletion — operator does in dashboard
- Cron deletion — operator does in dashboard

This is by design; the Render MCP only supports updates that don't change billing state. See `feedback_render_mcp_cannot_change_service_plan_must_use_dashboard` in the operator's memory for the full list.

## Related

- [Set up Grafana Cloud + OTel](/how-to/set-up-grafana-cloud/) — do this first; Render needs the OTel env vars during provisioning
- [Set up Vercel](/how-to/set-up-vercel/) — for the frontend (docs site + Observatory cockpit)
- [Platform dependencies](/reference/platform-dependencies/) — what each external service does
- [Memory](/systems/memory/), [Registry](/systems/registry/), [Observer](/systems/observer/) — the Systems pages for the components deployed here
- [the-loom/render.yaml](https://github.com/Lizo-RoadTown/the-loom/blob/main/render.yaml) — the actual Blueprint file
- [Render docs — Blueprint spec](https://render.com/docs/blueprint-spec)
- [Render docs — Infrastructure as Code](https://render.com/docs/infrastructure-as-code)
