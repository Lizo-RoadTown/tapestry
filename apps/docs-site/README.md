# `apps/docs-site/`

**Status:** Live. Authored by loom-agent 2026-06-20 per operator directive.

## Purpose

Public docs site explaining what keeps a Tapestry-consuming project on track —
the discipline stack of plugins, MCP wiring, hooks, and per-project configuration —
so new operators don't accidentally delete a load-bearing file without knowing
what it does.

Audience: an operator (often Liz herself, or someone she onboards) setting up a
NEW project that plugs into Tapestry the way SDE_Extraction does.

## Stack

Astro 5 + Starlight 0.36 + astro-mermaid. Identical template to `SDE_Extraction/apps/docs/`.

## Content (Diátaxis-aligned)

```
src/content/docs/
  index.mdx                                  — landing, audience, 4-card entry
  start/what-stays-on-track.md               — overview of the discipline stack
  explanation/discipline-stack.md            — why each piece exists + what fails
  how-to/set-up-a-new-project.md             — concrete 10-step setup
  how-to/recover-from-common-failures.md     — symptom → cause → fix table
  reference/load-bearing-files.md            — every file/config/env-var
```

## Develop

```sh
npm install
npm run dev          # local dev server
npm run build        # production build → dist/
npm run preview      # serve the build locally
```

## Deploy

Configured for Vercel via `vercel.json`. To deploy:

1. In the Vercel dashboard, import `Lizo-RoadTown/tapestry`.
2. Set **Root Directory** to `apps/docs-site`.
3. Vercel auto-detects Astro and applies the `vercel.json` config.
4. Confirm production URL (defaults to `tapestry-khaki.vercel.app` or a Vercel-assigned subdomain).

Auto-deploy: pushes to `main` rebuild the production site.

## Cross-agent provenance

This site was authored by **loom-agent** on 2026-06-20 with operator authorization,
NOT by Tapestry-agent. The decision rationale + handoff are recorded in loom-memory
under `loom_agent_built_tapestry_docs_site_v1_2026_06_20`.

Tapestry-agent owns this slot going forward — content edits, structural changes,
sidebar updates. loom-agent's role here ends with this initial scaffold + v1 content.

## When to update

- A NEW failure mode is discovered (someone hits a new way the discipline can silently
  drop) → add a row to `how-to/recover-from-common-failures.md`.
- The `tapestry-discipline` plugin gains a new hook or behavior → update
  `explanation/discipline-stack.md` and `reference/load-bearing-files.md`.
- The setup steps change (e.g., when `tapestry init` CLI lands) → update
  `how-to/set-up-a-new-project.md`.
- Tapestry services migrate from `the-loom` (per the migration plan) → update URLs
  in `reference/load-bearing-files.md` and the host references throughout.
