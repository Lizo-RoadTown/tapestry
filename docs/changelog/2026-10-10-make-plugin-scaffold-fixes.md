---
date: 2026-10-10
kind: fix
area: tapestry-cli
prs: []
adrs: []
memory:
supersedes:
---

# make-plugin scaffold fixes: opt-in memory, UTF-8 hook, multi-plugin marketplace

**What:** Three fixes to `tapestry make-plugin` (`packages/cli/tapestry_cli/make_plugin.py`), found by the education-lab agent while using it:

- **loom-memory is now opt-in** (`--with-memory`, default off). The scaffold previously always added an `mcpServers.loom-memory` block, which double-registers loom-memory for anyone who already has `tapestry-discipline` installed.
- **Generated hook decodes stdin as UTF-8.** The generated `scripts/pre_tool_use.py` used `json.load(sys.stdin)`, which decodes cp1252 on Windows and garbles non-ASCII input. Now `json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))`. (Same fix landed for the live discipline hooks separately.)
- **`--no-marketplace` mode** for adding a plugin to an existing multi-plugin marketplace repo: skips the per-plugin `marketplace.json` and switches the README/next-steps to "add an entry to your marketplace's marketplace.json" instead of "publish as its own repo."

Bumped tapestry-cli 0.1.6 → 0.1.7.

**Verification:** default build has no `mcpServers` and keeps `marketplace.json`; `--with-memory` registers loom-memory; `--no-marketplace` omits `marketplace.json`; the generated hook compiles and contains the UTF-8 decode, not `json.load(sys.stdin)`.
