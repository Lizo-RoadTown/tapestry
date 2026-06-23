"""Stdio MCP server entry point.

Run with:
  python -m docs_mcp

The Tapestry docs corpus is loaded once at startup from DOCS_ROOT (env var,
defaults to apps/docs-site/src/content/docs/ relative to this package) and
indexed in memory. Search/read/list calls dispatch against that index.

Stdio transport (mcp.server.stdio.stdio_server) means each MCP client spawns
its own subprocess; no shared server, no network listener.
"""
from __future__ import annotations

import asyncio

from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions

from . import corpus
from . import indexer
from . import mcp_server


async def _run() -> None:
    docs = corpus.load_corpus(corpus.default_docs_root())
    mcp_server.set_index(indexer.Index(docs))

    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="tapestry-docs-mcp",
                server_version="0.1.0",
                capabilities=mcp_server.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
