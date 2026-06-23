---
title: Run the Observatory
description: How to open the deployed Observatory console or run it locally, and the deploy requirements (Astro SSR via the Vercel adapter, Node 22.x for the serverless functions).
---

## Open the deployed console

The Observatory is part of the docs site. Open [`/observatory`](/observatory) on the deployed site — no setup required.

## Run it locally

The console lives in `apps/docs-site`. From the repo root, run these one at a time (PowerShell doesn't accept `&&`):

```powershell
cd apps/docs-site
npm install
npm run dev
```

The dev server prints a local URL (e.g. `http://localhost:4321/`). Open it and add `/observatory`:

```text
http://localhost:4321/observatory
```

Press **Ctrl + C** to stop.

In local dev the console reads this machine's own hook telemetry (`~/.claude/logs/hooks.jsonl`) when present, so you see your real working episodes; otherwise it falls back to a bundled real snapshot.

## Deploy requirements

The console and its feed (`/observatory`, `/observatory/raw`, `/api/episodes.json`) are **on-demand routes** — they render as serverless functions, while all the doc pages stay static. Two settings make that work:

| Requirement | Why |
|---|---|
| `@astrojs/vercel` adapter (`astro.config.mjs`), pinned to a version that supports Astro 5 (`^8`) | Produces the serverless functions for the on-demand routes. |
| **Node.js 22.x** in the Vercel project (not 24.x) | Vercel serverless functions don't run on Node 24 — on 24 the doc pages still serve but `/observatory` returns 404. |

Do **not** set a Vercel `Output Directory` override (e.g. `dist`) — the adapter owns the output. A `dist` override makes Vercel serve only the static pages and drop the functions.

## Make it live across sessions

By default the deployed console runs on a bundled snapshot. To feed it live coordination data from every session, point it at a central store — see **[The Observatory feed](/observatory/feed/)**.
