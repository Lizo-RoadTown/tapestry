---
title: Docs MCP
description: Three ways to grab the Tapestry docs as machine-readable content — a static llms.txt corpus, per-page raw markdown, and a local stdio MCP server. No hosted service required.
---

The Tapestry documentation ships in three forms aimed at agents and LLM clients, all backed by the same source-of-truth markdown files under `apps/docs-site/src/content/docs/`. Pick the one that fits your client.

## What's available

| Form | URL or invocation | Best for |
|---|---|---|
| **Static `llms.txt`** | [`https://tapestry-khaki.vercel.app/llms.txt`](/llms.txt) | A whole-corpus index. Fits the [llmstxt.org](https://llmstxt.org/) convention. |
| **Per-page raw Markdown** | `https://tapestry-khaki.vercel.app/raw/<slug>.md` (e.g., [`/raw/systems/observer.md`](/raw/systems/observer.md)) | Grabbing a single page as plain markdown — pasteable into an LLM or another document. |
| **Stdio MCP server** | `python -m docs_mcp` (after install) | A Claude Code (or other MCP client) session that wants structured `search` / `read` / `list` tool calls instead of fetching markdown blobs. |

The dropdown at the top-right of every docs page exposes the first two via "Copy page", "View as Markdown", and "llms.txt".

The stdio MCP is a separate install step, described below.

## How the static side is built

`scripts/generate-static-docs.mjs` runs as a prebuild step (wired into `package.json`'s `dev` + `build` scripts). It walks `src/content/docs/**/*.{md,mdx}` and emits:

- `public/llms.txt` — flattened corpus per [llmstxt.org](https://llmstxt.org/) (top H1 + per-section H2s + bullet list of page URLs with one-line descriptions).
- `public/raw/<slug>.md` — the raw markdown of each page, frontmatter included, ready to be served at `/raw/<slug>.md`.

Updates are picked up automatically on every Vercel build of the docs site.

## How the stdio MCP works

`services/docs-mcp/` ships a Python package (`docs_mcp`) that exposes three MCP tools over stdio:

| Tool | Purpose |
|---|---|
| `tapestry_docs_search` | Token-frequency ranked search over the corpus |
| `tapestry_docs_read` | Full body of a named doc by slug |
| `tapestry_docs_list` | List all slugs (optionally filtered to a section) |

Stdio transport means each MCP client spawns its own subprocess — no network, no hosted server, no auth.

## Install the stdio MCP

1. Install the package (one-time per machine):

   ```sh
   pip install -e services/docs-mcp
   ```

   (Or `pip install tapestry-docs-mcp` if the package has been published to PyPI; check the [pyproject.toml](https://github.com/Lizo-RoadTown/tapestry/blob/main/services/docs-mcp/pyproject.toml) for the current install target.)

2. Add to your project's `.mcp.json`:

   ```json
   {
     "mcpServers": {
       "tapestry-docs": {
         "command": "python",
         "args": ["-m", "docs_mcp"]
       }
     }
   }
   ```

3. Restart Claude Code (plugin/MCP loader binds at session start).

The package reads `DOCS_ROOT` env var if set; otherwise it falls back to a bundled corpus snapshot at install time. Future enhancement: fetch `/llms.txt` from the deployed docs site on startup so the corpus stays current without reinstalling.

## Why no hosted backend

The Tapestry docs corpus is ~250 KB across ~30 markdown pages. Hosting a FastAPI service for content this small would cost (operationally and financially) more than the static + stdio path. The static side ships with the existing Vercel docs deployment at zero additional cost; the stdio MCP runs locally inside each consuming client.

If the corpus ever outgrows in-memory search (~thousands of pages), the upgrade path is documented in the service's [README](https://github.com/Lizo-RoadTown/tapestry/blob/main/services/docs-mcp/README.md).

## Verify

- Open [`/llms.txt`](/llms.txt) — should return a markdown listing of every docs page.
- Open [`/raw/index.md`](/raw/index.md) — should return the homepage's raw markdown.
- Click the "Copy page" dropdown at the top of any docs page — should expose the three actions.
- After installing the stdio MCP: from a Claude Code session, invoke `tapestry_docs_search "observer"` — should return ranked hits including `systems/observer` and `explanation/the-observer`.

## Build status

| Step | Status |
|---|---|
| Static `llms.txt` generator | Done — `apps/docs-site/scripts/generate-static-docs.mjs` |
| Static `/raw/<slug>.md` generator | Done — same script |
| "Copy page" dropdown component | Done — `apps/docs-site/src/components/PageActions.astro` (overrides Starlight `PageTitle`) |
| Stdio MCP package | Done — `services/docs-mcp/docs_mcp/` |
| PyPI publish | Pending — operator decision |
| Bundled corpus snapshot vs runtime fetch | Pending — current package reads from `DOCS_ROOT`; bundling is a follow-up enhancement |
| Test suite | Pending — follow-on PR |

## Related

- [The plugins](/explanation/plugins/) — how `.mcp.json` is consumed by Claude Code
- [Load-bearing files — `.mcp.json`](/reference/load-bearing-files/) — the contract
- [Memory](/systems/memory/) — the platform's other MCP, hosted with auth (different shape from this one)
- [llmstxt.org](https://llmstxt.org/) — the static-corpus convention
