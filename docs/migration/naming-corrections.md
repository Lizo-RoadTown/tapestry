# Naming corrections to apply on import

Names that drifted during prototyping. When a piece imports to Tapestry, apply these renames.

## Known drift

### 1. "Pillar 2" → "the upskilling dashboard"

**Where it appears:** `Make_Skills/skills_private/agentic-upskilling/SKILL.md` (4 sites), `Make_Skills/docs/proposals/2026-06-12-bridge-receiver-and-compiler-phase-4-sketch.md` (1 site), the-loom's prior docs (largely already swept in PRs #9 + #13).

**On import:** rename to "the upskilling dashboard" wherever the reference is to the PAGE / SURFACE. Leave alone where the reference is to the conceptual three-pillar framework (Pillar 1 / 2 / 3 as a marketing framework).

**See:** loom-memory `naming_upskilling_dashboard_supersedes_atelier_2026_06_12`.

### 2. "Atelier" → "the upskilling dashboard"

**Where it appears:** `Make_Skills/skills_private/agentic-upskilling/SKILL.md` (4 sites that were renamed to Atelier in PR #68, before Liz superseded Atelier with the descriptive name), `Make_Skills/docs/proposals/2026-06-12-bridge-receiver-and-compiler-phase-4-sketch.md` (1 site).

**On import:** rename to "the upskilling dashboard."

**See:** loom-memory `feedback_prefer_descriptive_names_over_branded_for_internal_things`.

### 3. `make-skills-discipline` → `tapestry-discipline`

**Where it appears:** `Lizo-RoadTown/claude-skills-marketplace/plugins/make-skills-discipline/`, various references to "make-skills-discipline plugin" in CLAUDE.md and docs.

**On import:** rename to `tapestry-discipline` wherever the reference is the PLUGIN. The plugin folder, its `plugin.json` name field, its install command, its scope-check string — all rename.

**Caveat:** the public marketplace may keep both names callable for a while during transition. Coordinate with operator before deleting the `make-skills-discipline` registration.

### 4. `loom-observability` → `loom-project-observatory`

**Where it appears:** Render service name, `render.yaml` references, doc references. Mostly already swept in the-loom's PR #2 (commit 293da94, 2026-06-01).

**On import:** verify all doc references use `loom-project-observatory`. The service-on-disk is `services/project-observatory/` (already renamed).

### 5. Pillar 0 / Pillar 1 / Pillar 1b — generally retire

**Where it appears:** Throughout `Make_Skills/` legacy docs as the never-shipped product's three-pillar marketing framework.

**On import:** these are pre-public-release framing. Most are already archived to `Make_Skills/docs/_archive/`. The ones outside `_archive/` should generally be reframed in terms of the actual architecture (the three-layer engine model) without the pillar labels.

**See:** loom-memory `project_make_skills_was_skeleton_never_shipped`.

### 6. Tapestry positioning

**Earlier framing:** "Tapestry = public end-user product, distinct from the platform."

**Current framing:** "Tapestry = enterprise system-of-record monorepo containing apps + services + engine + everything."

**On import:** Any doc that says "Tapestry is for end-users" or implies Tapestry is a single application — rewrite to reflect that Tapestry is the whole platform monorepo. The OPERATOR-facing dashboard and the END-USER-facing apps both live in Tapestry under `apps/`.

**See:** loom-memory `tapestry_redefined_as_enterprise_monorepo_2026_06_12` + `feedback_tapestry_parallel_build_not_pause_and_migrate_2026_06_12`.

## Process for adding a new correction

1. Spot the drift during a migration scoping
2. Add a new section here with the same shape (Where it appears / On import / See)
3. Reference this doc in the migration PR so the rename happens at import time

## What this list is NOT

- A retrofit-prototype list. We do NOT sweep the source repos to apply these names (except where already done in dedicated rename PRs). The corrections apply on import.
- A blocker. A migration can proceed with renames applied inline; no separate naming-PR is required.
