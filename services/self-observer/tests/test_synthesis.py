"""Tests for synthesis.py — the §3.3 counters + health rules + memo body
that the self-observer cron writes after each scan.

Mostly pure-function tests; the orchestrator (build_and_write_synthesis)
gets one integration-shaped test with mocked I/O.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_SVC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC))

import synthesis  # noqa: E402
from config import AuthConfig, Endpoints  # noqa: E402


_NOW = 1_780_000_000.0  # frozen "now" for deterministic age math
_HOUR = 3600.0
_DAY = 24 * _HOUR


def _cand(status: str, kind: str, age_seconds: float = 0.0) -> dict:
    return {
        "status": status,
        "candidate_type": kind,
        "updated_at": _NOW - age_seconds,
    }


# ---------------------------------------------------------------------------
# compute_counters
# ---------------------------------------------------------------------------


def test_counters_empty_set_returns_zeros():
    c = synthesis.compute_counters([], now=_NOW)
    assert c.actionable_backlog_count == 0
    assert c.stuck_promotion_requested_count == 0
    assert c.oldest_stuck_candidate_age == 0.0
    assert c.unsupported_candidate_count_by_kind == {}


def test_counters_actionable_requires_skill_kind_and_actionable_status():
    candidates = [
        _cand("stable", "skill"),                # counted
        _cand("promotion_requested", "skill"),   # counted
        _cand("recurring", "skill"),             # NOT counted (status not actionable)
        _cand("stable", "agent"),                # NOT counted (kind not supported)
        _cand("promoted", "skill"),              # NOT counted (already promoted)
    ]
    c = synthesis.compute_counters(candidates, now=_NOW)
    assert c.actionable_backlog_count == 2


def test_counters_oldest_stuck_age_picks_max():
    candidates = [
        _cand("promotion_requested", "skill", age_seconds=_HOUR),
        _cand("promotion_requested", "skill", age_seconds=10 * _HOUR),
        _cand("promotion_requested", "agent", age_seconds=5 * _HOUR),
    ]
    c = synthesis.compute_counters(candidates, now=_NOW)
    assert c.stuck_promotion_requested_count == 3
    assert c.oldest_stuck_candidate_age == 10 * _HOUR


def test_counters_unsupported_by_kind_aggregates_correctly():
    candidates = [
        _cand("promotion_requested", "agent"),
        _cand("promotion_requested", "agent"),
        _cand("promotion_requested", "inline_tool"),
        _cand("promotion_requested", "skill"),  # supported — not counted as unsupported
    ]
    c = synthesis.compute_counters(candidates, now=_NOW)
    assert c.unsupported_candidate_count_by_kind == {"agent": 2, "inline_tool": 1}


# ---------------------------------------------------------------------------
# compute_health
# ---------------------------------------------------------------------------


def test_health_green_when_actionable_below_ceiling():
    c = synthesis.Counters(actionable_backlog_count=3)
    h = synthesis.compute_health(c, prior_actionable=None)
    assert h.flag == "GREEN"


def test_health_yellow_when_above_green_ceiling_for_two_scans():
    c = synthesis.Counters(actionable_backlog_count=7)
    h = synthesis.compute_health(c, prior_actionable=6)
    assert h.flag == "YELLOW"
    assert "2 consecutive scans" in h.reason


def test_health_green_when_first_breach_no_prior_yellow():
    """First scan above ceiling but no prior memo — stays GREEN with a note."""
    c = synthesis.Counters(actionable_backlog_count=7)
    h = synthesis.compute_health(c, prior_actionable=None)
    assert h.flag == "GREEN"
    assert "first occurrence" in h.reason


def test_health_red_when_actionable_above_red_floor():
    c = synthesis.Counters(actionable_backlog_count=11)
    h = synthesis.compute_health(c, prior_actionable=None)
    assert h.flag == "RED"


def test_health_red_when_skill_stuck_over_24h():
    c = synthesis.Counters(
        actionable_backlog_count=1,
        oldest_stuck_candidate_age=25 * _HOUR,
    )
    h = synthesis.compute_health(c, prior_actionable=None)
    assert h.flag == "RED"
    assert "24h" in h.reason


def test_health_red_when_non_skill_kind_exceeds_count_and_age_thresholds():
    """Per ms_agent §3 caveat #2: any non-skill kind > 20 stuck > 7 days = RED."""
    c = synthesis.Counters(
        actionable_backlog_count=1,
        unsupported_candidate_count_by_kind={"agent": 21},
        unsupported_oldest_age_by_kind={"agent": 8 * _DAY},
    )
    h = synthesis.compute_health(c, prior_actionable=None)
    assert h.flag == "RED"
    assert "agent" in h.reason


def test_health_green_when_unsupported_kind_under_age_threshold():
    """High count but recent — doesn't trip RED (both thresholds required)."""
    c = synthesis.Counters(
        actionable_backlog_count=1,
        unsupported_candidate_count_by_kind={"agent": 25},
        unsupported_oldest_age_by_kind={"agent": 1 * _DAY},  # < 7d
    )
    h = synthesis.compute_health(c, prior_actionable=None)
    assert h.flag == "GREEN"


# ---------------------------------------------------------------------------
# build_memo
# ---------------------------------------------------------------------------


def test_memo_contains_health_flag_and_reason_at_top():
    c = synthesis.Counters(actionable_backlog_count=3)
    h = synthesis.Health(flag="GREEN", reason="all good")
    body = synthesis.build_memo(c, h, {"scanned": 5, "emitted": 2}, now=_NOW)
    assert "Deferral health: GREEN" in body
    assert "all good" in body
    assert "scanned: 5" in body
    assert "emitted: 2" in body


def test_memo_includes_all_six_counter_labels():
    """§3.3 requires all 6 counters surfaced (2 will be 'awaiting' notes)."""
    c = synthesis.Counters(actionable_backlog_count=0)
    h = synthesis.Health(flag="GREEN", reason="x")
    body = synthesis.build_memo(c, h, {}, now=_NOW)
    for label in (
        "actionable_backlog_count",
        "stuck_promotion_requested_count",
        "oldest_stuck_candidate_age",
        "unsupported_candidate_count_by_kind",
        "dispatch_success_count_since_last_scan",
        "dispatch_failure_count_since_last_scan",
    ):
        assert label in body, f"missing counter label: {label}"


def test_memo_marks_deferred_counters_as_awaiting_telemetry():
    c = synthesis.Counters(actionable_backlog_count=0)
    h = synthesis.Health(flag="GREEN", reason="x")
    body = synthesis.build_memo(c, h, {}, now=_NOW)
    assert "awaiting telemetry rollup" in body


# ---------------------------------------------------------------------------
# _extract_prior_actionable
# ---------------------------------------------------------------------------


def test_extract_prior_actionable_from_well_formed_memo():
    prior = {"content": "junk\n- actionable_backlog_count: 7\nmore junk"}
    assert synthesis._extract_prior_actionable(prior) == 7


def test_extract_prior_actionable_returns_none_when_missing():
    assert synthesis._extract_prior_actionable(None) is None
    assert synthesis._extract_prior_actionable({"content": "no counter here"}) is None


def test_extract_prior_actionable_returns_none_on_unparseable():
    prior = {"content": "- actionable_backlog_count: not-an-int"}
    assert synthesis._extract_prior_actionable(prior) is None


# ---------------------------------------------------------------------------
# build_and_write_synthesis — orchestrator integration
# ---------------------------------------------------------------------------


_ENDPOINTS = Endpoints(
    candidate_registry_url="http://a", telemetry_query_url="http://t", memory_url="http://m"
)
_AUTH = AuthConfig()


@pytest.mark.asyncio
async def test_orchestrator_skips_on_empty_when_nothing_emitted_and_no_candidates():
    memory_client = AsyncMock()
    with patch("synthesis.fetch_open_candidates", new=AsyncMock(return_value=[])):
        ok = await synthesis.build_and_write_synthesis(
            memory_client=memory_client,
            endpoints=_ENDPOINTS,
            auth=_AUTH,
            run_counters={"emitted": 0},
        )
    assert ok is False
    memory_client.write_synthesis.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_writes_when_candidates_present():
    memory_client = AsyncMock()
    memory_client.read_synthesis_latest.return_value = None
    memory_client.write_synthesis.return_value = True
    candidates = [_cand("promotion_requested", "skill", age_seconds=2 * _HOUR)]
    with patch("synthesis.fetch_open_candidates", new=AsyncMock(return_value=candidates)):
        ok = await synthesis.build_and_write_synthesis(
            memory_client=memory_client,
            endpoints=_ENDPOINTS,
            auth=_AUTH,
            run_counters={"emitted": 0, "scanned": 1, "skipped_self": 0, "skipped_dedup": 0},
            now=_NOW,
        )
    assert ok is True
    memory_client.write_synthesis.assert_called_once()
    call_kwargs = memory_client.write_synthesis.call_args.kwargs
    assert call_kwargs["name"] == "self_observer_synthesis_latest"
    assert call_kwargs["actor"] == "self-observer"
    assert call_kwargs["record_type"] == "project"
    assert "Deferral health" in call_kwargs["content"]


@pytest.mark.asyncio
async def test_orchestrator_uses_prior_actionable_in_health_decision():
    """Prior memo says actionable=6, current is 7 → YELLOW (2 consecutive over ceiling)."""
    memory_client = AsyncMock()
    memory_client.read_synthesis_latest.return_value = {
        "content": "- actionable_backlog_count: 6\n",
    }
    memory_client.write_synthesis.return_value = True
    # Build 7 actionable skill candidates
    candidates = [_cand("stable", "skill") for _ in range(7)]
    with patch("synthesis.fetch_open_candidates", new=AsyncMock(return_value=candidates)):
        await synthesis.build_and_write_synthesis(
            memory_client=memory_client,
            endpoints=_ENDPOINTS,
            auth=_AUTH,
            run_counters={"emitted": 0},
            now=_NOW,
        )
    body = memory_client.write_synthesis.call_args.kwargs["content"]
    assert "Deferral health: YELLOW" in body
