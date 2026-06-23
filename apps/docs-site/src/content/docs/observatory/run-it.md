---
title: Run the Observatory
description: Open the Observatory console with the tapestry CLI, or run it locally for development. Includes the deployment settings the console needs.
---

## Open the console

```sh
tapestry observatory
```

This opens the console in your browser. You can also open [`/observatory`](/observatory) directly.

The Observatory is part of the platform — one deployed console. Once a project is onboarded with [`tapestry onboard`](/how-to/quickstart-vscode/), its coordination data flows into it.

## Run it locally

For development, run the docs site locally. From `apps/docs-site`, one line at a time (PowerShell doesn't accept `&&`):

```sh
cd apps/docs-site
npm install
npm run dev
```

Open the URL it prints and add `/observatory`. In local dev the console reads this machine's hook telemetry (`~/.claude/logs/hooks.jsonl`) when present; otherwise it uses a bundled sample.

## Deployment

The console and its feed render on demand (serverless functions); the doc pages stay static. The deployment uses:

- the `@astrojs/vercel` adapter (`^8`, for Astro 5) in `astro.config.mjs`,
- Node.js **22.x** in the Vercel project — the serverless functions do not run on Node 24,
- no Vercel `Output Directory` override — the adapter controls the output.

## Live data

By default the deployed console runs on a bundled sample. To feed it live data, see [The Observatory feed](/observatory/feed/).
