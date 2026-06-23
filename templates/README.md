# `templates/`

Seed templates for new consuming projects. Each is a placeholder-driven scaffold (`{{PROJECT_NAME}}`, `{{FRONTEND}}`, …) that comes Tapestry-wired out of the box: loom-memory MCP (`.mcp.json`), file-protocol memory (`scripts/seed-memory.*`), and the `tapestry-discipline` plugin.

## Two-axis layout: domain × shape

Templates are organized on **two axes**:

- **Domain** (the outer dir) — what kind of project: `software` / `classroom` / `research` / `operations`.
- **Shape** (the inner dir) — its technical form: `ui` (web/frontend app) or `agent` (agent app with a durable memory backbone).

```
templates/
  <domain>-project/
    README.md            # domain overview + which shape to pick
    <DOMAIN>_GUIDE.md     # domain-specific guidance (classroom/research only)
    ui/                  # self-contained scaffold, UI shape
    agent/               # self-contained scaffold, agent shape
```

A domain and a shape are independent: a classroom project can be a `ui` app or an `agent` app; so can a research project. That orthogonality is why the two axes are kept separate rather than collapsed into one list.

## What each shape leaf contains

Each `<domain>-project/<shape>/` is **self-contained** — clone that one directory and you have a working scaffold, no merge step:

| File | Axis | Purpose |
|---|---|---|
| `CLAUDE.md` | base | Project instructions (placeholder-driven). Auto-loaded every session. |
| `.mcp.json` | base | Wires the loom-memory MCP. |
| `.gitignore` | base | Standard ignores (incl. `.env`, secrets). |
| `scripts/seed-memory.{sh,ps1}` | base | Bootstraps the file-protocol memory hierarchy. |
| `CLAUDE.md.extension` | shape | Shape-specific additions to append to `CLAUDE.md`. |
| `SKILLS.md` | shape | Skills relevant to this shape. |
| `docs/UX_CONTRACT.md` | shape (`ui` only) | UX contract for UI projects. |

The base files are embedded in every leaf by design (self-contained clone-and-use). The domain guide lives once at the domain root (`<domain>-project/<DOMAIN>_GUIDE.md`), shared across both shapes.

## Provenance

Assembled from `project-starter/templates/` — the canonical scaffold source (`_common` base + `ui-app`/`agent-app` shape overlays) — reconciled onto Tapestry's domain × shape taxonomy. Domain guidance for classroom/research is grounded in `classroom-hub-starter` and `SDE_Extraction` respectively. See [`../docs/migration/import-map.md`](../docs/migration/import-map.md) (Step 5b).

Companion: [`../packages/cli/`](../packages/cli/) — the `loom` CLI that registers + wires a project after clone.

## Status

| Domain | `ui` | `agent` | Notes |
|---|---|---|---|
| `software-project` | ✅ | ✅ | Generic; no domain guide (software is the default case). |
| `classroom-project` | ✅ | ✅ | Domain guide from `classroom-hub-starter`. |
| `research-project` | ✅ | ✅ | Domain guide from `SDE_Extraction`. |
| `operations-project` | — | — | **Deferred** — no source repo identified yet (operator decision, 2026-06-21). Slot only. |
