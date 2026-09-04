"""Tests for memory_client.py — the self-observer's REST client for
loom-agent-context /v1/write + /v1/read.

Covers the timeout/retry contract from
tapestry/docs/research/2026-06-18-outside-review-runtime-observation-followup.md §5.5.2:
- Default 30s timeout
- One retry after 5s on transport error OR 5xx response
- No retry on 4xx (contract failure — surfaces immediately)
- 404 on read returns None (not a failure)
- Persistent failures log + return False (write) or None (read); don't raise
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

_SVC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC))

from config import AuthConfig, Endpoints  # noqa: E402
from memory_client import MemoryClient  # noqa: E402


_ENDPOINTS = Endpoints(
    candidate_registry_url="http://test-arch",
    telemetry_query_url="http://test-tel",
    memory_url="http://test-mem",
)
_AUTH_NO_JWT = AuthConfig()
_AUTH_WITH_JWT = AuthConfig(observer_jwt="tok-abc")


def _mock_response(status: int, json_body=None) -> httpx.Response:
    """Build a real httpx.Response with no underlying request — for stubbing."""
    req = httpx.Request("POST", "http://test-mem/v1/write")
    return httpx.Response(status, json=json_body or {}, request=req)


# ---------------------------------------------------------------------------
# write_synthesis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_synthesis_success_returns_true():
    client = MemoryClient(_ENDPOINTS, _AUTH_NO_JWT)
    with patch("memory_client.httpx.AsyncClient") as mock_async_client:
        instance = mock_async_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=_mock_response(200, {"ok": True}))

        ok = await client.write_synthesis(name="x", content="body")
        assert ok is True
        instance.post.assert_called_once()


@pytest.mark.asyncio
async def test_write_synthesis_4xx_no_retry_returns_false():
    """4xx is a contract failure — surface immediately, do NOT retry."""
    client = MemoryClient(_ENDPOINTS, _AUTH_NO_JWT)
    with patch("memory_client.httpx.AsyncClient") as mock_async_client:
        instance = mock_async_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=_mock_response(422, {"detail": "bad"}))

        ok = await client.write_synthesis(name="x", content="body")
        assert ok is False
        assert instance.post.call_count == 1, "4xx must not retry"


@pytest.mark.asyncio
async def test_write_synthesis_5xx_retries_once():
    """5xx is transient — one retry, then surface."""
    client = MemoryClient(_ENDPOINTS, _AUTH_NO_JWT)
    with patch("memory_client.httpx.AsyncClient") as mock_async_client, \
            patch("memory_client.asyncio.sleep", new=AsyncMock()) as mock_sleep:
        instance = mock_async_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(side_effect=[
            _mock_response(503, {}),
            _mock_response(503, {}),
        ])

        ok = await client.write_synthesis(name="x", content="body")
        assert ok is False
        assert instance.post.call_count == 2, "5xx must retry exactly once"
        mock_sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_synthesis_5xx_then_200_succeeds():
    client = MemoryClient(_ENDPOINTS, _AUTH_NO_JWT)
    with patch("memory_client.httpx.AsyncClient") as mock_async_client, \
            patch("memory_client.asyncio.sleep", new=AsyncMock()):
        instance = mock_async_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(side_effect=[
            _mock_response(503, {}),
            _mock_response(200, {"ok": True}),
        ])
        ok = await client.write_synthesis(name="x", content="body")
        assert ok is True


@pytest.mark.asyncio
async def test_write_synthesis_transport_error_retries_once():
    """httpx.HTTPError on first attempt → retry once."""
    client = MemoryClient(_ENDPOINTS, _AUTH_NO_JWT)
    with patch("memory_client.httpx.AsyncClient") as mock_async_client, \
            patch("memory_client.asyncio.sleep", new=AsyncMock()):
        instance = mock_async_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(side_effect=[
            httpx.ConnectError("connection refused"),
            _mock_response(200, {"ok": True}),
        ])
        ok = await client.write_synthesis(name="x", content="body")
        assert ok is True
        assert instance.post.call_count == 2


@pytest.mark.asyncio
async def test_write_synthesis_includes_jwt_header_when_present():
    client = MemoryClient(_ENDPOINTS, _AUTH_WITH_JWT)
    with patch("memory_client.httpx.AsyncClient") as mock_async_client:
        instance = mock_async_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=_mock_response(200, {"ok": True}))
        await client.write_synthesis(name="x", content="body")
        kwargs = instance.post.call_args.kwargs
        assert kwargs["headers"]["Authorization"] == "Bearer tok-abc"


@pytest.mark.asyncio
async def test_write_synthesis_omits_authorization_in_self_host():
    client = MemoryClient(_ENDPOINTS, _AUTH_NO_JWT)
    with patch("memory_client.httpx.AsyncClient") as mock_async_client:
        instance = mock_async_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=_mock_response(200, {"ok": True}))
        await client.write_synthesis(name="x", content="body")
        kwargs = instance.post.call_args.kwargs
        assert "Authorization" not in kwargs["headers"]


# ---------------------------------------------------------------------------
# read_synthesis_latest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_synthesis_latest_404_returns_none():
    """Absence is not an error — first run has no prior memo."""
    client = MemoryClient(_ENDPOINTS, _AUTH_NO_JWT)
    with patch("memory_client.httpx.AsyncClient") as mock_async_client:
        instance = mock_async_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=_mock_response(404, {"detail": "not found"}))
        result = await client.read_synthesis_latest("anything")
        assert result is None


@pytest.mark.asyncio
async def test_read_synthesis_latest_200_returns_memory_dict():
    client = MemoryClient(_ENDPOINTS, _AUTH_NO_JWT)
    fake_memory = {"id": "x", "content": "prior body", "tenant_id": "t1"}
    with patch("memory_client.httpx.AsyncClient") as mock_async_client:
        instance = mock_async_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=_mock_response(200, {"memory": fake_memory}))
        result = await client.read_synthesis_latest("x")
        assert result == fake_memory


@pytest.mark.asyncio
async def test_read_synthesis_latest_transport_error_retries_then_returns_none():
    client = MemoryClient(_ENDPOINTS, _AUTH_NO_JWT)
    with patch("memory_client.httpx.AsyncClient") as mock_async_client, \
            patch("memory_client.asyncio.sleep", new=AsyncMock()):
        instance = mock_async_client.return_value.__aenter__.return_value
        instance.post = AsyncMock(side_effect=[
            httpx.ConnectError("x"),
            httpx.ConnectError("x"),
        ])
        result = await client.read_synthesis_latest("x")
        assert result is None
        assert instance.post.call_count == 2
