"""Unit tests for the pure signal classifiers (services/project-observatory/
signals.py, Phase 1 task 3).

These exercise the PURE compute_* functions with hand-built aggregate dicts —
no DB, no clock. They assert each classifier fires and suppresses at its
boundaries:

  - hot_path : the HOT_MIN_INVOCATIONS floor and the within-project
               HOT_TOP_PERCENTILE cut, plus per-project grouping.
  - orphaned : known-but-0 (read_api-agreeing) vs never-seen (excluded) vs
               went-quiet/decayed.
  - degrading: the error-rate and latency triggers, the error floor, and the
               DEGRADE_MIN_SAMPLE noise floor.

The data-access layer (load_aggregates + the SQL) is NOT tested here — it needs
a Postgres; task 4's materialization tests cover it. The point of the pure/
data split is exactly that these run with zero infrastructure.
"""
from __future__ import annotations

from typing import Any

import config
import signals


# ---------------------------------------------------------------------------
# aggregate-dict builder
# ---------------------------------------------------------------------------


def agg(
    artifact_ref: str,
    project_slug: str = "proj",
    *,
    known: bool = True,
    windowed_invocations: int = 0,
    windowed_errors: int = 0,
    windowed_elapsed: int = 0,
    recent_invocations: int = 0,
    recent_errors: int = 0,
    recent_elapsed: int = 0,
    earlier_invocations: int = 0,
    earlier_errors: int = 0,
    earlier_elapsed: int = 0,
) -> dict[str, Any]:
    """Build one per-artifact aggregate dict in the shape load_aggregates
    returns. Every count defaults to 0 so a test sets only what it exercises."""
    return {
        "artifact_ref": artifact_ref,
        "project_slug": project_slug,
        "known": known,
        "windowed_invocations": windowed_invocations,
        "windowed_errors": windowed_errors,
        "windowed_elapsed": windowed_elapsed,
        "recent_invocations": recent_invocations,
        "recent_errors": recent_errors,
        "recent_elapsed": recent_elapsed,
        "earlier_invocations": earlier_invocations,
        "earlier_errors": earlier_errors,
        "earlier_elapsed": earlier_elapsed,
    }


def _kinds(records: list[dict[str, Any]]) -> set[str]:
    return {r["signal_kind"] for r in records}


def _by_ref(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["artifact_ref"]: r for r in records}


# ===========================================================================
# hot_path
# ===========================================================================


def test_hot_path_top_of_ten_fires_second_does_not():
    """In a project of 10 distinct-count artifacts (all above the min floor),
    the single top artifact is the top 10% (percentile 90) → hot; the runner-up
    (percentile 80) is not, with the default HOT_TOP_PERCENTILE=90."""
    # invocations 50..59, all >= HOT_MIN_INVOCATIONS (50).
    aggs = [
        agg(f"a{i}", windowed_invocations=50 + i)
        for i in range(10)
    ]
    out = signals.compute_hot_path(aggs)

    refs = _by_ref(out)
    assert set(refs) == {"a9"}, "only the strict top artifact is hot"
    hot = refs["a9"]
    assert hot["signal_kind"] == "hot_path"
    assert hot["score"] == 0.9  # percentile 90 normalized
    assert hot["evidence"]["windowed_invocations"] == 59
    assert hot["evidence"]["percentile"] == 90.0


def test_hot_path_min_invocations_floor_blocks_top_percentile():
    """An artifact can be the top of its project by rank yet still be excluded
    when it is below HOT_MIN_INVOCATIONS — the absolute floor gates first."""
    # nine tiny + one at 49 (< min 50). The 49 is rank-top (percentile 90) but
    # below the invocation floor → no hot_path.
    aggs = [agg(f"lo{i}", windowed_invocations=1) for i in range(9)]
    aggs.append(agg("peak", windowed_invocations=49))
    out = signals.compute_hot_path(aggs)
    assert out == [], "below HOT_MIN_INVOCATIONS is never hot, even at rank-top"


def test_hot_path_percentile_is_within_project():
    """Percentile is computed within each project_slug independently. A project
    of all-equal counts yields no standout (rank_below 0 → percentile 0)."""
    proj_a = [agg(f"a{i}", project_slug="A", windowed_invocations=50 + i) for i in range(10)]
    proj_b = [agg(f"b{i}", project_slug="B", windowed_invocations=100) for i in range(10)]
    out = signals.compute_hot_path(proj_a + proj_b)

    refs = _by_ref(out)
    # Only project A's top fires; project B is a flat tie (no top 10%).
    assert set(refs) == {"a9"}
    assert refs["a9"]["project_slug"] == "A"


def test_hot_path_at_exact_min_invocations_fires():
    """Boundary: an artifact at EXACTLY HOT_MIN_INVOCATIONS that is also rank-top
    fires — the floor is `>=`, not `>`. A regression to `>` would drop it."""
    aggs = [agg(f"lo{i}", windowed_invocations=1) for i in range(9)]
    aggs.append(agg("peak", windowed_invocations=config.HOT_MIN_INVOCATIONS))
    out = signals.compute_hot_path(aggs)
    refs = _by_ref(out)
    assert set(refs) == {"peak"}, "exactly at HOT_MIN_INVOCATIONS still counts (>=)"
    assert refs["peak"]["evidence"]["windowed_invocations"] == config.HOT_MIN_INVOCATIONS


# ===========================================================================
# orphaned
# ===========================================================================


def test_orphaned_known_but_zero_windowed_is_emitted_not_decayed():
    """known AND windowed_invocations == 0 (nothing anywhere in the window) →
    orphaned with decayed False. This is the byte-for-byte read_api agreement:
    read_api reports {invocations: 0, known: true} → orphan."""
    out = signals.compute_orphaned([agg("cold", known=True)])
    assert len(out) == 1
    rec = out[0]
    assert rec["signal_kind"] == "orphaned"
    assert rec["score"] == 1.0
    assert rec["window_days"] == config.WINDOW_DAYS
    assert rec["evidence"]["decayed"] is False
    assert rec["evidence"]["windowed_invocations"] == 0
    assert rec["evidence"]["known"] is True


def test_orphaned_never_seen_is_suppressed():
    """A never-seen artifact (known False) is SUPPRESSED — the read_api
    `invocations is None` contract. (In production such an artifact never even
    reaches the classifier; the flag is asserted here for contract safety.)"""
    out = signals.compute_orphaned([agg("ghost", known=False)])
    assert out == []


def test_orphaned_went_quiet_is_decayed():
    """Active in the earlier half, silent in the recent half (earlier > 0,
    recent == 0) → orphaned with decayed True. windowed == earlier here, so this
    is the additive enrichment beyond read_api's windowed-sum orphan."""
    out = signals.compute_orphaned([
        agg("quiet", earlier_invocations=40, recent_invocations=0, windowed_invocations=40),
    ])
    assert len(out) == 1
    rec = out[0]
    assert rec["signal_kind"] == "orphaned"
    assert rec["evidence"]["decayed"] is True
    assert rec["evidence"]["earlier_invocations"] == 40
    assert rec["evidence"]["recent_invocations"] == 0


def test_orphaned_recently_active_is_not_emitted():
    """Any recent activity (recent_invocations > 0) → not orphaned."""
    out = signals.compute_orphaned([
        agg("live", earlier_invocations=10, recent_invocations=5, windowed_invocations=15),
    ])
    assert out == []


# ===========================================================================
# degrading
# ===========================================================================


def test_degrading_error_rate_trigger():
    """Both halves above the sample floor; error-rate rises 0.02 -> 0.08
    (delta 0.06 >= DEGRADE_ERR_DELTA 0.05) and recent 0.08 >= DEGRADE_ERR_FLOOR
    0.02 → degrading via the error trigger."""
    out = signals.compute_degrading([
        agg(
            "err",
            earlier_invocations=100, earlier_errors=2,
            recent_invocations=100, recent_errors=8,
        ),
    ])
    assert len(out) == 1
    rec = out[0]
    assert rec["signal_kind"] == "degrading"
    assert "error_rate" in rec["evidence"]["triggers"]
    assert "latency" not in rec["evidence"]["triggers"]
    assert rec["evidence"]["error_rate_delta"] == 0.06
    # score = delta / (2*DEGRADE_ERR_DELTA) = 0.06 / 0.10 = 0.6
    assert abs(rec["score"] - 0.6) < 1e-9


def test_degrading_latency_trigger():
    """Mean latency 1000ms -> 1600ms (ratio 1.6 >= DEGRADE_LATENCY_RATIO 1.5),
    zero errors → degrading via the latency trigger only."""
    out = signals.compute_degrading([
        agg(
            "slow",
            earlier_invocations=100, earlier_elapsed=100_000,
            recent_invocations=100, recent_elapsed=160_000,
        ),
    ])
    assert len(out) == 1
    rec = out[0]
    assert rec["evidence"]["triggers"] == ["latency"]
    assert rec["evidence"]["latency_ratio"] == 1.6
    assert rec["evidence"]["earlier_mean_latency_ms"] == 1000.0
    assert rec["evidence"]["recent_mean_latency_ms"] == 1600.0
    # score = (ratio-1) / (2*(RATIO-1)) = 0.6 / 1.0 = 0.6
    assert abs(rec["score"] - 0.6) < 1e-9


def test_degrading_both_triggers():
    """Error-rate AND latency both regress → both triggers recorded."""
    out = signals.compute_degrading([
        agg(
            "both",
            earlier_invocations=100, earlier_errors=1, earlier_elapsed=100_000,
            recent_invocations=100, recent_errors=10, recent_elapsed=200_000,
        ),
    ])
    assert len(out) == 1
    assert set(out[0]["evidence"]["triggers"]) == {"error_rate", "latency"}


def test_degrading_below_min_sample_is_suppressed():
    """Earlier half below DEGRADE_MIN_SAMPLE (20) → the trend is noise, suppress
    even a large error jump."""
    out = signals.compute_degrading([
        agg(
            "tiny",
            earlier_invocations=10, earlier_errors=0,   # below the floor
            recent_invocations=100, recent_errors=50,
        ),
    ])
    assert out == [], "below DEGRADE_MIN_SAMPLE emits nothing"


def test_degrading_error_floor_suppresses_low_absolute_rate():
    """With err_delta lowered below the floor, a rise that clears the delta but
    whose recent rate is under DEGRADE_ERR_FLOOR is suppressed — the floor gate
    stops noisy small absolute rates. (Exercises the floor branch explicitly;
    the default err_delta > err_floor masks it.)"""
    out = signals.compute_degrading(
        [agg("lowrate", earlier_invocations=1000, earlier_errors=5,   # 0.005
             recent_invocations=1000, recent_errors=15)],             # 0.015 < 0.02 floor
        err_delta=0.005,   # delta 0.010 >= 0.005, so only the floor can block
    )
    assert out == [], "recent error rate below DEGRADE_ERR_FLOOR suppresses"


def test_degrading_zero_earlier_latency_no_divide_by_zero():
    """earlier mean latency == 0 (no baseline) → latency trigger suppressed, no
    divide-by-zero / trivial infinite ratio. With no error jump, nothing fires."""
    out = signals.compute_degrading([
        agg(
            "nobaseline",
            earlier_invocations=100, earlier_elapsed=0,
            recent_invocations=100, recent_elapsed=500_000,
        ),
    ])
    assert out == []


def test_degrading_at_exact_min_sample_fires():
    """Boundary: both sub-windows at EXACTLY DEGRADE_MIN_SAMPLE still compute —
    the sample floor is `>=`, not `>`. A latency regression then fires."""
    n = config.DEGRADE_MIN_SAMPLE
    out = signals.compute_degrading([
        agg(
            "atfloor",
            earlier_invocations=n, earlier_elapsed=n * 1000,   # 1000ms mean
            recent_invocations=n, recent_elapsed=n * 1600,     # 1600ms mean -> 1.6x
        ),
    ])
    assert len(out) == 1, "exactly at DEGRADE_MIN_SAMPLE is enough (>=)"
    assert out[0]["signal_kind"] == "degrading"
    assert out[0]["evidence"]["triggers"] == ["latency"]


def test_degrading_at_exact_latency_ratio_fires():
    """Boundary: mean-latency ratio EXACTLY DEGRADE_LATENCY_RATIO (1.5) fires —
    the trigger is `>=`, not `>`. 1.5 is exactly representable, so no float slop."""
    out = signals.compute_degrading([
        agg(
            "exactratio",
            earlier_invocations=100, earlier_elapsed=100_000,   # 1000ms
            recent_invocations=100, recent_elapsed=150_000,     # 1500ms -> ratio 1.5
        ),
    ])
    assert len(out) == 1, "ratio exactly at DEGRADE_LATENCY_RATIO fires (>=)"
    rec = out[0]
    assert rec["evidence"]["latency_ratio"] == config.DEGRADE_LATENCY_RATIO
    assert rec["evidence"]["triggers"] == ["latency"]


# ===========================================================================
# compute_signals — the combined pass
# ===========================================================================


def test_compute_signals_combines_all_three_kinds():
    """One aggregate set that should yield each kind exactly once; blind is
    never emitted in Phase 1."""
    aggs = [
        # hot_path: top of a 10-artifact project. Activity sits in the recent
        # half (windowed == recent) so these are NOT also orphaned, and
        # earlier == 0 keeps them below the degrading sample floor.
        *[
            agg(f"h{i}", project_slug="P", windowed_invocations=50 + i,
                recent_invocations=50 + i)
            for i in range(10)
        ],
        # orphaned: known, cold across the window — isolated in its own project
        # so it does not perturb P's percentile ranking.
        agg("orphan", project_slug="Q", known=True),
        # degrading: latency regression, both halves sampled — own project so
        # its 200 invocations do not outrank P's hot artifact.
        agg(
            "deg", project_slug="R",
            earlier_invocations=100, earlier_elapsed=100_000,
            recent_invocations=100, recent_elapsed=160_000,
            windowed_invocations=200,
        ),
    ]
    out = signals.compute_signals(aggs)
    kinds = _kinds(out)
    assert kinds == {"hot_path", "orphaned", "degrading"}
    assert "blind" not in kinds
    # exactly one of each expected artifact
    refs = {(r["signal_kind"], r["artifact_ref"]) for r in out}
    assert ("hot_path", "h9") in refs
    assert ("orphaned", "orphan") in refs
    assert ("degrading", "deg") in refs


def test_signal_records_have_the_006_shape():
    """Every record carries exactly the non-machine-stamped observation_signals
    columns task 4 will INSERT, and signal_kind is CHECK-constraint-valid."""
    aggs = [agg("cold", known=True)]
    for rec in signals.compute_signals(aggs):
        assert set(rec) == {
            "project_slug", "artifact_ref", "signal_kind",
            "score", "window_days", "evidence",
        }
        assert rec["signal_kind"] in config.SIGNAL_KINDS
        assert 0.0 <= rec["score"] <= 1.0
        assert isinstance(rec["evidence"], dict)
