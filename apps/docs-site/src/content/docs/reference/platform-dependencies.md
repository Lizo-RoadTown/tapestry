---
title: Platform dependencies
description: The external services Tapestry runs on. What's required to operate the platform vs what's required to use it from a consuming project.
---

Tapestry runs on four external services. Being honest about which ones the platform needs, and which ones a consuming project's operator needs, prevents the surprise of "I installed the plugin and nothing's logging."

## Required for the platform (operator + platform owner)

These are the services the Tapestry platform itself depends on. If you're standing the platform up (or self-hosting all of it), you need accounts at all four.

| Service | What it hosts | Why required |
|---|---|---|
| **Render** | `loom-agent-context` MCP server, `loom-project-registry`, Postgres (`loom-postgres`), the self-observer cron, future migrated services | The hosted-multitenant deployment target for every backend service. Postgres holds memory records + project registry + candidate registry. The cron emits the synthesis memo every 6h. |
| **Vercel** | `apps/docs-site/` (this site, at [tapestry-khaki.vercel.app](https://tapestry-khaki.vercel.app/)) + `apps/web-dashboard/` (the Project Observatory console, when deployed) | The frontend deployment target. Static docs + the dashboard. |
| **OpenTelemetry collector** | The OTel transport — receives OTLP traces/logs from the discipline plugin's hooks + future runtime services | The canonical telemetry transport per the [coordination contract](/reference/otel-coordination-contract/). Without it, hook events go to local `hooks.jsonl` only — no cross-machine observability. |
| **Grafana Cloud** | The dashboards + Loki (logs) + Tempo (traces) + the OTLP gateway | The telemetry destination. Read by the observer (queried for coordination-quality signals); read by the operator (dashboards). |

## Required for a consuming project (you, the operator wiring a new project)

Most consumers do NOT need accounts at the four services above. The platform owner (Liz) hosts those for the shared deployment. What you need:

| Service | Why | Cost |
|---|---|---|
| **Claude Code** (Anthropic) | The agent that runs in your IDE / terminal. Without it, no hooks fire, no memory recall, no observer. | Per Anthropic's pricing. |
| **GitHub access to `Lizo-RoadTown/tapestry`** | So `/plugin marketplace add Lizo-RoadTown/tapestry` resolves. Public repo — no special access needed. | Free. |
| **(Optional) Grafana Cloud OTel credentials** | Only if you want your project's hook events to flow to the shared Grafana stack alongside other consuming projects' telemetry. Without these, the discipline plugin still works — local `hooks.jsonl` is the source of truth — but no cross-machine observability for your project. | Free tier sufficient for most projects. |

The OTel credentials live in your `.env` as `OTEL_EXPORTER_OTLP_*` env vars — see [Load-bearing files §`OTEL_*`](/reference/load-bearing-files/#otel-otel-telemetry). The platform owner shares these on request.

## What happens if one is missing

| Missing | What breaks |
|---|---|
| Render | The platform backend doesn't exist. `loom-memory` MCP is unreachable; consuming projects with `loom-memory` declared in `.mcp.json` get connection errors. CORE DIRECTIVE 1 says the agent should HALT and report. |
| Vercel | This docs site doesn't exist; the Project Observatory console doesn't exist. Consuming projects' Claude Code installs still work (the plugin doesn't depend on Vercel) but you can't read the docs or see the dashboard. |
| OTel collector | Hook events still write to local `~/.claude/logs/hooks.jsonl` but don't flow anywhere shared. No cross-machine observability. The observer's runtime-telemetry inputs are blind (per the [signal hierarchy](/explanation/signal-hierarchy/) — telemetry is one of several inputs; observer keeps working on the others). |
| Grafana Cloud | OTLP push goes to a dead endpoint; emission errors land in `~/.claude/logs/hook-otel-errors.log` (per `_observability.py`); local hook writes still succeed. Dashboards don't exist. |
| Anthropic / Claude Code | Nothing runs. The whole point is the agent. |

## Self-host vs hosted-multitenant

The platform supports a two-mode commitment (every service has a `PLATFORM_MODE=self_host` default + a `PLATFORM_MODE=hosted` opt-in). Self-host means: run everything yourself, no JWT auth, single-tenant. Hosted-multitenant means: JWT-verified tenant isolation against the platform owner's deployment.

If you're standing up a fully self-hosted Tapestry, you need accounts + deployments at all four services above. If you're a consuming project using the platform owner's hosted deployment, you only need the second table.

## Related

- [Load-bearing files — `OTEL_*`](/reference/load-bearing-files/#otel-otel-telemetry) — the env-var contract
- [OTel coordination contract](/reference/otel-coordination-contract/) — the attribute schema
- [The observer](/explanation/the-observer/) — what reads the telemetry
- [The memory MCP](/explanation/memory-mcp/) — the Render-hosted service
