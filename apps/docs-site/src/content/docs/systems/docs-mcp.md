---
title: Docs MCP
description: Three ways to grab the Tapestry docs as machine-readable content — a static llms.txt corpus, per-page raw markdown, and a local stdio MCP server. No hosted service required.
---

The Tapestry documentation ships in three forms aimed at agents and LLM clients, all backed by the same source-of-truth markdown files under `apps/docs-site/src/content/docs/`. Pick the one that fits your client.

## What's available

| Form | Where | Best for |
|---|---|---|
| **Static `llms.txt`** | [`/llms.txt`](/llms.txt) | Whole-corpus index. Follows the [llmstxt.org](https://llmstxt.org/) convention. |
| **Per-page raw Markdown** | [`/raw/<slug>.md`](/raw/systems/observer.md) | Grabbing a single page as plain markdown — pasteable into an LLM or another document. |
| **Stdio MCP server** | `python -m docs_mcp` | Claude Code (or other MCP client) sessions that want structured `search` / `read` / `list` tool calls instead of fetching markdown blobs. |

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

The package bundles a snapshot of the docs corpus at build time, so a fresh install Just Works with no env vars.

1. Install the package (one-time per machine):

   ```sh
   pip install -e services/docs-mcp
   ```

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

   The `tapestry-discipline` plugin already declares this server in its [plugin.json](https://github.com/Lizo-RoadTown/tapestry/blob/main/integrations/claude-code/tapestry-discipline/.claude-plugin/plugin.json), so if you've installed the plugin you only need the `pip install` step.

3. Restart Claude Code so the MCP loader binds the new server.

To override the bundled snapshot — e.g., to point at a tapestry clone with newer docs than the installed package — set `DOCS_ROOT` to the absolute path of `apps/docs-site/src/content/docs/`.

## Verify

- Open [`/llms.txt`](/llms.txt) — returns a markdown listing of every docs page.
- Open [`/raw/index.mdx`](/raw/index.mdx) — returns the homepage's raw markdown.
- Click the "Copy page" dropdown at the top of any docs page — exposes the three actions.
- After installing the stdio MCP: from a Claude Code session, call `tapestry_docs_search` with `query="observer"` — returns ranked hits with `explanation/the-observer` as the top result.

## Related

- [The plugins](/explanation/plugins/) — how `.mcp.json` is consumed by Claude Code
- [Load-bearing files — `.mcp.json`](/reference/load-bearing-files/) — the contract
- [Memory](/systems/memory/) — the platform's other MCP, hosted with auth (different shape from this one)
- [llmstxt.org](https://llmstxt.org/) — the static-corpus convention
