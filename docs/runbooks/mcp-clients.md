# MCP servers used by this repo

Cross-client reference for the MCP servers this project uses. Each agent client (Claude Code, Cursor, OpenAI Codex, deepagents, LlamaIndex agents) configures MCPs differently — this file documents the equivalent snippets so you can wire the same server into whichever surface you're working in.

## Active MCPs

| Server | Purpose | Auth | Config |
|--------|---------|------|--------|
| **llama_index_docs** | Search LlamaIndex / LlamaParse / LlamaCloud documentation. Useful for looking up current API details. | None | Active in [`.mcp.json`](.mcp.json) (Claude Code project-scoped) |

## Documented but inactive (commented stubs in `deepagents.toml`)

| Server | Purpose | Why off | Activate by |
|--------|---------|---------|-------------|
| **tooluniverse** | ~1000 scientific tools (PubMed, ArXiv, etc.) via Compact Mode | Biomedical-leaning, requires `pip install tooluniverse` | Uncomment `[mcp.tooluniverse]` block |
| **docker** | Container management — agent can inspect / restart / exec into containers | Significant capability bump; enable for a concrete use case, not preemptively | Uncomment one of the two `[mcp.docker]` variants in `deepagents.toml` |

## Per-client setup snippets

### Claude Code (CLI or VS Code extension)

Project-scoped, lives in [`.mcp.json`](.mcp.json) — already committed, no setup needed beyond opening this repo in Claude Code.

CLI equivalent (writes to your global `~/.claude.json`, NOT what we did):
```bash
claude mcp add llama-index-docs --transport http https://developers.llamaindex.ai/mcp
```

### Cursor

Add to `~/.cursor/mcp.json` or project `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "llama_index_docs": {
      "url": "https://developers.llamaindex.ai/mcp"
    }
  }
}
```

### OpenAI Codex

Add to `~/.codex/config.toml` (or project equivalent):
```toml
[mcp_servers.llama_index_docs]
url = "https://developers.llamaindex.ai/mcp"
```

### deepagents (this repo's runtime)

Uncomment the block in [`deepagents.toml`](deepagents.toml):
```toml
[mcp.llama_index_docs]
transport = "http"
url = "https://developers.llamaindex.ai/mcp"
```

### LlamaIndex agents (Python, direct)

```python
from llama_index.tools.mcp import McpToolSpec, BasicMCPClient
client = BasicMCPClient("https://developers.llamaindex.ai/mcp")
tools = await McpToolSpec(client=client).to_tool_list_async()
```
Requires `pip install llama-index llama-index-tools-mcp`.

## Project-scoped vs. user-scoped

- **Project-scoped** (`.mcp.json` in repo root) — travels with the repo, every clone gets it, doesn't pollute your global config. Use for MCPs that are specific to *this* project.
- **User-scoped** (`~/.claude.json`, `~/.cursor/mcp.json`, etc.) — available everywhere you work, regardless of which repo is open. Use for MCPs you want available across all your projects (e.g. a personal notes MCP, your own GitHub MCP).

This repo uses project-scoped for `llama_index_docs` because it's only relevant when working on Make_Skills (which uses LlamaParse).

## Adding a new MCP

1. Decide scope: project (this repo only) or user (everywhere).
2. Add to the relevant config file from the snippets above.
3. If project-scoped, update this file's "Active MCPs" table and commit.
4. Restart the client (Claude Code, Cursor, etc.) so it picks up the new server.
