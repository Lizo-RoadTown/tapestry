"""Telemetry READ API — the query side of the telemetry substrate.

Phase 0 **task 6** of the observer-capacity build
(docs/plans/2026-08-23-observer-capacity-build-sequence.md:127). The write
path (task 3, skill_usage_handler.py) lands events in
`telemetry_events` + `telemetry_rollup_daily`
(infra/migrations/005_init_telemetry.sql); this module exposes the reads the
runtime-observer and the self-observer need, WITHOUT any Grafana/Loki
dependency (self-host parity — proposal lines 215/239).

## The endpoints (all read INSIDE db.tenant_transaction, so RLS scopes them)

  GET /telemetry/invocations          — the `invocations_30d` backing; the
                                         0-vs-None contract (highest value —
                                         retires the self-observer None stub).
  GET /telemetry/counts               — top-N grouped invocation/error counts.
  GET /telemetry/signals              — coordination-quality aggregate.
  GET /telemetry/episode/{ctx_id}     — ordered event list for one episode.

## The 0-vs-None contract (LOAD-BEARING)

The self-observer's `invocations_30d(repo, file_path)` returns `int | None`
(the-loom/services/self-observer/telemetry_client.py:22-35) and
`signal_rules.classify` (…/signal_rules.py:189-216) branches on it:

  - `invocations == 0` AND location is skill/agent → emit a `process`
    (archive/orphan) candidate. The artifact is INSTRUMENTED but UNUSED.
  - `invocations is None` → telemetry unavailable for this entry; SUPPRESS —
    do not emit a false orphan.

So the two "no activity in window" cases must be told apart:

  - never seen ANYWHERE (no lifetime row)  → invocations=null, known=false
  - seen (lifetime) but 0 in the window     → invocations=0,    known=true
  - active in the window                     → invocations=<n>,  known=true

`known` is driven by an EXISTENCE PROBE (does this artifact have ANY lifetime
row, ignoring the window); `invocations` is driven by the WINDOWED SUM. The
two are computed separately on purpose — a windowed SUM of 0 is ambiguous on
its own, which is exactly the bug the None-stub avoided by never returning 0.

## Tenant resolution (Phase 0: self-host only)

telemetry-ingestion deliberately omits python-jose (see requirements.txt), so
there is no JWT verification here yet. Reads resolve the tenant from the
environment using the SAME order the write path already uses
(skill_usage_handler._self_host_tenant_id: SELF_HOST_TENANT_ID →
LOOM_SELF_HOST_TENANT_ID → nil) — we reuse that helper rather than duplicate
it. If it resolves to the nil placeholder we FAIL CLOSED (503) instead of
serving an all-zeros-tenant read that would leak nothing but silently answer
"0 / not known" for every artifact — a false-negative that would poison the
orphan-detection contract above.

TODO(hosted-auth): when telemetry-ingestion gains hosted-multitenant read
auth, add Bearer-JWT verification here (mirror
services/agent-context/main.py:_resolve_tenant_for_rest — self-host fallback,
RS256 verify, tenant_id claim) and pull in python-jose. Until then reads are
self-host single-tenant only.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

import db
import skill_usage_handler

router = APIRouter()


# ---------------------------------------------------------------------------
# Tenant resolution (self-host; fail closed)
# ---------------------------------------------------------------------------


def _resolve_read_tenant() -> str:
    """Resolve the self-host tenant for a read, or fail closed.

    Reuses the write path's env resolver
    (skill_usage_handler._self_host_tenant_id, SAME order as
    loom_auth.auth_bridge.SELF_HOST_TENANT_ID) so reads and writes always land
    in the same tenant envelope. Returns 503 rather than reading the all-zeros
    tenant when unset — a silent nil-tenant read answers "0 / not known" for
    every artifact, which is a false negative the orphan-detection contract
    cannot tolerate.
    """
    tenant_id = skill_usage_handler._self_host_tenant_id()
    if not tenant_id or tenant_id == skill_usage_handler.NIL_TENANT_ID:
        raise HTTPException(
            503,
            "Telemetry read tenant unresolved: set SELF_HOST_TENANT_ID (or "
            "LOOM_SELF_HOST_TENANT_ID). Refusing to serve an all-zeros-tenant "
            "read (would answer 0/unknown for every artifact).",
        )
    return tenant_id


# ---------------------------------------------------------------------------
# artifact_ref normalization
# ---------------------------------------------------------------------------


def _normalize_artifact_ref(
    artifact_ref: Optional[str],
    repo: Optional[str],
    file_path: Optional[str],
) -> str:
    """Resolve the artifact_ref to probe.

    005 defines artifact_ref as a normalized `repo#path` or a `skill/agent`
    name. The self-observer identifies entries by (repo, file_path), so
    `repo`+`file_path` normalize to `repo#file_path`. An explicit
    `artifact_ref` (e.g. `skill/<uuid>` from the engine write path) is used
    verbatim and wins if both are supplied.
    """
    if artifact_ref:
        return artifact_ref
    if repo and file_path:
        return f"{repo}#{file_path}"
    raise HTTPException(
        422,
        "Provide either `artifact_ref`, or both `repo` and `file_path`.",
    )


# ---------------------------------------------------------------------------
# GET /telemetry/invocations — the 0-vs-None contract
# ---------------------------------------------------------------------------

# Existence probe: does this artifact have ANY lifetime row (window-agnostic)?
# Rollup is upserted on every accepted event, so its presence mirrors the fact
# table; we OR in the fact table too so a future rollup-retention trim (005's
# retention note) can never collapse "seen but old" into "never seen". Both
# scans are RLS-scoped to the transaction's app.tenant_id.
_EXISTS_SQL = """
SELECT
    EXISTS (
        SELECT 1 FROM telemetry_rollup_daily
        WHERE artifact_ref = %(artifact_ref)s
    )
    OR EXISTS (
        SELECT 1 FROM telemetry_events
        WHERE artifact_ref = %(artifact_ref)s
    ) AS known
"""

# Windowed sum from the rollup: O(#buckets) not a fact-table scan. bucket_day
# is stored as the event's UTC date (write path:
# `(to_timestamp(ts) AT TIME ZONE 'UTC')::date`), so the window boundary is
# computed in UTC too for consistency across server timezones.
_INVOCATIONS_SQL = """
SELECT COALESCE(SUM(invocation_count), 0) AS invocations
FROM telemetry_rollup_daily
WHERE artifact_ref = %(artifact_ref)s
  AND bucket_day >= (now() AT TIME ZONE 'UTC')::date - %(window_days)s::integer
  {project_filter}
"""


@router.get("/telemetry/invocations")
async def get_invocations(
    artifact_ref: Optional[str] = Query(
        None, description="Normalized artifact ref (e.g. `repo#path` or "
                          "`skill/<uuid>`). Or pass repo + file_path."),
    repo: Optional[str] = Query(None),
    file_path: Optional[str] = Query(None),
    window_days: int = Query(30, ge=1, le=365),
    project_slug: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Invocation count for one artifact over a window, with the 0-vs-None
    existence contract. Backs the self-observer's `invocations_30d`.

    Returns:
      never seen anywhere  → {invocations: null, known: false}
      seen but 0 in window → {invocations: 0,    known: true}
      active               → {invocations: <n>,  known: true}
    """
    ref = _normalize_artifact_ref(artifact_ref, repo, file_path)
    tenant_id = _resolve_read_tenant()

    project_filter = "AND project_slug = %(project_slug)s" if project_slug else ""
    params = {
        "artifact_ref": ref,
        "window_days": window_days,
        "project_slug": project_slug,
    }

    async with db.tenant_transaction(tenant_id) as conn:
        async with conn.cursor() as cur:
            # Existence probe (window-agnostic) → drives `known`.
            await cur.execute(_EXISTS_SQL, {"artifact_ref": ref})
            known = bool((await cur.fetchone())["known"])

            # Windowed SUM → drives `invocations`.
            await cur.execute(
                _INVOCATIONS_SQL.format(project_filter=project_filter), params
            )
            windowed = int((await cur.fetchone())["invocations"])

    if not known:
        # Never instrumented anywhere → None (caller SUPPRESSES). Ignore the
        # windowed sum, which is trivially 0 here anyway.
        return {
            "artifact_ref": ref,
            "window_days": window_days,
            "invocations": None,
            "known": False,
        }
    return {
        "artifact_ref": ref,
        "window_days": window_days,
        "invocations": windowed,  # 0 here == instrumented-but-unused → orphan
        "known": True,
    }


# ---------------------------------------------------------------------------
# GET /telemetry/counts — top-N grouped counts
# ---------------------------------------------------------------------------

# group_by is interpolated as an IDENTIFIER (column name), which CANNOT be a
# bind parameter — so it is whitelisted against the rollup's actual grain
# columns. Every VALUE below is still parameterized.
_COUNTS_GROUP_BY = {"project_slug", "artifact_ref", "tool_name", "event_kind"}

# Optional equality filters — same whitelist of columns; values parameterized.
_COUNTS_FILTERS = {"project_slug", "artifact_ref", "tool_name", "event_kind"}


@router.get("/telemetry/counts")
async def get_counts(
    group_by: str = Query(
        ..., description="One of: project_slug, artifact_ref, tool_name, "
                        "event_kind."),
    window_days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
    project_slug: Optional[str] = Query(None),
    artifact_ref: Optional[str] = Query(None),
    tool_name: Optional[str] = Query(None),
    event_kind: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Top-N invocation/error counts grouped by one dimension, summed from the
    daily rollup over a window. Rows sorted by invocations desc.

    Row shape: {key, invocations, errors, last_seen} where last_seen is epoch
    seconds (float) of the most recent event in the group.
    """
    if group_by not in _COUNTS_GROUP_BY:
        raise HTTPException(
            422,
            f"group_by must be one of {sorted(_COUNTS_GROUP_BY)}; got {group_by!r}.",
        )
    tenant_id = _resolve_read_tenant()

    params: dict[str, Any] = {"window_days": window_days, "limit": limit}
    filters = [
        "bucket_day >= (now() AT TIME ZONE 'UTC')::date - %(window_days)s::integer"
    ]
    candidate_filters = {
        "project_slug": project_slug,
        "artifact_ref": artifact_ref,
        "tool_name": tool_name,
        "event_kind": event_kind,
    }
    for col, val in candidate_filters.items():
        if val is not None and col in _COUNTS_FILTERS and col != group_by:
            filters.append(f"{col} = %({col})s")
            params[col] = val

    where = " AND ".join(filters)
    sql = f"""
        SELECT
            {group_by} AS key,
            SUM(invocation_count) AS invocations,
            SUM(error_count) AS errors,
            MAX(last_seen_ts) AS last_seen
        FROM telemetry_rollup_daily
        WHERE {where}
        GROUP BY {group_by}
        ORDER BY invocations DESC, {group_by} ASC
        LIMIT %(limit)s
    """

    async with db.tenant_transaction(tenant_id) as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()

    return {
        "group_by": group_by,
        "window_days": window_days,
        "rows": [
            {
                "key": r["key"],
                "invocations": int(r["invocations"] or 0),
                "errors": int(r["errors"] or 0),
                "last_seen": float(r["last_seen"] or 0.0),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# GET /telemetry/signals — coordination-quality aggregate
# ---------------------------------------------------------------------------

# Containment predicates hit the attrs GIN index (jsonb_path_ops). Keys are the
# canonical contract attributes (otel-coordination-contract.md:46-52), stored
# inside attrs by the emit-side mapper (Phase 0 task 4).
_SIGNALS_AGG_SQL = """
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (
        WHERE attrs @> '{"tapestry.friction_present": true}'::jsonb
    ) AS friction,
    COUNT(*) FILTER (
        WHERE attrs @> '{"tapestry.memory_miss": true}'::jsonb
    ) AS memory_miss,
    COUNT(*) FILTER (WHERE outcome = 'error') AS errors,
    COUNT(*) FILTER (
        WHERE attrs @> '{"tapestry.upskill_candidate_present": true}'::jsonb
    ) AS upskill_candidates,
    COUNT(*) FILTER (
        WHERE attrs @> '{"tapestry.correction_present": true}'::jsonb
    ) AS corrections
FROM telemetry_events
WHERE ts >= EXTRACT(EPOCH FROM now()) - (%(window_days)s::bigint * 86400)
  {project_filter}
"""

_SIGNALS_STATE_SQL = """
SELECT coordination_state, COUNT(*) AS n
FROM telemetry_events
WHERE ts >= EXTRACT(EPOCH FROM now()) - (%(window_days)s::bigint * 86400)
  {project_filter}
GROUP BY coordination_state
"""

# The four contract states (otel-coordination-contract.md:56-63); always
# reported so a consumer sees an explicit 0 rather than a missing key.
_COORDINATION_STATES = ("healthy", "degraded", "blind", "unknown")


@router.get("/telemetry/signals")
async def get_signals(
    window_days: int = Query(30, ge=1, le=365),
    project_slug: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Coordination-quality aggregate over a window: friction / memory-miss /
    error rates, per-coordination-state counts, and the upskill-candidate
    tally. Rates are fraction-of-events (0.0 when the window is empty).

    Rates are computed from telemetry_events.attrs containment
    (`attrs @> '{...}'`, GIN-indexed) plus the typed `coordination_state`
    column, per the OTel coordination contract.
    """
    tenant_id = _resolve_read_tenant()
    project_filter = "AND project_slug = %(project_slug)s" if project_slug else ""
    params = {"window_days": window_days, "project_slug": project_slug}

    async with db.tenant_transaction(tenant_id) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                _SIGNALS_AGG_SQL.format(project_filter=project_filter), params
            )
            agg = await cur.fetchone()

            await cur.execute(
                _SIGNALS_STATE_SQL.format(project_filter=project_filter), params
            )
            state_rows = await cur.fetchall()

    total = int(agg["total"] or 0)

    def _rate(n: Any) -> float:
        n = int(n or 0)
        return (n / total) if total else 0.0

    per_state = {s: 0 for s in _COORDINATION_STATES}
    for r in state_rows:
        # coordination_state is CHECK-constrained to the four values, but guard
        # against any legacy/unexpected value rather than KeyError.
        per_state[r["coordination_state"]] = int(r["n"] or 0)

    return {
        "window_days": window_days,
        "total_events": total,
        "friction_rate": _rate(agg["friction"]),
        "memory_miss_rate": _rate(agg["memory_miss"]),
        "error_rate": _rate(agg["errors"]),
        "correction_rate": _rate(agg["corrections"]),
        "coordination_state_counts": per_state,
        "upskill_candidates": int(agg["upskill_candidates"] or 0),
    }


# ---------------------------------------------------------------------------
# GET /telemetry/episode/{coordination_context_id} — ordered episode
# ---------------------------------------------------------------------------

# Uses the (tenant_id, coordination_context_id) index
# (telemetry_events_tenant_ctx_idx). Ordered by event time then arrival for a
# stable within-episode sequence.
_EPISODE_SQL = """
SELECT
    id, coordination_context_id, project_slug, session_id,
    agent_id, agent_role, surface_id, surface_type,
    event_kind, hook_name, tool_name, phase, artifact_ref,
    outcome, coordination_state, exit_code, elapsed_ms,
    tokens_in, tokens_out, model, ts, received_at, attrs
FROM telemetry_events
WHERE coordination_context_id = %(ctx_id)s
ORDER BY ts ASC, received_at ASC
LIMIT %(limit)s
"""


@router.get("/telemetry/episode/{coordination_context_id}")
async def get_episode(
    coordination_context_id: uuid.UUID,
    limit: int = Query(1000, ge=1, le=10000),
) -> dict[str, Any]:
    """Ordered event list for one coordination episode (all events sharing a
    coordination_context_id), earliest first. UUID path type validates the id;
    the (tenant_id, coordination_context_id) index backs the lookup.
    """
    tenant_id = _resolve_read_tenant()
    params = {"ctx_id": str(coordination_context_id), "limit": limit}

    async with db.tenant_transaction(tenant_id) as conn:
        async with conn.cursor() as cur:
            await cur.execute(_EPISODE_SQL, params)
            rows = await cur.fetchall()

    # dict_row rows are already JSON-serializable dicts (UUID/attrs handled by
    # FastAPI's encoder); return them in order.
    return {
        "coordination_context_id": str(coordination_context_id),
        "count": len(rows),
        "events": [_serialize_event(r) for r in rows],
    }


def _serialize_event(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a telemetry_events row for the JSON response — UUID columns to
    str so the shape is stable regardless of psycopg's return types."""
    out = dict(row)
    for k in ("id", "coordination_context_id"):
        if out.get(k) is not None:
            out[k] = str(out[k])
    return out
