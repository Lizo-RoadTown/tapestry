# tapestry-docs-mcp

Stdio MCP server exposing the Tapestry documentation as queryable tools. Any Claude Code session (or other MCP client) can call `tapestry_docs_search`, `tapestry_docs_read`, `tapestry_docs_list` to read the docs corpus directly instead of fetching individual pages or pattern-matching from training data.

Pairs with the static `/llms.txt` + `/raw/<slug>.md` artifacts published by the docs site itself — see [`apps/docs-site/scripts/generate-static-docs.mjs`](../../apps/docs-site/scripts/generate-static-docs.mjs).

## What it exposes

Three MCP tools over stdio:

| Tool | Signature | Returns |
|---|---|---|
| `tapestry_docs_search` | `query: str, limit: int = 5` | Top-N matching doc slugs + excerpts |
| `tapestry_docs_read` | `slug: str` | Full body of the named doc |
| `tapestry_docs_list` | `section: str \| None = None` | All slugs (optionally filtered to a section) |

Stdio transport means each MCP client spawns its own subprocess. No network, no hosting, no auth.

## Install

```sh
# from a clone of the tapestry repo
pip install -e services/docs-mcp
```

Or, once published to PyPI:

```sh
pip install tapestry-docs-mcp
```

## Configure your MCP client

Add to your project's `.mcp.json`:

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

Restart Claude Code so the MCP loader picks it up.

## Source of truth

The corpus is the markdown files in `apps/docs-site/src/content/docs/**/*.md{,x}`. The service reads them at startup (in-memory index) and dispatches search/read/list calls against the loaded set.

By default the package resolves the corpus relative to its install location. Set `DOCS_ROOT` if you need to point it elsewhere:

```sh
DOCS_ROOT=/path/to/tapestry/apps/docs-site/src/content/docs python -m docs_mcp
```

## Files

```
services/docs-mcp/
├── README.md             # this file
├── pyproject.toml        # package metadata + dependencies + entry point
└── docs_mcp/
    ├── __init__.py
    ├── __main__.py       # stdio entry point — `python -m docs_mcp`
    ├── corpus.py         # frontmatter parsing + llms.txt builder
    ├── indexer.py        # token-frequency search index
    └── mcp_server.py     # MCP tool definitions
```

## Run locally

```sh
cd services/docs-mcp
pip install -e .
DOCS_ROOT=../../apps/docs-site/src/content/docs python -m docs_mcp
```

The process blocks on stdin/stdout waiting for an MCP client to connect via stdio. Manual testing is awkward — easier to point a real MCP client (Claude Code) at it via `.mcp.json` and exercise the tools from a chat session.

## Why no hosted backend

The Tapestry docs corpus is ~250 KB across ~30 markdown pages. Hosting a FastAPI service for content this small costs more (operationally and financially) than the static + stdio path. The static `/llms.txt` + `/raw/<slug>.md` artifacts ship with the existing Vercel docs deployment at zero extra cost; the MCP tools run locally inside each consuming client.

If the corpus ever outgrows in-memory search (thousands of pages, sub-second search latency requirements, multiple concurrent agents querying simultaneously), the upgrade path is:

1. Switch `indexer.py` from token-frequency to BM25 + persistent index.
2. Optionally swap stdio transport for HTTP if many consumers share one large index — but only when the operational cost is justified.

## Related

- [Docs MCP system page](../../apps/docs-site/src/content/docs/systems/docs-mcp.md) — the consumer-facing explanation
- [`apps/docs-site/scripts/generate-static-docs.mjs`](../../apps/docs-site/scripts/generate-static-docs.mjs) — the static-side generator (llms.txt + per-page raw markdown)
- [`apps/docs-site/src/components/PageActions.astro`](../../apps/docs-site/src/components/PageActions.astro) — the "Copy page" dropdown that consumes those static artifacts
- [MCP spec — stdio transport](https://spec.modelcontextprotocol.io/specification/server/transports/)
- [llmstxt.org](https://llmstxt.org/) — the static-corpus convention
