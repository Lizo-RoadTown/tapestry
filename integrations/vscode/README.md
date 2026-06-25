# `integrations/vscode/`

The Tapestry VS Code extension. Registers Tapestry's MCP servers (memory + docs) with VS Code's Language Model API so they're available to Copilot Chat and other MCP-aware consumers in the editor.

This is **complementary to**, not a replacement for, the [Claude Code extension path](https://tapestry-khaki.vercel.app/how-to/quickstart-vscode/). If you use Claude Code in VS Code, the existing `tapestry-discipline` + `tapestry-patterns` plugins already wire the servers via Claude Code's own `.mcp.json`. This extension is for users who want the same servers available to VS Code's native MCP clients (e.g. Copilot Chat).

## What it registers

| MCP server | Transport | Requirement |
|---|---|---|
| `tapestry-docs` | stdio | `pip install tapestry-docs-mcp` on PATH |
| `loom-memory` | HTTP | Your Tapestry memory MCP deployment URL |

## Install

Either install from the VS Code Marketplace (once published — pending the operator's publisher setup) or build + install locally from this directory:

```sh
cd integrations/vscode
npm install
npm run compile
npx vsce package
code --install-extension tapestry-0.1.0.vsix
```

## Configure

Open VS Code settings (`Cmd/Ctrl+,`) and search for "Tapestry". Two settings matter:

- **`tapestry.memoryMcpUrl`** — paste your deployment's memory MCP URL, e.g. `https://your-memory-host.example.com/mcp/memory/`. Leave empty to skip the memory server cleanly (the docs server still registers).
- **`tapestry.docsMcpCommand`** — defaults to `python`. Set to `python3` or an absolute interpreter path if `python` on PATH doesn't resolve to the venv where you ran `pip install tapestry-docs-mcp`.
- **`tapestry.docsMcpEnabled`** — defaults to true. Set to false if you don't want the docs server registered.

Settings can also live in `.vscode/settings.json` per-workspace if you want per-project overrides.

## Verify

After install + configuration:

1. Reload the VS Code window.
2. Open Copilot Chat (or any MCP-aware chat surface).
3. The Tapestry tools (`memory_recall`, `memory_write`, `tapestry_docs_search`, etc.) should appear in the tools list.
4. Try a tool call — `tapestry_docs_search` with `query: "observer"` should return ranked hits.

If the memory tools 401 or 404, check that your deployment is reachable from your machine and the URL is right.

## What's NOT in v0.1.0

- No status bar UI
- No command palette ops (`Tapestry: Recall` etc.)
- No settings UI beyond the standard configuration page
- No signup flow (the memory URL is whatever you stand up)

All planned for v0.2+.

## See also

- [VS Code MCP server extension guide](https://code.visualstudio.com/api/extension-guides/ai/mcp) — the API this extension uses
- [Tapestry — Quickstart (VS Code via Claude Code)](https://tapestry-khaki.vercel.app/how-to/quickstart-vscode/) — the parallel path that doesn't need this extension
- [Tapestry Docs MCP](https://tapestry-khaki.vercel.app/systems/docs-mcp/) — what `tapestry-docs` is
- [Tapestry Memory MCP](https://tapestry-khaki.vercel.app/systems/memory/) — what `loom-memory` is
