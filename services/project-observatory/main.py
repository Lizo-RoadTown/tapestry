"""loom-project-observatory — the runtime-observer's home.

Phase 1 of the observer-capacity build (docs/plans/2026-08-23-observer-
capacity-build-sequence.md). project-observatory reads the Phase-0 telemetry
substrate (infra/migrations/005_init_telemetry.sql), computes the observation
signals ADR-0001 names — hot_path / orphaned / degrading / blind — over a
window, and writes them to observation_signals
(infra/migrations/006_init_observation_signals.sql), which the read layer
serves. A Render cron triggers the compute pass; this process serves health +
(later) the read endpoint.

This is the SCAFFOLD (Phase 1 task 2): the DB pool (db.py), thresholds
(config.py), the self-host tenant resolver (tenant.py), and this /health app.
The signal computation (task 3), the materialization entrypoint (task 4), and
the read endpoint (task 5) are NOT here yet.

Endpoints:
  GET /health                    — Render liveness probe

Later (not this scaffold):
  GET /signals                   — read layer over observation_signals (task 5)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

import db


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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "loom-project-observatory"}
