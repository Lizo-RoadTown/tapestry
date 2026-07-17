# Dev-experience observability — running locally

How to run the Loki + Promtail + Grafana stack so you can see your own Claude Code hook activity in real time, instead of asking the agent what it just did.

Status: **first iteration**. Captures hook fires from the make-skills-discipline plugin's `~/.claude/logs/hooks.jsonl`. Future iterations add memory writes, architecture-snapshot diffs, and git activity via a polling script.

## What this gives you

Once running, you point your browser at Grafana (default `http://localhost:3001`) and see the **Dev Experience — Hook Activity** dashboard:

- **Hook events over time** — count per minute, broken out by hook name (`UserPromptSubmit`, `PreToolUse`, `Stop`, `SessionStart`)
- **Action breakdown (last 24h)** — counts by action label (`reminder_injected`, `noop`, `block`, etc.)
- **Hook by name (last 24h)** — same total by hook name
- **Recent hook events** — log panel showing the last 50 raw entries with timestamps, scope, action, and notes

Use this when:
- You suspect the discipline plugin is misfiring (find false positives in the action breakdown)
- You want to verify a v0.1.x plugin change actually changed behavior (compare counts before/after)
- You want to see how much hook overhead your sessions are paying (elapsed_ms in the recent events panel)
- You want to drive your own work without asking the agent what it did

## Prerequisites

1. **Make_Skills repo cloned** with the platform stack present (`platform/deploy/docker-compose.yml`)
2. **Docker Desktop** (Windows / macOS) or `docker compose` CLI (Linux)
3. **make-skills-discipline plugin v0.1.2 or later installed** in Claude Code. The plugin is what writes `~/.claude/logs/hooks.jsonl`. Without v0.1.2+, the file won't exist and the dashboard will be empty.
4. **At least one Claude Code session run in Make_Skills since v0.1.2 installed**, so the log file has data.

## Run it

From the repo root:

```bash
cd platform/deploy
docker compose up -d loki promtail grafana
```

This brings up three new containers (plus the existing postgres + api if they aren't already running). Open `http://localhost:3001` for Grafana. Click the dashboard sidebar → "Dev Experience — Hook Activity".

If the dashboard is empty when it should have data, check:

1. **Did Promtail find the log file?**

   ```bash
   docker compose logs promtail | tail -20
   ```

   Should show lines like `seeked /var/log/claude/hooks.jsonl - offset 0 (NEW)`. If it shows "file not found", the host-path mount didn't resolve — see Troubleshooting below.

2. **Is the file actually being written?**

   ```bash
   tail -f ~/.claude/logs/hooks.jsonl
   ```

   You should see lines appearing as you interact with Claude Code in any Make_Skills repo. If nothing appears, the v0.1.2 plugin isn't actually firing — run `/doctor` in Claude Code and look for plugin errors.

3. **Is Loki receiving from Promtail?**

   ```bash
   docker compose logs loki | tail -5
   ```

   Should show recent inbound requests. If empty, Promtail isn't reaching Loki — check the docker network.

## How to override the host log path

The default mounts `~/.claude/logs/` on the host. If your Claude Code install uses a different location, set the env var before running compose:

```bash
DEV_HOOKS_LOG_DIR=/custom/path/to/logs docker compose up -d promtail
```

Or add `DEV_HOOKS_LOG_DIR=...` to a `.env` file next to `docker-compose.yml`.

## What's NOT in this iteration

- **Memory writes** — `~/.claude/projects/<key>/memory/` mtime tracking is not ingested yet. Planned: polling script `scripts/observe_dev_experience.py` writing to Postgres + a Grafana panel.
- **Architecture-snapshot diffs** — `docs/architecture-snapshots/*-diff.json` not surfaced in the dashboard yet. Same polling script.
- **Git commit / PR activity** — `git log` + GitHub API not polled yet.
- **Test-runs log frequency** — `docs/test-runs/*.md` line growth not tracked yet.
- **Hosted-mode dev-experience observability** — this is local-machine only by design. The developer's hook log lives on the machine where Claude Code runs, not on Render. Hosted mode runs the *running app*; the developer's tooling stays local.

The runtime observability stack (OTel + Tempo + Prometheus for FastAPI / Next.js HTTP / DB / metrics) is a separate concern — see `reference_observability_layering.md` in session memory.

## Troubleshooting

**Promtail can't find the log file (Windows host)**

On Windows with Docker Desktop, the `${HOME}` env var resolves differently than Linux/macOS. Try setting `DEV_HOOKS_LOG_DIR=C:/Users/<yourname>/.claude/logs` explicitly (forward slashes work in docker-compose YAML even on Windows).

**Loki schema migration warning on startup**

Expected on first start with schema v13. Loki initializes its TSDB store on the volume; subsequent restarts are silent.

**Dashboard panels show "no data" even though Promtail is shipping**

Check the dashboard's time range (top right). The default is "last 24h" — if you just started shipping data, switch to "last 5 minutes" to verify.

**Container resource usage**

Loki + Promtail combined use ~150MB RAM at idle, more under heavy log volume. If running on a constrained laptop, you can `docker compose stop loki promtail` between sessions and only bring them up when you want to view the dashboard.

## Two-mode discipline

This layer is **dev-tooling, local-machine only**. It does NOT ship with hosted-multitenant Render deploys — the Promtail volume mount points at the developer's local `~/.claude/logs/`, which doesn't exist on Render. Render's `render.yaml` provisions only the api + postgres + persistent disk for the running app's memory.

If you want operational observability for the *running app* (HTTP latency, error rate, LLM costs), that's a separate Phase B track using OpenTelemetry → Tempo / Loki / Prometheus → Grafana with different dashboards. See the wrapper plan in `reference_wrapper_research_per_interface.md`.

## Related files

- `platform/deploy/docker-compose.yml` — service definitions (Loki, Promtail, Grafana)
- `platform/deploy/loki-config.yml` — Loki server config
- `platform/deploy/promtail-config.yml` — Promtail scrape + parse + ship pipeline
- `platform/deploy/grafana/provisioning/datasources/loki.yml` — Grafana → Loki connection
- `platform/deploy/grafana/dashboards/dev-experience.json` — the dashboard itself
- `Lizo-RoadTown/claude-skills-marketplace` PR #2 — the v0.1.2 discipline plugin that writes `hooks.jsonl` in the first place
- `reference_observability_layering.md` (session memory) — the broader pattern this implements
