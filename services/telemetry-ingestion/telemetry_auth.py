"""Read-route authentication for the telemetry service.

Implements the read_api.py:54-58 TODO(hosted-auth) under the adopted
deployment arrangement (docs/plans/2026-10-21-telemetry-deployment-
recommendation.md; decision record decision-telemetry-deployment-all-
recommended-2026-10-21): authenticated reads from day one, NO anonymous
path. The write routes keep their existing HMAC auth (main.py:119-123,
:191-197); this module covers GET /telemetry/* only.

Two accepted credentials, mirroring the memory service's resolver
(services/agent-context/main.py:53-110) minus its anonymous branch:

1. **Telemetry read key** — a shared secret in `TAPESTRY_TELEMETRY_READ_KEY`,
   compared constant-time per the canonical `api_key_matches` pattern
   (packages/auth/python/loom_auth/auth_bridge.py:195-201, :228-236). A
   telemetry-specific name on purpose: presenting the memory key here must
   not work, so the memory key's blast radius does not widen. A key match
   resolves to the deployment's self-host tenant (same env order as the
   write path), failing CLOSED with 503 when that tenant is unset — the
   same false-negative guard the unauthenticated resolver had.
2. **RS256 JWT** — verified against `LOOM_JWT_PUBLIC_KEY` (already in the
   tapestry-shared-secrets group, infra/deploy/render.yaml:31-32); tenant
   comes from the `tenant_id` claim, `sub` required as a token-shape check.
   Matches loom_auth's hosted-multitenant mode; the self-observer's
   `OBSERVER_JWT` (services/self-observer/config.py:170-178) authenticates
   through this path.

No credentials → 401. A presented-but-invalid credential → 401 (never a
silent self-host fallback — the security-envelope rule from
loom_auth.auth_bridge's module contract). Env is read per call, not at
import, so deployments and tests may set it after module load.
"""
from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException
from jose import JWTError, jwt

import skill_usage_handler


def _telemetry_read_key() -> str:
    """The configured read key, or '' when none is set. Per-call env read,
    mirroring loom_auth.auth_bridge._memory_api_key (:195-201)."""
    return (os.environ.get("TAPESTRY_TELEMETRY_READ_KEY") or "").strip()


def read_key_matches(token: str) -> bool:
    """Constant-time comparison of a presented bearer token against the
    configured telemetry read key. False when no key is configured, so an
    unconfigured deployment can never be unlocked by a guessed empty token
    (mirrors loom_auth.auth_bridge.api_key_matches, :228-236)."""
    key = _telemetry_read_key()
    if not key or not token:
        return False
    return hmac.compare_digest(token, key)


def resolve_self_host_tenant() -> str:
    """Resolve the self-host tenant for a key-authenticated read, or fail
    closed.

    Reuses the write path's env resolver
    (skill_usage_handler._self_host_tenant_id — SELF_HOST_TENANT_ID →
    LOOM_SELF_HOST_TENANT_ID) so reads and writes land in the same tenant
    envelope. 503 rather than the all-zeros tenant when unset: a nil-tenant
    read answers "0 / not known" for every artifact, a false negative the
    orphan-detection contract (read_api.py module docstring) cannot
    tolerate.
    """
    tenant_id = skill_usage_handler._self_host_tenant_id()
    if not tenant_id or tenant_id == skill_usage_handler.NIL_TENANT_ID:
        raise HTTPException(
            503,
            "Telemetry read tenant unresolved: set SELF_HOST_TENANT_ID (or "
            "LOOM_SELF_HOST_TENANT_ID). Refusing to serve an all-zeros-tenant "
            "read (would answer 0/unknown for every artifact).",
        )
    return tenant_id


async def require_read_tenant(
    authorization: Optional[str] = Header(None),
) -> str:
    """FastAPI dependency: authenticate a /telemetry/* read and resolve its
    tenant. NO anonymous path (adoption requirement 3).

    Accepts `Authorization: Bearer <telemetry read key>` → self-host tenant,
    or `Authorization: Bearer <RS256 JWT>` → the token's tenant_id claim.
    Anything else → 401.
    """
    parts = (authorization or "").strip().split(" ", 1)
    scheme = parts[0].lower() if parts and parts[0] else ""
    token = parts[1].strip() if len(parts) == 2 else ""

    if not token:
        raise HTTPException(401, "Authorization required")
    if scheme != "bearer":
        raise HTTPException(401, "Malformed Authorization header")

    # Shared read key first: it is not a JWT and would fail RS256 decode
    # (same ordering rationale as services/agent-context/main.py:84-88).
    if read_key_matches(token):
        return resolve_self_host_tenant()

    public_key = os.environ.get("LOOM_JWT_PUBLIC_KEY")
    if not public_key:
        raise HTTPException(
            401, "JWT verification unavailable (LOOM_JWT_PUBLIC_KEY unset)"
        )

    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(401, "Invalid token")

    tid = claims.get("tenant_id")
    sub = claims.get("sub")
    if not tid or not sub:
        raise HTTPException(401, "Token missing tenant_id or sub claim")
    return tid
