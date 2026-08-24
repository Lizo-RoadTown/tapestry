"""loom-project-observatory — the runtime-observer's home.

Phase 1 of the observer-capacity build (docs/plans/2026-08-23-observer-
capacity-build-sequence.md). project-observatory reads the Phase-0 telemetry
substrate (infra/migrations/005_init_telemetry.sql), computes the observation
signals ADR-0001 names — hot_path / orphaned / degrading / blind — over a
window, and writes them to observation_signals
(infra/migrations/006_init_observation_signals.sql), which the read layer
serves. A Render cron triggers the compute pass; this process serves health +
(later) the read endpoint.

The DB pool (db.py), thresholds (config.py), the self-host tenant resolver
(tenant.py), the signal computation (task 3, signals.py), the write path
(task 4, writes.py), and the read endpoint (task 5, read_api.py) are all
present. The read routes live in read_api.py and read the 006 substrate inside
db.tenant_transaction so RLS scopes every query — mirroring how
services/telemetry-ingestion/main.py includes its read_api.

Endpoints:
  GET /health                    — Render liveness probe
  GET /observations/signals      — latest observation-signals snapshot (task 5)
  GET /observations/signals/runs — snapshot history (task 5)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

import db
import read_api


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Close the DB pool on shutdown. The pool opens lazily on the first
    read/write (db.get_pool), so there is nothing to force on startup — just
    drain it cleanly before the Render process exits. Mirrors
    services/telemetry-ingestion/main.py:lifespan.
    """
    yield
    await db.close_pool()


app = FastAPI(title="loom-project-observatory", version="0.1.0", lifespan=lifespan)

# Observation-signals READ API (Phase 1 task 5) — GET /observations/signals[/runs].
# Each route resolves the self-host tenant and reads inside db.tenant_transaction
# so the 006 RLS policies scope every query. Mirrors telemetry-ingestion/main.py.
app.include_router(read_api.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "loom-project-observatory"}
