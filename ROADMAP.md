# Tapestry roadmap

What's in flight (in the legacy prototype repos), what migrates to Tapestry when, and the build order the operator ratified.

## Where active development happens TODAY

| Project | Repo | What's in flight |
|---|---|---|
| Platform substrate | `Lizo-RoadTown/the-loom` | Phase 6 (upskilling dashboard) build in flight at `the-loom/apps/web-dashboard/`. Phases 0-5 done + live. |
| Engine | `Lizo-RoadTown/Make_Skills` | Phase 4 bridge_receiver parked. Default-seed/ canonical shipped. Skills library bundled. |
| Consumer seed | `Lizo-RoadTown/loom-platform` | Seeded; no app code yet. |
| Consuming projects | Hub, SDE_Extraction, humancensys-app, etc. | Each in their own repo |

**Active development continues in these repos.** Tapestry imports happen LATER, per-piece, when each piece has stabilized.

## The build order (engine first, UI last)

Per the outside-agent recommendation Liz ratified on 2026-06-12, and per the `feedback_engine_before_ui_no_potemkin_systems` discipline rule:

1. **Identity / tenant / project model**
2. **Project Registry**
3. **Agent Context / Memory**
4. **Session-end upskilling report enforcement**
5. **Local Observer**
6. **Candidate Registry**
7. **Promotion Governance** (manual first)
8. **Skill-Making Bridge**
9. **Skill Compiler**
10. **Usage Telemetry**
11. **Demotion Review**
12. **UI**

Steps 1-7 already exist in `the-loom` as Phase 0-5 work. Steps 8-9 exist in `Make_Skills` (8 as stub, 9 as working compiler). Steps 10-11 partial. Step 12 just starting in `the-loom/apps/web-dashboard/`.

**The build order tells Tapestry imports their order, not their schedule.** Each step migrates when its source has matured.

## Migration sequencing — what's ready vs. not ready for Tapestry

| Step | Source location | Maturity | Import target | Status |
|---|---|---|---|---|
| 1. Identity / tenant / project model | `the-loom/services/project-registry/` | Live, smoke-verified | `tapestry/services/project-registry/` | **Not ready** — still in active use; experimentation ongoing |
| 2. Project Registry | same as above | same | same | same |
| 3. Agent Context / Memory | `the-loom/services/agent-context/` (live as MCP) | Live, in production use | `tapestry/services/agent-context/` | **Not ready** |
| 4. Session-end upskilling enforcement | `the-loom/adapters/claude-code/loom-discipline/scripts/stop_audit.py` | Plugin v0.1.12 live | `tapestry/integrations/claude-code/` + `tapestry/services/audit-log/` | **Not ready** |
| 5. Local Observer | `the-loom/adapters/claude-code/loom-discipline/scripts/observer.py` | Live | `tapestry/engine/local-observer/` | **Not ready** |
| 6. Candidate Registry | `the-loom/services/architecture-registry/` | Live, deployed on Render | `tapestry/services/architecture-registry/` + `tapestry/services/candidate-registry/` | **Not ready** — split decision (registry vs candidate-registry) pending |
| 7. Promotion Governance | `the-loom/services/policy/` | Live, smoke-verified | `tapestry/services/policy/` | **Not ready** |
| 8. Skill-Making Bridge | `Make_Skills/services/skill_making/bridge_receiver.py` (stub) + bridge spec | Stub only; spec ratified | `tapestry/services/skill-making/` | **Not ready** — Phase 4 parked until Phase 3 candidates flow |
| 9. Skill Compiler | `Make_Skills/core/skill_making/compiler.py` | Working | `tapestry/engine/skill-compiler/` | Could import sooner; depends on operator priority |
| 10. Usage Telemetry | `the-loom/services/project-observatory/` + plugin observatory hooks | Partial | `tapestry/services/telemetry-ingestion/` + `tapestry/services/project-observatory/` | **Not ready** |
| 11. Demotion Review | Not built yet | n/a | `tapestry/services/policy/` (extension) | **Not built anywhere** |
| 12. UI | `the-loom/apps/web-dashboard/` | Just starting (2026-06-12) | `tapestry/apps/web-dashboard/` | **Active development** — wait until mature |

## Per-slot status

See each slot's `README.md` (e.g., `apps/web-dashboard/README.md`) for the specific source-and-status detail.

## Open decisions

| Decision | Owner | When |
|---|---|---|
| Tapestry repo visibility (currently private) | Liz | When migration completes or stabilizes |
| Tapestry-platform-agent vs multiple agents | Liz | When work in Tapestry starts ramping |
| Each piece's import timing | Liz, case-by-case | As pieces mature |
| Tapestry-agent spawn | Liz | When Tapestry is ready for an owner-agent |
| Security-review-agent spawn | Liz | Before any tool of kind `inline_tool`/`external_tool` touching FS/network/shell gets promoted |

## What's intentionally NOT in this roadmap

- A migration deadline. Per Liz's correction ([`tapestry_redefined_as_enterprise_monorepo_2026_06_12`](https://loom-agent-context.onrender.com) — see memory), this is parallel-build; deadlines would force premature consolidation.
- A commitment to where `loom-platform` lands. Absorption-or-keep decision deferred.
- A commitment that all 5 repos archive after migration. Some may remain useful indefinitely.
