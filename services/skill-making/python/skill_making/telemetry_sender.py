"""Telemetry callback sender — engine runtime -> the-loom Telemetry Ingestion.

The third message type in the bridge wire contract (after PromotionCandidate
and RegistrationAck). When a compiled skill is invoked by a real agent
turn, the engine emits a `TelemetryCallback` to
`LOOM_TELEMETRY_CALLBACK_URL` (defaults to
https://loom-telemetry-ingestion.onrender.com/skill-used).

Per the wire contract:
- Batching: up to 1000 events per request, flushed every 10s, whichever first
- Auth: same HMAC-SHA256 Stripe-style format as the other directions
  (`X-MakeSkills-Signature: t=<ts>,v1=<hex>` over `"<ts>.<body>"`)
- Privacy: structural metadata only — skill_id, tenant_id (opaque UUID),
  outcome, latency_ms, token_in/out. NO user message content, NO agent
  response content, NO PII.

This module exposes the SEND path. Wiring to runtime emission (the
collector that pushes events here from the agent loop) lives elsewhere
and is a future PR — for now this module is callable from a test or a
manual smoke.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from skill_making.hmac_verify import sign_payload

log = logging.getLogger("skill_making.telemetry_sender")

DEFAULT_URL = "https://loom-telemetry-ingestion.onrender.com/skill-used"

# Match ack_sender's retry policy: total worst-case ~7s.
RETRY_ATTEMPTS = 3
RETRY_BASE_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 10.0


class TelemetryEvent(BaseModel):
    """A single skill-invocation event. Privacy-bounded: structural
    metadata only (per wire-contract privacy note)."""

    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
    thread_id: str
    tenant_id: UUID  # source-side UUID (same convention as RegistrationAck.skill.tenant_id)
    invoked_at: str  # ISO 8601 UTC
    outcome: str  # "success" | "error" | "timeout"
    latency_ms: int
    tokens_in: int
    tokens_out: int
    model: str
    trigger_context: str  # short categorical tag — NOT the actual user message


class TelemetryBatch(BaseModel):
    """A batch of telemetry events — the POST body shape."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    batch_id: UUID = Field(default_factory=uuid4)
    events: list[TelemetryEvent]


class TelemetrySendError(Exception):
    """Raised when all retry attempts fail to deliver the batch."""


async def send_telemetry_batch(
    batch: TelemetryBatch,
    *,
    url: str | None = None,
    secret: str | None = None,
) -> None:
    """POST a TelemetryBatch to the-loom's telemetry-ingestion service.

    Same retry + auth shape as `send_registration_ack`. On all-retries-
    exhausted, raises `TelemetrySendError` — the caller (future runtime
    collector) decides whether to buffer locally + retry or drop oldest.
    """
    target_url = url or os.environ.get("LOOM_TELEMETRY_CALLBACK_URL") or DEFAULT_URL

    body_bytes = batch.model_dump_json().encode("utf-8")
    signature = sign_payload(body_bytes, secret=secret)
    headers = {
        "Content-Type": "application/json",
        "X-MakeSkills-Signature": signature,
    }

    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.post(target_url, content=body_bytes, headers=headers)
            if 200 <= resp.status_code < 300:
                log.info(
                    "telemetry batch POSTed (batch_id=%s events=%d status=%d)",
                    batch.batch_id, len(batch.events), resp.status_code,
                )
                return
            if 400 <= resp.status_code < 500:
                raise TelemetrySendError(
                    f"loom rejected batch with {resp.status_code}: "
                    f"{resp.text[:500]!r}"
                )
            last_exc = TelemetrySendError(
                f"loom returned 5xx on attempt {attempt}: "
                f"{resp.status_code} {resp.text[:200]!r}"
            )
        except (httpx.HTTPError, TelemetrySendError) as e:
            if isinstance(e, TelemetrySendError) and "loom rejected batch with 4" in str(e):
                raise
            last_exc = e

        if attempt < RETRY_ATTEMPTS:
            backoff = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            log.warning(
                "telemetry batch attempt %d/%d failed (%s); retrying in %.1fs",
                attempt, RETRY_ATTEMPTS, last_exc, backoff,
            )
            await asyncio.sleep(backoff)

    raise TelemetrySendError(
        f"all {RETRY_ATTEMPTS} telemetry batch attempts failed; last error: {last_exc}"
    )


def build_event(
    skill_id: UUID,
    thread_id: str,
    tenant_id: UUID,
    outcome: str,
    latency_ms: int,
    tokens_in: int,
    tokens_out: int,
    model: str,
    trigger_context: str = "agent_loop",
) -> TelemetryEvent:
    """Convenience constructor that stamps `invoked_at` to UTC now."""
    return TelemetryEvent(
        skill_id=skill_id,
        thread_id=thread_id,
        tenant_id=tenant_id,
        invoked_at=datetime.now(timezone.utc).isoformat(),
        outcome=outcome,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        model=model,
        trigger_context=trigger_context,
    )
