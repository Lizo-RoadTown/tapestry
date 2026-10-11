---
date: 2026-10-10
kind: fix
area: tapestry-discipline
prs: []
adrs: []
memory:
supersedes:
---

# Decode hook stdin as UTF-8 (Windows cp1252 garbled non-ASCII)

**What:** All four tapestry-discipline hooks read their input with `json.load(sys.stdin)`. On Windows, `sys.stdin` decodes as cp1252, so non-ASCII hook payloads (e.g. em dashes in Write content) were mis-decoded — the PreToolUse write audit could silently miss them. Changed to `json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))` in `pre_tool_use.py`, `session_start.py`, `stop_audit.py`, `user_prompt_submit.py`. Bumped tapestry-discipline 0.1.21 → 0.1.22.

**Why it matters:** The hooks are load-bearing and most operators (including the author) run Windows. A write-audit that silently drops non-ASCII is a correctness hole, not cosmetic. Surfaced by the education-lab agent while using `tapestry make-plugin` (the generated scaffold has the same bug — fixed separately).

**Verification:** all four hooks compile; `scripts/check_plugin_versions.py` reports both plugins aligned.
