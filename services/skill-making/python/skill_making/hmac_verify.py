"""HMAC-SHA256 verification for bridge POSTs.

Per the wire contract at `docs/proposals/2026-05-25-skill-making-bridge.md`
+ Loom-agent's bridge-complete memo
(`loom_agent_bridge_complete_status_and_secret_2026_06_12_evening`):

The-loom signs the POST with header `X-Loom-Signature` in Stripe-style
format:

    X-Loom-Signature: t=<unix_seconds>,v1=<sha256_hex>

Where `<sha256_hex>` is `HMAC-SHA256(LOOM_SKILL_BRIDGE_SECRET, "<t>.<body>").hexdigest()`.

The receiver:
  1. Parses the `t` and `v1` fields from the header
  2. Verifies the timestamp is within a ±5 minute window (replay protection)
  3. Recomputes the HMAC over the `t.body` payload
  4. Compares the digests via `hmac.compare_digest` (constant-time)

The timestamp binding prevents replay attacks beyond the freshness
window — even if an attacker captures a valid signed POST, they can't
re-use it after 5 minutes.

The matching outbound format for ack callbacks engine -> loom uses
header `X-MakeSkills-Signature` with the same scheme (built in PR B's
ack_sender.py).
"""
from __future__ import annotations

import hmac
import os
import time
from hashlib import sha256

# ±5 minute timestamp window for replay protection. Matches loom side
# (per their PR #21 implementation). Tightening reduces replay window;
# loosening tolerates clock drift between Render services.
WINDOW_SECONDS = 300


class HmacVerificationError(Exception):
    """Raised when verification fails for any reason. The receiver
    translates this to a 401 response — no candidate row written,
    no audit-log entry, no further work."""


def _parse_signature_header(header_value: str) -> tuple[int, str]:
    """Parse `t=<unix_seconds>,v1=<sha256_hex>` into (ts, hex).

    Raises HmacVerificationError on any malformed input. Tolerates
    whitespace around the `,` separator.
    """
    try:
        parts: dict[str, str] = {}
        for raw_part in header_value.split(","):
            k, _, v = raw_part.strip().partition("=")
            if not _ or not k or not v:
                raise ValueError(f"malformed part: {raw_part!r}")
            parts[k] = v
    except ValueError as e:
        raise HmacVerificationError(f"malformed signature header: {e}") from e

    if "t" not in parts:
        raise HmacVerificationError("signature header missing 't=' (timestamp)")
    if "v1" not in parts:
        raise HmacVerificationError("signature header missing 'v1=' (sha256 hex)")

    try:
        ts = int(parts["t"])
    except ValueError as e:
        raise HmacVerificationError(f"signature 't' is not an integer: {e}") from e

    return ts, parts["v1"]


def verify_signature(
    raw_body: bytes,
    signature_header: str,
    *,
    secret: str | None = None,
    now: int | None = None,
) -> None:
    """Verify a Stripe-style `t=<ts>,v1=<hex>` signature on `raw_body`.

    Args:
        raw_body: The exact bytes of the POST body. Must be the bytes
            received over the wire — re-serializing pydantic objects
            would change byte ordering and break verification.
        signature_header: The `X-Loom-Signature` header value, formatted
            as `t=<unix_seconds>,v1=<sha256_hex>`.
        secret: The shared HMAC secret. Defaults to the
            `LOOM_SKILL_BRIDGE_SECRET` env var.
        now: Override the current time for tests. Defaults to
            `int(time.time())`.

    Raises:
        HmacVerificationError: If the secret isn't configured, the
            header is missing/malformed, the timestamp is outside the
            window, or the digests don't match.
    """
    if secret is None:
        secret = os.environ.get("LOOM_SKILL_BRIDGE_SECRET")
    if not secret:
        raise HmacVerificationError(
            "LOOM_SKILL_BRIDGE_SECRET env var not set on the engine side; "
            "cannot verify bridge POSTs."
        )
    if not signature_header:
        raise HmacVerificationError("missing X-Loom-Signature header")

    ts, provided_hex = _parse_signature_header(signature_header)

    # Timestamp window check. Replay protection: even with a valid
    # signature, a captured POST is rejected after WINDOW_SECONDS.
    current = int(time.time()) if now is None else now
    if abs(current - ts) > WINDOW_SECONDS:
        raise HmacVerificationError(
            f"signature timestamp outside ±{WINDOW_SECONDS}s window "
            f"(ts={ts}, now={current}, drift={current - ts}s)"
        )

    # HMAC over "<ts>.<body>". The ts is included in the signed payload
    # so an attacker can't bump the timestamp inside the header without
    # invalidating the digest.
    signed_payload = f"{ts}.".encode("utf-8") + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_payload, sha256).hexdigest()
    if not hmac.compare_digest(expected, provided_hex):
        raise HmacVerificationError("signature mismatch")


def sign_payload(raw_body: bytes, *, secret: str | None = None, ts: int | None = None) -> str:
    """Produce a Stripe-style `t=<ts>,v1=<hex>` signature for `raw_body`.

    Used by the verification script + by PR B's ack_sender for outbound
    POSTs to loom (which use the same scheme under `X-MakeSkills-Signature`).
    """
    if secret is None:
        secret = os.environ.get("LOOM_SKILL_BRIDGE_SECRET")
    if not secret:
        raise HmacVerificationError(
            "LOOM_SKILL_BRIDGE_SECRET env var not set; cannot sign."
        )
    if ts is None:
        ts = int(time.time())
    signed_payload = f"{ts}.".encode("utf-8") + raw_body
    digest = hmac.new(secret.encode("utf-8"), signed_payload, sha256).hexdigest()
    return f"t={ts},v1={digest}"
