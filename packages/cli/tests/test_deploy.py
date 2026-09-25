"""Tests for tapestry_cli.deploy.

Pure payload/spec helpers are tested directly; the Render API is never hit —
_request is monkeypatched (and asserted NOT called on --dry-run).

Run from packages/cli/:  python -m pytest tests/ -q
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tapestry_cli import deploy  # noqa: E402


def _args(**overrides) -> argparse.Namespace:
    """A Namespace with every deploy arg defaulted (as argparse would)."""
    base = dict(
        spec=deploy.DEFAULT_SPEC_PATH, name=None, type=None, plan=None, region=None,
        branch=None, root=None, runtime=None, build=None, start=None,
        health_check_path=None, schedule=None, repo=None, owner_id=None,
        owner_name=None, env_group=None, auto_deploy=None, set=None, secret=None,
        api_key=None, dry_run=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# _build_service_payload
# ---------------------------------------------------------------------------
def test_web_payload_shape(monkeypatch):
    monkeypatch.setattr(deploy, "_resolve_env_vars", lambda spec: ([], []))
    spec = {
        "name": "svc", "type": "web", "buildCommand": "pip install -r r.txt",
        "startCommand": "uvicorn main:app", "healthCheckPath": "/health",
        "_envVars": {}, "_secretNames": [],
    }
    p = deploy._build_service_payload(spec, "https://github.com/o/r", "own-1")
    assert p["type"] == "web_service"          # friendly alias mapped
    assert p["name"] == "svc"
    assert p["ownerId"] == "own-1"
    assert p["repo"] == "https://github.com/o/r"
    assert p["branch"] == "main"               # default
    assert p["autoDeploy"] == "yes"            # default
    # build/start live UNDER serviceDetails.envSpecificDetails, not top-level
    esd = p["serviceDetails"]["envSpecificDetails"]
    assert esd["buildCommand"] == "pip install -r r.txt"
    assert esd["startCommand"] == "uvicorn main:app"
    assert p["serviceDetails"]["healthCheckPath"] == "/health"
    assert p["serviceDetails"]["plan"] == "starter"
    assert "schedule" not in p["serviceDetails"]


def test_cron_payload_shape():
    spec = {
        "name": "cron", "type": "cron", "buildCommand": "b", "startCommand": "s",
        "schedule": "0 */6 * * *", "_envVars": {}, "_secretNames": [],
    }
    p = deploy._build_service_payload(spec, "https://github.com/o/r", "own-1")
    assert p["type"] == "cron_job"
    assert p["serviceDetails"]["schedule"] == "0 */6 * * *"
    assert "healthCheckPath" not in p["serviceDetails"]


def test_payload_requires_build_and_start():
    spec = {"name": "svc", "type": "web", "_envVars": {}, "_secretNames": []}
    with pytest.raises(RuntimeError, match="buildCommand and startCommand"):
        deploy._build_service_payload(spec, "repo", "own-1")


def test_cron_requires_schedule():
    spec = {"name": "c", "type": "cron", "buildCommand": "b", "startCommand": "s",
            "_envVars": {}, "_secretNames": []}
    with pytest.raises(RuntimeError, match="schedule"):
        deploy._build_service_payload(spec, "repo", "own-1")


def test_invalid_type_rejected():
    spec = {"name": "s", "type": "banana", "buildCommand": "b", "startCommand": "s",
            "_envVars": {}, "_secretNames": []}
    with pytest.raises(RuntimeError, match="invalid service type"):
        deploy._build_service_payload(spec, "repo", "own-1")


# ---------------------------------------------------------------------------
# _load_spec / _resolve_env_vars
# ---------------------------------------------------------------------------
def test_load_spec_flags_override_file(tmp_path):
    (tmp_path / "deploy").mkdir()
    (tmp_path / "deploy" / "render-service.json").write_text(
        '{"name": "from-file", "plan": "free", "envVars": [{"key": "A", "value": "1"}]}',
        encoding="utf-8",
    )
    args = _args(name="from-flag", set=["B=2"], secret=["TOK"])
    spec = deploy._load_spec(tmp_path, args)
    assert spec["name"] == "from-flag"       # flag wins over file
    assert spec["plan"] == "free"            # file value preserved
    assert spec["_envVars"] == {"A": "1", "B": "2"}
    assert spec["_secretNames"] == ["TOK"]


def test_load_spec_bad_set_pair(tmp_path):
    with pytest.raises(RuntimeError, match="KEY=VALUE"):
        deploy._load_spec(tmp_path, _args(name="x", set=["NOEQUALS"]))


def test_resolve_env_vars_reports_missing(monkeypatch):
    monkeypatch.setenv("PRESENT", "yes")
    monkeypatch.delenv("ABSENT", raising=False)
    spec = {"_envVars": {"PLAIN": "p"}, "_secretNames": ["PRESENT", "ABSENT"]}
    env_vars, missing = deploy._resolve_env_vars(spec)
    keys = {ev["key"] for ev in env_vars}
    assert "PLAIN" in keys and "PRESENT" in keys and "ABSENT" not in keys
    assert missing == ["ABSENT"]


# ---------------------------------------------------------------------------
# _find_service_by_name — exact-match over the wrapper-array response
# ---------------------------------------------------------------------------
def test_find_service_exact_match(monkeypatch):
    rows = [
        {"service": {"name": "svc-other", "id": "a"}, "cursor": "c1"},
        {"service": {"name": "svc", "id": "b"}, "cursor": "c2"},
    ]
    monkeypatch.setattr(deploy, "_request", lambda *a, **k: rows)
    assert deploy._find_service_by_name("key", "svc")["id"] == "b"
    monkeypatch.setattr(deploy, "_request", lambda *a, **k: [])
    assert deploy._find_service_by_name("key", "svc") is None


# ---------------------------------------------------------------------------
# run(): --dry-run makes NO network call and needs no API key
# ---------------------------------------------------------------------------
def test_dry_run_makes_no_network_call(tmp_path, monkeypatch, capsys):
    def _boom(*a, **k):
        raise AssertionError("network call during --dry-run")
    monkeypatch.setattr(deploy, "_request", _boom)
    monkeypatch.chdir(tmp_path)
    rc = deploy.run(_args(
        name="dry-svc", type="web", build="pip install -e .",
        start="python -m x", repo="https://github.com/o/r", dry_run=True,
    ))
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "web_service" in out
    assert "own-DRYRUN" in out


def test_missing_name_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = deploy.run(_args(repo="https://github.com/o/r", dry_run=True))
    assert rc == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
