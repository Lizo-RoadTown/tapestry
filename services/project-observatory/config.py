"""Signal-computation thresholds + constants for the runtime-observer.

Phase 1 of the observer-capacity build (docs/plans/2026-08-23-observer-
capacity-build-sequence.md). The signal computation (Phase 1 **task 3**)
imports these; keeping them in one module means every threshold is tuned in
ONE place rather than scattered through the compute code.

## These are STARTING POINTS, not tuned constants

All values below are the DESIGN DEFAULTS — reasonable first cuts, not values
validated against real telemetry. They are meant to be tuned here as the
observer runs against actual project data and the false-positive / false-
negative rates on each signal become visible. Treat every constant as TUNABLE.

## What the observer computes (ADR-0001 docs/adr/0001-observer-topology.md)

The runtime-observer reads the 005 telemetry substrate over a window and
emits the observation signals ADR-0001 names — `hot_path`, `orphaned`,
`degrading` — plus `blind` (instrumented location with no telemetry reaching
the substrate at all). These land in observation_signals
(006_init_observation_signals.sql), whose CHECK constraint enumerates exactly
these four `signal_kind` values (see SIGNAL_KINDS below).

Signals are EVIDENCE, not candidates (ADR-0001:27-29,42) — no automation
level or activation lives here.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Observation window
# ---------------------------------------------------------------------------

# The window (in days) the observer computes signals over. Matches the read
# API's default window and observation_signals.window_days default (30).
# TUNABLE.
WINDOW_DAYS = 30

# The window is split into an earlier half and a recent half so trend signals
# (degrading) can compare recent behavior against the earlier baseline. The
# split is the number of days in EACH sub-window; 15/15 halves the 30-day
# window. Set so that 2 * SUBWINDOW_SPLIT == WINDOW_DAYS for a clean split.
# TUNABLE.
SUBWINDOW_SPLIT = 15  # -> earlier 15 days vs recent 15 days

# ---------------------------------------------------------------------------
# hot_path — the artifact is heavily used (a load-bearing path)
# ---------------------------------------------------------------------------

# Minimum windowed invocations for an artifact to be eligible as a hot_path.
# Below this the sample is too small to call anything "hot". TUNABLE.
HOT_MIN_INVOCATIONS = 50

# Percentile (of windowed invocation counts across artifacts) at/above which an
# eligible artifact is flagged hot_path — the top 10% by default. TUNABLE.
HOT_TOP_PERCENTILE = 90

# ---------------------------------------------------------------------------
# degrading — the artifact's health is trending worse across the window
# ---------------------------------------------------------------------------

# Minimum increase in error-rate (recent sub-window minus earlier sub-window)
# to count as degrading — e.g. 0.05 == a 5-percentage-point rise. TUNABLE.
DEGRADE_ERR_DELTA = 0.05

# Error-rate floor: ignore error-rate deltas when the recent error rate is
# below this (e.g. 0.02 == 2%) — small absolute rates produce noisy deltas.
# TUNABLE.
DEGRADE_ERR_FLOOR = 0.02

# Latency-regression trigger: recent-window latency this many times the earlier
# window's latency counts as degrading (1.5 == 50% slower). TUNABLE.
DEGRADE_LATENCY_RATIO = 1.5

# Minimum sample size (invocations) in EACH sub-window before a degrading
# comparison is trusted — below this the trend is not statistically meaningful.
# TUNABLE.
DEGRADE_MIN_SAMPLE = 20

# ---------------------------------------------------------------------------
# signal_kind — the enumerated observation signals
# ---------------------------------------------------------------------------

# The four signal kinds, matching the CHECK constraint
# `observation_signals_kind_enum` in
# infra/migrations/006_init_observation_signals.sql:69-71 EXACTLY. Task 4's
# writes set signal_kind to one of these; keeping the tuple in sync with the
# migration's CHECK is required or the INSERT fails the constraint.
#
#   hot_path  — heavily-invoked, load-bearing path (see HOT_* above)
#   orphaned  — instrumented artifact with 0 windowed invocations but a
#               lifetime row (the 005 read API's 0-vs-None "known but unused"
#               case; None/never-seen is SUPPRESSED, not orphaned)
#   degrading — health trending worse across the window (see DEGRADE_* above)
#   blind     — an instrumented location with NO telemetry reaching the
#               substrate (self-host-parity gap: emit path exists, storage
#               shows nothing)
SIGNAL_KINDS = ("hot_path", "orphaned", "degrading", "blind")
