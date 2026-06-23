# integrations/claude-code

Claude Code plugins that ship from the tapestry marketplace.

## What's here

```
integrations/claude-code/
├── tapestry-discipline/    # PROBE-first behavior + hooks + MCP wiring + Path A observer
└── tapestry-patterns/      # canonical agents/skills/tools library
```

## Install

```text
/plugin marketplace add Lizo-RoadTown/tapestry
/plugin install tapestry-discipline@tapestry
/plugin install tapestry-patterns@tapestry
```

The marketplace manifest lives at [`../../.claude-plugin/marketplace.json`](../../.claude-plugin/marketplace.json).

## Plugin identities

| Plugin | Role |
|---|---|
| `tapestry-discipline` | The 4 hook scripts (SessionStart, UserPromptSubmit, PreToolUse, Stop) that auto-inject PROBE discipline, recall top-N memories from `loom-memory`, run the architecture-snapshot pipeline, and emit OTel telemetry per the [coordination contract](https://tapestry-docs.vercel.app/reference/otel-coordination-contract/). Scope-gated by `LOOM_PROJECT_ID` in `.env`. |
| `tapestry-patterns` | Reusable agents (drift-watcher, infrastructure-mapping, next-actions-planning, lessons-learned, …) and skills (agentic-skill-design, deep-research-pattern, documentation, …) available by name in every consuming project. |

## Renaming history

Both plugins consolidated into this monorepo 2026-06-22:

- `tapestry-discipline` (formerly at `the-loom/adapters/claude-code/loom-discipline/`, marketplace `lizo-loom`) → `tapestry-discipline`
- `tapestry-patterns` (formerly at `claude-skills-marketplace/plugins/liz-patterns/`, marketplace `lizo-skills`) → `tapestry-patterns`

The standalone source repos remain available during the transition; the canonical home is now this monorepo.

## What stays at the loom-* names

- `OTEL_SERVICE_NAME=loom-discipline` — the OTel service identity in Grafana Cloud telemetry. Preserved for dashboard query continuity; consumers can override via env if they want fresh service identity for new dashboards.
- `loom-memory` MCP server URL (`loom-agent-context.onrender.com`) — the service URL didn't change in the Step 2 cutover; only the source repo did.
- `LOOM_PROJECT_ID` env var — the scope-gate variable consumers already set in `.env`.

These three are stable contracts with consumers; renaming them is a separate, coordinated decision.

## Sub-directory layout (per plugin)

Each plugin follows the standard Claude Code plugin shape:

```
<plugin>/
├── .claude-plugin/plugin.json     # manifest
├── README.md                       # plugin-specific docs
├── agents/    *.md                 # subagent definitions
├── commands/  *.md                 # slash commands
├── hooks/     hooks.json + scripts # hook manifest + runner
├── scripts/   *.py                 # hook implementations
├── skills/    <skill-name>/SKILL.md
└── tests/     test_*.py
```

`tapestry-discipline` has all of these. `tapestry-patterns` has `agents/`, `scripts/`, and `skills/`.
