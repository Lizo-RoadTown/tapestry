# Working in Tapestry

Project context for Claude Code. Loaded into every conversation. Keep it tight; subsystem-specific rules belong in subdirectory `CLAUDE.md` files (e.g., `services/<svc>/CLAUDE.md`), not here.

## CORE DIRECTIVE 1 — loom-memory access is mandatory

Every session in this repo MUST have the `loom-memory` MCP server reachable. Tools: `memory_read`, `memory_write`, `memory_recall`, `memory_search`, `memory_list`, `memory_delete`. Endpoint: `https://loom-agent-context.onrender.com/mcp/memory/`. The `.mcp.json` here is wired with the URL; v0.1.8 of loom-agent-context added a self-host fallback so no JWT header is needed (each operator gets their own fallback tenant).

If the SessionStart additionalContext shows `*** CONCRETE-RULE VIOLATION DETECTED ***` — **halt all substantive work and report to the operator.** Do not proceed silently using only in-session context.

## CORE DIRECTIVE 2 — parallel-build, not pause-and-migrate

Tapestry is being built **in parallel** with active prototype repos (`the-loom`, `Make_Skills`, `loom-platform`, consuming projects). It is **NOT** a destination for active work yet. Specifically:

- **Do NOT migrate code from prototype repos to Tapestry unless the operator has explicitly approved that piece for migration**
- **Do NOT pause work in prototype repos to "wait for Tapestry"** — work continues in its current home until stable enough for curated import
- **Do NOT treat slot READMEs in Tapestry as commitments to current architecture** — they're targets for future import, not authoritative descriptions of working code
- New Tapestry work in this phase is limited to: docs (architecture, ADRs, migration), schemas (if no canonical version exists elsewhere), and skeleton placeholders

See `docs/migration/README.md` for the migration approach.

## What Tapestry is

The enterprise system-of-record monorepo. **Not** the public-facing product. Not the operator-facing dashboard. Not the engine. It's the container that eventually holds all of those, with clean boundaries.

This is NOT:

- An immediate replacement for any existing repo
- A place to do new feature work today (with rare exceptions named above)
- A copy of any existing repo's structure (no lift-and-shift)

## How Tapestry relates to the existing fleet

| Repo | Role today | Eventual fate |
|---|---|---|
| `Lizo-RoadTown/the-loom` | Platform prototype (services, observer, registry, policy, dashboard) | Source for `services/`, `apps/web-dashboard/`, `integrations/claude-code/` |
| `Lizo-RoadTown/Make_Skills` | Engine prototype (skill compiler, adapters, default-seed/, skills library) | Source for `engine/`, `templates/` |
| `Lizo-RoadTown/loom-platform` | Consumer prototype seed | Source material; absorption decision deferred |
| Per-project consumer repos (Hub, SDE_Extraction, etc.) | Consuming-project prototypes | Source for `templates/` shape + integration patterns |
| `Lizo-RoadTown/claude-skills-marketplace` | Public plugin marketplace | Source for `packages/` distribution |

See [`docs/migration/legacy-repo-inventory.md`](docs/migration/legacy-repo-inventory.md).

## Boundary rule (inherited)

> **Make_Skills improves local agency and produces candidates. The-loom observes across projects, governs promotion, and stores durable structure.**

This boundary survives the migration to Tapestry: it becomes the rule for what lives in `engine/` vs `services/`.

## Discipline plugin (required)

```text
/plugin marketplace add Lizo-RoadTown/tapestry
/plugin install tapestry-discipline@tapestry
```

The plugin auto-injects behavioral rules into every session — PROBE before asserting, cite `file:line`, distinguish dev-tooling from runtime, write friction as memory at the moment of correction, cite skills by name, append to test-runs log, enforce session-end upskilling reports.

The plugin source lives at `integrations/claude-code/tapestry-discipline/` (consolidated into the tapestry monorepo in PR #42, 2026-06-22 — renamed from `loom-discipline`). The prior `/plugin install loom-discipline@lizo-loom` still works during the transition window. The runtime hook reminder text consumers see is still `[loom-discipline]` — preserved-identity contract; rename is install-only.

## Canonical patterns (operator's patterns library)

The canonical home for reusable agents + skills + tools is the `tapestry-patterns` plugin:

```text
/plugin install tapestry-patterns@tapestry
```

This makes the following available **by name in every project**, with one canonical implementation:

- **Agents** (invoke via `Agent({subagent_type: "tapestry-patterns:<name>", ...})`):
  `infrastructure-mapping`, `next-actions-planning`, `lessons-learned`, `orchestration-cataloging`, `eval-deep-research`, `web-app-scaffold`, `agentic-upskilling`, `drift-watcher`
- **Skills** (invoke via Skill tool with `tapestry-patterns:<name>`):
  `agentic-skill-design`, `deep-research-pattern`, `design-evaluation`, `documentation`, `document-parsing`, `layered-explanation`, `open-source-documentation`, `proposal-authoring`

Per [MANIFESTO Pillar 1](MANIFESTO.md): every reusable pattern has ONE name, ONE home, available everywhere via reference, not copy. When Tapestry's `engine/` is built out, compiled-skill output will land in this plugin (auto-write loop closure is future scope per MANIFESTO Part 4.7).

## Two-mode commitment (will apply once code arrives)

Every service + app considers BOTH self-host AND hosted-multitenant. `PLATFORM_MODE=self_host` (default) or `=hosted`. Until code exists, this is forward-looking discipline.

## Tone — no marketing voice

Describe what *is*, not what it *isn't*. No "the unlock," no "delightful," no defensive contrasts. Plain, direct, descriptive. Applies to docs, commit messages, PR bodies, error messages.

## Commit + PR discipline

- **Small PRs.** One concern per branch.
- **Always open via `gh pr create`** with a Test Plan checklist.
- **Cite proposals + ADRs** when relevant.
- **Never `--no-verify`, never `--amend` on something already pushed.** Make a new commit.
- **Co-author tag**: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

## What to do when in doubt

1. Recall memory first (`memory_recall` — automatic at session start)
2. Read [`docs/architecture/UMBRELLA.md`](docs/architecture/UMBRELLA.md) for the canonical model
3. Read [`docs/migration/README.md`](docs/migration/README.md) before proposing any code import
4. If you're about to make a destructive change, ask before acting
