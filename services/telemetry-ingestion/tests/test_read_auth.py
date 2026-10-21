"""Read-route auth (telemetry_auth.require_read_tenant) through the app.

Adoption requirement 3: every /telemetry/* read requires authentication; no
anonymous path. Key → self-host tenant (fail closed); RS256 JWT → tenant_id
claim.
"""
from __future__ import annotations

from jose import jwt

from .conftest import TEST_READ_KEY, TEST_TENANT

READ_ROUTES = [
    "/telemetry/invocations?artifact_ref=repo%23path",
    "/telemetry/counts?group_by=tool_name",
    "/telemetry/signals",
    "/telemetry/episode/00000000-0000-0000-0000-000000000001",
]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_401_without_credentials_on_every_read_route(client, fake_db):
    for route in READ_ROUTES:
        r = client.get(route)
        assert r.status_code == 401, route
    assert fake_db.tenants == []  # nothing reached the DB layer


def test_401_wrong_key(client, fake_db):
    r = client.get(READ_ROUTES[0], headers=_bearer("not-the-key"))
    assert r.status_code == 401
    assert fake_db.tenants == []


def test_401_non_bearer_scheme(client):
    r = client.get(READ_ROUTES[0], headers={"Authorization": f"Basic {TEST_READ_KEY}"})
    assert r.status_code == 401


def test_read_key_resolves_self_host_tenant(client, fake_db):
    fake_db.script({"known": True}, {"invocations": 3})
    r = client.get(READ_ROUTES[0], headers=_bearer(TEST_READ_KEY))
    assert r.status_code == 200
    assert r.json()["invocations"] == 3
    assert fake_db.tenants == [TEST_TENANT]


def test_503_key_valid_but_tenant_unset(client, fake_db, monkeypatch):
    monkeypatch.delenv("SELF_HOST_TENANT_ID", raising=False)
    monkeypatch.delenv("LOOM_SELF_HOST_TENANT_ID", raising=False)
    r = client.get(READ_ROUTES[0], headers=_bearer(TEST_READ_KEY))
    assert r.status_code == 503
    assert fake_db.tenants == []


def test_jwt_resolves_claim_tenant(client, fake_db, rsa_keys, monkeypatch):
    private_pem, public_pem = rsa_keys
    monkeypatch.setenv("LOOM_JWT_PUBLIC_KEY", public_pem)
    token = jwt.encode(
        {"tenant_id": "11111111-2222-3333-4444-555555555555", "sub": "svc"},
        private_pem,
        algorithm="RS256",
    )
    fake_db.script([])  # counts: one fetchall
    r = client.get(READ_ROUTES[1], headers=_bearer(token))
    assert r.status_code == 200
    # Tenant isolation: the JWT's tenant drives RLS, not the self-host tenant.
    assert fake_db.tenants == ["11111111-2222-3333-4444-555555555555"]


def test_401_jwt_missing_claims(client, rsa_keys, monkeypatch):
    private_pem, public_pem = rsa_keys
    monkeypatch.setenv("LOOM_JWT_PUBLIC_KEY", public_pem)
    token = jwt.encode({"sub": "svc"}, private_pem, algorithm="RS256")
    r = client.get(READ_ROUTES[2], headers=_bearer(token))
    assert r.status_code == 401


def test_401_jwt_bad_signature(client, rsa_keys, monkeypatch):
    _, public_pem = rsa_keys
    monkeypatch.setenv("LOOM_JWT_PUBLIC_KEY", public_pem)
    r = client.get(READ_ROUTES[2], headers=_bearer("ey.not-a-real.jwt"))
    assert r.status_code == 401


def test_401_token_with_no_public_key_configured(client):
    # Not the read key, and no LOOM_JWT_PUBLIC_KEY set (conftest clears it):
    # must 401, never fall back to self-host.
    r = client.get(READ_ROUTES[2], headers=_bearer("some-jwt-looking-token"))
    assert r.status_code == 401
