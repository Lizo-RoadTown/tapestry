"""Tests for registry_client.py — the dynamic scan-target discovery that makes
the observer registry-driven.

Covers:
- repo_slug_from_url normalization (https / ssh / .git / trailing slash)
- merge_targets de-dup of the static core against discovered repos
- discover_dynamic_targets against a mocked project-registry (projects → repos)
- OBSERVER_JWT bearer header on registry calls; self-host = no header
- soft-fail to [] when the registry is unreachable / non-200
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

_SVC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC))

import registry_client  # noqa: E402
from config import (  # noqa: E402
    CONSUMING_REPO_DEFAULT_PATHS,
    AuthConfig,
    Endpoints,
    RegistryTarget,
)


_ENDPOINTS = Endpoints(
    candidate_registry_url="http://arch",
    telemetry_query_url="http://tel",
    memory_url="http://mem",
    project_registry_url="http://registry",
)
_AUTH_NO_JWT = AuthConfig()
_AUTH_WITH_JWT = AuthConfig(observer_jwt="tok-xyz")


# ---------------------------------------------------------------------------
# repo_slug_from_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/Lizo-RoadTown/hub", "Lizo-RoadTown/hub"),
        ("https://github.com/Lizo-RoadTown/hub.git", "Lizo-RoadTown/hub"),
        ("https://github.com/Lizo-RoadTown/hub/", "Lizo-RoadTown/hub"),
        ("git@github.com:Lizo-RoadTown/hub.git", "Lizo-RoadTown/hub"),
        ("http://github.com/Owner/Repo", "Owner/Repo"),
        ("", None),
        ("not-a-url", None),
        ("https://github.com/onlyone", None),
    ],
)
def test_repo_slug_from_url(url, expected):
    assert registry_client.repo_slug_from_url(url) == expected


# ---------------------------------------------------------------------------
# merge_targets
# ---------------------------------------------------------------------------


def test_merge_dedups_static_core_against_discovered():
    static = (
        RegistryTarget(repo="Lizo-RoadTown/tapestry", paths=("engine",)),
        RegistryTarget(repo="Lizo-RoadTown/claude-skills-marketplace", paths=("plugins",)),
    )
    dynamic = [
        # duplicate of the static core (different case) — must not be added twice
        RegistryTarget(repo="lizo-roadtown/TAPESTRY", paths=("skills",)),
        RegistryTarget(repo="Lizo-RoadTown/hub", paths=("skills",), project_id="p1"),
    ]
    merged = registry_client.merge_targets(static, dynamic)
    slugs = [t.repo for t in merged]
    assert slugs == [
        "Lizo-RoadTown/tapestry",
        "Lizo-RoadTown/claude-skills-marketplace",
        "Lizo-RoadTown/hub",
    ]


def test_merge_dedups_within_dynamic():
    static = (RegistryTarget(repo="Lizo-RoadTown/tapestry", paths=("engine",)),)
    dynamic = [
        RegistryTarget(repo="Lizo-RoadTown/hub", paths=("skills",)),
        RegistryTarget(repo="Lizo-RoadTown/hub", paths=("agents",)),  # dup slug
    ]
    merged = registry_client.merge_targets(static, dynamic)
    assert [t.repo for t in merged].count("Lizo-RoadTown/hub") == 1


# ---------------------------------------------------------------------------
# discover_dynamic_targets — mocked project-registry
# ---------------------------------------------------------------------------


def _resp(status: int, json_body) -> httpx.Response:
    req = httpx.Request("GET", "http://registry/x")
    return httpx.Response(status, json=json_body, request=req)


@pytest.mark.asyncio
async def test_discover_walks_projects_then_repos():
    projects = {"projects": [{"id": "proj-1", "kind": "dev"}, {"id": "proj-2", "kind": "dev"}]}
    repos_1 = {"repos": [{"url": "https://github.com/Lizo-RoadTown/hub", "default_branch": "main"}]}
    repos_2 = {"repos": [{"url": "https://github.com/Lizo-RoadTown/sde", "default_branch": "dev"}]}

    async def fake_get(url, *a, **k):
        if url.endswith("/projects"):
            return _resp(200, projects)
        if url.endswith("/projects/proj-1/repos"):
            return _resp(200, repos_1)
        if url.endswith("/projects/proj-2/repos"):
            return _resp(200, repos_2)
        return _resp(404, {})

    with patch("registry_client.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=fake_get)
        targets = await registry_client.discover_dynamic_targets(_ENDPOINTS, _AUTH_NO_JWT)

    by_repo = {t.repo: t for t in targets}
    assert set(by_repo) == {"Lizo-RoadTown/hub", "Lizo-RoadTown/sde"}
    assert by_repo["Lizo-RoadTown/hub"].project_id == "proj-1"
    assert by_repo["Lizo-RoadTown/hub"].branch == "main"
    assert by_repo["Lizo-RoadTown/sde"].branch == "dev"
    assert by_repo["Lizo-RoadTown/hub"].paths == CONSUMING_REPO_DEFAULT_PATHS


@pytest.mark.asyncio
async def test_discover_soft_fails_to_empty_on_projects_error():
    with patch("registry_client.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_resp(500, {"detail": "boom"}))
        targets = await registry_client.discover_dynamic_targets(_ENDPOINTS, _AUTH_NO_JWT)
    assert targets == []


@pytest.mark.asyncio
async def test_discover_soft_fails_to_empty_on_transport_error():
    with patch("registry_client.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        targets = await registry_client.discover_dynamic_targets(_ENDPOINTS, _AUTH_NO_JWT)
    assert targets == []


@pytest.mark.asyncio
async def test_discover_skips_unparseable_repo_urls():
    projects = {"projects": [{"id": "proj-1", "kind": "dev"}]}
    repos = {"repos": [
        {"url": "https://github.com/Lizo-RoadTown/hub", "default_branch": "main"},
        {"url": "garbage", "default_branch": "main"},
    ]}

    async def fake_get(url, *a, **k):
        if url.endswith("/projects"):
            return _resp(200, projects)
        return _resp(200, repos)

    with patch("registry_client.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=fake_get)
        targets = await registry_client.discover_dynamic_targets(_ENDPOINTS, _AUTH_NO_JWT)
    assert [t.repo for t in targets] == ["Lizo-RoadTown/hub"]


def test_headers_include_bearer_when_jwt_present():
    assert registry_client._headers(_AUTH_WITH_JWT)["Authorization"] == "Bearer tok-xyz"


def test_headers_omit_authorization_in_self_host():
    assert "Authorization" not in registry_client._headers(_AUTH_NO_JWT)
