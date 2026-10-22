"""Pytest setup for services/telemetry-ingestion tests.

Offline — no Postgres. db.tenant_transaction is replaced with a fake that
records the tenant each route resolved and serves scripted cursor results,
so the tests exercise the AUTH layer (telemetry_auth.py) and the 0-vs-None
read contract (read_api.py) end to end through the FastAPI app without a
database. Mirrors the offline-test convention of the other service suites
(services/project-observatory/tests/conftest.py).

Run from services/telemetry-ingestion/:

    pip install -r requirements.txt -r requirements-test.txt
    pytest tests/ -q
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

_SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))

import db  # noqa: E402

# The fleet's self-host tenant constant (auth_bridge.py / render.yaml).
TEST_TENANT = "1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8"
TEST_READ_KEY = "test-telemetry-read-key"


class FakeCursor:
    """Serves scripted results in call order. fetchone/fetchall both pop the
    same queue, so a test scripts results in the exact order the route
    consumes them."""

    def __init__(self, results: list[Any]):
        self._results = results
        self.executed: list[tuple[str, Any]] = []

    async def execute(self, sql: str, params: Any = None) -> None:
        self.executed.append((sql, params))

    async def fetchone(self) -> Any:
        return self._results.pop(0)

    async def fetchall(self) -> Any:
        return self._results.pop(0)

    async def __aenter__(self) -> "FakeCursor":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None


class FakeConn:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    def cursor(self) -> FakeCursor:
        return self._cursor


class FakeDB:
    """Stands in for db.tenant_transaction; records resolved tenants."""

    def __init__(self):
        self.tenants: list[str] = []
        self.results: list[Any] = []
        self.cursor = FakeCursor(self.results)

    def script(self, *results: Any) -> None:
        self.results.extend(results)

    @asynccontextmanager
    async def tenant_transaction(self, tenant_id: str):
        self.tenants.append(tenant_id)
        yield FakeConn(self.cursor)


@pytest.fixture()
def fake_db(monkeypatch) -> FakeDB:
    fake = FakeDB()
    monkeypatch.setattr(db, "tenant_transaction", fake.tenant_transaction)
    return fake


@pytest.fixture(scope="session")
def rsa_keys() -> tuple[str, str]:
    """(private_pem, public_pem) for RS256 test tokens."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


@pytest.fixture()
def client(monkeypatch, fake_db):
    """TestClient over the real app, offline, with self-host env configured."""
    monkeypatch.setenv("SELF_HOST_TENANT_ID", TEST_TENANT)
    monkeypatch.delenv("LOOM_SELF_HOST_TENANT_ID", raising=False)
    monkeypatch.setenv("TAPESTRY_TELEMETRY_READ_KEY", TEST_READ_KEY)
    monkeypatch.delenv("LOOM_JWT_PUBLIC_KEY", raising=False)

    from fastapi.testclient import TestClient

    import main

    return TestClient(main.app)
