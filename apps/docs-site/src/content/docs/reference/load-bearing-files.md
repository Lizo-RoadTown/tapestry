---
title: Load-bearing files
description: Every file, config block, and environment variable the discipline stack depends on, with a one-line "why it exists" and what fails if it's missing.
---

This is the lookup reference. For each load-bearing piece: WHERE it lives, WHAT it is, and WHAT fails if it's missing or wrong.

For how the pieces fit together conceptually, see [The discipline stack](/explanation/discipline-stack/). To set up a new project, see [Set up a new project](/how-to/set-up-a-new-project/).

## Project-side files (in your repo)

### `.mcp.json`

**Location:** repo root.

**What it is:** declares MCP servers Claude Code should connect to in this project's sessions. JSON object with a top-level `mcpServers` key.

**Minimal contents for a Tapestry-consuming project:**

```json
{
  "mcpServers": {
    "loom-memory": {
      "type": "http",
      "url": "https://your-memory-host.example.com/mcp/memory/"
    }
  }
}
```

**Why it exists:** explicit per-project MCP wiring. If the `tapestry-discipline` plugin's own MCP declaration fails to load for any reason, this file ensures the memory tools remain available.

**If missing:** the agent has no `memory_recall`/`memory_write` tools UNLESS the discipline plugin successfully declares them (it usually does, but defense-in-depth fails when both layers fail).

**Gitignore status:** typically gitignored if it contains secrets (API tokens in headers). Pure URL-only contents can be committed safely.

### `.claude/settings.json`

**Location:** `.claude/settings.json` at repo root.

**What it is:** project-shared Claude Code settings. Critically: enables plugins for this project.

**Minimal contents:**

```json
{
  "enabledPlugins": {
    "tapestry-discipline@tapestry": true
  }
}
```

**Why it exists:** plugins are installed-once-per-machine but enabled-per-project. This file is the per-project opt-in.

**If missing or empty:** no plugins fire. The agent operates in stock Claude Code mode. No discipline hooks, no auto-recall, no memory MCP declared via plugin.

**Gitignore status:** committed (shared across team members).

### `.claude/settings.local.json`

**Location:** `.claude/settings.local.json` at repo root.

**What it is:** local-only overrides per developer. Most commonly used for `permissions.allow` lists of WebFetch domains or MCP server enables.

**Why it exists:** lets individual developers add personal permissions without polluting the shared settings.

**If missing:** non-blocking. Defaults apply.

**Gitignore status:** typically gitignored.

### `.env`

**Location:** repo root.

**What it is:** plain-text env-var declarations. At minimum should contain `LOOM_PROJECT_ID`. Often also contains OTel credentials, API keys, DB URLs.

**Minimal contents for Tapestry-consuming projects:**

```
LOOM_PROJECT_ID=your-project-id
```

**Why it exists:** the `LOOM_PROJECT_ID` is the scope gate for the `tapestry-discipline` plugin's hooks (v0.1.12+) AND the tag applied to memory writes from this project.

**If missing or empty:** hooks may no-op (no scope to activate against). Memory writes may be untagged or default-tagged. Cross-project memory recall becomes unfocused.

**Gitignore status:** ALWAYS gitignored. Never commit. Contains secrets.

### `.project-intelligence/<project-id>/`

**Location:** `.project-intelligence/your-project-id/` at repo root.

**What it is:** per-project agent configuration directory. Contains:
- `agent-profile.json` — role, memory tag, discipline rules
- `project-context.json` — what this project is about
- `observatory-config.json` — what events to log, what triggers candidates
- `workflow-candidates/` — local longitudinal state for skill candidates the agent surfaces
- `promotion-candidates/` — outbox for items the agent thinks should become durable structure

**Why it exists:** the discipline plugin is generic across all projects. This directory tells it what specialization to apply for THIS project (role, observability, candidate triggers).

**If missing:** the agent loses per-project specialization. Generic discipline still applies but role-specific behavior is gone.

**Gitignore status:** committed. The configs are intentional shared decisions.

### `CLAUDE.md`

**Location:** repo root.

**What it is:** plain markdown auto-loaded by Claude Code at session start. Conventional content includes project description, agent role, memory hierarchy pointers, discipline rules, token discipline conventions, tone.

**Why it exists:** primary per-project context Claude Code auto-loads. Different from `.project-intelligence/` (which is JSON config); CLAUDE.md is prose for the agent to read.

**If missing:** the agent has no project-specific context beyond what hooks inject. The agent might function but loses project-specific framing.

**Gitignore status:** committed.

### `scripts/architecture_snapshot.py` and `scripts/architecture_diff.py`

**Location:** `scripts/` at repo root.

**What it is:** snapshot pipeline scripts that produce a structural snapshot of your repo and a diff against the prior baseline. For Tapestry-consuming projects, these should be thin wrappers that dispatch to the canonical implementations in the `tapestry-patterns` plugin.

**Why it exists:** the `tapestry-discipline` plugin's SessionStart hook runs these to inject the architecture context into the session's initial state. Without them, the hook silently no-ops on the snapshot piece.

**If missing:** SessionStart still fires (auto-recall still happens) but no architecture context is added. The agent loses structural awareness at session start.

**Gitignore status:** committed (they're code).

**Reference:** [the wrapper-pattern PR in a real consuming project](https://github.com/Lizo-RoadTown/sde-extraction/commit/2325e67) (commit `2325e67`).

### `.project-intelligence/<project-id>/workflow-candidates/`

**Location:** `.project-intelligence/<project-id>/workflow-candidates/` at repo root.

**What it is:** per-project longitudinal state for the Path A observer (see [The observer](/explanation/the-observer/)). One JSON file per skill the observer has surfaced in any session; each file tracks cumulative `sessions_seen`, the most-recent `status`, and the prior session IDs where the skill appeared.

**Why it exists:** the observer runs at the end of every session, but candidates only make sense over time. This directory keeps the count across sessions so the observer can dedup and advance status (`draft → observed → recurring`) without re-reading every prior transcript.

**If missing:** the observer recreates the directory on next emission. Cumulative state from prior sessions is lost — every skill in repeated sessions emits as a new candidate every time, status never advances past `draft`.

**Gitignore status:** committed (it's intentional cumulative state, useful as an audit trail).

### `docs/architecture-snapshots/` directory

**Location:** `docs/architecture-snapshots/` at repo root.

**What it is:** output directory for the architecture snapshot scripts. Contains timestamped `*-snapshot.json`, `*-diff.json`, and `*-narrative.md` files.

**Why it exists:** historical record of structural changes. Each snapshot is the input for the next diff.

**If missing or empty:** first snapshot has no prior baseline to diff against, so the first session produces a snapshot but no diff. Subsequent sessions work normally.

**Gitignore status:** typically committed (they're auditable history). Some setups gitignore them to reduce repo size; either is defensible.

## Platform-side (hosted, not in your repo)

### The `loom-memory` MCP server

**Location:** `https://your-memory-host.example.com/mcp/memory/` (hosted on Render).

**What it is:** HTTP-transport MCP server exposing six memory tools (`memory_recall`, `memory_read`, `memory_write`, `memory_search`, `memory_list`, `memory_delete`).

**Why it exists:** the canonical cross-session, cross-agent memory store. Every Tapestry-consuming project uses the SAME hosted instance.

**If down:** all memory operations fail. CORE DIRECTIVE 1 says the agent should HALT and report when the MCP is unavailable. In practice, sessions can still PROCEED but the operator should know they're degraded.

**Health check:** `curl https://your-memory-host.example.com/health` returns `{"status":"ok","service":"memory-mcp"}`.

### The `tapestry-discipline` plugin (cached locally per machine)

**Location:** `~/.claude/plugins/cache/tapestry/tapestry-discipline/<version>/`.

**What it is:** a Claude Code plugin. Contains hook scripts (`hooks/run-python.mjs` dispatcher + Python hook implementations under `scripts/`), agent files, skill files, command files, and a `plugin.json` that declares the `loom-memory` MCP.

**Why it exists:** the source of all discipline behavior. Installed once per machine; enabled per project.

**If missing:** plugin enable in `.claude/settings.json` resolves to nothing; no hooks fire.

**Install:** `/plugin marketplace add Lizo-RoadTown/tapestry`, then `/plugin install tapestry-discipline@tapestry`. (The prior `loom-discipline@lizo-loom` sourced from `Lizo-RoadTown/the-loom` still works during the transition.)

**Current version:** check `~/.claude/plugins/cache/tapestry/tapestry-discipline/` for the latest cached version. v0.1.13+ honors `LOOM_PROJECT_ID` as the scope gate; v0.1.12+ added the explicit `mcpServers.loom-memory` declaration.

### The `tapestry-patterns` plugin (cached locally per machine)

**Location:** `~/.claude/plugins/cache/tapestry/tapestry-patterns/<version>/`.

**What it is:** the canonical patterns plugin. Contains the reusable agents and skills (`documentation`, `deep-research-pattern`, `next-actions-planning`, `infrastructure-mapping`, etc.) AND the canonical architecture-snapshot scripts that consuming-project wrappers dispatch to.

**Why it exists:** Pillar 1 of the MANIFESTO — "one pattern, one home, available everywhere via reference." Skills live in the plugin, not duplicated in every repo.

**If missing:** consuming projects can still wrap their own architecture-snapshot scripts but lose access to the canonical agents and skills via the `tapestry-patterns:` namespace.

**Install:** `/plugin marketplace add Lizo-RoadTown/tapestry`, then `/plugin install tapestry-patterns@tapestry`. (The prior `liz-patterns@lizo-skills` sourced from `Lizo-RoadTown/claude-skills-marketplace` still works during the transition.)

### The Path A observer (inside the `tapestry-discipline` plugin)

**Location:** `~/.claude/plugins/cache/tapestry/tapestry-discipline/<version>/scripts/observer.py`.

**What it is:** the Stop-hook observer that parses session transcripts, counts skill invocations, dedups against `.project-intelligence/<project-id>/workflow-candidates/`, and POSTs candidates to the architecture-registry as evidence accumulates. See [The observer](/explanation/the-observer/).

**If missing:** candidates from session activity stop emitting. Manual operator POSTs become the only path into the registry.

### The self-observer Render cron

**Location:** hosted as Render cron `crn-d8n2q4ernols73d7upbg` (`self-observer`), starter plan, every 6h. Source at `services/self-observer/` (currently in `the-loom`; eventual destination `tapestry/services/self-observer/`).

**What it is:** the cross-repo drift scanner. Walks registered repos via GitHub API, applies signal rules (agent / tool / skill / orphan), emits drift candidates to the architecture-registry, writes a synthesis memo to the loom-memory MCP as `self_observer_synthesis_latest`. See [The observer](/explanation/the-observer/).

**Health check:** read `self_observer_synthesis_latest` from the MCP. Should be within the last 6 hours. If older, check the Render dashboard for the `self-observer` service.

**If down:** Pillar-1 violations (duplicates of canonical patterns in non-canonical homes) and cross-repo drift accumulate undetected.

## Environment variables

### `LOOM_PROJECT_ID`

**Where:** `.env` in your project root.

**What:** the project identifier. Kebab-case, often suffixed `-dev` for projects that may spawn an `-app` instance.

**Why:** scope gate for the discipline plugin's hooks (v0.1.12+). Tag applied to memory writes. Foreign-key into `.project-intelligence/<project-id>/`.

**Examples:** `sde-extraction-dev`, `summer-2026-hub`, `your-project-dev`.

### `OTEL_*` (OTel telemetry)

**Where:** `.env` in your project root.

**What:** OpenTelemetry credentials for telemetry export.

```
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-west-0.grafana.net/otlp
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<base64-token>
OTEL_RESOURCE_ATTRIBUTES=service.namespace=loom,deployment.environment=dev
OTEL_SERVICE_NAME=loom-discipline
```

**Why:** lets hook events flow to the same Grafana Cloud LGTM stack as other Tapestry-consuming projects, tagged with your `LOOM_PROJECT_ID`. Enables cross-project observability.

**If missing:** hooks still fire and discipline still applies. Just no telemetry export.

### `TAPESTRY_*_URL` and `LOOM_*_URL` env vars

**Where:** optional in `.env`, or set at deploy time.

**What:** override the default platform service URLs. The naming precedence is `TAPESTRY_<X>_URL` (Tapestry-aware deployments) → `LOOM_<X>_URL` (pre-Tapestry deployments) → hardcoded default.

**Examples:**

- `TAPESTRY_MEMORY_MCP_URL` or `LOOM_MEMORY_MCP_URL` — full URL of the memory MCP
- `TAPESTRY_ARCHITECTURE_REGISTRY_URL` or `LOOM_ARCHITECTURE_REGISTRY_URL` — architecture-registry base URL
- `TAPESTRY_AGENT_CONTEXT_URL` or `LOOM_AGENT_CONTEXT_URL` — agent-context base URL

**Why:** lets consuming projects point at alternate deployments (staging, alternate region, future Tapestry-hosted services) without code changes.

**If unset:** the deployment's configured default hosts apply.

## Marketplaces

### `tapestry` (canonical)

**Source:** [`https://github.com/Lizo-RoadTown/tapestry`](https://github.com/Lizo-RoadTown/tapestry). The marketplace manifest lives at the repo root in `.claude-plugin/marketplace.json`; plugins live under `integrations/claude-code/`.

**Contents:** the `tapestry-discipline` plugin and the `tapestry-patterns` plugin.

**Add to Claude Code:** `/plugin marketplace add Lizo-RoadTown/tapestry`.

### Transitional marketplaces

Two prior marketplaces remain available during the cutover window — the plugins they host were renamed + relocated into the `tapestry` marketplace on 2026-06-22 (PR #42).

- `lizo-loom` — sourced from [`https://github.com/Lizo-RoadTown/the-loom`](https://github.com/Lizo-RoadTown/the-loom) — formerly hosted `tapestry-discipline` (now `tapestry-discipline`)
- `lizo-skills` — sourced from `https://github.com/Lizo-RoadTown/claude-skills-marketplace` — formerly hosted `tapestry-patterns` (now `tapestry-patterns`) plus per-project guard plugins like `sde-extraction-guard`

Existing projects with these marketplaces registered keep working. New projects should add the `tapestry` marketplace.

## File-existence audit at session start

To audit a project for discipline-stack completeness, run from the repo root:

```sh
echo "=== Discipline stack audit ==="
test -f .mcp.json && echo "OK: .mcp.json" || echo "MISSING: .mcp.json"
test -f .claude/settings.json && echo "OK: .claude/settings.json" || echo "MISSING: .claude/settings.json"
test -f .env && echo "OK: .env" || echo "MISSING: .env"
test -d .project-intelligence && echo "OK: .project-intelligence/" || echo "MISSING: .project-intelligence/"
test -f CLAUDE.md && echo "OK: CLAUDE.md" || echo "MISSING: CLAUDE.md"
test -f scripts/architecture_snapshot.py && echo "OK: snapshot script" || echo "MISSING: snapshot script"
echo "=== LOOM_PROJECT_ID ==="
grep LOOM_PROJECT_ID .env 2>/dev/null || echo "MISSING: LOOM_PROJECT_ID in .env"
echo "=== Enabled plugins ==="
cat .claude/settings.json 2>/dev/null | grep -iE "tapestry-discipline|loom-discipline" || echo "MISSING: tapestry-discipline (or transitional loom-discipline) in settings.json"
```

If any line shows MISSING, see [Recover from common failures](/how-to/recover-from-common-failures/) for the fix.
