"""Observation-signals READ API — the query side of the runtime-observer.

Phase 1 **task 5** of the observer-capacity build (docs/plans/2026-08-23-
observer-capacity-build-sequence.md). The compute+write path (task 3 signals.py
/ task 4 writes.py) lands one `run_id` snapshot per pass in observation_signals
(infra/migrations/006_init_observation_signals.sql); this module exposes the
read a consumer needs — the LATEST snapshot's signal rows — WITHOUT any Grafana
dependency (self-host parity). Mirrors the sibling read API at
services/telemetry-ingestion/read_api.py (the canonical read-API pattern in
this monorepo): tenant-resolve → 503-on-unresolved, FastAPI Query params,
dict_row reads inside db.tenant_transaction, and stable-JSON casting.

## The endpoints (all read INSIDE db.tenant_transaction, so 006 RLS scopes them)

  GET /observations/signals        — the LATEST snapshot's signal rows,
                                      optionally filtered by project / kind /
                                      artifact, ranked by score desc.
  GET /observations/signals/runs   — recent snapshot history (run_id +
                                      computed_at + row count) so a consumer can
                                      see a signal's trajectory across passes.

## "Latest snapshot" = one run_id (not one timestamp)

A snapshot is a whole `run_id` (writes.py stamps a single run_id + computed_at
across every row of a pass). The latest snapshot is therefore the rows of the
run_id whose computed_at is greatest — resolved as a run_id, NOT by matching
`computed_at = MAX(computed_at)`. The run_id approach means a partial-timestamp
tie (should two rows ever differ by a hair) can never split a snapshot in half:
we pick one run_id and return exactly its rows. The
(tenant_id, computed_at DESC) index backs the "latest run_id" probe and the
(tenant_id, run_id) index backs fetching that snapshot's rows.

## Tenant resolution (Phase 1: self-host only)

project-observatory resolves the tenant from the environment via
tenant.require_self_host_tenant() (SELF_HOST_TENANT_ID ->
LOOM_SELF_HOST_TENANT_ID -> nil). If it would resolve to the all-zeros nil
tenant we FAIL CLOSED with a 503 rather than serve an all-zeros-tenant read
that would answer "no snapshot" for every real tenant — the same fail-closed
rule the write path (writes.py) and the sibling read API
(telemetry-ingestion/read_api.py:78-97) enforce.

TODO(hosted-auth): when project-observatory gains hosted-multitenant read auth,
add Bearer-JWT verification here (mirror services/agent-context/main.py
_resolve_tenant_for_rest — self-host fallback, RS256 verify, tenant_id claim)
and pull in python-jose. Until then reads are self-host single-tenant only.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

import config
import db
import tenant

router = APIRouter()


# ---------------------------------------------------------------------------
# Tenant resolution (self-host; fail closed)
# ---------------------------------------------------------------------------


def _resolve_read_tenant() -> str:
    """Resolve the self-host tenant for a read, or fail closed with a 503.

    Delegates to tenant.require_self_host_tenant() (the service's single
    resolver) and translates its TenantUnresolved into an HTTP 503, exactly as
    services/telemetry-ingestion/read_api.py:_resolve_read_tenant does. Never
    reads under the nil tenant: an all-zeros read is RLS-scoped to a phantom
    tenant and answers "no snapshot" for every real one — a silent false
    negative, so we refuse rather than serve it.
    """
    try:
        return tenant.require_self_host_tenant()
    except tenant.TenantUnresolved as exc:
        raise HTTPException(503, str(exc))


# ---------------------------------------------------------------------------
# GET /observations/signals — the latest snapshot's rows
# ---------------------------------------------------------------------------

# Identify the latest snapshot as a run_id (see module docstring): the run_id of
# the row with the greatest computed_at. RLS scopes this to app.tenant_id, so no
# tenant_id predicate is needed here — the (tenant_id, computed_at DESC) index
# backs the ORDER BY / LIMIT 1. computed_at is stamped once per pass, so this
# row's computed_at is the whole snapshot's timestamp.
_LATEST_RUN_SQL = """
SELECT run_id, computed_at
FROM observation_signals
ORDER BY computed_at DESC
LIMIT 1
"""

# Fetch one snapshot's rows by run_id (the (tenant_id, run_id) index), with the
# optional equality filters folded in as parameterized predicates. Every value
# binds (%(...)s); only the pre-validated filter FRAGMENTS are formatted in, and
# each names a fixed column — no user string ever reaches the SQL text. Ranked
# by score desc so the most significant signal leads.
_SNAPSHOT_ROWS_SQL = """
SELECT project_slug, artifact_ref, signal_kind, score, window_days,
       evidence, computed_at
FROM observation_signals
WHERE run_id = %(run_id)s
  {filters}
ORDER BY score DESC, artifact_ref ASC
LIMIT %(limit)s
"""


@router.get("/observations/signals")
async def get_signals(
    project_slug: Optional[str] = Query(
        None, description="Filter to one project's signals (exact match)."),
    signal_kind: Optional[str] = Query(
        None, description="Filter to one signal kind: one of hot_path, "
                          "orphaned, degrading, blind."),
    artifact_ref: Optional[str] = Query(
        None, description="Filter to one artifact_ref (exact match)."),
    limit: int = Query(500, ge=1, le=1000),
) -> dict[str, Any]:
    """The LATEST observation-signals snapshot's rows, ranked by score desc.

    "Latest snapshot" is the most recent `run_id` (not a bare MAX(computed_at)
    match — a snapshot is one whole run_id). Optional filters narrow within that
    snapshot; they never reach back into older snapshots.

    Response:
      {run_id, computed_at, count, signals: [{project_slug, artifact_ref,
       signal_kind, score, window_days, evidence, computed_at}, ...]}
    No snapshot yet (nothing written for this tenant) ->
      {run_id: null, computed_at: null, count: 0, signals: []} (200, not error).

    `score` and `computed_at` are cast to float and `window_days` to int for a
    stable JSON shape; `evidence` comes back as a dict (JSONB).
    """
    # signal_kind is whitelisted against the migration's CHECK enum (config.
    # SIGNAL_KINDS) BEFORE any DB work — a bad value is a 422, never a query.
    if signal_kind is not None and signal_kind not in config.SIGNAL_KINDS:
        raise HTTPException(
            422,
            f"signal_kind must be one of {list(config.SIGNAL_KINDS)}; "
            f"got {signal_kind!r}.",
        )

    tenant_id = _resolve_read_tenant()

    # Build the optional equality filters. Each fragment names a FIXED column;
    # the corresponding value is bound as a parameter (never interpolated).
    filters = ""
    params: dict[str, Any] = {"limit": limit}
    candidate_filters = {
        "project_slug": project_slug,
        "signal_kind": signal_kind,
        "artifact_ref": artifact_ref,
    }
    filter_sql: list[str] = []
    for col, val in candidate_filters.items():
        if val is not None:
            filter_sql.append(f"AND {col} = %({col})s")
            params[col] = val
    if filter_sql:
        filters = "\n  ".join(filter_sql)

    async with db.tenant_transaction(tenant_id) as conn:
        async with conn.cursor() as cur:
            # Resolve the latest snapshot's identity (run_id + its computed_at).
            await cur.execute(_LATEST_RUN_SQL)
            latest = await cur.fetchone()
            if latest is None:
                # No snapshot written for this tenant yet — not an error.
                return {
                    "run_id": None,
                    "computed_at": None,
                    "count": 0,
                    "signals": [],
                }

            run_id = str(latest["run_id"])
            snapshot_computed_at = float(latest["computed_at"])

            # Fetch that snapshot's rows, filtered + ranked.
            params["run_id"] = run_id
            await cur.execute(
                _SNAPSHOT_ROWS_SQL.format(filters=filters), params
            )
            rows = await cur.fetchall()

    signals = [
        {
            "project_slug": r["project_slug"],
            "artifact_ref": r["artifact_ref"],
            "signal_kind": r["signal_kind"],
            "score": float(r["score"]),
            "window_days": int(r["window_days"]),
            "evidence": r["evidence"],  # JSONB -> dict
            "computed_at": float(r["computed_at"]),
        }
        for r in rows
    ]

    return {
        "run_id": run_id,
        "computed_at": snapshot_computed_at,
        "count": len(signals),
        "signals": signals,
    }


# ---------------------------------------------------------------------------
# GET /observations/signals/runs — snapshot history
# ---------------------------------------------------------------------------

# One row per snapshot (run_id), newest first. computed_at is stamped once per
# pass so MAX() collapses the pass's identical values to that one timestamp.
# RLS scopes it to app.tenant_id; the (tenant_id, run_id) index backs the group.
_RUNS_SQL = """
SELECT run_id, MAX(computed_at) AS computed_at, COUNT(*) AS row_count
FROM observation_signals
GROUP BY run_id
ORDER BY computed_at DESC
LIMIT %(limit)s
"""


@router.get("/observations/signals/runs")
async def get_signal_runs(
    limit: int = Query(50, ge=1, le=1000),
) -> dict[str, Any]:
    """Recent snapshot history: each pass's run_id, its computed_at, and how
    many signal rows it produced — newest first. Lets a consumer see snapshot
    trajectory (e.g. "this run wrote fewer signals than the last") and pick an
    older run_id to inspect. Empty -> {count: 0, runs: []} (200).
    """
    tenant_id = _resolve_read_tenant()

    async with db.tenant_transaction(tenant_id) as conn:
        async with conn.cursor() as cur:
            await cur.execute(_RUNS_SQL, {"limit": limit})
            rows = await cur.fetchall()

    runs = [
        {
            "run_id": str(r["run_id"]),
            "computed_at": float(r["computed_at"]),
            "row_count": int(r["row_count"]),
        }
        for r in rows
    ]
    return {"count": len(runs), "runs": runs}
