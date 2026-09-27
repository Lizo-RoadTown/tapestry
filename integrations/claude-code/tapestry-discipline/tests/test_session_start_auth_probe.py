"""Tests for the v0.1.21 SessionStart auth probe.

The reachability probe used to check only `/health` (unauthenticated), so an
expired/invalid memory token — which 401s every real memory_* call — passed
silently (the failure mode that hid the Aug-2026 outage for ~5 weeks). These
tests pin the new behavior: `_check_auth` distinguishes token-rejected from
host-down, and `_mcp_status_block` raises a loud CONCRETE-RULE violation when
the host is up but the token is rejected.

Run from the plugin root:
    python -m pytest integrations/claude-code/tapestry-discipline/tests/test_session_start_auth_probe.py -q
"""
from __future__ import annotations

import sys
import urllib.error
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import session_start  # noqa: E402


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://mem.example/v1/recall", code=code,
        msg="err", hdrs=None, fp=None,
    )


class TestCheckAuth(unittest.TestCase):
    def test_no_token_is_skipped_not_flagged(self):
        with mock.patch.dict(session_start.os.environ, {}, clear=True):
            state, _ = session_start._check_auth("https://mem.example")
        self.assertEqual(state, "no_token")

    def test_401_is_unauthorized(self):
        with mock.patch.dict(session_start.os.environ,
                             {"TAPESTRY_MEMORY_API_KEY": "k"}, clear=True), \
             mock.patch("urllib.request.urlopen", side_effect=_http_error(401)):
            state, detail = session_start._check_auth("https://mem.example")
        self.assertEqual(state, "unauthorized")
        self.assertIn("401", detail)

    def test_403_is_unauthorized(self):
        with mock.patch.dict(session_start.os.environ,
                             {"TAPESTRY_MEMORY_API_KEY": "k"}, clear=True), \
             mock.patch("urllib.request.urlopen", side_effect=_http_error(403)):
            state, _ = session_start._check_auth("https://mem.example")
        self.assertEqual(state, "unauthorized")

    def test_500_is_not_blamed_on_token(self):
        with mock.patch.dict(session_start.os.environ,
                             {"TAPESTRY_MEMORY_API_KEY": "k"}, clear=True), \
             mock.patch("urllib.request.urlopen", side_effect=_http_error(500)):
            state, _ = session_start._check_auth("https://mem.example")
        self.assertEqual(state, "ok")

    def test_network_blip_is_skip(self):
        with mock.patch.dict(session_start.os.environ,
                             {"TAPESTRY_MEMORY_API_KEY": "k"}, clear=True), \
             mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("boom")):
            state, _ = session_start._check_auth("https://mem.example")
        self.assertEqual(state, "skip")


class TestStatusBlock(unittest.TestCase):
    def test_host_up_but_token_rejected_raises_violation(self):
        with mock.patch.object(session_start, "_check_mcp_reachable",
                               return_value=(True, "OK")), \
             mock.patch.object(session_start, "_check_auth",
                               return_value=("unauthorized", "HTTP 401")):
            block = "\n".join(session_start._mcp_status_block("https://mem.example"))
        self.assertIn("CONCRETE-RULE VIOLATION", block)
        self.assertIn("AUTH REJECTED", block)
        self.assertIn("TAPESTRY_MEMORY_API_KEY", block)  # actionable fix present

    def test_host_up_and_token_ok_is_healthy(self):
        with mock.patch.object(session_start, "_check_mcp_reachable",
                               return_value=(True, "OK")), \
             mock.patch.object(session_start, "_check_auth",
                               return_value=("ok", "HTTP 200")):
            block = "\n".join(session_start._mcp_status_block("https://mem.example"))
        self.assertIn("MCP transport", block)
        self.assertIn("token accepted", block)
        self.assertNotIn("VIOLATION", block)

    def test_host_down_still_raises_unreachable(self):
        with mock.patch.object(session_start, "_check_mcp_reachable",
                               return_value=(False, "HTTP 502")):
            block = "\n".join(session_start._mcp_status_block("https://mem.example"))
        self.assertIn("MCP UNREACHABLE", block)
        self.assertIn("CONCRETE-RULE VIOLATION", block)


if __name__ == "__main__":
    unittest.main()
