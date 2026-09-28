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

## Install (VS Code without Claude Code)

For VS Code users who want Tapestry's memory + docs MCP servers available to Copilot Chat (no Claude Code required), install the Tapestry VS Code extension:

```sh
code --install-extension tapestry.tapestry
```

Marketplace listing: <https://marketplace.visualstudio.com/items?itemName=tapestry.tapestry>. After install, set `tapestry.memoryMcpUrl` in VS Code settings to your deployment's memory MCP URL and reload. See [`integrations/vscode/README.md`](integrations/vscode/README.md) for full setup.

## What's in this repo

```text
tapestry/
├── apps/
│   ├── docs-site/           Astro Starlight site + marketing pages (Vercel)
│   └── web-dashboard/       Operator-facing dashboard (forward home)
├── services/                Backend bounded services
│   ├── agent-context/       the memory MCP (cut over from the-loom)
│   ├── project-registry/    project / repo / machine registration
│   ├── architecture-registry/   code present; cutover pending (see README)
│   ├── policy/                  code present; cutover pending (see README)
│   ├── telemetry-ingestion/     code present; deploy pending
│   ├── project-observatory/     code present; deploy pending
│   ├── self-observer/           deployed live (Render cron)
│   ├── skill-making/            code present (engine lift); deploy shape TBD
│   ├── docs-mcp/                stdio MCP exposing the docs (pip-installable)
│   ├── candidate-registry/      absorbed into architecture-registry (no service)
│   └── audit-log/               deferred — no consumer yet
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

Most of `services/` now holds real, migrated code rather than empty slots:

- **Live / cut over:** `self-observer` is deployed as a Render cron; `agent-context` (the memory MCP) and `project-registry` are cut over from `the-loom`.
- **Code present, cutover or deploy pending:** `architecture-registry`, `policy`, `telemetry-ingestion`, and `project-observatory` carry working code with passing tests; their live Render services still build from `the-loom` (or await first deploy) until the operator repoints — see each service README. `docs-mcp` (a pip-installable stdio MCP) and `skill-making` (the engine lift) also hold working code.
- **Still slots:** `audit-log` (deferred — no consumer yet) and `candidate-registry` (absorbed into `architecture-registry` — no separate service).

Migration follows the [migration framework](docs/migration-cicd/).

## Relationship to other repos

Tapestry is the **canonical product system** and the live system. `Lizo-RoadTown/the-loom` and `Lizo-RoadTown/Make_Skills` are **retired legacy source repos**, not active parallel prototypes — no new building happens there. Migration brings mature capabilities home into Tapestry via curated PRs, scoped Lift / Refactor / Rewrite / Retire per piece. The end state is Tapestry standing alone, with no new runtime dependency on either legacy repo. See [docs/migration/README.md](docs/migration/README.md) for the approach.

## Self-host vs hosted

Tapestry is **self-host by default** — every operator runs their own backend, picks their own tenant UUID, points consuming projects at their own deployment. The platform supports a two-mode commitment (`PLATFORM_MODE=self_host` default; `=hosted` opt-in with multi-tenant JWT). See [Platform dependencies](https://tapestry-khaki.vercel.app/reference/platform-dependencies/) for what each external service does and which are operator-supplied vs platform-supplied.

## License

Apache 2.0 — see [LICENSE](LICENSE).
