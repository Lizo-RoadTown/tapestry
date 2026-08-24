"""Write layer for observation_signals — the runtime-observer's OUTPUT.

Phase 1 **task 4** of the observer-capacity build (docs/plans/2026-08-23-
observer-capacity-build-sequence.md). `signals.compute_signals` returns pure
signal-record dicts; this module INSERTs them into observation_signals
(infra/migrations/006_init_observation_signals.sql), stamping the machine-owned
columns (tenant_id / run_id / computed_at) the pure records do NOT carry.

Kept separate from `compute_signals.py` (the cron entrypoint) so the entrypoint
stays a thin argparse + orchestrate shell and the actual INSERT — with its
`evidence::jsonb` cast and its tenant/run/clock stamping — lives in one small,
testable place. Mirrors how the sibling service splits its write path out into
services/telemetry-ingestion/persist.py.

## The single-transaction / single-snapshot contract

`insert_signals` runs INSIDE the caller's already-open
`db.tenant_transaction(tenant_id)` connection — the SAME transaction that read
the 005 substrate for this pass. It opens no transaction and resolves no
tenant. That means the read of 005 and the write of 006 commit atomically: a
failed INSERT rolls back the whole pass, so a snapshot is never half-written.

`tenant_id` MUST equal the transaction's `app.tenant_id` (the resolved
self-host tenant), or 006's INSERT WITH CHECK policy (006:121-125) rejects the
row. The caller passes the same resolved tenant it opened the transaction with.

`run_id` and `computed_at` are generated ONCE per pass by the caller and passed
in, so every row in the snapshot shares them (a coherent `run_id` snapshot at a
single `computed_at`). We stamp `computed_at` explicitly rather than leaning on
006's per-row `EXTRACT(EPOCH FROM NOW())` DEFAULT, which would vary row-to-row
within the same pass and smear the snapshot's timestamp.

`id` is left to 006's `gen_random_uuid()` DEFAULT — we never supply it.

Every value is a bound parameter (%(name)s); `evidence` is JSON-serialized with
`json.dumps` and cast `%(evidence)s::jsonb` — the same idiom as
telemetry-ingestion/persist.py's `attrs` write. No identifier or value is ever
string-interpolated into the statement.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

import psycopg


# One parameterized multi-column INSERT, reused for every row via executemany.
# Column set is fixed: the six pure signal-record fields plus the three stamped
# columns (tenant_id / run_id / computed_at). `id` is omitted so 006's
# gen_random_uuid() DEFAULT fills it. `evidence` casts ::jsonb (persist.py
# idiom); every other value binds directly.
_INSERT_SIGNAL_SQL = """
INSERT INTO observation_signals (
    tenant_id, run_id, project_slug, artifact_ref,
    signal_kind, score, window_days, evidence, computed_at
)
VALUES (
    %(tenant_id)s, %(run_id)s, %(project_slug)s, %(artifact_ref)s,
    %(signal_kind)s, %(score)s, %(window_days)s, %(evidence)s::jsonb, %(computed_at)s
)
"""


def _to_params(
    record: Mapping[str, Any],
    *,
    tenant_id: str,
    run_id: str,
    computed_at: float,
) -> dict[str, Any]:
    """Turn one pure signal record + the pass-wide stamps into a bind-param dict.

    The pure record carries project_slug / artifact_ref / signal_kind / score /
    window_days / evidence (signals._signal_record); this adds tenant_id /
    run_id / computed_at. `evidence` is serialized to a JSON string here — the
    statement casts it `::jsonb`.
    """
    return {
        "tenant_id": tenant_id,
        "run_id": run_id,
        "computed_at": computed_at,
        "project_slug": record["project_slug"],
        "artifact_ref": record["artifact_ref"],
        "signal_kind": record["signal_kind"],
        "score": record["score"],
        "window_days": record["window_days"],
        "evidence": json.dumps(record["evidence"]),
    }


async def insert_signals(
    conn: psycopg.AsyncConnection,
    records: Iterable[Mapping[str, Any]],
    *,
    tenant_id: str,
    run_id: str,
    computed_at: float,
) -> int:
    """Batch-INSERT signal records into observation_signals; return the count.

    `conn` MUST already be inside a `db.tenant_transaction(tenant_id)` whose
    `app.tenant_id` equals the `tenant_id` passed here (006 INSERT WITH CHECK).
    All rows share the one `run_id` + `computed_at` the caller generated for the
    pass, so they form a single coherent snapshot. Empty `records` is a no-op
    returning 0 (no executemany on an empty sequence).

    One `executemany` over the fixed parameterized statement — a single batch,
    no per-row Python round-trips beyond building params, no string
    interpolation. Because there is no ON CONFLICT branch and `id` defaults,
    every supplied row inserts (or the whole transaction rolls back), so the
    returned count is the number of rows written.
    """
    params = [
        _to_params(
            r, tenant_id=tenant_id, run_id=run_id, computed_at=computed_at
        )
        for r in records
    ]
    if not params:
        return 0
    async with conn.cursor() as cur:
        await cur.executemany(_INSERT_SIGNAL_SQL, params)
    return len(params)
