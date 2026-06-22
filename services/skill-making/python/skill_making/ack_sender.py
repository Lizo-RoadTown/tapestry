"""Registration ack sender — engine -> the-loom.

After a bridge-delivered candidate compiles (or fails), the engine
POSTs a `RegistrationAck` back to the-loom's Architecture Registry so
the-loom can update its candidate row from `promotion_requested` to
`promoted` (or `rejected`).

Per wire contract section 2 + Loom-agent's bridge-complete memo:
  - Target: `LOOM_REGISTRATION_ACK_URL` env (defaults to
    https://loom-architecture-registry.onrender.com/skill-registered)
  - Auth: HMAC-SHA256, header `X-MakeSkills-Signature`,
    Stripe-style `t=<unix_seconds>,v1=<sha256_hex>` over `"<ts>.<body>"`
  - Body shape: `RegistrationAck` pydantic model

Retry strategy: 3 attempts with exponential backoff (1s, 2s, 4s). On
final failure, log loudly — the engine state stays at `compiled` so a
future repair script could re-ack from the `promoted_skills` row.
Loom-agent's memo says "the-loom dedups by promotion_id" so re-acks
are safe.
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

from skill_making.hmac_verify import sign_payload
from skill_making.models import RegistrationAck

log = logging.getLogger("skill_making.ack_sender")

DEFAULT_ACK_URL = "https://loom-architecture-registry.onrender.com/skill-registered"

# Retry tuning. Total worst-case wait = 1 + 2 + 4 = 7s before giving up.
# Conservative; the engine's request handler is already past 202 by the
# time this runs (background task).
RETRY_ATTEMPTS = 3
RETRY_BASE_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 10.0


class AckSendError(Exception):
    """Raised when all retry attempts fail. The compile_worker logs and
    continues — the engine state is the source of truth; the-loom can
    pull or wait for a repair re-ack."""


async def send_registration_ack(
    ack: RegistrationAck,
    *,
    url: str | None = None,
    secret: str | None = None,
) -> None:
    """POST a RegistrationAck to the-loom. Retries on transient HTTP
    failure (5xx, connection error, timeout). Does NOT retry on 4xx —
    those indicate a contract bug, not a transient blip.

    On success, returns None silently. On all-retries-exhausted, raises
    AckSendError with the last error captured.
    """
    target_url = url or os.environ.get("LOOM_REGISTRATION_ACK_URL") or DEFAULT_ACK_URL

    body_bytes = ack.model_dump_json().encode("utf-8")
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
                    "registration ack POSTed (promotion_id=%s outcome=%s status=%d)",
                    ack.promotion_id, ack.outcome.value, resp.status_code,
                )
                return
            if 400 <= resp.status_code < 500:
                # Contract bug, not transient — don't retry.
                raise AckSendError(
                    f"loom rejected ack with {resp.status_code}: {resp.text[:500]!r}"
                )
            last_exc = AckSendError(
                f"loom returned 5xx on attempt {attempt}: {resp.status_code} {resp.text[:200]!r}"
            )
        except (httpx.HTTPError, AckSendError) as e:
            if isinstance(e, AckSendError) and "loom rejected ack with 4" in str(e):
                # Re-raise immediately on 4xx; no point retrying.
                raise
            last_exc = e

        if attempt < RETRY_ATTEMPTS:
            backoff = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            log.warning(
                "registration ack attempt %d/%d failed (%s); retrying in %.1fs",
                attempt, RETRY_ATTEMPTS, last_exc, backoff,
            )
            await asyncio.sleep(backoff)

    raise AckSendError(
        f"all {RETRY_ATTEMPTS} ack POST attempts failed; last error: {last_exc}"
    )
