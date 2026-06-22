"""Pin the Stripe-style HMAC header format invariants.

Catches the failure mode of `lesson_hmac_format_mismatch_pr_70_2026_06_12`:
silent drift between the spec and the implementation. If any of these
break, both sides of the bridge need to coordinate the schema change.
"""
from __future__ import annotations

import hmac
import time
from hashlib import sha256

import pytest

from skill_making.hmac_verify import (
    HmacVerificationError,
    sign_payload,
    verify_signature,
)


SECRET = "test-secret-3a04e875"


def _make_signature(body: bytes, ts: int, secret: str = SECRET) -> str:
    signed = f"{ts}.".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), signed, sha256).hexdigest()
    return f"t={ts},v1={digest}"


def test_valid_signature_passes():
    body = b'{"hello":"world"}'
    ts = int(time.time())
    sig = _make_signature(body, ts)
    # Should NOT raise.
    verify_signature(body, sig, secret=SECRET)


def test_missing_t_field_rejected():
    body = b"abc"
    with pytest.raises(HmacVerificationError, match="missing 't='"):
        verify_signature(body, "v1=deadbeef", secret=SECRET)


def test_missing_v1_field_rejected():
    body = b"abc"
    with pytest.raises(HmacVerificationError, match="missing 'v1='"):
        verify_signature(body, "t=12345", secret=SECRET)


def test_malformed_t_field_rejected():
    body = b"abc"
    with pytest.raises(HmacVerificationError, match="not an integer"):
        verify_signature(body, "t=notnumeric,v1=deadbeef", secret=SECRET)


def test_timestamp_outside_window_rejected():
    body = b"abc"
    ts = int(time.time()) - 1000  # 1000s in the past — outside ±300s window
    sig = _make_signature(body, ts)
    with pytest.raises(HmacVerificationError, match="outside"):
        verify_signature(body, sig, secret=SECRET)


def test_timestamp_at_window_edge_accepted():
    body = b"abc"
    now = int(time.time())
    ts = now - 295  # just inside ±300s
    sig = _make_signature(body, ts)
    verify_signature(body, sig, secret=SECRET, now=now)


def test_wrong_digest_rejected():
    body = b"abc"
    ts = int(time.time())
    bad_sig = f"t={ts},v1=deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    with pytest.raises(HmacVerificationError, match="mismatch"):
        verify_signature(body, bad_sig, secret=SECRET)


def test_secret_mismatch_rejected():
    body = b"abc"
    ts = int(time.time())
    sig = _make_signature(body, ts, secret="other-secret")
    with pytest.raises(HmacVerificationError, match="mismatch"):
        verify_signature(body, sig, secret=SECRET)


def test_missing_secret_env_var_rejected(monkeypatch):
    monkeypatch.delenv("LOOM_SKILL_BRIDGE_SECRET", raising=False)
    body = b"abc"
    ts = int(time.time())
    sig = _make_signature(body, ts)
    with pytest.raises(HmacVerificationError, match="LOOM_SKILL_BRIDGE_SECRET"):
        verify_signature(body, sig)


def test_sign_payload_round_trip():
    body = b'{"promotion_id":"abc"}'
    sig = sign_payload(body, secret=SECRET)
    assert sig.startswith("t=")
    assert ",v1=" in sig
    # Round-trip: sign + verify with the same secret.
    verify_signature(body, sig, secret=SECRET)


def test_signed_payload_includes_timestamp():
    """Pin: HMAC payload MUST be `<ts>.<body>`, not just `<body>`.

    If this changes, both sides need a coordinated update — this is the
    spec drift class lessons described.
    """
    body = b"abc"
    ts = 1700000000
    sig = sign_payload(body, secret=SECRET, ts=ts)
    # Reconstruct the expected hex independently:
    expected_payload = b"1700000000.abc"
    expected_digest = hmac.new(SECRET.encode("utf-8"), expected_payload, sha256).hexdigest()
    assert sig == f"t={ts},v1={expected_digest}"
