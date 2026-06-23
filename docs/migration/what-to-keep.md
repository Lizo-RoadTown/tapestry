# What to keep — initial keep list

Candidates for migration (per [`legacy-repo-inventory.md`](legacy-repo-inventory.md)). Reviewed and refined as each piece is scoped for actual import.

## From `the-loom`

- **Deployed services** (`services/agent-context/`, `services/project-registry/`, `services/architecture-registry/`) — production-validated. NOTE (2026-06-18): `services/policy/` is deployed but **inert** (records decisions, doesn't write status); `services/project-observatory/` is a **23-line `/health` stub** (Phase-6 content built in Tapestry, not lifted). Don't treat all five as mature substance.
- **Migrations** under each `services/*/migrations/` — durable schema history
- **Render deploy configs** (`render.yaml`) — adapt to Tapestry layout
- **The discipline plugin** (`adapters/claude-code/loom-discipline/`) — v0.1.13 with Stop hook + observer
- **The Project Observatory Grafana dashboards** — if shipped as JSON in repo
- **Architecture proposal docs** (`docs/proposals/`) — provenance for the architecture model
- **The scaffolder** (`scripts/new-loom-project.ps1`) — gets Refactored into `packages/cli/`

## From `Make_Skills`

- **`core/` modules** — providers, orchestration, auth (tenant ContextVar + secrets), db, runtime, skill_making, observability, tools
- **`adapters/{development,classroom,research-project}/default-seed/`** — canonical seed templates (just shipped 2026-06-12 in PR #67)
- **`adapters/<type>/README.md`** — adapter contracts
- **`services/skill_making/bridge_receiver.py`** — Phase 4 stub
- **`skills/` + `skills_private/`** — methodology skill library (16 skills)
- **`subagents/`** — 4 named subagent definitions
- **`docs/proposals/2026-05-31-three-layer-engine-spec.md`** — canonical spec
- **`docs/proposals/2026-05-25-skill-making-bridge.md`** — wire contract
- **`docs/proposals/2026-06-12-bridge-receiver-and-compiler-phase-4-sketch.md`** — Phase 4 sketch (just merged in PR #66)

## From `loom-platform`

- **The seed pattern shape** — already informed `Make_Skills/adapters/default-seed/`; cross-reference

## From consuming-project prototypes (Hub, SDE, humancensys-app)

- **PATTERNS, not content.** The `.project-intelligence/` two-instance shape, the seed bundling pattern, the project-context.json structure
- The hub's embedded-agent design spec — informs `apps/` framework choices

## From `claude-skills-marketplace`

- **The three plugins**: `tapestry-discipline`, `ai-agents-architect`, `onboarding-psychologist`
- **The publishing workflow** — adapts to Tapestry distribution

## From `project-starter` + template repos

- **The placeholder convention** (`{{project-slug}}`, etc.) — already in Tapestry's planned `templates/`
- **The template shapes** — adapt into `tapestry/templates/`

## What this list is NOT

- A commitment to import any of these on a specific timeline. Each one waits for the operator's go-ahead.
- A blocking list. Items can be added or removed as Tapestry's architecture clarifies.
- A complete inventory. New worth-keeping items surface as more PROBE happens.
