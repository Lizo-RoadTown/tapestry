# Grafana provisioning + dashboards

Tapestry's local + deployed Grafana stack. Companion to the Loki + Promtail config under [`../docker/`](../docker/).

## Structure

```
grafana/
├── dashboards/                   # JSON dashboard specs (auto-provisioned)
│   ├── dev-experience.json       # dev/CI dashboard
│   └── loom-phase1-observability.json  # platform telemetry dashboard
└── provisioning/                 # Grafana auto-discovers these on startup
    ├── dashboards/
    │   └── dashboards.yml        # tells Grafana to load `dashboards/` above
    └── datasources/
        ├── loki.yml              # Loki datasource (logs)
        └── postgres.yml          # Postgres datasource (metrics from app tables)
```

## How to bring this up locally

See [`../../docs/runbooks/dev-experience-observability.md`](../../docs/runbooks/dev-experience-observability.md).

## How to rebuild a dashboard from JSON after UI drift

See [`../../docs/runbooks/grafana-dashboard-rebuild.md`](../../docs/runbooks/grafana-dashboard-rebuild.md).
