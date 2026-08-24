"""Signal-computation core for the runtime-observer.

Phase 1 **task 3** of the observer-capacity build (docs/plans/2026-08-23-
observer-capacity-build-sequence.md). This module reads the Phase-0 telemetry
substrate (infra/migrations/005_init_telemetry.sql — telemetry_rollup_daily,
with telemetry_events as the lifetime existence probe) and produces the
observation signals ADR-0001 names — `hot_path`, `orphaned`, `degrading` — as
plain signal-record dicts. It does NOT write anything: task 4 (materialization)
takes the records this returns and INSERTs them into observation_signals
(infra/migrations/006_init_observation_signals.sql), stamping id / tenant_id /
run_id / computed_at. `blind` is intentionally NOT emitted in Phase 1 (see
compute_orphaned's docstring).

## Two layers, split on purpose

  (a) DATA ACCESS — async psycopg3 reads that run inside the caller's open
      `db.tenant_transaction` connection (RLS-scoped by app.tenant_id). Every
      value is a bind parameter; window boundaries are computed in SQL in UTC,
      byte-for-byte matching services/telemetry-ingestion/read_api.py.
  (b) PURE CLASSIFY — functions that take the per-artifact aggregate dicts +
      config thresholds and return signal records. No DB, no clock, no I/O —
      so they are unit-testable in isolation (tests/test_signals.py).

`load_aggregates()` bridges the two: it runs the SQL and returns the list of
per-artifact aggregate dicts the pure functions consume.

## The 0-vs-None / orphaned agreement with the read API (LOAD-BEARING)

services/telemetry-ingestion/read_api.py:137-216 defines the contract the
self-observer's orphan detection consumes:

  - existence probe (`known`): does this artifact have ANY lifetime row,
    window-agnostic — `EXISTS telemetry_rollup_daily OR EXISTS telemetry_events`
    (read_api.py:137-147). Mirrored here by `_KNOWN_SQL` (rollup UNION events).
  - windowed invocations: `SUM(invocation_count)` over
    `bucket_day >= (now() AT TIME ZONE 'UTC')::date - window_days`
    (read_api.py:153-159). Mirrored here by `_WINDOW_AGG_SQL`'s
    `windowed_invocations`, same UTC boundary expression.
  - orphan verdict: known AND windowed sum == 0 (read_api.py:202-216 →
    self-observer classify: `invocations == 0` → orphan; `None`/never-seen →
    suppress).

`compute_orphaned` emits `orphaned` for exactly `known AND
windowed_invocations == 0`, so this observer and the read API agree
byte-for-byte on that verdict. The `decayed` enrichment is additive (it flags
went-quiet artifacts the read API's single windowed sum cannot yet see — see
compute_orphaned).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

import config

if TYPE_CHECKING:
    # psycopg is only referenced in a type annotation; `from __future__ import
    # annotations` keeps that annotation a string, so the pure-classifier tests
    # import this module with no psycopg installed.
    import psycopg


# ===========================================================================
# (a) DATA ACCESS — SQL that runs inside the caller's tenant_transaction conn
# ===========================================================================
#
# The caller opens the RLS-scoped transaction and passes the connection in:
#
#     async with db.tenant_transaction(tenant_id) as conn:
#         aggregates = await load_aggregates(conn)
#         signals = compute_signals(aggregates)   # pure, no conn
#
# Every value below is a bind parameter (%(name)s); the only non-parameterized
# text is the fixed UTC boundary expression, which is a literal (no user input).

# Per-artifact windowed + sub-window aggregate. Grain: (artifact_ref,
# project_slug), matching telemetry_rollup_daily's grain reduced to the two
# identity columns. The FILTERed sums split the window into the recent half
# (bucket_day >= today - SUBWINDOW_SPLIT) and the earlier half (the rest of the
# window), so degrading/decayed can compare recent vs earlier without a second
# query. Boundaries are computed in SQL in UTC — the SAME expression read_api
# uses (read_api.py:157) — so a rollup row lands in the same window regardless
# of the server's local timezone.
_WINDOW_AGG_SQL = """
SELECT
    artifact_ref,
    project_slug,
    COALESCE(SUM(invocation_count), 0)                                 AS windowed_invocations,
    COALESCE(SUM(error_count), 0)                                      AS windowed_errors,
    COALESCE(SUM(sum_elapsed_ms), 0)                                   AS windowed_elapsed,
    COALESCE(SUM(invocation_count) FILTER (
        WHERE bucket_day >= (now() AT TIME ZONE 'UTC')::date - %(subwindow_split)s::integer
    ), 0)                                                              AS recent_invocations,
    COALESCE(SUM(error_count) FILTER (
        WHERE bucket_day >= (now() AT TIME ZONE 'UTC')::date - %(subwindow_split)s::integer
    ), 0)                                                              AS recent_errors,
    COALESCE(SUM(sum_elapsed_ms) FILTER (
        WHERE bucket_day >= (now() AT TIME ZONE 'UTC')::date - %(subwindow_split)s::integer
    ), 0)                                                              AS recent_elapsed,
    COALESCE(SUM(invocation_count) FILTER (
        WHERE bucket_day < (now() AT TIME ZONE 'UTC')::date - %(subwindow_split)s::integer
    ), 0)                                                              AS earlier_invocations,
    COALESCE(SUM(error_count) FILTER (
        WHERE bucket_day < (now() AT TIME ZONE 'UTC')::date - %(subwindow_split)s::integer
    ), 0)                                                              AS earlier_errors,
    COALESCE(SUM(sum_elapsed_ms) FILTER (
        WHERE bucket_day < (now() AT TIME ZONE 'UTC')::date - %(subwindow_split)s::integer
    ), 0)                                                              AS earlier_elapsed
FROM telemetry_rollup_daily
WHERE bucket_day >= (now() AT TIME ZONE 'UTC')::date - %(window_days)s::integer
  AND artifact_ref <> ''   -- exclude the empty pseudo-artifact (hook/memory/
                           -- snapshot/etc. events roll up under '' per 005's
                           -- NOT NULL DEFAULT ''); same guard as _KNOWN_SQL,
                           -- else '' would emit a false hot_path/degrading.
GROUP BY artifact_ref, project_slug
"""

# Existence probe / "known" universe: DISTINCT (artifact_ref, project_slug)
# that have ANY lifetime row (window-agnostic), from the rollup OR the fact
# table. This is read_api's `_EXISTS_SQL` (rollup OR events, read_api.py:137-
# 147) lifted from a single-ref probe to the whole set, and it also carries
# project_slug so a lifetime-orphan absent from the window (no in-window row,
# so absent from _WINDOW_AGG_SQL) still gets a project_slug + a zero aggregate.
# We OR in telemetry_events (not just the rollup) for the SAME reason read_api
# does: a future rollup-retention trim (005's retention note, 005:59-63) must
# never collapse "seen but old" into "never seen". artifact_ref is nullable on
# telemetry_events and defaults '' on the rollup, so NULL/empty are excluded —
# they are not real artifacts.
_KNOWN_SQL = """
SELECT DISTINCT artifact_ref, project_slug
FROM (
    SELECT artifact_ref, project_slug FROM telemetry_rollup_daily
    UNION
    SELECT artifact_ref, project_slug FROM telemetry_events
) t
WHERE artifact_ref IS NOT NULL AND artifact_ref <> ''
"""

# The aggregate-dict keys the pure classifiers read. Kept as a constant so the
# data-access layer and the tests build the same shape.
_AGG_INT_FIELDS = (
    "windowed_invocations",
    "windowed_errors",
    "windowed_elapsed",
    "recent_invocations",
    "recent_errors",
    "recent_elapsed",
    "earlier_invocations",
    "earlier_errors",
    "earlier_elapsed",
)


def _zero_aggregate(artifact_ref: str, project_slug: str) -> dict[str, Any]:
    """A known-but-no-window-activity aggregate: every count 0, `known` True.

    This is the classic orphan shape — an artifact with a lifetime row but
    nothing inside the observation window (so it is ABSENT from
    _WINDOW_AGG_SQL, which only sees in-window rows). read_api reports exactly
    this as `{invocations: 0, known: true}` → orphan.
    """
    agg: dict[str, Any] = {
        "artifact_ref": artifact_ref,
        "project_slug": project_slug,
        "known": True,
    }
    for f in _AGG_INT_FIELDS:
        agg[f] = 0
    return agg


async def load_aggregates(
    conn: psycopg.AsyncConnection,
    *,
    window_days: int = config.WINDOW_DAYS,
    subwindow_split: int = config.SUBWINDOW_SPLIT,
) -> list[dict[str, Any]]:
    """Read the rollup + existence probe and return per-artifact aggregate dicts.

    Runs INSIDE the caller's open, RLS-scoped `db.tenant_transaction`
    connection — this function never opens its own transaction or resolves a
    tenant; the caller (task 4's materialization pass) does. All reads are
    parameterized; the tenant scope comes from the transaction's app.tenant_id.

    The returned list is the union of:
      - every (artifact_ref, project_slug) with at least one in-window rollup
        row (from _WINDOW_AGG_SQL) — carries real windowed + sub-window counts;
      - every known (artifact_ref, project_slug) with NO in-window row (lifetime
        row only) — added as a `_zero_aggregate` so lifetime-orphans surface.

    Every entry has `known == True` (it is, by construction, in the rollup
    and/or the fact table). The pure classifiers still gate on `known` so the
    contract is explicit and so a synthetic never-seen aggregate (`known:
    False`) can be fed in tests to prove suppression — never-seen artifacts
    have no telemetry anywhere, so they can never appear in this list in
    production, which is exactly why `blind` cannot be emitted from telemetry
    alone (see compute_orphaned).
    """
    params = {"window_days": window_days, "subwindow_split": subwindow_split}

    async with conn.cursor() as cur:
        await cur.execute(_WINDOW_AGG_SQL, params)
        window_rows = await cur.fetchall()

        await cur.execute(_KNOWN_SQL)
        known_rows = await cur.fetchall()

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for r in window_rows:
        key = (r["artifact_ref"], r["project_slug"])
        agg: dict[str, Any] = {
            "artifact_ref": r["artifact_ref"],
            "project_slug": r["project_slug"],
            "known": True,
        }
        for f in _AGG_INT_FIELDS:
            agg[f] = int(r[f] or 0)
        by_key[key] = agg

    # Lifetime-known artifacts with no in-window row → zero aggregates so the
    # classic orphan (known, 0 windowed) is not silently dropped.
    for r in known_rows:
        key = (r["artifact_ref"], r["project_slug"])
        if key not in by_key:
            by_key[key] = _zero_aggregate(r["artifact_ref"], r["project_slug"])

    return list(by_key.values())


# ===========================================================================
# (b) PURE CLASSIFY — aggregates + config in, signal-record dicts out
# ===========================================================================
#
# A signal record is exactly the columns task 4 populates on observation_signals
# that are NOT machine-stamped (006:51-72 stamps id / tenant_id / run_id /
# computed_at itself):
#
#     {project_slug, artifact_ref, signal_kind, score, window_days, evidence}
#
# score is a normalized 0..1 strength for ranking (006:59). evidence is the
# self-explaining JSONB bag (006:62-65) — the measured inputs behind the signal.


def _signal_record(
    *,
    project_slug: str,
    artifact_ref: str,
    signal_kind: str,
    score: float,
    window_days: int,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Build one signal record. `signal_kind` MUST be one of config.SIGNAL_KINDS
    (== observation_signals' CHECK constraint, 006:69-71) or task 4's INSERT
    fails the constraint — assert here so a typo surfaces at compute time."""
    assert signal_kind in config.SIGNAL_KINDS, (
        f"signal_kind {signal_kind!r} not in {config.SIGNAL_KINDS}"
    )
    return {
        "project_slug": project_slug,
        "artifact_ref": artifact_ref,
        "signal_kind": signal_kind,
        "score": float(max(0.0, min(1.0, score))),  # clamp to 006's 0..1 domain
        "window_days": window_days,
        "evidence": evidence,
    }


def compute_hot_path(
    aggregates: Iterable[dict[str, Any]],
    *,
    window_days: int = config.WINDOW_DAYS,
    min_invocations: int = config.HOT_MIN_INVOCATIONS,
    top_percentile: float = config.HOT_TOP_PERCENTILE,
) -> list[dict[str, Any]]:
    """Flag heavily-used, load-bearing artifacts.

    An artifact is `hot_path` when BOTH:
      - windowed_invocations >= HOT_MIN_INVOCATIONS (absolute floor — below this
        the sample is too small to call anything "hot"), AND
      - it sits in the top (100 - HOT_TOP_PERCENTILE)% by windowed_invocations
        WITHIN its own project_slug.

    Percentile rank is computed per project group as
        percentile = 100 * (# artifacts in project with strictly FEWER
                            windowed_invocations) / n
    and the artifact is hot when percentile >= HOT_TOP_PERCENTILE. For a project
    of 10 distinct-count artifacts the single top artifact scores 90 → the
    top 10% with the default HOT_TOP_PERCENTILE=90.

    score = percentile / 100 (the normalized within-project invocation rank).
    evidence carries windowed_invocations and the computed percentile.

    NOTE (flagged): percentile is RELATIVE within a project, so a small project
    can never surface a hot_path — the top of 5 distinct artifacts scores
    100*4/5 = 80 < 90. This is correct "top 10%" semantics but may under-report
    load-bearing paths in small projects; if that matters, add an absolute-rate
    fallback. TUNABLE via HOT_TOP_PERCENTILE / HOT_MIN_INVOCATIONS.
    """
    aggregates = list(aggregates)

    # Group by project so the percentile is within-project.
    by_project: dict[str, list[dict[str, Any]]] = {}
    for a in aggregates:
        by_project.setdefault(a["project_slug"], []).append(a)

    out: list[dict[str, Any]] = []
    for project_slug, group in by_project.items():
        n = len(group)
        counts = [a["windowed_invocations"] for a in group]
        for a in group:
            inv = a["windowed_invocations"]
            if inv < min_invocations:
                continue
            rank_below = sum(1 for c in counts if c < inv)
            percentile = 100.0 * rank_below / n if n else 0.0
            if percentile < top_percentile:
                continue
            out.append(
                _signal_record(
                    project_slug=project_slug,
                    artifact_ref=a["artifact_ref"],
                    signal_kind="hot_path",
                    score=percentile / 100.0,
                    window_days=window_days,
                    evidence={
                        "windowed_invocations": inv,
                        "percentile": round(percentile, 4),
                        "project_artifact_count": n,
                        "min_invocations": min_invocations,
                        "top_percentile": top_percentile,
                    },
                )
            )
    return out


def compute_orphaned(
    aggregates: Iterable[dict[str, Any]],
    *,
    window_days: int = config.WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Flag known-but-quiet artifacts.

    Emit `orphaned` when the artifact is KNOWN (has a lifetime row — the
    existence probe) AND has no RECENT activity (recent_invocations == 0). Two
    flavors, distinguished by evidence.decayed:

      - decayed == False: earlier_invocations == 0 too, so
        windowed_invocations == 0 — nothing anywhere in the window. This is the
        BYTE-FOR-BYTE agreement with read_api: `known AND windowed sum == 0` →
        orphan (read_api.py:202-216; self-observer classify `invocations == 0`).

      - decayed == True: earlier_invocations > 0 but recent_invocations == 0 —
        it was active in the earlier half of the window and went quiet. This is
        an ADDITIVE enrichment: read_api's single windowed sum is > 0 here, so
        the self-observer would NOT yet call it an orphan. The observer surfaces
        the decay earlier. (Flagged in the task summary — if strict parity with
        read_api is wanted, gate emission on windowed_invocations == 0 instead
        of recent_invocations == 0.)

    NOT emitted:
      - never-seen artifacts (`known` False): they have no telemetry anywhere,
        so they never appear in load_aggregates' output at all → correctly
        excluded. This is the read_api `invocations is None` → SUPPRESS case.
      - `blind`: an instrumented location that SHOULD exist but has produced no
        telemetry. Detecting it needs an external should-exist inventory that
        Phase 1 does not have — telemetry alone cannot tell "never emitted"
        from "does not exist". So `blind` is deliberately NOT emitted here
        (config.SIGNAL_KINDS still lists it for task 4 / a later phase).

    score = 1.0 (orphaned is a binary condition — recent activity is zero;
    rank via evidence, e.g. earlier volume, not via score).
    """
    out: list[dict[str, Any]] = []
    for a in aggregates:
        if not a.get("known"):
            continue  # never-seen → suppress (read_api None contract)
        recent = a["recent_invocations"]
        if recent != 0:
            continue  # still active recently → not orphaned
        earlier = a["earlier_invocations"]
        windowed = a["windowed_invocations"]
        decayed = earlier > 0  # active earlier, quiet now (windowed == earlier)
        out.append(
            _signal_record(
                project_slug=a["project_slug"],
                artifact_ref=a["artifact_ref"],
                signal_kind="orphaned",
                score=1.0,
                window_days=window_days,
                evidence={
                    "windowed_invocations": windowed,
                    "earlier_invocations": earlier,
                    "recent_invocations": recent,
                    "known": True,
                    # decayed=True → went quiet (earlier>0, recent==0);
                    # decayed=False → cold across the whole window (windowed==0),
                    # the read_api-agreeing orphan.
                    "decayed": decayed,
                },
            )
        )
    return out


def compute_degrading(
    aggregates: Iterable[dict[str, Any]],
    *,
    window_days: int = config.WINDOW_DAYS,
    min_sample: int = config.DEGRADE_MIN_SAMPLE,
    err_delta: float = config.DEGRADE_ERR_DELTA,
    err_floor: float = config.DEGRADE_ERR_FLOOR,
    latency_ratio: float = config.DEGRADE_LATENCY_RATIO,
) -> list[dict[str, Any]]:
    """Flag artifacts whose health is trending worse across the window.

    Compare the recent sub-window against the earlier sub-window per artifact.
    Emit `degrading` only when BOTH sub-windows carry a trustworthy sample
    (recent_invocations >= DEGRADE_MIN_SAMPLE AND earlier_invocations >=
    DEGRADE_MIN_SAMPLE) — below that floor the trend is noise, so emit nothing.

    With the sample floor met, flag when EITHER trigger fires:
      A) error-rate regression: error_rate rose by >= DEGRADE_ERR_DELTA AND the
         recent error_rate >= DEGRADE_ERR_FLOOR (the floor stops tiny absolute
         rates producing noisy deltas). error_rate = errors / invocations.
      B) latency regression: recent mean latency >= DEGRADE_LATENCY_RATIO *
         earlier mean latency, with earlier mean latency > 0. mean latency =
         elapsed_ms / invocations. (earlier mean latency == 0 → no baseline to
         regress from → trigger B suppressed, avoids a divide-by-zero / trivial
         infinite ratio.)

    All divides are guarded: the sample floor guarantees invocations > 0 for the
    rate/mean denominators; earlier mean latency > 0 is checked for trigger B.

    score = the stronger triggered regression, normalized so that a signal AT
    its trigger threshold scores 0.5 and roughly twice-the-threshold scores 1.0
    (err_delta of 2*DEGRADE_ERR_DELTA → 1.0; latency ratio of
    1 + 2*(DEGRADE_LATENCY_RATIO-1) → 1.0). Heuristic + TUNABLE.
    evidence carries both sub-windows' error-rates + mean latencies, the deltas,
    and which trigger(s) fired.
    """
    out: list[dict[str, Any]] = []
    for a in aggregates:
        recent_inv = a["recent_invocations"]
        earlier_inv = a["earlier_invocations"]
        # Sample floor — both halves must be statistically meaningful.
        if recent_inv < min_sample or earlier_inv < min_sample:
            continue

        recent_err_rate = a["recent_errors"] / recent_inv
        earlier_err_rate = a["earlier_errors"] / earlier_inv
        error_rate_delta = recent_err_rate - earlier_err_rate

        recent_lat = a["recent_elapsed"] / recent_inv
        earlier_lat = a["earlier_elapsed"] / earlier_inv
        lat_ratio = (recent_lat / earlier_lat) if earlier_lat > 0 else None

        triggers: list[str] = []
        err_score = 0.0
        lat_score = 0.0

        # Trigger A — error-rate regression above the floor.
        if error_rate_delta >= err_delta and recent_err_rate >= err_floor:
            triggers.append("error_rate")
            denom = 2.0 * err_delta if err_delta > 0 else 1.0
            err_score = error_rate_delta / denom

        # Trigger B — latency regression against a real earlier baseline.
        if lat_ratio is not None and lat_ratio >= latency_ratio:
            triggers.append("latency")
            denom = 2.0 * (latency_ratio - 1.0) if latency_ratio > 1.0 else 1.0
            lat_score = (lat_ratio - 1.0) / denom

        if not triggers:
            continue

        out.append(
            _signal_record(
                project_slug=a["project_slug"],
                artifact_ref=a["artifact_ref"],
                signal_kind="degrading",
                score=max(err_score, lat_score),  # _signal_record clamps to 0..1
                window_days=window_days,
                evidence={
                    "triggers": triggers,
                    "earlier_error_rate": round(earlier_err_rate, 6),
                    "recent_error_rate": round(recent_err_rate, 6),
                    "error_rate_delta": round(error_rate_delta, 6),
                    "earlier_mean_latency_ms": round(earlier_lat, 4),
                    "recent_mean_latency_ms": round(recent_lat, 4),
                    "latency_ratio": round(lat_ratio, 6) if lat_ratio is not None else None,
                    "earlier_invocations": earlier_inv,
                    "recent_invocations": recent_inv,
                },
            )
        )
    return out


def compute_signals(
    aggregates: Iterable[dict[str, Any]],
    *,
    window_days: int = config.WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Run all three classifiers over one aggregate set and return the combined
    signal-record list. `blind` is not among them (see compute_orphaned).

    Materialization order into observation_signals is task 4's concern; this
    just concatenates hot_path, orphaned, degrading. `aggregates` is consumed
    once, so materialize it to a list before fanning out.
    """
    aggregates = list(aggregates)
    return [
        *compute_hot_path(aggregates, window_days=window_days),
        *compute_orphaned(aggregates, window_days=window_days),
        *compute_degrading(aggregates, window_days=window_days),
    ]
