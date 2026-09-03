"""Client for the loom-agent-context REST memory surface.

Posts to /v1/write (write synthesis memo) + /v1/read (read prior synthesis
memo for consecutive-scan health computation). Both are REST counterparts
to the loom-memory MCP tools — designed for this cron's one-shot Python
process where the MCP HTTP transport handshake would be heavy.

Per tapestry/docs/research/2026-06-18-outside-review-runtime-observation-followup.md
§5.5.2: ≥30s timeout + 1 retry after 5s to absorb the cold-start window
that loom-agent-context's MCP can hit at session-start. (As of 2026-06-18
loom-agent-context is on starter plan — no spin-down — but the timeout/
retry stays for resilience against transient errors.)

Wire contract verified against services/agent-context/main.py:160-219
(WriteRequest / WriteResponse / ReadRequest / ReadResponse).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from config import AuthConfig, Endpoints


_DEFAULT_TIMEOUT_SECONDS = 30.0
_RETRY_DELAY_SECONDS = 5.0


@dataclass
class MemoryClient:
    """Writes synthesis memos + reads prior synthesis. Mode-agnostic
    (self-host falls back to SELF_HOST_TENANT_ID at the receiver; hosted
    multitenant uses the bearer JWT from AuthConfig.observer_jwt)."""

    endpoints: Endpoints
    auth: AuthConfig

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth.observer_jwt:
            headers["Authorization"] = f"Bearer {self.auth.observer_jwt}"
        return headers

    async def write_synthesis(
        self,
        name: str,
        content: str,
        *,
        record_type: str = "project",
        actor: str = "self-observer",
        project_tags: list[str] | None = None,
        why: str = "",
    ) -> bool:
        """POST /v1/write. Returns True on success, False on persistent failure.

        Failure is logged + absorbed (the scan run already produced its
        candidates; the memo write is best-effort visibility).
        """
        url = f"{self.endpoints.memory_url}/v1/write"
        body = {
            "name": name,
            "record_type": record_type,
            "content": content,
            "actor": actor,
            "project_tags": project_tags or [],
            "why": why,
        }
        return await self._post_with_retry(url, body, action="write")

    async def read_synthesis_latest(self, name: str) -> dict[str, Any] | None:
        """POST /v1/read. Returns the memory dict or None if absent/error.

        Used to fetch the prior scan's synthesis so the current run can
        compute "2 consecutive scans" health thresholds (§3.3).
        """
        url = f"{self.endpoints.memory_url}/v1/read"
        body = {"name": name}
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_SECONDS) as client:
            try:
                resp = await client.post(url, headers=self._headers(), json=body)
            except httpx.HTTPError as exc:
                # First-shot transport error — single retry after delay.
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
                try:
                    resp = await client.post(url, headers=self._headers(), json=body)
                except httpx.HTTPError as exc2:
                    print(f"WARN: memory read failed (retry exhausted): {exc2}")
                    return None
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                print(f"WARN: memory read {resp.status_code}: {resp.text[:200]}")
                return None
            return resp.json().get("memory")

    async def _post_with_retry(
        self,
        url: str,
        body: dict[str, Any],
        *,
        action: str,
    ) -> bool:
        """POST with one retry after a short delay. Treats 2xx as success."""
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_SECONDS) as client:
            for attempt in (1, 2):
                try:
                    resp = await client.post(url, headers=self._headers(), json=body)
                except httpx.HTTPError as exc:
                    if attempt == 1:
                        await asyncio.sleep(_RETRY_DELAY_SECONDS)
                        continue
                    print(f"WARN: memory {action} failed (retry exhausted): {exc}")
                    return False
                if resp.status_code < 400:
                    return True
                # 4xx is a contract failure — don't retry; log and return False.
                if 400 <= resp.status_code < 500:
                    print(
                        f"WARN: memory {action} {resp.status_code}: {resp.text[:200]}"
                    )
                    return False
                # 5xx is transient — retry once.
                if attempt == 1:
                    await asyncio.sleep(_RETRY_DELAY_SECONDS)
                    continue
                print(
                    f"WARN: memory {action} {resp.status_code} after retry: "
                    f"{resp.text[:200]}"
                )
                return False
            return False
