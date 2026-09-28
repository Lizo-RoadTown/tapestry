# `infra/deploy/`

**Status:** Populated. Holds the `render.yaml` Blueprint (staging-first) that reuses the existing `loom-postgres` via a `sync:false` `LOOM_DB_URL` secret rather than creating a new database.

## Purpose

Render `render.yaml` Blueprint + (future) Vercel configs + deploy scripts.

## What's here

- `render.yaml` — the Tapestry deploy Blueprint. Staging-first draft; it does not create a new Postgres (`fromDatabase:` would spawn a fresh empty DB), so the DB connection is supplied as a `sync:false` `LOOM_DB_URL` secret that points at the existing `loom-postgres`. Env-group name: `tapestry-shared-secrets`.

Operator setup walkthrough: [`../../apps/docs-site/src/content/docs/how-to/set-up-render.md`](../../apps/docs-site/src/content/docs/how-to/set-up-render.md).

## Source

render.yaml in the-loom + per-app vercel.json. See [`../../docs/migration/README.md`](../../docs/migration/README.md).
