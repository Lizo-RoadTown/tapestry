# Tapestry

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**Tapestry is a user/agent support and reinforcement system.** Memory, telemetry, observability, architecture analysis, friction analysis, and upskilling are mechanisms used to observe, strengthen, stabilize, and evolve coordination between operators and agents — across many projects, over time.

- **Marketing site + docs:** [tapestry-khaki.vercel.app](https://tapestry-khaki.vercel.app/)
- **Quickstart:** [Set up a new project](https://tapestry-khaki.vercel.app/how-to/set-up-a-new-project/)
- **What it is, in depth:** [the docs](https://tapestry-khaki.vercel.app/docs/)

## Install (consumer side)

The two pieces a consuming project installs in their Claude Code session:

```text
/plugin marketplace add Lizo-RoadTown/tapestry
/plugin install tapestry-discipline@tapestry
/plugin install tapestry-patterns@tapestry
```

Plus the CLI (one-time per machine):

```sh
pipx install tapestry-cli
tapestry onboard <your-project-name>
```

That writes the per-project config (`.env`, `.mcp.json`, `.project-intelligence/`, `.claude/settings.json`) so the discipline plugin activates and the memory MCP connects. See the [Quickstart — VS Code](https://tapestry-khaki.vercel.app/how-to/quickstart-vscode/) walkthrough for the full setup.

## What's in this repo

```text
tapestry/
├── apps/
│   ├── docs-site/           Astro Starlight site + marketing pages (Vercel)
│   └── web-dashboard/       Operator-facing dashboard (forward home)
├── services/                Backend bounded services
│   ├── agent-context/       ← live; the memory MCP (Render-hosted)
│   ├── project-registry/    ← live; project / repo / machine registration
│   ├── architecture-registry/   slot README; canonical home pending migration
│   ├── candidate-registry/      slot README
│   ├── policy/                  slot README
│   ├── audit-log/               slot README
│   ├── docs-mcp/                stdio MCP exposing the docs (pip-installable)
│   ├── project-observatory/     slot README
│   ├── skill-making/            slot README
│   └── telemetry-ingestion/     slot README
├── engine/                  Recursive skill engine slots (forward homes)
├── packages/
│   ├── auth/                Canonical loom_auth (JWT + tenant resolution)
│   └── cli/                 tapestry-cli (published to PyPI)
├── integrations/claude-code/
│   ├── tapestry-discipline/ The discipline plugin (4 hooks; OTel emission)
│   └── tapestry-patterns/   Reusable agents + skills + scripts (architecture
│                            snapshot, drift-watcher, infrastructure-mapping, etc.)
├── templates/               Project-type seed templates
├── infra/                   Render Blueprint, Postgres migrations, deploy configs
├── docs/                    Architecture, ADRs, migration, runbooks, plans
└── .claude-plugin/          Marketplace manifest (`tapestry`)
```

Two services (`agent-context`, `project-registry`) have been cut over from `the-loom` to this repo and run in production. The rest of `services/` is forward-home slots: code matures in the legacy source repos and migrates here per the [migration framework](docs/migration-cicd/).

## Relationship to other repos

Tapestry is the **canonical product system**. Legacy source repos (`Lizo-RoadTown/the-loom`, `Lizo-RoadTown/Make_Skills`) continue to be built in; mature pieces consolidate here via curated migration PRs. The parallel-build is intentional — premature consolidation would import unfinished structure. See [docs/migration/README.md](docs/migration/README.md) for the approach.

## Self-host vs hosted

Tapestry is **self-host by default** — every operator runs their own backend, picks their own tenant UUID, points consuming projects at their own deployment. The platform supports a two-mode commitment (`PLATFORM_MODE=self_host` default; `=hosted` opt-in with multi-tenant JWT). See [Platform dependencies](https://tapestry-khaki.vercel.app/reference/platform-dependencies/) for what each external service does and which are operator-supplied vs platform-supplied.

## License

Apache 2.0 — see [LICENSE](LICENSE).
