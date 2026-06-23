---
title: Names you'll see in these docs
description: Quick context for the repo names, marketplace names, and project names referenced throughout the documentation. Read this first if any name feels unfamiliar.
---

The platform is in a beta transition. A few names appear throughout the docs that won't make sense without context. This page is a single place to look them up.

## The platform

| Name | What it is |
|---|---|
| **Tapestry** | The canonical name for the platform itself — the unified system this docs site describes. Eventually everything migrates here. |
| **the-loom** | The beta implementation where most platform services currently live (the memory MCP server, the architecture registry, the policy service, the self-observer cron). As each component stabilizes, it migrates into Tapestry. When you see "currently in the-loom; eventual destination is tapestry/...", that's the migration in progress. |
| **Make_Skills** | A second beta implementation, focused on the skill-engine. Another transitional repo whose components migrate into Tapestry over time. Less frequently referenced in these docs. |

## The plugins and marketplaces

| Name | What it is |
|---|---|
| **`tapestry-discipline`** (formerly `loom-discipline`) | The Claude Code plugin that provides the universal discipline stack — PROBE hooks, memory wiring, auto-recall, observer, upskilling audit. Installed once per machine; enabled per project. Renamed 2026-06-22 (PR #42); the prior `loom-discipline@lizo-loom` install still works during transition. See [The plugins](/explanation/plugins/). |
| **`tapestry-patterns`** (formerly `liz-patterns`) | A second plugin: the canonical reusable agents, skills, and scripts (documentation, deep-research, infrastructure-mapping, etc.). Also hosts the architecture-snapshot scripts. Renamed 2026-06-22; the prior `liz-patterns@lizo-skills` install still works during transition. |
| **`tapestry`** (canonical marketplace) | The Claude Code plugin marketplace that publishes `tapestry-discipline` and `tapestry-patterns`. Add via `/plugin marketplace add Lizo-RoadTown/tapestry`. |
| **`lizo-loom`** (transitional marketplace) | Formerly published `loom-discipline` from `Lizo-RoadTown/the-loom`. Still resolves; new projects should use the `tapestry` marketplace. |
| **`lizo-skills`** (transitional marketplace) | Formerly published `liz-patterns` from `Lizo-RoadTown/claude-skills-marketplace`. Still hosts per-project guard plugins (`sde-extraction-guard` etc.). New projects should use the `tapestry` marketplace for the consolidated plugins. |

## Example project referenced throughout

| Name | What it is |
|---|---|
| **SDE_Extraction** | A real research project that was the first major consumer of the platform. Used throughout the docs as the WORKED EXAMPLE — when you see "see how SDE_Extraction did X", that's the canonical reference implementation for what a consuming project looks like. Its repo at `Lizo-RoadTown/sde-extraction` shows the patterns in practice (wrapper scripts, per-project guard plugin, `.project-intelligence/` configs). |

## URL hosts you'll see

The platform's hosted services currently live at these URLs:

| Name | URL | What it is |
|---|---|---|
| `loom-agent-context` | `https://loom-agent-context.onrender.com` | Where the memory MCP server is hosted. |
| `loom-architecture-registry` | `https://loom-architecture-registry.onrender.com` | Where candidates surfaced by the observer get stored. |
| `loom-policy` | `https://loom-policy.onrender.com` | Where promotion decisions are governed. |
| `loom-project-registry` | `https://loom-project-registry.onrender.com` | Where consuming projects register themselves. |
| `loom-self-observer` | (Render cron, no public URL) | The scheduled job that scans repos for drift every 6 hours. |

These URLs all have `loom-` prefixes because they're hosted from the beta repo (`the-loom`). When services migrate into Tapestry, the URLs will change too — env-var overrides (`TAPESTRY_*_URL` precedence over `LOOM_*_URL`) are wired throughout the platform so consuming projects don't have to chase the rename.

If a reference confuses you, the meaning is almost always one of:

- A beta repo name → "where this currently lives during the transition"
- A marketplace name → "where the plugin is published; add it once to Claude Code"
- An agent name (`loom-agent`, `MS-agent`, `Tapestry-agent`) → an internal coordination name for the AI agent working in each repo; not relevant to operators using the platform

When in doubt, the names in this glossary are all that matter.
