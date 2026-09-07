# Docs-site accuracy audit — consolidated findings (2026-09-06)

Four read-only agents audited all 36 `apps/docs-site` pages against the actual code. This is the consolidated, prioritized work order. Every fix cites the code that proves it. Nothing was edited during the audit.

**Verdict:** ~18 pages accurate; ~18 have findings. The dominant problem is **stale service/env names** (the `loom-*` rename + the migrations), plus a few **broken setup commands** that fail as written.

## Tier 1 — BROKEN (fails or misleads a user following it today)

| Page:line | Issue | Fix (code proof) |
|---|---|---|
| `how-to/quickstart-vscode.md:29` | `tapestry onboard my-project-name` errors — no positional arg | `tapestry onboard --slug my-project-name` (`init.py:614` requires `--slug`) |
| `how-to/quickstart-vscode.md:39` | onboarding described as best-effort; it's mandatory-blocking and the default registry URL is a placeholder | Document `--registry-url`/`TAPESTRY_REGISTRY_URL` as required; init aborts + writes nothing if registration fails (`init.py:52-54,682-690`) |
| `how-to/set-up-render.md:12,16,59` | says the Blueprint provisions Postgres and lives at repo root | It has NO `databases:` block (reuses `loom-postgres` via `LOOM_DB_URL` secret) and lives at `infra/deploy/render.yaml` (`render.yaml:14-17`) |
| `how-to/set-up-render.md:68-91` | env-group `loom-shared-secrets`; missing `LOOM_DB_URL` + `SELF_HOST_TENANT_ID` | group is `tapestry-shared-secrets` (`render.yaml:29`); add the two required secrets (`render.yaml:60,117`) |
| `how-to/set-up-render.md:116-124` | `.mcp.json` uses a nested `transport` wrapper + no auth header | flat `type`/`url` + `Bearer ${TAPESTRY_MEMORY_API_KEY}` (`.mcp.json:3-8`) |
| `how-to/set-up-a-new-project.md:176` | "`tapestry init` is future / use curl" | `tapestry init`/`onboard` ship now (`cli.py:40-49`, `pyproject.toml` v0.1.5) |
| `reference/otel-coordination-contract.md:81` | names `docs/reference/coordination-telemetry-contract.md` as canonical source of truth — file does not exist | create it, or repoint to `coordination-episode-model.md` |

## Tier 2 — WRONG FACTS (misleading, not blocking)

**Service/Postgres/cron names (cross-cutting — the `loom-*` reality):**
- `memory-mcp` → **`loom-agent-context`** (health payload `agent-context/main.py:220`; `render.yaml:304`) — `systems/memory.md:23,42,46,50,75`, `reference/platform-dependencies.md:14`, `reference/load-bearing-files.md:168`.
- `architecture-registry` → **`loom-architecture-registry`** (`render.yaml:214`) — `systems/registry.md:14`.
- `postgres` → **`loom-postgres`** (`render.yaml:11-15`) — `systems/memory.md:42,46,50`.
- `self-observer` → **`tapestry-self-observer-cron`**, and it is operator-gated (`autoDeploy:false`), not auto-running (`render.yaml:156-161,170`) — `systems/observer.md:16,48`.
- `policy-service` → the policy service (SOFT/pure-audit) — `how-to/set-up-render.md`.

**Env-var names:**
- `systems/observer.md:54-59` — real vars: `LOOM_MEMORY_URL`, `TAPESTRY_ARCHITECTURE_REGISTRY_URL`||`LOOM_ARCHITECTURE_REGISTRY_URL`, `TAPESTRY_REGISTRY_URL`, `OBSERVER_JWT`, `GITHUB_TOKEN`, `TAPESTRY_PROJECT_ID` (`config.py:139-185`). Drop `MEMORY_BASE_URL`/`CANDIDATE_REGISTRY_URL`/`OTEL_*` (observer emits no OTel).
- `systems/observatory.md:36-38,55` — phantom `MEMORY_BASE_URL`/`REGISTRY_BASE_URL`/`OBSERVATORY_AUTH_*`; the only data-source var is `COORDINATION_EVENTS_URL` (`episodes.json.ts:14`).
- `systems/registry.md:63,84` — `BRIDGE_HMAC_SECRET` → **`LOOM_SKILL_BRIDGE_SECRET`** (`bridge_hmac.py:73`, `render.yaml:230`).
- `systems/telemetry.md:56,74,86` — the OTel stream defaults to **`loom-discipline`**, not `tapestry-discipline` (`_observability.py:225,239`); and `telemetry_client.py` is a stub with no Loki query.

**Data-source model:**
- `systems/observatory.md:13-28` — the console reads a single `/api/episodes.json` (← `COORDINATION_EVENTS_URL` → `~/.claude/logs/hooks.jsonl` → bundled sample), NOT Memory + the registries, and has no approve/reject write path (`episodes.json.ts:12-37`).

**`.project-intelligence/<project-id>/` is fiction** — the CLI writes the JSON files FLAT under `.project-intelligence/` (`init.py:337-376`) — `how-to/set-up-a-new-project.md:98-146`, `how-to/quickstart-vscode.md:36`, `reference/load-bearing-files.md:89-104,132`, `start/your-first-project.md:16`, `how-to/recover-from-common-failures.md:74`.

**Onboarding footprint:**
- `start/your-first-project.md:39` — "onboarding does not author `CLAUDE.md`" is WRONG; it seeds one from a template (`init.py:570-573`).
- `start/your-first-project.md:10` — "writes four files" undercounts (also `CLAUDE.md`, `.gitignore`, `docs/`, `skills/`; `init.py:562-609`).

**Small factual errors:**
- `explanation/discipline-stack.md:70` — upskilling audit is **CORE DIRECTIVE 3**, not 2 (`stop_audit.py:139`, CLAUDE.md).
- `explanation/memory-mcp.md:29` — "Six categories" → **Ten** (its own table lists 10).
- `explanation/plugins.md:25` — plugin declares **two** MCP servers (`loom-memory` + `tapestry-docs`, `plugin.json:26-38`).
- `explanation/plugins.md:48` — add the **`roadmap-maintenance` agent** + **`changelog-entry` skill** (new in patterns 0.1.6).
- `explanation/plugins.md:30` — Stop threshold is git OR (≥10 tools AND ≥3 turns) OR ≥30 turns (`stop_audit.py:244-259`).
- `systems/observer.md:13` — `liz-patterns:` → **`tapestry-patterns:`** (plugin renamed).

## Tier 3 — STALE / incomplete (low)

- `explanation/architecture-snapshots.md:62-88` — SessionStart runs the **canonical** snapshot script from the tapestry-patterns plugin with `--repo-root`, not a per-repo `scripts/architecture_snapshot.py`; log keys are `patterns_scripts_unresolved`/`canonical_snapshot_script_absent`/`snapshot_script_error` (`session_start.py:310-434`). Load-bearing dependency = the plugin installed, not a per-repo file.
- `reference/load-bearing-files.md:96-98,182` — missing `local-skills/`+`lessons-learned/` subdirs (`init.py:378`); inconsistent LOOM_PROJECT_ID version marker (v0.1.12 vs v0.1.13).
- `observatory/feed.md:38-52` — response shape omits the `trends` key (`episodes.json.ts:73`).
- Version/count examples drift: `plugins.md:148` (0.1.15 → 0.1.19), `set-up-vercel.md:76` ("37 pages").

## Accurate (no changes)
set-up-claude-code, set-up-github, set-up-vercel, set-up-grafana-cloud, create-your-own-plugin, recover-from-common-failures (minor), the-memory, the-observer, why-memory-is-built-this-way, shared-language, docs-mcp, docs.mdx, first-observatory-visit, verify-it-worked, what-stays-on-track, what-tapestry-is-not, observatory/about, observatory/feed (minor), observatory/run-it.

## Cross-cutting root causes (fix once, apply everywhere)
1. **The `loom-*` service names** — a single find/replace pass across systems/ + reference/ + how-to/set-up-render, keyed off `render.yaml` + service READMEs.
2. **`.project-intelligence/` is flat, not per-project-id** — 5 pages.
3. **The `.mcp.json` canonical block** (flat `type`/`url` + env-ref `Authorization` header) — 3 pages.
4. **Doc-vs-reality on self-observer**: `services/self-observer/README.md:3` still says "Not yet deployed from Tapestry", but the operator created + ran the cron this session — the README (not a docs-site page) is now stale too; update it to "deployed (operator-gated cron live)".

## Recommended fix approach
Land as **one docs-fix PR** (or two: Tier 1 blockers first, then Tier 2/3), reviewed before merge, then deploy to the live site (Vercel). The cross-cutting root causes (§) are the efficient starting point — they resolve most Tier-2 findings in a few sweeps.
