"""pytest configuration for skill_making tests.

These tests pin the wire-contract invariants per
`loom_agent_to_ms_agent_coordinated_alignment_plan_2026_06_13`.

All tests in this directory are pure unit tests — no DB, no network.
The receiver itself talks to Postgres, but the layers we pin here (HMAC
verify, schema validation, response shape) are testable in isolation.
"""
import sys
import pathlib

# Allow `from services... / from core...` imports when running pytest
# directly from this directory or from the repo root.
_repo_root = pathlib.Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
