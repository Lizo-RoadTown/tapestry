# Legacy repo inventory

Per-repo audit of what exists, what's worth keeping, what's worth retiring. Initial pass written 2026-06-12; not exhaustive.

## `Lizo-RoadTown/the-loom` (private)

**Role:** Platform substrate prototype.

**Live services on Render:**

- `loom-agent-context.onrender.com` — Agent Context MCP (memory)
- `loom-project-registry.onrender.com` — Project Registry
- `loom-project-observatory.onrender.com` — Project Observatory
- `loom-architecture-registry.onrender.com` — Candidate / Architecture Registry
- `loom-policy.onrender.com` — Policy Service (just shipped 2026-06-12)

**In flight:**

- Phase 6 upskilling dashboard build at `apps/web-dashboard/` (started 2026-06-12 evening)
- Plugin v0.1.12 (`adapters/claude-code/loom-discipline/`) with Stop hook + observer

**Worth keeping (probable Lifts or Refactors):**

- Service implementations (project-registry, agent-context, observatory, architecture-registry, policy)
- Migrations under `services/*/migrations/`
- Render deploy configs (`render.yaml`)
- The discipline plugin (`adapters/claude-code/loom-discipline/`)
- The Architecture proposal docs (`docs/proposals/`)
- The scaffolder (`scripts/new-loom-project.ps1`) — likely Refactor into `packages/cli/`

**Worth reviewing (Refactor candidates):**

- The split between `architecture-registry` (durable structure) and the candidate-registry concept (pending Liz's call)
- The dashboard's framing (operator dashboard vs observability platform) — actively being reframed
- Inter-service auth: each currently uses its own JWT + SELF_HOST_TENANT_ID fallback; should consolidate to `packages/auth/`

**Worth retiring (probable):**

- `docs/INTER_AGENT_DIALOGUE.md` (fallback file from when MCP was down)
- Architecture snapshots (auto-generated artifacts; not load-bearing)

## `Lizo-RoadTown/Make_Skills` (public)

**Role:** Engine prototype.

**Already public-released** as initial module 2026-06-10. Apache 2.0 licensed.

**Worth keeping (probable Lifts):**

- `core/` engine modules (providers, orchestration, auth, db, runtime, skill_making, observability, tools)
- `adapters/{development,classroom,research-project}/default-seed/` — canonical seed templates (shipped 2026-06-12)
- `adapters/<type>/README.md` — adapter contracts
- `services/skill_making/bridge_receiver.py` — stub for Phase 4
- `skills/` + `skills_private/` — the methodology skill library (16 skills)
- `subagents/` — 4 named subagent definitions
- `docs/proposals/2026-05-31-three-layer-engine-spec.md` — canonical spec
- `docs/proposals/2026-05-25-skill-making-bridge.md` — wire contract for bridge

**Worth reviewing:**

- `platform/` legacy (still ships the FastAPI app + LangChain wiring). After the MVP migration that consolidated runtime to `core/` + `services/`, `platform/` may be ready to deprecate
- `chatgpt/`, `copilot/`, `vs_code/` directories — sparse; their purpose vs `integrations/` in Tapestry

**Worth retiring (probable):**

- `deprecated/lancedb-memory/` — fully replaced by the-loom MCP
- `docs/_archive/` — historical; useful for provenance but not load-bearing

## `Lizo-RoadTown/loom-platform` (public)

**Role:** Consumer prototype seed.

**Status:** Seeded 2026-06-10 from `web-starter`. README + CLAUDE.md + `.env.template` + `.project-intelligence/` + 16 methodology skills bundled. NO app code yet.

**Worth keeping:**

- The seed pattern itself (proven works for `templates/` shape)
- The `.project-intelligence/loom-platform-dev/` structure (informs default-seed/ canonical shape)

**Worth retiring (probable):**

- The repo itself eventually — its role gets absorbed by `tapestry/apps/web-dashboard/` once that's the operator-facing surface. Decision deferred.

## Consuming-project prototypes

| Repo | Role | Worth keeping |
|---|---|---|
| `Summer 2026 Hub` (private) | Classroom prototype | `.project-intelligence/` two-instance pattern (`ime4020-hub-dev` + `ime4020-hub-app`); the seed shape generalized into `Make_Skills/adapters/classroom/default-seed/` |
| `SDE_Extraction` (private) | Research prototype | Same pattern; informed `Make_Skills/adapters/research-project/default-seed/` |
| `humancensys-app` (private) | Public-user-facing prototype | Auth.js + Next.js patterns; informs `apps/` framework choices |

These don't get imported. They're examples of consuming projects. Their PATTERNS migrate; their CONTENT stays project-specific.

## `Lizo-RoadTown/claude-skills-marketplace` (public)

**Role:** Public plugin marketplace.

**Worth keeping:**

- The three plugins (`onboarding-psychologist`, `ai-agents-architect`, `loom-discipline`) — they migrate as `tapestry/packages/cli/` distributions OR remain in claude-skills-marketplace as the public distribution channel
- The publishing workflow

**Decision:** Whether `claude-skills-marketplace` absorbs into Tapestry or remains a separate public-distribution repo is **open**. The discipline plugin in particular benefits from being in the marketplace for one-command-install.

## `Lizo-RoadTown/project-starter` + template repos

**Role:** Day-1 scaffolding.

**Status:** Per [`project_loom_as_umbrella_public_release_eventual`](https://loom-agent-context.onrender.com), eventually retired once Tapestry's `templates/` + `packages/cli/` cover the same ground.

**Worth keeping:**

- The templates' shape (each `*-starter` repo has one template kind)
- The placeholder convention (`{{project-slug}}`, etc.)

**Worth retiring (probable):**

- The repos themselves once `tapestry/templates/` + `packages/cli/init` handle the same job

## What's NOT yet inventoried

- Auth-related secrets, env vars, and tenant configs across services (each service has its own; needs consolidation review)
- Test artifacts per repo
- Build artifacts per repo
- CI/CD per repo (some have `.github/workflows/`, some don't)
- Each repo's `CHANGELOG.md` (provenance only; not load-bearing)

These get inventoried as each section's import is proposed.
