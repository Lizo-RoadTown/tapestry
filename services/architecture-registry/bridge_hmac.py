"""HMAC-SHA256 signing + verification for the skill-making bridge.

Per the spec at Make_Skills `docs/proposals/2026-05-25-skill-making-bridge.md`
§"Auth, idempotency, replay protection":

- HMAC-SHA256 over `timestamp + body`
- ±5 minute timestamp window for replay protection
- Shared secret `LOOM_SKILL_BRIDGE_SECRET` in env on both sides
- Outgoing requests from the-loom sign with X-Loom-Signature header
- Incoming requests from engine carry X-MakeSkills-Signature header
- Both headers carry the same shape: signature value + a timestamp

## Header format

`X-Loom-Signature: t=<unix_ts>,v1=<hex_hmac>`
`X-MakeSkills-Signature: t=<unix_ts>,v1=<hex_hmac>`

The `v1=` prefix is a version marker for future algorithm changes (e.g.,
v2 might use HMAC-SHA512). Today we only emit + accept v1.

## Why timestamp inside the header AND inside the signed payload

Replay protection requires the timestamp to be UN-modifiable by an
attacker. If the timestamp were only inside the JSON body, an attacker
could re-send an old valid payload with a fresh timestamp in the header.
By signing `timestamp + body` together, any modification to the timestamp
invalidates the signature.

## Dual-mode

This module is mode-agnostic. The shared secret `LOOM_SKILL_BRIDGE_SECRET`
is the same value in both self-host and hosted-multitenant deployments
(per-deployment, not per-tenant). Tenant scoping happens at the message-
body layer via `tenant_id` (see bridge_models.py); the HMAC layer only
authenticates the SENDER (the-loom OR the engine), not the tenant.

## What this module does NOT do

- Construct request bodies (callers serialize Pydantic models to JSON
  via `model.model_dump_json()` before signing)
- Make HTTP requests (callers POST the signed body via httpx/requests)
- Receive HTTP requests (callers verify the signature on the raw body
  they received)
- Manage the shared secret beyond reading from env

## Failure modes

- `BridgeAuthError` raised on: missing header, malformed header, bad
  timestamp, signature mismatch, timestamp outside window
- Caller maps to HTTP 401 (per spec §"Failure modes" table)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time


class BridgeAuthError(Exception):
    """Raised by verify_signature() on any auth failure. Caller maps to HTTP 401."""


# ±5 minute replay window per the spec.
TIMESTAMP_WINDOW_SECONDS = 5 * 60


def _get_secret() -> bytes:
    """Read LOOM_SKILL_BRIDGE_SECRET at call time so env updates take effect
    in tests + redeploys without restart. Raises RuntimeError if unset —
    that's a configuration error worth surfacing loud.
    """
    raw = os.environ.get("LOOM_SKILL_BRIDGE_SECRET")
    if not raw:
        raise RuntimeError(
            "LOOM_SKILL_BRIDGE_SECRET is unset. Set the shared secret in env "
            "on both the-loom AND Make_Skills (same value)."
        )
    return raw.encode("utf-8")


def _now_unix() -> int:
    """Wallclock seconds since epoch. Separate function so tests can monkeypatch."""
    return int(time.time())


def sign(body: str, *, timestamp: int | None = None) -> str:
    """Produce the X-Loom-Signature / X-MakeSkills-Signature header value
    for the given JSON body string.

    Returns the literal header value: 't=<unix>,v1=<hex>'.

    Caller is responsible for serializing the request body to JSON FIRST
    (Pydantic: `model.model_dump_json(exclude_none=False)`) and passing
    the EXACT string that will be the request body. Any whitespace
    difference between signed string and request body invalidates the
    signature on the verifier side.
    """
    ts = timestamp if timestamp is not None else _now_unix()
    secret = _get_secret()
    payload = f"{ts}.{body}".encode("utf-8")
    digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def verify_signature(body: str, header_value: str | None) -> None:
    """Verify the signature on an incoming request. Raises BridgeAuthError
    on any failure; returns None on success.

    Caller passes the raw request body (the bytes/string as received,
    BEFORE any JSON parsing or normalization). Re-serialization of
    parsed JSON can drift in field order or whitespace and break the
    signature.

    The verification:

    1. Header is present and well-formed: `t=<int>,v1=<hex>`
    2. Timestamp is within ±TIMESTAMP_WINDOW_SECONDS of now (replay protection)
    3. HMAC-SHA256 of `f"{ts}.{body}"` matches the v1 digest
    4. Constant-time comparison via hmac.compare_digest (timing-attack safe)
    """
    if not header_value:
        raise BridgeAuthError("Missing signature header")

    ts, sig = _parse_header(header_value)
    _check_timestamp(ts)

    secret = _get_secret()
    payload = f"{ts}.{body}".encode("utf-8")
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise BridgeAuthError("Signature mismatch")


def _parse_header(header_value: str) -> tuple[int, str]:
    """Split 't=<int>,v1=<hex>' into (timestamp, hex_digest). Raises
    BridgeAuthError on malformed input."""
    parts = header_value.split(",")
    if len(parts) != 2:
        raise BridgeAuthError(
            "Malformed signature header (expected 't=<int>,v1=<hex>')"
        )

    ts_part, sig_part = parts[0].strip(), parts[1].strip()
    if not ts_part.startswith("t=") or not sig_part.startswith("v1="):
        raise BridgeAuthError(
            "Malformed signature header (expected 't=<int>,v1=<hex>')"
        )

    try:
        ts = int(ts_part[2:])
    except ValueError:
        raise BridgeAuthError("Timestamp is not an integer")

    sig = sig_part[3:]
    # SHA-256 hex digest is always 64 chars
    if len(sig) != 64 or not all(c in "0123456789abcdef" for c in sig.lower()):
        raise BridgeAuthError("Signature is not a SHA-256 hex digest")

    return ts, sig


def _check_timestamp(ts: int) -> None:
    """Enforce the ±5 minute replay window. Raises BridgeAuthError if outside."""
    now = _now_unix()
    delta = abs(now - ts)
    if delta > TIMESTAMP_WINDOW_SECONDS:
        raise BridgeAuthError(
            f"Timestamp outside ±{TIMESTAMP_WINDOW_SECONDS}s window "
            f"(delta={delta}s)"
        )
