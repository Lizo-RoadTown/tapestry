# tapestry-patterns

**The canonical patterns library for Liz Osborn.** One home for her reusable agents, skills, and tools. Available in every Claude Code session in every project — so when she invokes a pattern by name, it works the same way wherever she invokes it.

## What this plugin is

This plugin is the canonical home for Liz's personal patterns. Per the binding rule in [`tapestry/MANIFESTO.md` Part 3 Pillar 1](https://github.com/Lizo-RoadTown/tapestry/blob/main/MANIFESTO.md):

> Every reusable pattern (skill, agent, tool) the operator uses has ONE name, ONE home, and is available everywhere via REFERENCE, not copy.

Previously these patterns lived as duplicated copies across `docs-agent/skills/`, `Make_Skills/skills/`, `Make_Skills/skills_private/`, `the-loom/skills/`, and `the-loom/skills_private/`. This plugin replaces all of those copies with ONE canonical source.

## What's in here

### `agents/` — specialized subagents

| Agent | What it does |
|---|---|
| `agentic-upskilling` | Documentation wrapper for the deployed self-observer service (the-loom/services/self-observer/). Runs as a Render cron — not an interactive invocation. |
| `drift-watcher` | Read-only oversight agent spawned in background during long multi-repo executions. Watches the primary for drift (per-repo solutions when cross-repo required, enumeration errors, forgetting binding rules, re-creating just-deleted duplicates) and surfaces concerns via memory_write. Does NOT execute work. Added v0.1.1; validated twice in production. |
| `eval-deep-research` | Runs the deep_research_bench (DRB) harness against a deepagents-produced report set. Scores RACE + FACT. |
| `infrastructure-mapping` | Maps any project's infrastructure as modules + interfaces + bond strength (Simon-grounded). Produces a map file + identifies silent leaks. |
| `lessons-learned` | Walks prior chat transcripts to find systematic friction patterns; routes each cluster into intake forms + memory updates. |
| `next-actions-planning` | Generates a grounded "what to do next" plan based on git + proposals + memory + recent conversation. |
| `orchestration-cataloging` | Identifies recurring work patterns and recommends turning the high-frequency ones into tools / subagents / skills. |
| `web-app-scaffold` | Agentic web app scaffolder. Probes context, decides the stack, executes the build, deploys, reports. |

### `skills/` — methodology skills (output-shape rules)

| Skill | What it does |
|---|---|
| `agentic-skill-design` | Meta-skill for designing skills that DECIDE and EXECUTE rather than ask permission. The PROBE → DECIDE → ACT → REPORT pattern. |
| `deep-research-pattern` | Architectural pattern for multi-agent deep research with strict context isolation. |
| `design-evaluation` | Evaluates a design question with multiple options across the dimensions that matter. Produces a tradeoff matrix. |
| `document-parsing` | Decision tree for picking the right parser (LlamaParse vs pdfplumber vs pypandoc) when converting PDFs / Word / PowerPoint / Excel / scanned images into LLM-friendly markdown. |
| `documentation` | Plan, write, and audit documentation using the Diátaxis framework + ADRs + docs-as-code workflow. |
| `layered-explanation` | Structures every technical explanation as ELI5 → quick-reference → depth (with file:line) → mental model. |
| `open-source-documentation` | OSS-specific documentation patterns. |
| `proposal-authoring` | Authors a design proposal in the project's house style. |

## Exceptions to "one home"

ONE agent intentionally lives outside this plugin: `roadmap-maintenance` at [`Make_Skills/subagents/roadmap-maintenance/`](https://github.com/Lizo-RoadTown/Make_Skills/tree/main/subagents/roadmap-maintenance). Reason: its tools (`update_roadmap_status`, `add_roadmap_item`, `roadmap_overview`) are LangChain `@tool`-decorated Python functions imported in-process via `Make_Skills/core/runtime/agent.py`, not exposed via MCP. The agent must run inside the Make_Skills runtime to call them.

Future work: expose those tools as MCP, then move the agent into this plugin. Tracked at `tapestry/docs/proposals/2026-06-13-skill-vs-agent-conversion-and-self-observer.md`.

## Installation

```bash
/plugin marketplace add Lizo-RoadTown/tapestry
/plugin install tapestry-patterns@tapestry
```

Restart Claude Code after install. The agents + skills are then available in every session in every project.

## How patterns get added to this plugin

The recursive-skill-engine loop. Briefly:

1. Liz works in any project
2. Observers (`local-observer` + `self-observer`) watch
3. Repeated patterns surface as candidates in `architecture-registry`
4. Liz reviews in the upskilling dashboard, decides: promote / hold / reject
5. Approved candidates flow through `policy` → `bridge` → `engine`
6. Engine compiles the candidate into a runnable artifact
7. (Future scope) Engine auto-writes the compiled artifact into this plugin, commits, pushes
8. Next Claude Code session loads the new pattern automatically — available everywhere

Today step 7 is manual. Full loop closure tracked in [`tapestry/MANIFESTO.md` Part 4.7](https://github.com/Lizo-RoadTown/tapestry/blob/main/MANIFESTO.md).

## Related

- [Tapestry MANIFESTO](https://github.com/Lizo-RoadTown/tapestry/blob/main/MANIFESTO.md) — what the application IS
- [Self-observer service](https://github.com/Lizo-RoadTown/the-loom/tree/main/services/self-observer) — the cron that surfaces category-drift candidates
- [Conversion plan](https://github.com/Lizo-RoadTown/tapestry/blob/main/docs/proposals/2026-06-13-skill-vs-agent-conversion-and-self-observer.md) — the plan that drove these patterns' promotion

## License

Apache 2.0 — see repo root LICENSE.
