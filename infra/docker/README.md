# `infra/docker/`

**Status:** Populated. Local dev observability stack (Loki/Promtail/Grafana via `docker-compose`).

## Purpose

Dockerfiles + docker-compose for local dev.

## What's here

- `docker-compose.yml` + `Dockerfile` + `loki/` + `promtail/` — the local dev observability stack (Loki/Promtail/Grafana) run via docker-compose.

## Source

Scattered across services today. See [`../../docs/migration/README.md`](../../docs/migration/README.md).
