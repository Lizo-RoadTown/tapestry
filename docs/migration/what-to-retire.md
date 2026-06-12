# What to retire — initial retire list

Candidates for NOT importing. Reviewed when each migration is scoped — if a "retire" turns out to be load-bearing, demote it to keep.

## From `the-loom`

- **`docs/INTER_AGENT_DIALOGUE.md`** — fallback file from when MCP was unavailable. Once MCP is the canonical channel (and it has been since 2026-05-31 starter-tier upgrade), this file is provenance only
- **`docs/architecture-snapshots/`** — auto-generated artifacts from the discipline plugin; not load-bearing
- **The 5 keep-warm cron jobs** in `render.yaml` (commit 2b6b372, later reverted in commit 4b43248 once Liz upgraded to starter tier) — the cron approach was superseded by the tier upgrade

## From `Make_Skills`

- **`deprecated/lancedb-memory/`** — fully replaced by the-loom MCP in Phase 4 of the MVP migration (PR #62, merged 2026-06-10). Was the LanceDB-backed memory subsystem
- **`docs/_archive/`** — 14 pre-public-release proposals, 10 historical plans, 4 obsolete scripts, etc. Provenance only; preserved on Make_Skills' side, not re-imported to Tapestry
- **`platform/`** (probably) — legacy FastAPI app. After the MVP migration that moved runtime to `core/` + `services/`, `platform/` was largely vestigial. Confirm via PROBE before retiring
- **`chatgpt/`, `copilot/`, `vs_code/`** directories — sparse README-only stubs from an earlier cross-client-skill-export idea. The cross-client packaging concept moves to `integrations/` instead

## From `loom-platform`

- **Whether the repo itself retires** is a deferred decision. If Tapestry's `apps/web-dashboard/` absorbs the operator-facing surface AND `Lizo-RoadTown/tapestry` becomes the canonical consumer-target, `loom-platform` becomes redundant.
- **The web-starter-derived initial code** (`.env.template`, base README) — possibly retire if `templates/software-project/` covers the same shape

## From `claude-skills-marketplace`

- **The repo itself probably does NOT retire** during the prototype phase — it's the public distribution channel for the plugins. If Tapestry's `packages/cli/install` mechanism replaces the marketplace's role for loom-discipline specifically, that plugin moves; the marketplace stays for general-purpose skills.

## From `project-starter` and `web-starter` / `ux-starter` / `docs-agent` / `classroom-hub-starter`

- **Probably all retire** once `tapestry/templates/*` + `packages/cli/init` cover their job. Until then they stay primary; retire when the replacement ships and a few projects have spawned successfully through the new path.

## What this list is NOT

- A delete order. "Retire" means "don't import to Tapestry" — the source repo can still archive or stay read-only.
- Irreversible. If a "retire" turns out to have been load-bearing, the entry moves to `what-to-keep.md` and the source is preserved.

## Process for retiring a source piece

1. Confirm via PROBE that no Tapestry slot needs it
2. Confirm with operator that the legacy source can mark the piece as retired
3. Optionally: add a `RETIRED` marker file or section in the source location pointing here
4. The source repo itself isn't archived until *all* its retire decisions are confirmed AND nothing else is importing from it
