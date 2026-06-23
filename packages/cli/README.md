# `packages/cli/`

**Status:** Populated — Step 5a (CLI lift), 2026-06-21. Code lifted; not yet published.

The `loom` CLI: scaffolds + registers new consuming projects (the cross-platform replacement for the old PowerShell `new-loom-project.ps1`).

## What's here

Verbatim **Lift** (`cmp`-verified identical) of `the-loom/tapestry-cli/`:
- `tapestry_cli/cli.py` — argparse entrypoint (`main`).
- `tapestry_cli/init.py` — `init` command: creates `.env` (OTel propagation + `LOOM_PROJECT_ID`), registers the project, etc.
- `tapestry_cli/__init__.py`, `__main__.py`, `pyproject.toml`.

Stdlib-only (no third-party deps); **URL-env-driven** (reads `LOOM_MEMORY_MCP_URL` / `LOOM_MEMORY_URL` / `LOOM_PROJECT_ID` — no hardcoded loom hostnames). `tapestry_cli` package name kept (rename deferred, like `loom_auth`).

## Migration status

**Decision: Lift.** Verified: files byte-identical to source, compiles, `tapestry_cli.cli` resolves. Companion: Step 5b (templates assembly) — `templates/*` are assembled from the starter repos separately (curation, not a lift).

## Provenance
- the-loom: `tapestry-cli/` (the cross-platform scaffolder)
- loom-memory: `tapestry_step3_prod_cutover_complete_2026_06_21` (migration state)
