"""loom-telemetry-ingestion — Telemetry Ingestion.

OTel receiver + enrichment layer. Persists skill-usage telemetry into the
loom-postgres read-substrate (infra/migrations/005_init_telemetry.sql),
RLS-scoped by tenant (Phase 0 task 3). Grafana Cloud stays an optional
export target, never a read dependency.

Endpoints:
  GET  /health          — Render liveness probe
  POST /skill-used      — bridge telemetry receiver (PR D); HMAC auth
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Header, HTTPException, Request

import bridge_hmac
import bridge_models
import db
import skill_usage_handler


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
