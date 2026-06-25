---
title: Connect VS Code (without Claude Code)
description: Add Tapestry's memory and docs MCP servers to VS Code's native MCP support, so Copilot Chat and other MCP-aware assistants can use them — no Claude Code, no extension required.
---

VS Code (1.99+) can talk to MCP servers natively. This wires Tapestry's two servers — your memory and the docs search — into that, so Copilot Chat and any other MCP-aware assistant in the editor can use them. No Claude Code, no extension.

Prefer one click? The [Tapestry VS Code extension](https://marketplace.visualstudio.com/items?itemName=tapestry.tapestry) registers the same two servers for you. This page is the manual path — useful when you want the wiring in your repo, or you'd rather not install an extension.

## Prerequisites

- **VS Code 1.99 or newer** — native MCP support.
- **For the docs server:** `pip install tapestry-docs-mcp`, on the same `python` your editor can reach.
- **For the memory server:** the URL of your Tapestry memory deployment (you run your own; the server is skipped cleanly if you leave it out).

## Configure

Add the servers to a `.vscode/mcp.json` file. Put it in your workspace to share the wiring with a repo, or open your user-level file with the **MCP: Open User Configuration** command to use it everywhere.

```json
{
  "servers": {
    "tapestry-docs": {
      "command": "python",
      "args": ["-m", "docs_mcp"]
    },
    "loom-memory": {
      "type": "http",
      "url": "https://your-memory-host.example.com/mcp/memory/"
    }
  }
}
```

- **`tapestry-docs`** runs locally over stdio. If `python` doesn't resolve to the environment where you ran `pip install tapestry-docs-mcp`, use `python3` or an absolute interpreter path instead.
- **`loom-memory`** is your own deployment. Replace the URL with yours. To use only the docs server, drop the `loom-memory` block entirely.

## Verify

1. Reload the VS Code window.
2. Open Copilot Chat (or another MCP-aware chat surface).
3. The Tapestry tools — `tapestry_docs_search`, and `memory_recall` / `memory_write` if you wired the memory server — appear in the tools list.
4. Call `tapestry_docs_search` with a query like `observer`; it should return ranked results.

If the memory tools return 401 or 404, check that your deployment is reachable from your machine and the URL is exact.

## Related

- [Quickstart — VS Code](/how-to/quickstart-vscode/) — the Claude Code path, which wires these servers through its own plugins.
- [The Tapestry VS Code extension](https://marketplace.visualstudio.com/items?itemName=tapestry.tapestry) — the same wiring as a one-click install.
- VS Code's own [MCP servers guide](https://code.visualstudio.com/docs/copilot/chat/mcp-servers) — the native MCP configuration reference.
