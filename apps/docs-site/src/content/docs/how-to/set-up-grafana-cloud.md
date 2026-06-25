---
title: Set up Grafana Cloud + OTel
description: Step-by-step walkthrough for the telemetry pipeline — sign up for Grafana Cloud, get OTLP credentials, and wire OTEL_EXPORTER_OTLP_* env vars so the discipline plugin's hooks emit to Grafana Loki/Tempo. Required for cross-machine observability.
---

This walkthrough stands up the telemetry pipeline on Grafana Cloud for your own deployment. Your projects' hooks emit to it via OTel env vars set in each project's `.env`.

Estimated time: 15–25 minutes including waiting for the first signal to land.

## What you'll set up

| Piece | What it does |
|---|---|
| **Grafana Cloud account** | Hosts Loki (logs), Tempo (traces), Prometheus/Mimir (metrics), and the OTLP gateway |
| **OTLP endpoint URL** | Where the discipline plugin's hooks POST their OTLP/HTTP logs |
| **OTLP auth header** | Pre-built `Authorization: Basic <b64>` for the endpoint |
| **`OTEL_EXPORTER_OTLP_*` env vars** | Distributed to operators' `.env` files + to Render services |

Without this, hook events still write to local `~/.claude/logs/hooks.jsonl` (the source of truth — see [Telemetry system page](/systems/telemetry/)). The Grafana Cloud pipeline is the cross-machine extension.

## Prerequisites

- A reachable email for the Grafana Cloud signup
- Decision: free-tier or paid? Per [Grafana Cloud pricing](https://grafana.com/products/cloud/) the free tier includes 10K series of metrics, 50 GB logs, 50 GB traces. Adequate for early-stage Tapestry usage.

## Step 1 — Sign up

1. Open [grafana.com/auth/sign-up/create-user](https://grafana.com/auth/sign-up/create-user) and create an account.
2. Choose a **stack name** (it becomes part of your URLs — pick something recognizable, e.g., `tapestry`).
3. Choose a region close to your operators / services (us-east-2, eu-west-2, etc.). This affects OTLP endpoint latency.

After signup, you land at the **Organization Overview** page. Bookmark it.

## Step 2 — Open the OpenTelemetry tile + generate OTLP credentials

Per [Grafana's OTLP setup docs](https://grafana.com/docs/grafana-cloud/send-data/otlp/send-data-otlp/):

1. From Organization Overview, **launch your stack** (click into the stack you named).
2. Find the **OpenTelemetry tile** in the stack's dashboard. Click **Configure**.
3. Follow the in-page instructions to generate:
   - An authentication token (Grafana calls this an "Access Policy" token).
   - A pre-built set of OpenTelemetry environment variables.

Grafana's UI generates the exact values for:

```sh
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-<region>.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<base64(instance_id:token)>
```

The `OTEL_EXPORTER_OTLP_HEADERS` value is base64-encoded and URL-escaped; copy it verbatim — manual reconstruction is error-prone.

## Step 3 — Save the credentials

These three values are the canonical credentials for every place that emits telemetry. Save them in a password manager — Grafana does NOT let you re-view the token after generation (only rotate).

Distribute them to:

| Where | How |
|---|---|
| **Render env group `loom-shared-secrets`** | Set during [Render setup](/how-to/set-up-render/) Step 5 |
| **Operator `.env` files** | Each operator's project gets these in `.env` (gitignored) so their discipline plugin hooks emit |
| **Future runtime services** | Any new platform service that emits OTel reads these from env |

Operators add to their consuming project's `.env`:

```sh
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-<region>.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<your-base64-blob>
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_RESOURCE_ATTRIBUTES=service.namespace=loom,deployment.environment=dev
OTEL_SERVICE_NAME=tapestry-discipline
```

See [Load-bearing files — `OTEL_*`](/reference/load-bearing-files/) for the contract per env var.

## Step 4 — Verify a signal lands

The fastest way to verify the pipeline:

1. In any Claude Code session with the discipline plugin installed AND the `.env` populated with the OTel vars above, type any prompt. The `UserPromptSubmit` hook fires.
2. In Grafana Cloud, open **Explore** (left sidebar) → select **Loki** as the data source.
3. Run the query:

   ```
   {service_name="tapestry-discipline"}
   ```

4. Within a few seconds, you should see the hook event records appear. Each is a JSON line with fields like `hook`, `phase`, `action`, `exit_code`, `elapsed_ms`.

If nothing appears within 60 seconds:

- Check `~/.claude/logs/hook-otel-errors.log` on the machine that ran the session. Empty file = pushes succeeded; entries = pushes failed (URL or auth issue).
- Verify the env vars are actually loaded by the shell that started Claude Code (`echo $OTEL_EXPORTER_OTLP_ENDPOINT` — should print the URL, not an empty line).
- See [Telemetry troubleshoot](/systems/telemetry/#troubleshoot) for the full diagnostic flow.

## Step 5 — Set up dashboards (optional)

Once signals are flowing, the operator can build Grafana dashboards over them. Two starting points:

- **Loki** for log queries — search by `service_name`, `hook`, `project_id`, etc. See [Loki query language docs](https://grafana.com/docs/loki/latest/query/).
- **Tempo** for traces — when runtime services start emitting traces (currently only the hooks emit logs). See [Tempo docs](https://grafana.com/docs/tempo/latest/).

For Tapestry-specific dashboards, pre-built dashboard JSON ships in `infra/grafana/` (when that lands; currently dashboards are operator-built and shared informally).

## Step 6 — Rotate credentials (when needed)

Per [Grafana's Access Policies docs](https://grafana.com/docs/grafana-cloud/account-management/authentication-and-permissions/access-policies/), rotating the OTLP token is:

1. Grafana Cloud Portal → **Access Policies** → find the token → **Rotate**.
2. Update the `OTEL_EXPORTER_OTLP_HEADERS` value everywhere it's set (Render env group, operator `.env` files, runtime services).
3. The old token continues to work for ~24 hours after rotation so deployments don't break instantly.

## Self-hosted alternative

If you don't want to use Grafana Cloud, the OTel pipeline works against any [OTLP-compatible backend](https://opentelemetry.io/ecosystem/vendors/) — the hook scripts (`integrations/claude-code/tapestry-discipline/scripts/_observability.py`) just POST OTLP/HTTP. Common self-hosted choices:

- Self-hosted [Grafana Loki + Tempo + Mimir (LGTM)](https://github.com/grafana/loki) stack — same UX as Grafana Cloud, different ops profile.
- [SigNoz](https://signoz.io/), [HyperDX](https://www.hyperdx.io/), other OTel-compatible vendors.

The Tapestry code itself doesn't change — only the `OTEL_EXPORTER_OTLP_*` env vars point at a different endpoint.

## Cost notes

[Grafana Cloud's free tier](https://grafana.com/products/cloud/) covers 10K active series, 50 GB logs, 50 GB traces, 14-day retention. For early Tapestry usage (a handful of operators emitting hook events) this is comfortable. Watch for:

- Log volume — hooks are chatty. If one operator runs 1000+ Claude Code interactions/day, logs add up. Free tier holds about a month of hook traffic per operator at default verbosity.
- Trace volume scales similarly once runtime services emit traces.

Paid tier kicks in at $0 base with usage-based billing per [the pricing page](https://grafana.com/pricing/) — most platforms stay free.

## Related

- [Set up Render](/how-to/set-up-render/) — needs OTel env vars during provisioning
- [Set up Vercel](/how-to/set-up-vercel/) — the frontend doesn't emit OTel directly but reads queries from Grafana for some Observatory lenses (future)
- [Telemetry system page](/systems/telemetry/) — what the pipeline does end-to-end
- [OTel coordination contract](/reference/otel-coordination-contract/) — the typed-attribute schema
- [Load-bearing files — `OTEL_*`](/reference/load-bearing-files/) — the env-var contract
- [Grafana Cloud OTLP setup docs](https://grafana.com/docs/grafana-cloud/send-data/otlp/send-data-otlp/)
- [OpenTelemetry SDK env var reference](https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/)
