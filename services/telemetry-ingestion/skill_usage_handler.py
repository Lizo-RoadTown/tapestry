# TODO(Phase 0 task 3): replace the stdout/Loki log-emit in apply_batch with the Postgres write (telemetry_events INSERT + telemetry_rollup_daily UPSERT) inside a SET LOCAL app.tenant_id tx.
"""Skill usage telemetry handler.

PR D of the loom-side bridge build. Receives engine-side telemetry
batches at POST /skill-used, validates, emits structured log lines per
event for the Grafana Cloud / Loki pipeline.

## Migration note (Tapestry, Phase 0 task 2)

Migrated verbatim from `the-loom/services/telemetry-ingestion/
skill_usage_handler.py` as the log-only base. The Postgres persistence
that this module's docstring calls "broader Phase 4 work" is now Phase 0
**task 3** of the observer-capacity build sequence
(docs/plans/2026-08-23-observer-capacity-build-sequence.md): task 3
replaces the stdout/Loki emit below with a write into the telemetry
substrate (infra/migrations/005_init_telemetry.sql) using the pool +
tenant-transaction wrapper in `db.py`. Until then the emit stays as-is so
the receiver keeps working; `db.py` is present but unused by apply_batch.

## What this module does (v1.0)

1. Take a verified, parsed `TelemetryBatch` (HMAC + Pydantic done by
   the endpoint).
2. Emit one structured log line per event. The log line is a JSON
   object — Loki picks them up via the OTel pipeline configured per
   render.yaml's loom-shared-secrets group; queryable by `skill_id`,
   `tenant_id`, `outcome`, etc.
3. Return a count of events processed (no per-event persistence beyond
   the log emission; the persistence layer is Phase 0 task 3 work
   for telemetry-ingestion — see the migration note above).

## What this module does NOT do (yet)

- Postgres write — the DB layer lands in Phase 0 task 3. `db.py` in this
  service already exposes the pool + `tenant_transaction()` wrapper task 3
  will use; apply_batch does not call it yet.
- Aggregation / rollup — the dashboard reads raw events from Loki;
  rollup happens at the query layer if needed. Task 3 adds the
  telemetry_rollup_daily UPSERT.
- Forwarding to other observability backends — Render's structured
  log shipper handles the export.

## Dual-mode

- Schema layer (bridge_models.TelemetryEvent) enforces tenant_id
  non-null in BOTH modes. Adjustment #1 + extra='forbid' carry over.
- Log emission is mode-agnostic — same JSON shape regardless of
  whether tenant_id is SELF_HOST_TENANT_ID or per-tenant UUID.
- Privacy invariant (no message_content) holds in both modes:
  enforced by extra='forbid' in the schema.
- Hosted-multitenant FUTURE persistence: when task 3's storage lands, it
  scopes by event.tenant_id via RLS (mirror of architecture-registry /
  agent-context pattern; see db.py). Today: log emission only; Loki is
  single-tenant for Liz.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import bridge_models

logger = logging.getLogger("loom.telemetry.skill_usage")


def apply_batch(batch: bridge_models.TelemetryBatch) -> dict[str, Any]:
    """Process a verified TelemetryBatch.

    Emits one structured log entry per event for Loki indexing. Returns
    a small ack dict for the HTTP response.

    Each emitted log entry is a JSON object on stdout:

      {"skill_id": "...", "tenant_id": "...", "outcome": "success",
       "latency_ms": 100, "tokens_in": 10, "tokens_out": 5,
       "model": "claude-opus-4-7", "trigger_context": "user message",
       "thread_id": "...", "invoked_at": "...", "batch_id": "..."}

    The batch_id is included on every event line so Loki can group
    + dedup if the engine retries the batch.
    """
    for event in batch.events:
        # Emit as a single-line JSON via the logger so OTel + the Render
        # log shipper can pick it up reliably. Pydantic's model_dump_json
        # is identical-byte-for-byte to what was signed at the wire layer.
        record = {
            "event_kind": "skill_usage",
            "schema_version": batch.schema_version,
            "batch_id": str(batch.batch_id),
            "skill_id": str(event.skill_id),
            "thread_id": str(event.thread_id),
            "tenant_id": str(event.tenant_id),
            "invoked_at": event.invoked_at,
            "outcome": event.outcome,
            "latency_ms": event.latency_ms,
            "tokens_in": event.tokens_in,
            "tokens_out": event.tokens_out,
            "model": event.model,
            "trigger_context": event.trigger_context,
        }
        logger.info(json.dumps(record, separators=(",", ":")))

    return {
        "batch_id": str(batch.batch_id),
        "events_processed": len(batch.events),
    }
