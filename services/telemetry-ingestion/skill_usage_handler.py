"""Skill usage telemetry handler.

PR D of the loom-side bridge build. Receives engine-side telemetry
batches at POST /skill-used, validates, and persists each event into the
telemetry read-substrate (infra/migrations/005_init_telemetry.sql) under
row-level tenant scoping.

## Migration note (Tapestry, Phase 0 tasks 2 + 3)

Migrated from `the-loom/services/telemetry-ingestion/skill_usage_handler.py`
as the log-only base (task 2), then this module's `apply_batch` was
rewritten (Phase 0 **task 3**,
docs/plans/2026-08-23-observer-capacity-build-sequence.md) to replace the
stdout/Loki emit with a Postgres write:

  - INSERT INTO telemetry_events (... ON CONFLICT (id) DO NOTHING)
  - UPSERT INTO telemetry_rollup_daily (... increment on the inserted row only)

both inside a single `async with db.tenant_transaction(tenant_id)` block so
the fact row and its rollup increment commit atomically under the same RLS
scope. `db.py` (task 2) owns the pool + tenant-transaction wrapper.

## What this module does (v2.0)

1. Take a verified, parsed `TelemetryBatch` (HMAC + Pydantic done by the
   endpoint).
2. Resolve the write tenant for each event (see `_resolve_event_tenant`)
   and group events by it so every inserted row's `tenant_id` matches the
   transaction's `app.tenant_id` GUC that RLS WITH CHECK compares against.
3. For each event: INSERT the fact row with a STABLE deterministic id
   (derived from batch_id + per-event index) using ON CONFLICT (id) DO
   NOTHING so a retried batch does not double-count, then UPSERT the daily
   rollup FROM the actually-inserted row only (CTE), keeping the rollup and
   the fact table consistent under retries.
4. Return `{batch_id, events_processed}` where events_processed is the
   number of rows ACTUALLY persisted this call (duplicates excluded).

## Dual-mode

- Self-host: events carry SELF_HOST_TENANT_ID (or the nil UUID, which falls
  back to the deployment's configured SELF_HOST_TENANT_ID env). One tenant
  envelope for the whole deployment.
- Hosted-multitenant: each event's `tenant_id` (the trusted, HMAC-authed
  engine's assertion) is the write tenant, so telemetry lands in the right
  tenant envelope; RLS isolates.
- `db.py` is agnostic to how the tenant was resolved — it only stamps
  `app.tenant_id`; the 005 RLS policies do the isolation.

## Privacy invariant (no message_content)

Held by bridge_models' `extra='forbid'`; nothing here reintroduces content.
`trigger_context` is a short categorical tag, persisted into `attrs`.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import bridge_models
import db

logger = logging.getLogger("loom.telemetry.skill_usage")

# All-zeros / nil tenant. RLS in 005_init_telemetry.sql fails closed to this
# same value when app.tenant_id is unset — so writing here is the "no real
# tenant" sink, which we refuse to do silently (see _resolve_event_tenant).
NIL_TENANT_ID = "00000000-0000-0000-0000-000000000000"

# Namespace for deterministic per-event ids. uuid5 over "batch_id:index" gives
# a STABLE id so an at-least-once retry of the same batch dedups on the
# telemetry_events PK (ON CONFLICT (id) DO NOTHING) instead of double-counting.
_EVENT_ID_NAMESPACE = uuid.NAMESPACE_URL


# ---------------------------------------------------------------------------
# Tenant resolution
# ---------------------------------------------------------------------------


def _self_host_tenant_id() -> str:
    """The deployment's self-host tenant, read with the SAME resolution order
    as loom_auth.auth_bridge.SELF_HOST_TENANT_ID (auth_bridge.py:108-114):
    SELF_HOST_TENANT_ID → LOOM_SELF_HOST_TENANT_ID → nil placeholder.

    Read from env directly (not by importing loom_auth) so telemetry-ingestion
    does not have to pull python-jose + the full auth stack just for one
    constant — its requirements.txt intentionally omits them. Read per-call so
    a deployment/test that sets the env after import is honored.
    """
    return os.environ.get(
        "SELF_HOST_TENANT_ID",
        os.environ.get("LOOM_SELF_HOST_TENANT_ID", NIL_TENANT_ID),
    )


def _resolve_event_tenant(event: bridge_models.TelemetryEvent) -> str | None:
    """Resolve the tenant this event's row is written under.

    1. The event's own `tenant_id` (wire-contract REQUIRED field, "Adjustment
       #1") — the tenant the trusted (HMAC-authenticated) engine asserts. This
       is the only tenant signal in hosted-multitenant mode, so it must drive
       the write to keep tenants isolated.
    2. If the event carries the nil UUID (no real tenant asserted), fall back
       to the server's configured SELF_HOST_TENANT_ID.
    3. If that is ALSO nil/unset, return None → the caller fails closed
       (skip + warn) rather than silently writing to the all-zeros tenant.
    """
    tid = str(event.tenant_id)
    if tid and tid != NIL_TENANT_ID:
        return tid
    fallback = _self_host_tenant_id()
    if fallback and fallback != NIL_TENANT_ID:
        return fallback
    return None


# ---------------------------------------------------------------------------
# Field mapping helpers (bridge_models → 005 telemetry_events columns)
# ---------------------------------------------------------------------------


def _event_id(batch_id: uuid.UUID, index: int) -> str:
    """Deterministic, stable telemetry_events.id from batch_id + item index."""
    return str(uuid.uuid5(_EVENT_ID_NAMESPACE, f"{batch_id}:{index}"))


def _iso_to_epoch(invoked_at: str) -> float:
    """ISO-8601 `invoked_at` → epoch seconds (double), matching the schema's
    `ts DOUBLE PRECISION`. Naive timestamps are treated as UTC."""
    s = invoked_at.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _artifact_ref(skill_id: uuid.UUID) -> str:
    """artifact_ref for a skill-usage event. 005 defines artifact_ref as a
    normalized `repo#path` or `skill/agent name`. The wire contract carries
    only the skill's UUID (no human name), so we key on `skill/<uuid>`."""
    return f"skill/{skill_id}"


# One statement per event: insert the fact row (dedup on id), then upsert the
# daily rollup FROM the row that was actually inserted. The CTE guarantees the
# rollup increments ONLY when the fact INSERT was not a duplicate — so under
# at-least-once retries the rollup and the fact table stay consistent. The
# final INSERT's rowcount is 1 when the event was newly persisted, 0 when the
# id already existed (duplicate) — that is how events_processed is counted.
_WRITE_SQL = """
WITH ins AS (
    INSERT INTO telemetry_events (
        id, tenant_id, event_kind, skill_id, artifact_ref,
        outcome, elapsed_ms, tokens_in, tokens_out, model,
        ts, batch_id, attrs
    )
    VALUES (
        %(id)s, %(tenant_id)s, 'skill_usage', %(skill_id)s, %(artifact_ref)s,
        %(outcome)s, %(elapsed_ms)s, %(tokens_in)s, %(tokens_out)s, %(model)s,
        %(ts)s, %(batch_id)s, %(attrs)s::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, ts, project_slug, artifact_ref,
              tool_name, event_kind, elapsed_ms, outcome
)
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


def _event_params(
    batch: bridge_models.TelemetryBatch,
    index: int,
    event: bridge_models.TelemetryEvent,
    tenant_id: str,
) -> dict[str, Any]:
    """Map one bridge_models event → the _WRITE_SQL bind params.

    Fields without a typed 005 column (thread_id, trigger_context,
    schema_version, the raw invoked_at string) are carried in `attrs`.
    """
    attrs = {
        "schema_version": batch.schema_version,
        "thread_id": str(event.thread_id),
        "trigger_context": event.trigger_context,
        "invoked_at": event.invoked_at,
    }
    return {
        "id": _event_id(batch.batch_id, index),
        "tenant_id": tenant_id,
        "skill_id": str(event.skill_id),
        "artifact_ref": _artifact_ref(event.skill_id),
        "outcome": event.outcome,
        "elapsed_ms": event.latency_ms,
        "tokens_in": event.tokens_in,
        "tokens_out": event.tokens_out,
        "model": event.model,
        "ts": _iso_to_epoch(event.invoked_at),
        "batch_id": str(batch.batch_id),
        "attrs": json.dumps(attrs),
    }


# ---------------------------------------------------------------------------
# Batch entry point
# ---------------------------------------------------------------------------


async def apply_batch(batch: bridge_models.TelemetryBatch) -> dict[str, Any]:
    """Persist a verified TelemetryBatch into the telemetry substrate.

    Groups events by resolved write tenant (normally one, since a batch is
    single-tenant by the wire contract) and writes each group inside one
    `db.tenant_transaction` — atomic + RLS-scoped. Returns the ack dict for
    the HTTP response; `events_processed` is the count ACTUALLY persisted
    (retried duplicates are excluded via ON CONFLICT (id) DO NOTHING).
    """
    # Resolve tenant per event and group so each INSERT's row tenant matches
    # the transaction's app.tenant_id (RLS WITH CHECK). Index is preserved so
    # the deterministic id stays stable across retries.
    groups: dict[str, list[tuple[int, bridge_models.TelemetryEvent]]] = {}
    skipped = 0
    for index, event in enumerate(batch.events):
        tenant_id = _resolve_event_tenant(event)
        if tenant_id is None:
            skipped += 1
            logger.warning(
                json.dumps(
                    {
                        "event": "telemetry_event_skipped_no_tenant",
                        "reason": "no real tenant on event and SELF_HOST_TENANT_ID unset",
                        "batch_id": str(batch.batch_id),
                        "index": index,
                    },
                    separators=(",", ":"),
                )
            )
            continue
        groups.setdefault(tenant_id, []).append((index, event))

    persisted = 0
    for tenant_id, items in groups.items():
        async with db.tenant_transaction(tenant_id) as conn:
            async with conn.cursor() as cur:
                for index, event in items:
                    try:
                        params = _event_params(batch, index, event, tenant_id)
                    except ValueError:
                        # Unparseable invoked_at — skip this one event rather
                        # than aborting the whole tenant group's transaction.
                        skipped += 1
                        logger.warning(
                            json.dumps(
                                {
                                    "event": "telemetry_event_skipped_bad_timestamp",
                                    "batch_id": str(batch.batch_id),
                                    "index": index,
                                    "invoked_at": event.invoked_at,
                                },
                                separators=(",", ":"),
                            )
                        )
                        continue
                    await cur.execute(_WRITE_SQL, params)
                    # rowcount is 1 when the fact row was newly inserted (the
                    # rollup upsert ran on it), 0 when the id already existed.
                    persisted += cur.rowcount

    if skipped:
        logger.info(
            json.dumps(
                {
                    "event": "telemetry_batch_partial",
                    "batch_id": str(batch.batch_id),
                    "received": len(batch.events),
                    "persisted": persisted,
                    "skipped": skipped,
                },
                separators=(",", ":"),
            )
        )

    return {
        "batch_id": str(batch.batch_id),
        "events_processed": persisted,
    }
