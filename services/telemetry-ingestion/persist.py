"""Shared low-level write path for the telemetry substrate.

Factored out of `skill_usage_handler` (Phase 0 task 3) so BOTH `/skill-used`
and `/hook-event` (Phase 0 **task 4**,
docs/plans/2026-08-23-observer-capacity-build-sequence.md) persist through the
SAME verified dedup + rollup mechanism:

  - a CTE that INSERTs the fact row into `telemetry_events`
    `ON CONFLICT (id) DO NOTHING RETURNING` (the id dedup key), then
  - feeds the actually-inserted row into the `telemetry_rollup_daily` UPSERT.

The fact INSERT and its rollup increment run in ONE statement (so they commit
atomically inside the caller's `db.tenant_transaction`), and a replayed event
dedups on the `telemetry_events` PK so the rollup is never double-counted. This
is the mechanism `skill_usage_handler._WRITE_SQL` was adversarially verified
with in task 3; task 4 reuses it verbatim rather than reinventing a second
insert/rollup path.

The only thing that varies between producers is the fact row's COLUMN SET:
skill-usage carries `skill_id` / `tokens_*` / `model`; hook events carry
`project_slug` / `session_id` / `hook_name` / `phase` / `exit_code` / ... .
`persist_events` builds the INSERT column list from each row dict's keys
(validated against the 005 column allowlist — defense in depth; values are
always bound parameters) and keeps the rollup tail byte-for-byte identical for
every producer, so every producer feeds one consistent rollup.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

import psycopg


# telemetry_events columns from infra/migrations/005_init_telemetry.sql.
# persist_events only inserts columns from this allowlist. Callers supply
# column->value dicts (never raw SQL); column names are validated here so a
# typo or a future caller can never smuggle an identifier into the statement.
# Every VALUE is bound as a parameter regardless.
_TELEMETRY_EVENTS_COLUMNS = frozenset(
    {
        "id",
        "tenant_id",
        "coordination_context_id",
        "project_id",
        "project_slug",
        "session_id",
        "agent_id",
        "agent_role",
        "surface_id",
        "surface_type",
        "event_kind",
        "hook_name",
        "tool_name",
        "phase",
        "artifact_ref",
        "skill_id",
        "outcome",
        "coordination_state",
        "exit_code",
        "elapsed_ms",
        "tokens_in",
        "tokens_out",
        "model",
        "ts",
        "received_at",
        "batch_id",
        "attrs",
    }
)

# The columns the rollup SELECT reads out of `ins`. Every INSERT persist_events
# builds RETURNs exactly these, so the rollup tail below is invariant across
# producers (skill-usage and hook events alike).
_ROLLUP_RETURNING = (
    "id, tenant_id, ts, project_slug, artifact_ref, "
    "tool_name, event_kind, elapsed_ms, outcome"
)

# The daily-rollup UPSERT, byte-for-byte the tail of the task-3
# skill_usage_handler._WRITE_SQL. It increments FROM the row that was actually
# inserted (the CTE `ins`), so the rollup only moves when the fact INSERT was
# not a duplicate — under at-least-once retries the rollup and the fact table
# stay consistent.
_ROLLUP_TAIL = """
INSERT INTO telemetry_rollup_daily (
    tenant_id, bucket_day, project_slug, artifact_ref, tool_name, event_kind,
    invocation_count, error_count, sum_elapsed_ms, last_seen_ts
)
SELECT
    tenant_id,
    (to_timestamp(ts) AT TIME ZONE 'UTC')::date,
    COALESCE(project_slug, ''),
    COALESCE(artifact_ref, ''),
    COALESCE(tool_name, ''),
    event_kind,
    1,
    -- error_count is strictly outcome='error'; a 'timeout' is counted as an
    -- invocation but NOT as a failure (there is no separate timeout tally yet).
    CASE WHEN outcome = 'error' THEN 1 ELSE 0 END,
    COALESCE(elapsed_ms, 0),
    ts
FROM ins
ON CONFLICT (tenant_id, bucket_day, project_slug, artifact_ref, tool_name, event_kind)
DO UPDATE SET
    invocation_count = telemetry_rollup_daily.invocation_count + EXCLUDED.invocation_count,
    error_count      = telemetry_rollup_daily.error_count      + EXCLUDED.error_count,
    sum_elapsed_ms   = telemetry_rollup_daily.sum_elapsed_ms   + EXCLUDED.sum_elapsed_ms,
    last_seen_ts     = GREATEST(telemetry_rollup_daily.last_seen_ts, EXCLUDED.last_seen_ts)
RETURNING invocation_count
"""


def _build_sql(columns: list[str]) -> str:
    """Assemble the CTE INSERT + rollup UPSERT for a fixed column list.

    Column identifiers are pre-validated against `_TELEMETRY_EVENTS_COLUMNS`;
    every value is a `%(name)s` bind parameter (attrs additionally cast
    `::jsonb`, matching the task-3 write path).
    """
    placeholders = []
    for col in columns:
        if col == "attrs":
            placeholders.append("%(attrs)s::jsonb")
        else:
            placeholders.append(f"%({col})s")
    return (
        "WITH ins AS (\n"
        f"    INSERT INTO telemetry_events ({', '.join(columns)})\n"
        f"    VALUES ({', '.join(placeholders)})\n"
        "    ON CONFLICT (id) DO NOTHING\n"
        f"    RETURNING {_ROLLUP_RETURNING}\n"
        ")\n"
        f"{_ROLLUP_TAIL}"
    )


async def persist_events(
    conn: psycopg.AsyncConnection,
    rows: Iterable[Mapping[str, Any]],
) -> int:
    """Persist fact rows + increment the daily rollup, returning the count
    ACTUALLY persisted (duplicates excluded via ON CONFLICT (id) DO NOTHING).

    `conn` MUST already be inside a `db.tenant_transaction(tenant_id)` whose
    `app.tenant_id` matches every row's `tenant_id` (RLS WITH CHECK). Each row
    is a `{column: value}` mapping whose keys are a subset of the 005
    telemetry_events columns; `attrs` may be a dict (JSON-serialized here) or a
    pre-serialized JSON string (the skill-usage path passes a string).

    One statement per row: the fact INSERT (dedup on id) and the rollup UPSERT
    execute together, so the rollup moves only when the fact row was newly
    inserted. `cur.rowcount` on the combined statement is 1 for a fresh row and
    0 for a duplicate — that is how the persisted count is tallied.
    """
    persisted = 0
    async with conn.cursor() as cur:
        for row in rows:
            columns = list(row.keys())
            for col in columns:
                if col not in _TELEMETRY_EVENTS_COLUMNS:
                    raise ValueError(
                        f"persist_events: unknown telemetry_events column {col!r}"
                    )
            params: dict[str, Any] = {}
            for col in columns:
                value = row[col]
                if col == "attrs" and not isinstance(value, str):
                    value = json.dumps(value)
                params[col] = value
            await cur.execute(_build_sql(columns), params)
            # 1 when the fact row was newly inserted (rollup ran on it), 0 when
            # the id already existed (duplicate replay).
            persisted += cur.rowcount
    return persisted
