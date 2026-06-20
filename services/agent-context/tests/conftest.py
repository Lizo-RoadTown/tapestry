"""
Pytest fixtures for services/agent-context tests.

Sets up RSA keypair (for RS256 JWT minting in tests), env vars, and an
httpx.AsyncClient + LifespanManager wired to the FastAPI app.

Run from services/agent-context/:

    cd services/agent-context
    pip install -r requirements.txt -r requirements-test.txt
    pytest tests/ -v

The tests do NOT require a real Postgres — pure ASGI in-process, with
storage layer calls mocked or routed to a test DB depending on the test.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import AsyncIterator

import pytest


# Generate a test RSA keypair BEFORE importing the app. The app's auth
# code reads LOOM_JWT_PUBLIC_KEY at runtime (lazy in auth_bridge.py;
# eager in main._resolve_tenant_for_rest via os.environ.get) — both
# paths pick up whatever we set here.
def _generate_test_keypair() -> tuple[str, str]:
    """Generate a fresh RSA-4096 keypair in PEM format. Returns (private, public)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return private_pem, public_pem


# Session-scoped: generate the keypair ONCE per pytest session. Sets env
# vars BEFORE the app module imports so auth_bridge picks up the public key.
TEST_PRIVATE_KEY, TEST_PUBLIC_KEY = _generate_test_keypair()
os.environ["LOOM_JWT_PUBLIC_KEY"] = TEST_PUBLIC_KEY


# Add services/agent-context/ to sys.path so `import main` works when
# pytest is invoked from the repo root.
_AGENT_CONTEXT_DIR = Path(__file__).resolve().parent.parent
if str(_AGENT_CONTEXT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_CONTEXT_DIR))


# Helper available to all tests — mints an RS256 JWT the production
# code path will accept (matches auth_bridge.LoomTokenVerifier +
# main._resolve_tenant_for_rest verification logic).
def mint_test_jwt(tenant_id: str, sub: str = "test-user", expires_in_seconds: int = 3600) -> str:
    """Mint an RS256 JWT signed with the test private key. The public
    counterpart is in LOOM_JWT_PUBLIC_KEY env var, so the production
    code accepts it as if minted by a real loom-self-host issuer."""
    import time as _time
    from jose import jwt
    now = int(_time.time())
    return jwt.encode(
        {
            "sub": sub,
            "tenant_id": tenant_id,
            "iat": now,
            "exp": now + expires_in_seconds,
            "iss": "loom-self-host-test",
        },
        TEST_PRIVATE_KEY,
        algorithm="RS256",
    )


@pytest.fixture
def jwt_minter():
    """Fixture exposing the test JWT minter to test functions."""
    return mint_test_jwt


@pytest.fixture
def test_private_key() -> str:
    """The RSA private key matching LOOM_JWT_PUBLIC_KEY — for tests that
    need to mint malformed tokens (missing claims, wrong algorithm, etc.)
    that jwt_minter() doesn't cover."""
    return TEST_PRIVATE_KEY
