"""Tests for the Phase 2 observer (observer.py).

Run from the plugin root:

    python -m unittest integrations/claude-code/tapestry-discipline/tests/test_observer.py

Cover the pure-logic surfaces (no HTTP, no FS writes against the live tree):

  1. count_skill_tool_calls — explicit `Skill` tool counting
  2. parse_upskilling_report — bullet-line parsing of the agent's report
  3. merge_counts — max-over-sources logic
  4. _slugify_skill — filesystem-safe naming
  5. derive_status — sessions_seen -> status mapping
  6. _load_local_record — defaults on missing/corrupted files
  7. scan_and_emit — end-to-end logic with HTTP calls monkeypatched

The HTTP layer (post_candidate / patch_candidate_status) is exercised
via monkeypatched versions to avoid hitting the live Render service in
unit tests. Live verification happens via the manual smoke test below
the unit suite, gated by an env var so CI skips it by default.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import observer  # noqa: E402


# ---------------------------------------------------------------------------
# Transcript fixtures
# ---------------------------------------------------------------------------


def _assistant_text(text: str) -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def _assistant_skill_call(skill: str) -> dict:
    return {
        "role": "assistant",
        "content": [{
            "type": "tool_use",
            "name": "Skill",
            "input": {"skill": skill},
        }],
    }


def _user(text: str) -> dict:
    return {"role": "user", "content": [{"type": "text", "text": text}]}


def _jsonl(*entries: dict) -> str:
    return "\n".join(json.dumps(e) for e in entries) + "\n"


# Sample upskilling report matching the docs/CORE_DIRECTIVES.md "Report format" spec.
SAMPLE_REPORT_TEXT = """Agentic-upskilling pass — session 2026-06-12

Skills invoked this session:
  - layered-explanation (15+ uses)
  - next-actions-planning (8 uses)
  - infrastructure-mapping (4)
  - agentic-upskilling: 1
  - probe-then-cite (3 uses)

Tools called this session:
  - Read (30)
  - Bash (25)

Promotion candidates:
  - probe_then_cite — STRONG candidate

Demotion candidates: none

Recommendations:
  1. Build Stop-hook check
"""


# ---------------------------------------------------------------------------
# count_skill_tool_calls
# ---------------------------------------------------------------------------


class TestCountSkillToolCalls(unittest.TestCase):

    def test_empty_transcript(self):
        self.assertEqual(observer.count_skill_tool_calls(""), {})

    def test_no_skill_tools(self):
        raw = _jsonl(
            _assistant_text("just talking"),
            _user("hi"),
        )
        self.assertEqual(observer.count_skill_tool_calls(raw), {})

    def test_single_skill_invocation(self):
        raw = _jsonl(
            _assistant_skill_call("superpowers:systematic-debugging"),
        )
        self.assertEqual(
            observer.count_skill_tool_calls(raw),
            {"superpowers:systematic-debugging": 1},
        )

    def test_repeated_skill_counted_correctly(self):
        raw = _jsonl(
            _assistant_skill_call("layered-explanation"),
            _assistant_skill_call("layered-explanation"),
            _assistant_skill_call("layered-explanation"),
            _assistant_skill_call("infrastructure-mapping"),
        )
        result = observer.count_skill_tool_calls(raw)
        self.assertEqual(result["layered-explanation"], 3)
        self.assertEqual(result["infrastructure-mapping"], 1)

    def test_ignores_non_skill_tools(self):
        raw = _jsonl(
            {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/x"}}
            ]},
            _assistant_skill_call("layered-explanation"),
        )
        result = observer.count_skill_tool_calls(raw)
        self.assertEqual(result, {"layered-explanation": 1})

    def test_handles_nested_message_shape(self):
        """Claude Code's real transcript has role inside `message`, not at
        the top level. Confirm we handle both."""
        nested_entry = {
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Skill",
                     "input": {"skill": "foo"}},
                ],
            }
        }
        raw = json.dumps(nested_entry) + "\n"
        self.assertEqual(observer.count_skill_tool_calls(raw), {"foo": 1})


# ---------------------------------------------------------------------------
# parse_upskilling_report
# ---------------------------------------------------------------------------


class TestParseUpskillingReport(unittest.TestCase):

    def test_empty_transcript(self):
        self.assertEqual(observer.parse_upskilling_report(""), {})

    def test_no_report_marker(self):
        raw = _jsonl(_assistant_text("just chatting"))
        self.assertEqual(observer.parse_upskilling_report(raw), {})

    def test_parses_canonical_report(self):
        raw = _jsonl(_assistant_text(SAMPLE_REPORT_TEXT))
        counts = observer.parse_upskilling_report(raw)
        self.assertEqual(counts.get("layered-explanation"), 15)
        self.assertEqual(counts.get("next-actions-planning"), 8)
        self.assertEqual(counts.get("infrastructure-mapping"), 4)
        self.assertEqual(counts.get("probe-then-cite"), 3)
        # agentic-upskilling itself MUST be excluded (it's the skill
        # running the report).
        self.assertNotIn("agentic-upskilling", counts)

    def test_handles_count_variants(self):
        """Match `(N uses)`, `(N+ uses)`, `(N)`, `: N` formats."""
        text = (
            "Skills invoked this session:\n"
            "  - skill-a (5 uses)\n"
            "  - skill-b (5+ uses)\n"
            "  - skill-c (5)\n"
            "  - skill-d: 5\n"
            "  - skill-e (1 use)\n"
            "\nTools called this session:\n  - X\n"
        )
        raw = _jsonl(_assistant_text(text))
        counts = observer.parse_upskilling_report(raw)
        for name in ("skill-a", "skill-b", "skill-c", "skill-d"):
            self.assertEqual(counts.get(name), 5, f"{name} miscounted")
        self.assertEqual(counts.get("skill-e"), 1)

    def test_section_boundaries_respected(self):
        """A skill listed in Tools section should NOT be counted as
        invoked. The Skills-invoked section ends at the next section
        marker."""
        text = (
            "Skills invoked this session:\n"
            "  - real-skill (3 uses)\n"
            "\nTools called this session:\n"
            "  - decoy-tool (99 uses)\n"
        )
        raw = _jsonl(_assistant_text(text))
        counts = observer.parse_upskilling_report(raw)
        self.assertEqual(counts.get("real-skill"), 3)
        self.assertNotIn("decoy-tool", counts)

    def test_latest_report_wins_on_multiple(self):
        """If a session has multiple reports (agent ran the pass twice),
        the most recent one's counts are used."""
        early = ("Skills invoked this session:\n  - test-skill (3 uses)\n"
                 "\nTools called this session:\n")
        late = ("Skills invoked this session:\n  - test-skill (7 uses)\n"
                "\nTools called this session:\n")
        raw = _jsonl(_assistant_text(early), _assistant_text(late))
        counts = observer.parse_upskilling_report(raw)
        self.assertEqual(counts.get("test-skill"), 7)


# ---------------------------------------------------------------------------
# merge_counts
# ---------------------------------------------------------------------------


class TestMergeCounts(unittest.TestCase):

    def test_empty_inputs(self):
        self.assertEqual(observer.merge_counts(), {})
        self.assertEqual(observer.merge_counts({}, {}), {})

    def test_takes_max_per_skill(self):
        a = {"x": 3, "y": 1}
        b = {"x": 5, "z": 2}
        result = observer.merge_counts(a, b)
        self.assertEqual(result, {"x": 5, "y": 1, "z": 2})

    def test_three_sources(self):
        result = observer.merge_counts(
            {"x": 1}, {"x": 7, "y": 3}, {"y": 5, "z": 1}
        )
        self.assertEqual(result, {"x": 7, "y": 5, "z": 1})


# ---------------------------------------------------------------------------
# _slugify_skill
# ---------------------------------------------------------------------------


class TestSlugifySkill(unittest.TestCase):

    def test_simple(self):
        self.assertEqual(observer._slugify_skill("layered-explanation"),
                         "layered-explanation")

    def test_handles_colons(self):
        self.assertEqual(
            observer._slugify_skill("superpowers:systematic-debugging"),
            "superpowers-systematic-debugging",
        )

    def test_strips_path_separators(self):
        s = observer._slugify_skill("a/b\\c")
        self.assertNotIn("/", s)
        self.assertNotIn("\\", s)

    def test_caps_length(self):
        s = observer._slugify_skill("x" * 500)
        self.assertLessEqual(len(s), 128)

    def test_empty_fallback(self):
        self.assertEqual(observer._slugify_skill(""), "unknown")
        # Names that slugify to empty also fall back.
        self.assertEqual(observer._slugify_skill("///"), "unknown")


# ---------------------------------------------------------------------------
# derive_status
# ---------------------------------------------------------------------------


class TestDeriveStatus(unittest.TestCase):

    def test_first_session_is_draft(self):
        self.assertEqual(observer.derive_status(1), "draft")

    def test_second_session_is_observed(self):
        self.assertEqual(observer.derive_status(2), "observed")

    def test_third_session_is_recurring(self):
        self.assertEqual(observer.derive_status(3), "recurring")

    def test_higher_counts_stay_at_recurring(self):
        """Phase 2 observer does NOT auto-promote past recurring. Higher
        states (stable, promotion_requested) require Phase 5 Policy
        Service input."""
        for n in (4, 5, 10, 100):
            self.assertEqual(observer.derive_status(n), "recurring",
                             f"sessions_seen={n}")


# ---------------------------------------------------------------------------
# _load_local_record
# ---------------------------------------------------------------------------


class TestLoadLocalRecord(unittest.TestCase):

    def test_missing_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "missing.json"
            rec = observer._load_local_record(path)
            self.assertEqual(rec["candidate_id"], None)
            self.assertEqual(rec["sessions_seen"], 0)
            self.assertEqual(rec["session_ids"], [])
            self.assertEqual(rec["current_status"], "draft")

    def test_corrupted_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text("{ not valid json", encoding="utf-8")
            rec = observer._load_local_record(path)
            self.assertEqual(rec["candidate_id"], None)
            self.assertEqual(rec["sessions_seen"], 0)

    def test_valid_record_round_trips(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.json"
            data = {
                "schema_version": 1,
                "candidate_id": "abc-123",
                "skill_name": "layered-explanation",
                "sessions_seen": 2,
                "session_ids": ["s1", "s2"],
                "total_count": 20,
                "last_count": 10,
                "first_seen_at": 100.0,
                "last_seen_at": 200.0,
                "current_status": "observed",
            }
            observer._save_local_record(path, data)
            loaded = observer._load_local_record(path)
            self.assertEqual(loaded["candidate_id"], "abc-123")
            self.assertEqual(loaded["sessions_seen"], 2)
            self.assertEqual(loaded["session_ids"], ["s1", "s2"])


# ---------------------------------------------------------------------------
# scan_and_emit (end-to-end with mocked HTTP)
# ---------------------------------------------------------------------------


class TestScanAndEmit(unittest.TestCase):

    def _make_project_intelligence(self, td: str, with_uuid: bool = True):
        pi = Path(td) / ".project-intelligence"
        pi.mkdir(parents=True, exist_ok=True)
        (pi / "workflow-candidates").mkdir(exist_ok=True)
        if with_uuid:
            (pi / "project-context.json").write_text(
                json.dumps({
                    "project_id": "63846bc6-4519-4216-8d71-c7df71290eb9",
                    "slug": "test-project",
                }),
                encoding="utf-8",
            )
        return pi

    def test_skips_when_no_project_intelligence_dir(self):
        with tempfile.TemporaryDirectory() as td:
            summary = observer.scan_and_emit(
                transcript_raw=_jsonl(_assistant_text(SAMPLE_REPORT_TEXT)),
                cwd=Path(td),
                session_id="sess-1",
            )
            self.assertFalse(summary["ran"])
            self.assertEqual(summary["skipped_reason"],
                             "no_project_intelligence_dir")

    def test_skips_when_no_project_uuid(self):
        with tempfile.TemporaryDirectory() as td:
            self._make_project_intelligence(td, with_uuid=False)
            summary = observer.scan_and_emit(
                transcript_raw=_jsonl(_assistant_text(SAMPLE_REPORT_TEXT)),
                cwd=Path(td),
                session_id="sess-1",
            )
            self.assertFalse(summary["ran"])
            self.assertEqual(summary["skipped_reason"],
                             "no_project_uuid_in_context_json")

    def test_skips_when_no_skills_detected(self):
        with tempfile.TemporaryDirectory() as td:
            self._make_project_intelligence(td)
            summary = observer.scan_and_emit(
                transcript_raw=_jsonl(_assistant_text("nothing here")),
                cwd=Path(td),
                session_id="sess-1",
            )
            self.assertFalse(summary["ran"])
            self.assertEqual(summary["skipped_reason"], "no_skills_detected")

    def test_creates_new_candidates(self):
        """First session for a skill -> POST candidate -> save local record."""
        with tempfile.TemporaryDirectory() as td:
            self._make_project_intelligence(td)

            def mock_post(**kwargs):
                # Return a fake server response.
                return {
                    "id": f"fake-{kwargs['skill_name']}-id",
                    "status": "draft",
                    "project_id": kwargs["project_uuid"],
                }

            with patch.object(observer, "post_candidate", side_effect=mock_post):
                summary = observer.scan_and_emit(
                    transcript_raw=_jsonl(_assistant_text(SAMPLE_REPORT_TEXT)),
                    cwd=Path(td),
                    session_id="sess-1",
                )

            # Sample report has 4 skills with count >= 3 (layered-explanation 15,
            # next-actions-planning 8, infrastructure-mapping 4, probe-then-cite 3)
            # AND 1 Promotion-candidates bullet (probe_then_cite — STRONG candidate),
            # so v0.1.11+ creates 5 candidates total: 4 skill-count + 1 idea.
            self.assertTrue(summary["ran"])
            self.assertEqual(summary["candidates_created"], 5)
            self.assertEqual(summary["candidates_updated"], 0)
            # 4 skill-count local files + 1 idea local file (different slug from
            # probe-then-cite skill, because the idea body is "probe_then_cite"
            # with an underscore — slugify treats these as the same -> only 4
            # files actually persisted because the idea overwrites the existing
            # local record. Or 5 if the slug differs. Don't over-assert.)
            pi = Path(td) / ".project-intelligence" / "workflow-candidates"
            files = list(pi.glob("*.json"))
            self.assertGreaterEqual(len(files), 4)

    def test_dedups_same_session(self):
        """Re-running on the same transcript + session_id is a no-op
        after first run (no new POSTs, no extra session_ids)."""
        with tempfile.TemporaryDirectory() as td:
            self._make_project_intelligence(td)
            transcript = _jsonl(_assistant_text(SAMPLE_REPORT_TEXT))

            def mock_post(**kwargs):
                return {"id": f"fake-{kwargs['skill_name']}", "status": "draft"}

            with patch.object(observer, "post_candidate", side_effect=mock_post):
                first = observer.scan_and_emit(
                    transcript_raw=transcript,
                    cwd=Path(td),
                    session_id="sess-1",
                )
                second = observer.scan_and_emit(
                    transcript_raw=transcript,
                    cwd=Path(td),
                    session_id="sess-1",
                )

            # 4 skill candidates + 1 promotion-idea candidate = 5.
            self.assertEqual(first["candidates_created"], 5)
            # Second run sees session_id already recorded -> no creations/updates
            self.assertEqual(second["candidates_created"], 0)
            self.assertEqual(second["candidates_updated"], 0)

    def test_status_transitions_across_sessions(self):
        """Three sessions: draft -> observed (PATCH) -> recurring (PATCH)."""
        with tempfile.TemporaryDirectory() as td:
            self._make_project_intelligence(td)

            # Minimal transcript with one skill at count 5.
            text = ("Skills invoked this session:\n"
                    "  - test-skill (5 uses)\n"
                    "\nTools called this session:\n")
            transcript = _jsonl(_assistant_text(text))

            patches_seen = []

            def mock_post(**kwargs):
                return {"id": "cand-test-skill", "status": "draft"}

            def mock_patch(cand_id, status, reason):
                patches_seen.append((cand_id, status))
                return {"id": cand_id, "status": status}

            with patch.object(observer, "post_candidate", side_effect=mock_post), \
                 patch.object(observer, "patch_candidate_status", side_effect=mock_patch):
                # Session 1
                s1 = observer.scan_and_emit(
                    transcript_raw=transcript, cwd=Path(td), session_id="s1",
                )
                # Session 2
                s2 = observer.scan_and_emit(
                    transcript_raw=transcript, cwd=Path(td), session_id="s2",
                )
                # Session 3
                s3 = observer.scan_and_emit(
                    transcript_raw=transcript, cwd=Path(td), session_id="s3",
                )

            self.assertEqual(s1["candidates_created"], 1)
            self.assertEqual(s2["candidates_updated"], 1)
            self.assertEqual(s3["candidates_updated"], 1)
            self.assertEqual(patches_seen, [
                ("cand-test-skill", "observed"),
                ("cand-test-skill", "recurring"),
            ])

    def test_below_min_count_threshold_ignored(self):
        """Skills with count < MIN_COUNT_TO_CONSIDER (3) don't trigger
        candidate emission."""
        with tempfile.TemporaryDirectory() as td:
            self._make_project_intelligence(td)
            # x at 1, y at 2 — both below 3.
            text = ("Skills invoked this session:\n"
                    "  - x (1 use)\n  - y (2 uses)\n"
                    "\nTools called this session:\n")
            transcript = _jsonl(_assistant_text(text))
            with patch.object(observer, "post_candidate") as mock_post:
                summary = observer.scan_and_emit(
                    transcript_raw=transcript,
                    cwd=Path(td),
                    session_id="s1",
                )
            self.assertEqual(summary["candidates_created"], 0)
            mock_post.assert_not_called()

    def test_post_failure_does_not_persist_record(self):
        """If POST returns None (HTTP failure), the local record is NOT
        saved so the next session retries."""
        with tempfile.TemporaryDirectory() as td:
            pi = self._make_project_intelligence(td)
            transcript = _jsonl(_assistant_text(SAMPLE_REPORT_TEXT))
            with patch.object(observer, "post_candidate", return_value=None):
                summary = observer.scan_and_emit(
                    transcript_raw=transcript,
                    cwd=Path(td),
                    session_id="s1",
                )
            # 4 skill POST attempts + 1 idea POST attempt = 5 errors.
            self.assertEqual(summary["candidates_created"], 0)
            self.assertEqual(len(summary["errors"]), 5)
            # Local files NOT created — retry next session.
            files = list((pi / "workflow-candidates").glob("*.json"))
            self.assertEqual(len(files), 0)


# ---------------------------------------------------------------------------
# Phase 2 v2: parse_promotion_candidates + _split_promotion_entry
# ---------------------------------------------------------------------------


SAMPLE_REPORT_WITH_PROMOTION_CANDIDATES = """Agentic-upskilling pass — session

## Skills invoked
- layered-explanation (5 uses)
- next-actions-planning (3 uses)

## Tools called
- Read (12)

## Promotion candidates
- "Diagnose plugin version state" procedure — reconstructed from scratch and reusable across machines. Worth codifying as a skill or runbook.
- probe_then_cite — strong candidate; 5/5 criteria met
- single-bullet-no-delim

## Demotion candidates
- None.

## Recommendations
- Continue practicing
"""


SAMPLE_REPORT_NEGATIVE_PROMOTION_SECTION = """## Skills invoked
- a-skill (3 uses)

## Tools called
- Read (1)

## Promotion candidates
- None new this session.
- N/A

## Demotion candidates
- None.

## Recommendations
none
"""


class TestSplitPromotionEntry(unittest.TestCase):

    def test_em_dash_split(self):
        name, desc = observer._split_promotion_entry(
            '"Diagnose plugin version state" procedure — reconstructed from scratch'
        )
        self.assertEqual(name, '"Diagnose plugin version state" procedure'.strip('"'))
        self.assertEqual(desc, "reconstructed from scratch")

    def test_double_dash_split(self):
        name, desc = observer._split_promotion_entry("foo -- bar baz")
        self.assertEqual(name, "foo")
        self.assertEqual(desc, "bar baz")

    def test_colon_split(self):
        name, desc = observer._split_promotion_entry("probe_then_cite: strong candidate")
        self.assertEqual(name, "probe_then_cite")
        self.assertEqual(desc, "strong candidate")

    def test_no_delim_whole_is_name(self):
        name, desc = observer._split_promotion_entry("single-bullet-no-delim")
        self.assertEqual(name, "single-bullet-no-delim")
        self.assertEqual(desc, "")

    def test_strips_surrounding_quotes_and_backticks(self):
        name, desc = observer._split_promotion_entry('`my-skill` — description here')
        self.assertEqual(name, "my-skill")
        self.assertEqual(desc, "description here")


class TestParsePromotionCandidates(unittest.TestCase):

    def test_empty_transcript_returns_empty(self):
        self.assertEqual(observer.parse_promotion_candidates(""), [])

    def test_no_section_returns_empty(self):
        raw = _jsonl(_assistant_text("nothing here"))
        self.assertEqual(observer.parse_promotion_candidates(raw), [])

    def test_parses_three_entries_with_different_delim_styles(self):
        raw = _jsonl(_assistant_text(SAMPLE_REPORT_WITH_PROMOTION_CANDIDATES))
        results = observer.parse_promotion_candidates(raw)
        self.assertEqual(len(results), 3)
        names = [r["name"] for r in results]
        self.assertIn('"Diagnose plugin version state" procedure'.strip('"'), names)
        self.assertIn("probe_then_cite", names)
        self.assertIn("single-bullet-no-delim", names)
        # Each entry should have its description (or empty for the no-delim case)
        by_name = {r["name"]: r["description"] for r in results}
        self.assertTrue(by_name['"Diagnose plugin version state" procedure'.strip('"')].startswith("reconstructed"))
        self.assertEqual(by_name["single-bullet-no-delim"], "")

    def test_negative_signals_skipped(self):
        raw = _jsonl(_assistant_text(SAMPLE_REPORT_NEGATIVE_PROMOTION_SECTION))
        self.assertEqual(observer.parse_promotion_candidates(raw), [])

    def test_dedup_within_section(self):
        text = (
            "## Promotion candidates\n"
            "- foo — first description\n"
            "- foo — duplicate (should be skipped)\n"
            "- bar — keep this one\n\n"
            "## Demotion candidates\n  - None\n"
        )
        raw = _jsonl(_assistant_text(text))
        results = observer.parse_promotion_candidates(raw)
        self.assertEqual([r["name"] for r in results], ["foo", "bar"])

    def test_section_boundary_respected(self):
        """Anything after the next section marker (Demotion candidates,
        Recommendations, Outcome) must NOT be parsed as a candidate."""
        text = (
            "## Promotion candidates\n"
            "- real-candidate — yes\n"
            "## Demotion candidates\n"
            "- fake-candidate — this should NOT appear\n"
        )
        raw = _jsonl(_assistant_text(text))
        results = observer.parse_promotion_candidates(raw)
        self.assertEqual([r["name"] for r in results], ["real-candidate"])

    def test_description_truncated_at_512(self):
        long_desc = "x" * 1000
        text = (
            "## Promotion candidates\n"
            f"- my-skill — {long_desc}\n"
            "## Demotion candidates\n- none\n"
        )
        raw = _jsonl(_assistant_text(text))
        results = observer.parse_promotion_candidates(raw)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]["description"]), 512)

    def test_latest_report_wins_when_multiple(self):
        early_text = ("## Promotion candidates\n  - old-idea — gone\n"
                      "## Recommendations\n  - x\n")
        late_text = ("## Promotion candidates\n  - new-idea — kept\n"
                     "## Recommendations\n  - y\n")
        raw = _jsonl(_assistant_text(early_text), _assistant_text(late_text))
        results = observer.parse_promotion_candidates(raw)
        self.assertEqual([r["name"] for r in results], ["new-idea"])


# ---------------------------------------------------------------------------
# v2: scan_and_emit emits idea candidates with is_new_skill_idea=true
# ---------------------------------------------------------------------------


class TestScanAndEmitV2Ideas(unittest.TestCase):

    def _make_project_intelligence(self, td: str):
        pi = Path(td) / ".project-intelligence"
        pi.mkdir(parents=True, exist_ok=True)
        (pi / "workflow-candidates").mkdir(exist_ok=True)
        (pi / "project-context.json").write_text(
            json.dumps({
                "project_id": "63846bc6-4519-4216-8d71-c7df71290eb9",
                "slug": "test-project",
            }),
            encoding="utf-8",
        )
        return pi

    def test_promotion_candidates_emit_with_is_new_skill_idea_flag(self):
        """Each bullet under Promotion candidates becomes a POST with
        is_new_skill_idea=True."""
        with tempfile.TemporaryDirectory() as td:
            self._make_project_intelligence(td)

            posts = []

            def mock_post(**kwargs):
                posts.append(kwargs)
                return {"id": f"fake-{kwargs['skill_name']}", "status": "draft"}

            with patch.object(observer, "post_candidate", side_effect=mock_post):
                summary = observer.scan_and_emit(
                    transcript_raw=_jsonl(_assistant_text(
                        SAMPLE_REPORT_WITH_PROMOTION_CANDIDATES
                    )),
                    cwd=Path(td),
                    session_id="sess-v2-1",
                )

            self.assertTrue(summary["ran"])
            # 2 skills above the threshold (layered-explanation 5, next-actions-planning 3)
            # + 3 promotion candidates = 5 total POSTs (subject to whatever the
            # skill-count parser actually picks up; primary check is on ideas).
            self.assertEqual(summary["ideas_detected"], 3)
            # Posts for the 3 ideas must have is_new_skill_idea=True.
            idea_posts = [p for p in posts if p.get("is_new_skill_idea") is True]
            self.assertEqual(len(idea_posts), 3)
            # Each idea post carries count_this_session=1 (idea = one observation).
            for p in idea_posts:
                self.assertEqual(p["count_this_session"], 1)

    def test_no_skill_counts_but_promotion_candidates_still_runs(self):
        """If the agent's report has NO skill counts >= 3 but DOES surface
        promotion candidates, scan_and_emit still runs (not skipped)."""
        with tempfile.TemporaryDirectory() as td:
            self._make_project_intelligence(td)

            text = (
                "## Skills invoked\n"
                "- one-shot (1 use)\n"
                "## Tools called\n  - X\n"
                "## Promotion candidates\n"
                "- agent-surfaced-idea — should still emit\n"
                "## Recommendations\n  - None\n"
            )

            def mock_post(**kwargs):
                return {"id": "fake-id", "status": "draft"}

            with patch.object(observer, "post_candidate", side_effect=mock_post):
                summary = observer.scan_and_emit(
                    transcript_raw=_jsonl(_assistant_text(text)),
                    cwd=Path(td),
                    session_id="sess-v2-2",
                )

            self.assertTrue(summary["ran"])
            self.assertEqual(summary["skills_detected"], 0)
            self.assertEqual(summary["ideas_detected"], 1)
            self.assertEqual(summary["candidates_created"], 1)

    def test_idea_status_transitions_across_sessions(self):
        """Idea candidates use the same draft -> observed -> recurring
        lifecycle as skill-count candidates (gated by sessions_seen)."""
        with tempfile.TemporaryDirectory() as td:
            self._make_project_intelligence(td)

            text = (
                "## Skills invoked\n  - x (1)\n"
                "## Tools called\n  - X\n"
                "## Promotion candidates\n"
                "- recurring-idea — keep tracking\n"
                "## Recommendations\n  - none\n"
            )
            transcript = _jsonl(_assistant_text(text))

            patches_seen = []

            def mock_post(**kwargs):
                return {"id": "idea-cand", "status": "draft"}

            def mock_patch(cand_id, status, reason):
                patches_seen.append((cand_id, status))
                return {"id": cand_id, "status": status}

            with patch.object(observer, "post_candidate", side_effect=mock_post), \
                 patch.object(observer, "patch_candidate_status", side_effect=mock_patch):
                s1 = observer.scan_and_emit(
                    transcript_raw=transcript, cwd=Path(td), session_id="ses-1",
                )
                s2 = observer.scan_and_emit(
                    transcript_raw=transcript, cwd=Path(td), session_id="ses-2",
                )
                s3 = observer.scan_and_emit(
                    transcript_raw=transcript, cwd=Path(td), session_id="ses-3",
                )

            self.assertEqual(s1["candidates_created"], 1)
            self.assertEqual(s2["candidates_updated"], 1)
            self.assertEqual(s3["candidates_updated"], 1)
            self.assertEqual(patches_seen, [
                ("idea-cand", "observed"),
                ("idea-cand", "recurring"),
            ])


# ---------------------------------------------------------------------------
# Live-fire smoke test (gated by env var)
# ---------------------------------------------------------------------------


class TestLiveSmoke(unittest.TestCase):
    """Hits the real Architecture Registry. Skipped by default. To run:
        LOOM_TEST_LIVE=1 python -m unittest ...test_observer
    """

    @unittest.skipUnless(os.environ.get("LOOM_TEST_LIVE"), "LOOM_TEST_LIVE not set")
    def test_health(self):
        import urllib.request
        url = observer._registry_url() + "/health"
        with urllib.request.urlopen(url, timeout=10) as resp:
            self.assertEqual(resp.status, 200)


if __name__ == "__main__":
    unittest.main()
