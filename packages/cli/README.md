# tapestry-cli

The command-line interface for [Tapestry](https://github.com/Lizo-RoadTown/tapestry) — project intelligence for AI-native teams.

Wire a project into the platform, then open the live console. Stdlib-only, no third-party dependencies, no model downloads — it works the moment `pip install` completes, on Windows, macOS, and Linux.

## Install

```bash
pipx install tapestry-cli
```

(or `pip install tapestry-cli`)

## Commands

```text
tapestry onboard      Onboard the current directory and write
                      .claude/settings.json with the Tapestry plugins enabled
                      (the recommended quickstart path).
tapestry observatory  Open the Observatory console in a browser.
tapestry init         Register the project and write .env / .mcp.json /
                      .project-intelligence/ (granular path; does not touch
                      .claude/settings.json).
tapestry version      Print version and platform info.
```

## Quickstart

```bash
pipx install tapestry-cli
tapestry onboard
tapestry observatory
```

The agents pick up memory, telemetry, and the discipline rules from there. See the [setup guide](https://tapestry-khaki.vercel.app/how-to/set-up-a-new-project/) for the full walkthrough.

## Configuration

The CLI is URL-env-driven — no hardcoded hostnames. It reads:

- `LOOM_MEMORY_MCP_URL` / `LOOM_MEMORY_URL` — the memory MCP endpoint
- `LOOM_PROJECT_ID` — the project identifier
- `TAPESTRY_OBSERVATORY_URL` — override the Observatory URL opened by `tapestry observatory`

## Notes

`tapestry` is the primary entry point; `loom` is kept as a deprecated alias during the transition. The Python package is named `tapestry_cli`.

---

*Provenance: lifted verbatim from `the-loom/tapestry-cli/` during the Tapestry monorepo migration (Step 5a, 2026-06-21) — the cross-platform replacement for the old PowerShell `new-loom-project.ps1` scaffolder.*
