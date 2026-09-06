"""Tests for stop_audit.py's v0.1.9 agentic-upskilling boundary check.

Run from the plugin root:

    python -m unittest integrations/claude-code/tapestry-discipline/tests/test_stop_audit_upskilling.py

Cover the three components of the check:

1. Session metrics scanning (assistant turns, tool calls, git actions,
   upskilling-report detection) over a synthetic JSONL transcript.
2. Substantive-boundary heuristic (3 thresholds, ANY-of semantics).
3. Marker-file logic that prevents repeated warnings within one session.

The existing PROBE-citation check is left intact — only the new code
paths are tested here.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# Import the hook under test (mirrors test_pre_tool_use.py pattern).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import stop_audit  # noqa: E402


# ---------------------------------------------------------------------------
# Transcript fixtures — minimal JSONL shapes the hook reads.
# ---------------------------------------------------------------------------


def _assistant_text_entry(text: str) -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def _assistant_tool_use_entry(tool_name: str, tool_input: dict | None = None) -> dict:
    return {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "name": tool_name, "input": tool_input or {}}
        ],
    }


def _user_entry(text: str) -> dict:
    return {"role": "user", "content": [{"type": "text", "text": text}]}


def _jsonl(*entries: dict) -> str:
    return "\n".join(json.dumps(e) for e in entries) + "\n"


# ---------------------------------------------------------------------------
# Session metrics scan
# ---------------------------------------------------------------------------


class TestScanSessionMetrics(unittest.TestCase):
    """_scan_session_metrics walks the JSONL once and returns counts +
    detection flags. Tests the canonical shapes."""

    def test_empty_transcript_returns_zero_counts(self):
        m = stop_audit._scan_session_metrics("")
        self.assertEqual(m["assistant_turns"], 0)
        self.assertEqual(m["tool_calls"], 0)
        self.assertFalse(m["git_action_seen"])
        self.assertFalse(m["upskilling_report_seen"])

    def test_assistant_turns_counted(self):
        raw = _jsonl(
            _user_entry("hi"),
            _assistant_text_entry("hello"),
            _user_entry("again"),
            _assistant_text_entry("yes"),
            _user_entry("third"),
            _assistant_text_entry("third"),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertEqual(m["assistant_turns"], 3)

    def test_tool_calls_counted_across_turns(self):
        raw = _jsonl(
            _assistant_tool_use_entry("Read", {"file_path": "/foo.py"}),
            _assistant_tool_use_entry("Bash", {"command": "ls"}),
            _assistant_tool_use_entry("Grep", {"pattern": "x"}),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertEqual(m["tool_calls"], 3)

    def test_git_action_detected_in_bash_command(self):
        raw = _jsonl(
            _assistant_tool_use_entry("Bash", {"command": "git commit -m foo"}),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertTrue(m["git_action_seen"])

    def test_gh_pr_merge_detected_as_shipped_action(self):
        # A PR squash-merge has no local `git merge`; detect the gh flow so
        # shipping a PR is a first-class upskilling boundary.
        raw = _jsonl(
            _assistant_tool_use_entry("Bash", {"command": "gh pr merge 170 --squash --delete-branch"}),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertTrue(m["git_action_seen"])

    def test_gh_pr_create_detected_as_shipped_action(self):
        raw = _jsonl(
            _assistant_tool_use_entry("Bash", {"command": "gh pr create --title x --body y"}),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertTrue(m["git_action_seen"])

    def test_git_action_detected_in_assistant_text(self):
        raw = _jsonl(
            _assistant_text_entry("Now running git push origin main"),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertTrue(m["git_action_seen"])

    def test_prose_phrases_alone_dont_count(self):
        # REGRESSION: emitting the report's section-header phrases in assistant
        # text must NOT count as the report being run. The old detector matched
        # these phrases anywhere in the transcript, which false-fired whenever
        # the report/observer/spec was merely discussed (163/166 in-scope
        # sessions). Detection now requires an actual memory_write tool block.
        raw = _jsonl(
            _assistant_text_entry(
                "Upskilling pass:\n\n"
                "Skills invoked this session:\n  - layered-explanation (5)\n\n"
                "Tools called this session:\n  - Read (10)\n\n"
                "Promotion candidates:\n  - probe_then_cite"
            ),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertFalse(m["upskilling_report_seen"])

    def test_memory_read_of_prior_report_does_not_count(self):
        # A memory_READ/recall of a prior upskilling_report_* record must NOT
        # trip the flag (only a memory_write does). Closes the second loophole.
        raw = _jsonl(
            _assistant_tool_use_entry(
                "mcp__loom-memory__memory_read",
                {"name": "upskilling_report_session_2026_06_12"},
            ),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertFalse(m["upskilling_report_seen"])

    def test_upskilling_report_detected_via_memory_write_tool_call(self):
        # Alternative: memory_write with name starting `upskilling_report_`.
        raw = _jsonl(
            _assistant_tool_use_entry(
                "mcp__loom-memory__memory_write",
                {
                    "name": "upskilling_report_session_2026_06_12",
                    "record_type": "lesson",
                    "content": "...",
                },
            ),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertTrue(m["upskilling_report_seen"])

    def test_partial_upskilling_phrases_dont_count(self):
        # Only one of the two markers present -> not detected.
        raw = _jsonl(
            _assistant_text_entry(
                "I will list Skills invoked this session next time."
            ),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertFalse(m["upskilling_report_seen"])

    def test_last_assistant_text_is_last(self):
        raw = _jsonl(
            _assistant_text_entry("first turn"),
            _assistant_text_entry("middle turn"),
            _assistant_text_entry("last turn"),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertEqual(m["last_assistant_text"], "last turn")


# ---------------------------------------------------------------------------
# Substantive boundary heuristic
# ---------------------------------------------------------------------------


class TestSubstantiveBoundary(unittest.TestCase):
    """Heuristic fires if ANY: git action, OR (10+ tool calls AND 3+ turns),
    OR 30+ turns alone."""

    def _metrics(self, turns=0, tool_calls=0, git=False):
        return {
            "assistant_turns": turns,
            "tool_calls": tool_calls,
            "git_action_seen": git,
            "upskilling_report_seen": False,
            "last_assistant_text": "",
        }

    def test_empty_session_not_substantive(self):
        self.assertFalse(stop_audit._is_substantive_boundary(self._metrics()))

    def test_short_conversational_session_not_substantive(self):
        # 2 turns, 0 tool calls — typical "hi / hello" exchange.
        self.assertFalse(stop_audit._is_substantive_boundary(
            self._metrics(turns=2, tool_calls=0)
        ))

    def test_git_action_alone_is_substantive(self):
        self.assertTrue(stop_audit._is_substantive_boundary(
            self._metrics(turns=1, tool_calls=1, git=True)
        ))

    def test_tool_and_turn_thresholds_combined(self):
        # 10 tools + 3 turns is at the boundary -> substantive.
        self.assertTrue(stop_audit._is_substantive_boundary(
            self._metrics(turns=3, tool_calls=10)
        ))

    def test_tools_below_threshold_not_substantive(self):
        # 9 tools, 3 turns — below the pair threshold.
        self.assertFalse(stop_audit._is_substantive_boundary(
            self._metrics(turns=3, tool_calls=9)
        ))

    def test_many_turns_alone_is_substantive(self):
        self.assertTrue(stop_audit._is_substantive_boundary(
            self._metrics(turns=30, tool_calls=0)
        ))


# ---------------------------------------------------------------------------
# Marker file behavior
# ---------------------------------------------------------------------------


class TestMarkerFile(unittest.TestCase):
    """Marker file logic — _warned_marker_path is pure; we test its naming
    + sanitization, not actual file I/O."""

    def test_marker_path_includes_session_id(self):
        p = stop_audit._warned_marker_path("abc-123")
        self.assertIn("abc-123", str(p))
        self.assertTrue(str(p).endswith("upskilling-warned"))

    def test_marker_path_sanitizes_special_chars(self):
        # Path separators, colons, etc. must not bleed into the filename.
        p = stop_audit._warned_marker_path("a/b:c\\d")
        self.assertNotIn("/", p.name)
        self.assertNotIn(":", p.name)
        self.assertNotIn("\\", p.name)

    def test_marker_path_truncates_long_ids(self):
        p = stop_audit._warned_marker_path("x" * 200)
        # Sanitized portion capped at 64 chars per the implementation.
        # Total filename = "session-<<=64>>-upskilling-warned" -> ≤ ~90 chars.
        self.assertLessEqual(len(p.name), 100)

    def test_marker_path_empty_session_id_safe(self):
        # Empty / unknown session id should still produce a valid path.
        p = stop_audit._warned_marker_path("")
        self.assertIn("session-", str(p))


# ---------------------------------------------------------------------------
# Recurring trigger (v0.1.20): measure work SINCE the last report
# ---------------------------------------------------------------------------


def _report_entry(name: str) -> dict:
    return _assistant_tool_use_entry(
        "mcp__loom-memory__memory_write",
        {"name": name, "record_type": "lesson", "content": "..."},
    )


class TestRecurringUpskilling(unittest.TestCase):
    """The trigger measures work done SINCE the most recent upskilling report,
    so it recurs in long-lived sessions instead of firing once per session."""

    def test_scan_returns_recurring_watermark_keys(self):
        m = stop_audit._scan_session_metrics("")
        for k in ("report_count", "turns_at_last_report",
                  "tools_at_last_report", "git_since_last_report"):
            self.assertIn(k, m)
        self.assertEqual(m["report_count"], 0)

    def test_report_count_increments_per_report(self):
        raw = _jsonl(
            _report_entry("upskilling_report_session_2026_06_12"),
            _assistant_text_entry("more"),
            _report_entry("upskilling_report_session_2026_06_13"),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertEqual(m["report_count"], 2)

    def test_watermark_snapshots_metrics_at_last_report(self):
        # Two work turns, then a report (the 3rd assistant turn) -> snapshot 3.
        raw = _jsonl(
            _assistant_text_entry("work 1"),
            _assistant_text_entry("work 2"),
            _report_entry("upskilling_report_session_2026_06_12"),
            _assistant_text_entry("after 1"),
            _assistant_text_entry("after 2"),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertEqual(m["assistant_turns"], 5)
        self.assertEqual(m["turns_at_last_report"], 3)

    def test_git_before_report_does_not_count_as_since(self):
        raw = _jsonl(
            _assistant_tool_use_entry("Bash", {"command": "git commit -m a"}),
            _report_entry("upskilling_report_session_2026_06_12"),
            _assistant_text_entry("quiet after"),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertTrue(m["git_action_seen"])         # whole session: yes
        self.assertFalse(m["git_since_last_report"])  # since the report: no

    def test_git_after_report_counts_as_since(self):
        raw = _jsonl(
            _report_entry("upskilling_report_session_2026_06_12"),
            _assistant_tool_use_entry("Bash", {"command": "git commit -m b"}),
        )
        m = stop_audit._scan_session_metrics(raw)
        self.assertTrue(m["git_since_last_report"])

    def test_since_report_metrics_are_deltas(self):
        metrics = {
            "assistant_turns": 40, "tool_calls": 25, "git_action_seen": True,
            "turns_at_last_report": 30, "tools_at_last_report": 20,
            "git_since_last_report": False,
        }
        since = stop_audit._since_report_metrics(metrics)
        self.assertEqual(since["assistant_turns"], 10)
        self.assertEqual(since["tool_calls"], 5)
        self.assertFalse(since["git_action_seen"])

    def test_no_rewarn_immediately_after_a_big_report(self):
        # Whole session is substantive, but nothing has happened since the
        # report -> since-boundary not crossed -> no re-warn yet.
        metrics = {
            "assistant_turns": 35, "tool_calls": 40, "git_action_seen": True,
            "turns_at_last_report": 35, "tools_at_last_report": 40,
            "git_since_last_report": False,
        }
        self.assertFalse(
            stop_audit._is_substantive_boundary(
                stop_audit._since_report_metrics(metrics)
            )
        )

    def test_rewarn_after_new_work_since_report(self):
        # A single git action since the report re-crosses the boundary.
        metrics = {
            "assistant_turns": 36, "tool_calls": 41, "git_action_seen": True,
            "turns_at_last_report": 35, "tools_at_last_report": 40,
            "git_since_last_report": True,
        }
        self.assertTrue(
            stop_audit._is_substantive_boundary(
                stop_audit._since_report_metrics(metrics)
            )
        )

    def test_read_marker_absent_returns_none(self):
        self.assertIsNone(
            stop_audit._read_marker("no-such-session-xyz-987654321")
        )


if __name__ == "__main__":
    unittest.main()
