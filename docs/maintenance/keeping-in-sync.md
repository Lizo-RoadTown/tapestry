# Keeping machines, plugins, and configs in sync

Some Tapestry changes have blast radius beyond the repo — they need propagating to each machine, or they set up a state that drifts if unmaintained. This is the living checklist of what to update after a change, and the standing things to keep in sync. Update this doc when a new drift point appears.

## Why this exists

Plugins install **per machine** (user scope), not per repo. Credentials live in machine-wide and per-repo config. A version bump or a token rotation is not "done" when it merges — it's done when every machine and consumer has it. Without a checklist, that propagation is silent and easy to forget (see the loom-memory outage recorded in loom-memory `loom_memory_expired_literal_jwt_global_config_2026_09_05`: a machine-wide config carried an expired token for 9 days).

## After a change — propagate it

| Change | What it affects | What to do |
|---|---|---|
| **Plugin version bump** (`tapestry-patterns`, `tapestry-discipline`) | Every machine's installed plugin is now behind | On **each machine**: run `scripts/catch-up-machine.ps1`, then **restart Claude Code**. New agents/skills aren't usable until then. **Also update any project-scoped install** (see the project-scope drift point below) — the script only does user scope. |
| **New machine** onboarded | Its machine-wide `~/.claude.json` may lack loom-memory, or carry a literal token | Ensure `~/.claude.json` → `mcpServers/loom-memory` → `Authorization` is `Bearer ${TAPESTRY_MEMORY_API_KEY}` (env-ref, never a literal JWT). Run `catch-up-machine.ps1` for plugins. |
| **New skill or agent** in a plugin | Consumers can't invoke it until they update | Bump the plugin version (the CI guard requires `marketplace.json` == `plugin.json`), then propagate per "Plugin version bump". |
| **Runtime PR** (`services/`, `engine/`, `infra/migrations/`, `apps/`, `packages/`, `integrations/`) | The change trail | Add a `docs/changelog/` entry in the same PR (the `changelog-entry` skill; the advisory `changelog-check.yml` nudges if missing). |
| **Service migration merged** | The legacy service still deploys until cutover | Follow that service's README "Cutover" (verify live schema/tenant, enable the `render.yaml` block, ensure the-loom stops deploying it — ONE-BLUEPRINT). |
| **Credential / token rotation** | Every machine using it | Now that configs are env-ref, update the value in ONE place per machine: `~/.claude/settings.json` (and the shell env). Do not paste literals into `.mcp.json` or `~/.claude.json`. |

## Standing drift points — check periodically

- **Machine-wide `~/.claude.json`** — loom-memory header must be env-ref, not a literal JWT. tapestry-cli (v0.1.4+) writes env-ref into onboarded **projects**; the **machine-wide** config is a once-per-machine migration that predates the CLI and must be done by hand.
- **Plugin versions across machines** — `scripts/catch-up-machine.ps1` is the one command that catches a machine up (it refreshes the marketplace catalog, updates both Tapestry plugins, then every other installed plugin). Run it on any machine that's been idle while the marketplace moved forward; restart after.
- **`ROADMAP.md`** — kept current by the `tapestry-patterns:roadmap-maintenance` agent as work ships; reconcile it when it lags reality.
- **Per-repo `.mcp.json`** — env-ref loom-memory header, valid JSON, no UTF-8 BOM (a BOM makes Claude Code fail to parse it, silently disabling every MCP server in that repo).
- **Project-scoped plugin installs** — a plugin can be installed at BOTH user scope and project scope, and **project scope overrides user scope** for a session opened in that repo. `scripts/catch-up-machine.ps1` updates **user scope only**, so a repo with a project-scoped install can silently run an old version even after a catch-up. Check with `claude plugin list` (look for `Scope: project`). Fix per repo, run from inside it: `claude plugin update tapestry-patterns@tapestry --scope project` (and `tapestry-discipline`). To eliminate the drift permanently, `claude plugin uninstall <name>@tapestry --scope project` so the single user-scope install applies everywhere (enablement in `.claude/settings.json` is unversioned and stays). There is no flag to update all scopes at once; user and project scope are handled separately.

## The mechanisms (what does the propagating)

| Mechanism | Location | Covers |
|---|---|---|
| `catch-up-machine.ps1` | `scripts/` | Per-machine plugin updates (marketplace refresh + all plugins) |
| Plugin version guard | `scripts/check_plugin_versions.py` + `.github/workflows/plugin-version-check.yml` | `marketplace.json` vs each `plugin.json` drift (required check) |
| Change trail | `docs/changelog/` + `scripts/check_changelog.py` + `.github/workflows/changelog-check.yml` | A findable record of every notable change (advisory check) |
| roadmap-maintenance | `tapestry-patterns:roadmap-maintenance` agent | `ROADMAP.md` status currency |

## Cross-machine actions can't run from here

Editing another machine's `~/.claude.json`, running `catch-up-machine.ps1` there, or setting a Render/GitHub secret are per-machine / per-service operator actions — an agent on one machine cannot reach another machine or the Render/GitHub dashboards. Track those as operator to-dos.
