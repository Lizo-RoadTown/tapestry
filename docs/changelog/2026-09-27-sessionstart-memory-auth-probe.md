# 2026-09-27 — SessionStart memory-auth probe (tapestry-discipline 0.1.21)

The SessionStart reachability probe (`_mcp_status_block` / `_check_mcp_reachable`)
checked only `/health`, which requires **no auth** — so an expired or wrong memory
token, which 401s every authenticated `memory_*` call, passed the probe silently
and the session reported "MCP reachable ... OK." That `/health`-only blind spot is
what hid the Aug-2026 loom-memory outage for ~5 weeks (and let a later agent read
the healthy host as proof memory was fine).

Added `_check_auth` in [session_start.py](../../integrations/claude-code/tapestry-discipline/scripts/session_start.py):
on a reachable host, it makes one authenticated call (`POST /v1/recall`, the same
auth path the MCP tools use) and, on **401/403**, raises a loud
`*** CONCRETE-RULE VIOLATION DETECTED ***` block that names the exact fix (use the
`Bearer ${TAPESTRY_MEMORY_API_KEY}` env-ref, not a literal JWT; set the key; restart).
A missing token → self-host fallback (no violation); a 5xx or network blip → not
blamed on the token. Host-down still raises the existing unreachable violation.

Tests: `tests/test_session_start_auth_probe.py` (no_token / 401 / 403 / 5xx / blip,
plus the three status-block branches). Plugin bumped 0.1.20 → 0.1.21 (plugin.json +
marketplace.json).

**Why:** CORE DIRECTIVE 1 — memory must be not just *reachable* but *usable*.
host-up ≠ memory-usable.

Pre-existing, unrelated: `test_scope.py` (stale hardcoded-substring `_in_scope`
assertions) and `test_observer.py` (status transitions) fail independently of this
change; not addressed here.
