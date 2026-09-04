# `services/self-observer/`

**Status:** Migrated into Tapestry from the-loom legacy source (CORE DIRECTIVE 2 Lift/Refactor). Stands alone — GitHub API scan + HTTP POST only, no runtime dependency on the-loom or Make_Skills. Not yet deployed from Tapestry; a staging cron block is drafted in `infra/deploy/render.yaml` (`tapestry-self-observer-cron-staging`, `autoDeploy: false`).

## What this is

A Render cron service that periodically scans the platform's own skill / agent / tool registries across multiple repos, detects category-drift candidates (skill that should be an agent, skill that should be a tool, agent that should be a skill, orphan skill never invoked), and emits them as candidates to the architecture-registry's existing `POST /candidates` endpoint. The operator sees them in the upskilling dashboard and clicks promote / hold / reject.

This is the INPUT side of the recursive-skill-engine loop — it observes the platform's OWN structure.

## What changed in the Tapestry migration

1. **De-coupled from the-loom.** No imports of or references to the-loom source paths. The service talks to GitHub and two Tapestry HTTP services by URL.
2. **Endpoints are env-driven** (`config.Endpoints.from_env`), defaulting at the existing deployed services so restored data appends to what is already there:
   - architecture-registry (candidate POST): `TAPESTRY_ARCHITECTURE_REGISTRY_URL` || `LOOM_ARCHITECTURE_REGISTRY_URL`, default `https://loom-architecture-registry.onrender.com`.
   - project-registry (discovery): `TAPESTRY_REGISTRY_URL` || `LOOM_PROJECT_REGISTRY_URL`, default `https://loom-project-registry.onrender.com`.
3. **Scan targets are registry-driven** (see below). The static per-repo list is gone.

## Scan targets = static core + dynamic discovery

Built each pass by `registry_client.build_scan_targets`:

- **Static core** (`config.static_core_targets`, always scanned):
  - `Lizo-RoadTown/tapestry` — `integrations/claude-code/tapestry-patterns/skills`, `integrations/claude-code/tapestry-patterns/agents`, `engine`
  - `Lizo-RoadTown/claude-skills-marketplace` — `plugins` (walked recursively; `plugins/*/skills` + `plugins/*/agents` land underneath)
- **Dynamic** (`registry_client.discover_dynamic_targets`): `GET {project-registry}/projects` → for each project, `GET {project-registry}/projects/{id}/repos`. Each returned repo (registry `Repo` model: `url` + `default_branch`, `services/project-registry/models.py:87-93`) is scanned using the convention paths in `config.CONSUMING_REPO_DEFAULT_PATHS` (`skills`, `agents`, `.claude/skills`, `.claude/agents`, `plugins`).

The static core is **de-duped** against discovered repos by slug (case-insensitive), so tapestry/marketplace are never scanned twice.

Everything except the repo list stays config-driven: `SIGNAL_WEIGHTS`, `EMIT_THRESHOLD`, `EXCLUDE_PATH_PATTERNS`, skip-self, and the consuming-repo path set.

## Auth

Two independent tokens, both env-driven (`config.AuthConfig.from_env`):

- **`GITHUB_TOKEN`** → `Authorization: Bearer` on the GitHub contents API, so PRIVATE consuming repos (e.g. class repos) are readable. Absent → public-only scan at a low rate limit. A repo/path that 403s or 404s is logged and skipped — one unreadable repo never crashes the pass.
- **`OBSERVER_JWT`** → `Authorization: Bearer` on BOTH Tapestry services (project-registry discovery + architecture-registry emission + memory). Unset → no header → the receiver resolves the request to its `SELF_HOST_TENANT_ID` (self-host mode). This is the existing `auth_bridge.verify_bearer` contract, not a new scheme.

## Project ids

The candidate schema requires a `project_id` (UUID). Resolved per entry (`config.project_id_for`):
- discovered repos carry the project id from the registry;
- static-core marketplace uses its known id (env override `MARKETPLACE_PROJECT_ID`);
- static-core tapestry uses `TAPESTRY_PROJECT_ID` if set, else the platform default;
- fallback: `TAPESTRY_DEFAULT_PROJECT_ID`, else a baked platform-tenant UUID (so restored candidates land where the dashboard already reads).

## Wire contract

POSTs to `{architecture-registry}/candidates` using the existing `CandidateCreate` schema:

```json
{
  "project_id": "<uuid>",
  "source_path": "path_b",
  "candidate_type": "agent",
  "instance_id": "<repo>/<path>",
  "evidence_refs": [{"kind": "self_observation", "source_repo": "...", "file_path": "...", "description_text": "...", "signal_match": "...", "current_kind": "skill"}],
  "signals": {"confidence": 0.85, "matched_rules": ["..."]}
}
```

## Dedup

Candidate identity = `content_hash(candidate_type + source_repo + description_text)`. Within a repo, identical description+kind collapses (re-scans don't duplicate). Across repos, same description + same body dedups; same description + different body stays separate (`source_repo` is part of the hash).

## Skip-self

The observer's own agent file is excluded from emission by `migration_destination:` prefix (canonical) OR by name pattern (`agentic-upskilling`, `self-observer`) as a belt-and-suspenders fallback.

## Local development

```bash
cd services/self-observer
pip install -r requirements.txt -r requirements-test.txt

pytest tests/                          # unit tests (signal rules, synthesis, memory, discovery, scanner)

python main.py --dry-run               # scan via GitHub + discovery, log candidates, no POSTs
python main.py --no-discovery --dry-run  # static core only, no registry call
python main.py --local <root> --dry-run  # scan a local filesystem tree instead of GitHub (offline)
```

`--local` reads `<root>/<repo_name>/<paths>/` from disk — the fully offline path used by the smoke test and the scanner unit tests. Discovery targets remote repos, so `--local` uses the static-core layout only.

## Schedule

Production intent: every 6h (`0 */6 * * *`), matching the project-observatory cron cadence. Deployed as a `type: cron` `runtime: python` service. Staging block: `infra/deploy/render.yaml` → `tapestry-self-observer-cron-staging`.

## Provenance

- the-loom: `services/self-observer/` (retired legacy source).
- Sibling migrations followed the same shape: `services/project-observatory/`, `services/telemetry-ingestion/`.
