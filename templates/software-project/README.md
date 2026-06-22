# `templates/software-project/`

**Status:** Populated — Step 5b (templates assembly), first template, 2026-06-21.

Seed template for a software-dev consuming project (web/app shape). Clone the directory, fill the `{{PLACEHOLDER}}` tokens, and you have a Tapestry-wired project: loom-memory MCP, file-protocol memory, and the discipline plugin all pre-configured.

## What's here

Assembled from `project-starter/templates/` — the canonical scaffold source — by combining the shared `_common` base with the `ui-app` variant overlay:

| File | From | Purpose |
|---|---|---|
| `CLAUDE.md` | `_common` | Project instructions (placeholder-driven: `{{PROJECT_NAME}}`, `{{FRONTEND}}`, …). Auto-loaded every session. |
| `CLAUDE.md.extension` | `ui-app` | UI-app-specific additions to append to `CLAUDE.md`. |
| `SKILLS.md` | `ui-app` | Skills relevant to a UI/web project. |
| `.mcp.json` | `_common` | Wires the loom-memory MCP (`loom-agent-context.onrender.com`). |
| `.gitignore` | `_common` | Standard ignores (incl. `.env`, secrets). |
| `scripts/seed-memory.{sh,ps1}` | `_common` | Bootstraps the file-protocol memory hierarchy. |
| `docs/UX_CONTRACT.md` | `ui-app` | UX contract doc for UI projects. |

## Decision: assembly (not lift, not rewrite)

`project-starter/templates/` is itself a curated, placeholder-driven scaffold — not a "full starter app." So this is closer to a **lift of the relevant template slices** than a from-scratch rewrite. Files are copied faithfully from `project-starter`; only the README (this file) is new.

## Taxonomy note (open for the other three kinds)

`project-starter` splits templates by **app-type** (`ui-app`, `agent-app`); Tapestry's `templates/` slots split by **domain** (`software` / `classroom` / `research` / `operations`). These are orthogonal axes. `software-project ← _common + ui-app` is the clearest mapping. The remaining three (`classroom`/`research`/`operations`) need their domain source repos resolved (see `docs/migration/import-map.md` Step 5b row) before assembly.

## Provenance

- `project-starter/templates/_common/` + `project-starter/templates/ui-app/`
- Companion: `packages/cli/` (Step 5a) — the `loom` CLI that wires projects post-clone.
