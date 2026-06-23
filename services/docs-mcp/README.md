# tapestry-docs-mcp

MCP server that exposes the Tapestry documentation as queryable tools. Any Claude Code session (or other MCP client) can call `tapestry_docs_search`, `tapestry_docs_read`, `tapestry_docs_list` to read the docs corpus directly instead of fetching individual pages or pattern-matching from training data.

Companion to the LangChain / Mintlify [docs-as-MCP pattern](https://llmstxt.org/) — same shape, applied to Tapestry's Astro Starlight site.

## Status

**Skeleton scaffold — not deployed.** This directory contains the service code; deployment to Render is a separate operator step. See [Deploy](#deploy) below.

The forward-looking page at [`apps/docs-site/src/content/docs/systems/docs-mcp.md`](../../apps/docs-site/src/content/docs/systems/docs-mcp.md) describes the consumer-facing experience once the service is live.

## What it exposes

Three tools via MCP HTTP transport at `/mcp`:

| Tool | Signature | Returns |
|---|---|---|
| `tapestry_docs_search` | `query: str, limit: int = 5` | Top-N matching doc slugs + excerpts |
| `tapestry_docs_read` | `slug: str` | Full body of the named doc |
| `tapestry_docs_list` | `section: str \| None = None` | All slugs (optionally filtered to a section) |

Plus two static endpoints:

| Endpoint | Purpose |
|---|---|
| `/llms.txt` | Flattened text corpus per the [llmstxt.org](https://llmstxt.org/) convention. Read by LLM clients that don't speak MCP. |
| `/.well-known/mcp.json` | MCP discovery manifest. Read by MCP clients to auto-configure the tool list. |

## Source of truth

The corpus is the markdown files in `apps/docs-site/src/content/docs/**/*.md{,x}`. The service reads them at startup (in-memory index — corpus is small enough that disk-backed search isn't worth the operational overhead).

When the docs site is rebuilt, this service must be redeployed to pick up the changes. Future enhancement: webhook from Vercel build to Render to trigger redeploy automatically.

## Files

```
services/docs-mcp/
├── README.md          # this file
├── main.py            # FastAPI app: /health, /llms.txt, /.well-known/mcp.json, mounts MCP at /mcp
├── mcp_http.py        # StreamableHTTPSessionManager wrapper (no auth — public read-only)
├── mcp_server.py      # MCP tool definitions: search, read, list
├── indexer.py         # in-memory full-text search index over the docs corpus
├── corpus.py          # corpus loader + llms.txt generator
├── requirements.txt   # fastapi, uvicorn, mcp, pydantic
└── render.yaml.example  # Render Blueprint template (not auto-deployed)
```

## Run locally

```sh
cd services/docs-mcp
pip install -r requirements.txt
DOCS_ROOT=../../apps/docs-site/src/content/docs uvicorn main:app --port 8002
```

Then visit:

- `http://localhost:8002/health` → `{"status": "ok"}`
- `http://localhost:8002/llms.txt` → flattened corpus
- `http://localhost:8002/.well-known/mcp.json` → discovery manifest

To call MCP tools, configure an MCP client (Claude Code, etc.) with `http://localhost:8002/mcp` as the URL.

## Deploy

This service is NOT auto-deployed. The platform owner deploys it manually:

1. Provision a Render Web Service from `render.yaml.example` (rename to `render.yaml` in your deployment branch).
2. Set the `DOCS_ROOT` env var to the path the build sees (default in the blueprint: clones the tapestry repo, points to `apps/docs-site/src/content/docs/`).
3. Note the deployed URL (e.g., `https://tapestry-docs-mcp.onrender.com`).
4. Update `apps/docs-site/src/content/docs/systems/docs-mcp.md` to remove the caution banner and replace placeholders with the real URL.
5. Add the MCP server entry to `integrations/claude-code/tapestry-discipline/.claude-plugin/plugin.json` so every consuming project auto-discovers it.
6. Publish `/llms.txt` + `/.well-known/mcp.json` at the docs site root (Vercel rewrite from `apps/docs-site/vercel.json` to the Render service, OR static-build the corpus at the docs site directly — see indexer-vs-static decision in [the docs MCP page](../../apps/docs-site/src/content/docs/systems/docs-mcp.md)).

## Env vars

| Var | Default | Purpose |
|---|---|---|
| `DOCS_ROOT` | `../../apps/docs-site/src/content/docs` | Path to the docs corpus root |
| `SITE_BASE_URL` | `https://tapestry-khaki.vercel.app` | Used in `/llms.txt` and `/.well-known/mcp.json` to construct absolute URLs |
| `MCP_PUBLIC_URL` | unset | The URL clients should connect to (e.g., `https://tapestry-docs-mcp.onrender.com/mcp`); appears in `/.well-known/mcp.json` |

## Why no auth

The Tapestry docs are public. Any auth would be friction without benefit. Compare with `the-loom/services/agent-context/` which gates writes per tenant — docs MCP only reads, and reads are public.

## Tests

Deferred to a follow-on PR. The skeleton compiles and runs but does not have a test suite yet.

## Related

- [The docs MCP page (consumer-facing)](../../apps/docs-site/src/content/docs/systems/docs-mcp.md)
- [`the-loom/services/agent-context/`](https://github.com/Lizo-RoadTown/the-loom/tree/main/services/agent-context) — the template this followed
- [LangChain docs MCP pattern](https://llmstxt.org/) — the public reference implementation
- [MCP spec — HTTP transport](https://spec.modelcontextprotocol.io/specification/server/transports/)
