"""loom-telemetry-ingestion — Telemetry Ingestion.

OTel receiver + enrichment layer. Persists skill-usage telemetry into the
loom-postgres read-substrate (infra/migrations/005_init_telemetry.sql),
RLS-scoped by tenant (Phase 0 task 3). Grafana Cloud stays an optional
export target, never a read dependency.

Endpoints:
  GET  /health                                  — Render liveness probe
  POST /skill-used                              — bridge telemetry receiver
                                                  (PR D); HMAC auth
  POST /hook-events (and POST /hook-event)      — discipline-hook ingest
                                                  (Phase 0 task 4); HMAC auth
  GET  /telemetry/invocations                   — read API: invocations_30d
                                                  (0-vs-None contract)
  GET  /telemetry/counts                        — read API: grouped counts
  GET  /telemetry/signals                       — read API: coordination signals
  GET  /telemetry/episode/{ctx_id}              — read API: one episode

The `/telemetry/*` read routes live in read_api.py (Phase 0 task 6); they read
the Postgres substrate inside db.tenant_transaction so RLS scopes every query.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from fastapi import FastAPI, Header, HTTPException, Request

import bridge_hmac
import bridge_models
import db
import hook_event_handler
import read_api
import skill_usage_handler

# Discipline-hook ingest (Phase 0 task 4). Secret is SEPARATE from the engine's
# LOOM_SKILL_BRIDGE_SECRET so the hook emitter (task 5) authenticates with its
# own shared secret. Batch cap mirrors the skill-usage 1000/batch contract.
_HOOK_SECRET_ENV = "LOOM_HOOK_BRIDGE_SECRET"
_MAX_HOOK_EVENTS = 1000


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Close the DB pool on shutdown. The pool opens lazily on the first
    persisted batch (db.get_pool), so nothing to force on startup — just
    drain it cleanly before the Render process exits. Mirrors
    services/project-registry/main.py:lifespan.
    """
    yield
    await db.close_pool()


app = FastAPI(title="loom-telemetry-ingestion", version="0.1.0", lifespan=lifespan)

# Telemetry READ API (Phase 0 task 6) — GET /telemetry/{invocations,counts,
# signals,episode}. Each route resolves the self-host tenant and reads inside
# db.tenant_transaction so the 005 RLS policies scope every query.
app.include_router(read_api.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "loom-telemetry-ingestion"}


# ---------------------------------------------------------------------------
# Skill-making bridge — telemetry batch receiver (PR D)
# ---------------------------------------------------------------------------


@app.post("/skill-used", status_code=202)
async def receive_skill_usage_batch(
    request: Request,
    x_makeskills_signature: Optional[str] = Header(None),
) -> dict:
    """Receive a TelemetryBatch callback from the Make_Skills engine.

    Engine-to-loom direction: NOT a user endpoint. Auth via HMAC
    signature in `X-MakeSkills-Signature` header. Both sides share
    `LOOM_SKILL_BRIDGE_SECRET`.

    Per the spec at Make_Skills `docs/proposals/2026-05-25-skill-making-
    bridge.md` §3 + Loom-agent's ratification.

    Flow:

    1. Read raw body BEFORE parsing (signature verification needs exact
       bytes)
    2. Verify HMAC; 401 on any failure (generic message; no info-leak
       about WHICH check failed)
    3. Parse `TelemetryBatch`; 400 on Pydantic validation failure
       (this is where the privacy invariant catches any attempt to
       smuggle message_content or other forbidden fields)
    4. Hand off to `skill_usage_handler.apply_batch` for the Postgres
       persist (telemetry_events INSERT + telemetry_rollup_daily UPSERT)
    5. Return 202 with batch_id + events_processed

    Status codes:

    - 202: batch accepted; body = {batch_id, events_processed}
    - 400: malformed batch (Pydantic validation, including extra-fields
      rejection — privacy enforcement)
    - 401: HMAC missing / malformed / outside timestamp window / mismatch

    Tenant scope: apply_batch resolves each event's write tenant
    (event.tenant_id, falling back to SELF_HOST_TENANT_ID for a nil
    event tenant) and writes inside db.tenant_transaction so the 005 RLS
    policies isolate rows. Self-host: one tenant envelope. Hosted: the
    engine's per-event tenant assertion drives isolation.
    """
    # Step 1: raw body before parsing.
    raw_body_bytes = await request.body()
    raw_body = raw_body_bytes.decode("utf-8")

    # Step 2: HMAC verify.
    try:
        bridge_hmac.verify_signature(raw_body, x_makeskills_signature)
    except bridge_hmac.BridgeAuthError:
        # Generic error — don't leak which check failed.
        raise HTTPException(401, "Invalid signature")

    # Step 3: parse + privacy enforcement via extra='forbid'.
    try:
        batch = bridge_models.TelemetryBatch.model_validate_json(raw_body)
    except Exception as e:
        raise HTTPException(400, f"Malformed batch: {e}")

    # Step 4: persist to the telemetry substrate (telemetry_events INSERT +
    # telemetry_rollup_daily UPSERT, RLS-scoped) and return the ack.
    return await skill_usage_handler.apply_batch(batch)


# ---------------------------------------------------------------------------
# Discipline-hook ingest — bare-entry receiver (Phase 0 task 4)
# ---------------------------------------------------------------------------


def _coerce_hook_entries(parsed: Any) -> Optional[list[dict[str, Any]]]:
    """Normalize the accepted request bodies to a list of entry dicts.

    Accepts three shapes so task 5's emitter and task 7's backfill can use
    whichever is convenient:
      - a single entry object                     -> [entry]
      - a bare JSON array of entries              -> entries
      - an envelope {"events": [ ...entries ]}    -> entries

    Returns None if the shape is not one of these (caller -> 400).
    """
    if isinstance(parsed, list):
        return parsed if all(isinstance(e, dict) for e in parsed) else None
    if isinstance(parsed, dict):
        events = parsed.get("events")
        if isinstance(events, list):
            return events if all(isinstance(e, dict) for e in events) else None
        # A bare single entry (must at least look like a hook entry).
        return [parsed]
    return None


@app.post("/hook-events", status_code=202)
@app.post("/hook-event", status_code=202)
async def receive_hook_events(
    request: Request,
    x_loom_hook_signature: Optional[str] = Header(None),
) -> dict:
    """Receive discipline-hook telemetry entries and persist them (project-
    attributed) into the telemetry substrate.

    `/hook-events` is the canonical (batch) route; `/hook-event` is an alias
    for a single entry. Both accept a single entry, a JSON array, or an
    `{"events": [...]}` envelope (see `_coerce_hook_entries`).

    Auth mirrors /skill-used: HMAC-SHA256 (bridge_hmac) verified on the RAW body
    BEFORE parsing, using the SEPARATE `LOOM_HOOK_BRIDGE_SECRET` in the
    `X-Loom-Hook-Signature: t=<unix>,v1=<hex>` header. Works self-host now and
    hosted later (same mechanism, per-deployment secret; tenant scoping happens
    at the write layer, not here).

    Status codes:
      - 202: accepted; body = {events_processed: N} (duplicates excluded)
      - 400: malformed JSON, or a body that is not entry/array/envelope
      - 401: HMAC missing / malformed / outside window / mismatch
      - 413: batch exceeds _MAX_HOOK_EVENTS
    """
    # Step 1: raw body before parsing (signature covers exact bytes).
    raw_body = (await request.body()).decode("utf-8")

    # Step 2: HMAC verify with the hook-events secret.
    try:
        bridge_hmac.verify_signature(
            raw_body, x_loom_hook_signature, secret_env=_HOOK_SECRET_ENV
        )
    except bridge_hmac.BridgeAuthError:
        raise HTTPException(401, "Invalid signature")

    # Step 3: parse + normalize to a list of entries.
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Malformed body: {e}")
    entries = _coerce_hook_entries(parsed)
    if entries is None:
        raise HTTPException(
            400,
            'Body must be a hook entry, a JSON array of entries, or '
            '{"events": [...]}.',
        )
    if not entries:
        return {"events_processed": 0}
    if len(entries) > _MAX_HOOK_EVENTS:
        raise HTTPException(
            413, f"Too many events in one request (max {_MAX_HOOK_EVENTS})."
        )

    # Step 4: map bare keys -> 005 columns and persist (RLS-scoped). The mapper
    # fails closed per-entry when no tenant resolves.
    return await hook_event_handler.apply_hook_events(entries)
