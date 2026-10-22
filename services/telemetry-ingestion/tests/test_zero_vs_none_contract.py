"""The 0-vs-None contract survives the auth layer (read_api.py docstring:
never seen → null/known:false; seen-but-0 → 0/true; active → n/true)."""
from __future__ import annotations

from .conftest import TEST_READ_KEY

ROUTE = "/telemetry/invocations?repo=some-repo&file_path=skills/x/SKILL.md"
HEADERS = {"Authorization": f"Bearer {TEST_READ_KEY}"}


def test_never_seen_returns_null_and_not_known(client, fake_db):
    fake_db.script({"known": False}, {"invocations": 0})
    r = client.get(ROUTE, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["invocations"] is None
    assert body["known"] is False
    assert body["artifact_ref"] == "some-repo#skills/x/SKILL.md"


def test_seen_but_zero_in_window_returns_zero_and_known(client, fake_db):
    fake_db.script({"known": True}, {"invocations": 0})
    body = client.get(ROUTE, headers=HEADERS).json()
    assert body["invocations"] == 0
    assert body["known"] is True


def test_active_returns_count(client, fake_db):
    fake_db.script({"known": True}, {"invocations": 7})
    body = client.get(ROUTE, headers=HEADERS).json()
    assert body["invocations"] == 7
    assert body["known"] is True
