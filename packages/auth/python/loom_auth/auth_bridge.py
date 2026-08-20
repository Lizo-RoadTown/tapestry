"""Canonical JWT auth + tenant resolution for loom services.

Two consumers share this module:

1. **FastAPI services** (architecture-registry, policy, project-registry,
   future) use `verify_bearer` as a FastAPI dependency. Returns the
   resolved tenant_id; sets `tenant_ctx_var` so storage.py reads RLS
   tenant.

2. **MCP HTTP transport** (agent-context) uses `LoomTokenVerifier` —
   the MCP SDK's `TokenVerifier` protocol — to validate bearer tokens
   on incoming streamable HTTP requests. Returns an `AccessToken` and
   sets `tenant_ctx_var` for downstream MCP tool handlers.

Both consumers share:
- RS256 decode against `LOOM_JWT_PUBLIC_KEY` (PEM, env var, lazy-loaded
  so /health works while keys are being provisioned)
- Self-host fallback to `SELF_HOST_TENANT_ID` (no header / no key)
- The same per-request `tenant_ctx_var` contextvar (so any code in the
  request's call stack reads the same tenant via `resolve_tenant()`)

## Two-mode commitment (preserved verbatim from each predecessor file)

- **Self-host mode** (no Authorization header, no `LOOM_JWT_PUBLIC_KEY`):
  resolves to `SELF_HOST_TENANT_ID` — set via env var per deployment
  (`SELF_HOST_TENANT_ID` preferred; `LOOM_SELF_HOST_TENANT_ID` accepted
  for backward compatibility), with an all-zeros placeholder default.
  The same value is used across the fleet (records/candidates/
  policy_decisions/projects all live in this single tenant envelope
  for a given self-host deployment).

- **Hosted-multitenant mode** (Bearer JWT + `LOOM_JWT_PUBLIC_KEY` set):
  RS256 signature verified; `tenant_id` claim drives RLS via
  `storage._set_tenant`. `sub` claim required as a token-shape sanity
  check (defends against tokens issued for non-loom purposes).

- **Bearer present but unverifiable**: 401 (FastAPI) or None (MCP).
  Do NOT silently fall back to self-host when the caller TRIED to
  authenticate — that would be a security envelope violation.

## Provenance

Consolidates the prior 4 duplicate files (PR-prep-2b, 2026-06-19):
- services/agent-context/auth_bridge.py (100 LOC, MCP TokenVerifier)
- services/architecture-registry/auth_bridge.py (144 LOC, FastAPI)
- services/policy/auth_bridge.py (126 LOC, FastAPI)
- services/project-registry/auth_bridge.py (129 LOC, FastAPI)

The 3 FastAPI variants were functionally identical (size differences
were entirely docstring / cross-references). The MCP variant diverged
in surface (TokenVerifier class returning AccessToken) but shared the
RS256 + key-load + tenant-set core. Both core paths now share the
`_load_public_key` + `_decode_rs256` helpers below.
"""
from __future__ import annotations

import hmac
import os
from contextvars import ContextVar
from typing import Optional

from fastapi import Header, HTTPException
from jose import JWTError, jwt

# The `mcp` package is only used by LoomTokenVerifier (the MCP SDK
# TokenVerifier surface), which is consumed exclusively by
# services/agent-context. The 3 FastAPI services (architecture-registry,
# policy, project-registry) import this module via their shim only for
# verify_bearer + tenant_ctx_var + SELF_HOST_TENANT_ID, and they do NOT
# list `mcp` in their requirements.txt. A top-level `from mcp.server...`
# would fail at module load on those services' Render venvs (the symptom
# that broke the 2026-06-19 PR-prep-2b deploys — see
# feedback_consolidating_modules_check_per_service_deps_2026_06_19).
#
# Guard the import: when mcp is unavailable, LoomTokenVerifier is None
# and the FastAPI services that never instantiate it are unaffected.
try:
    from mcp.server.auth.provider import AccessToken, TokenVerifier
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False
    AccessToken = None  # type: ignore[assignment, misc]
    TokenVerifier = object  # type: ignore[assignment, misc]


# ---------------------------------------------------------------------------
# Tenant envelope
# ---------------------------------------------------------------------------

# Stable self-host tenant_id — sourced from env so every deployment runs
# under its own tenant envelope. The literal UUID is no longer baked here.
#
# Resolution order:
#   1. SELF_HOST_TENANT_ID env (canonical, no prefix)
#   2. LOOM_SELF_HOST_TENANT_ID env (deprecated alias; kept for backward
#      compatibility with existing deployments)
#   3. All-zeros placeholder (clearly synthetic; safe for dev/local smoke;
#      a real deployment should set its own UUID)
#
# This constant is read by every service in the fleet:
#   services/agent-context/{main,mcp_server,mcp_self_host_middleware}.py
#   services/{architecture-registry,policy,project-registry}/auth_bridge.py
#   scripts/{backfill_projects,memory_snapshot,mint_loom_token}.py
#
# If the env value drifts between services in the same deployment, self-host
# queries silently scope to the wrong tenant and RLS quietly returns empty
# result sets. Pin the env in one place per deployment (a shared env group).
SELF_HOST_TENANT_ID = os.environ.get(
    "SELF_HOST_TENANT_ID",
    os.environ.get(
        "LOOM_SELF_HOST_TENANT_ID",
        "00000000-0000-0000-0000-000000000000",
    ),
)

# Per-request tenant. Set by `verify_bearer()` (FastAPI) or
# `LoomTokenVerifier.verify_token()` (MCP) when auth succeeds; read by
# storage.py to drive RLS via `_set_tenant`. asyncio contextvar means
# each FastAPI/MCP request gets its own — no cross-request leakage.
tenant_ctx_var: ContextVar[Optional[str]] = ContextVar(
    "tenant_id", default=None
)


# ---------------------------------------------------------------------------
# Shared internals (used by both verify_bearer and LoomTokenVerifier)
# ---------------------------------------------------------------------------

_public_key_cache: Optional[str] = None


def _load_public_key() -> Optional[str]:
    """Read `LOOM_JWT_PUBLIC_KEY` on first call; None if unset.

    Lazy so `/health` works while the key is being provisioned by Render —
    same import-time-no-crash discipline as the predecessor files
    (services/*/auth_bridge.py:_load_public_key).

    Cache is process-wide and immutable after first set. Env-var
    re-provisioning requires a service restart.
    """
    global _public_key_cache
    if _public_key_cache is None:
        _public_key_cache = os.environ.get("LOOM_JWT_PUBLIC_KEY")
    return _public_key_cache


def _decode_rs256(token: str, public_key: str) -> Optional[dict]:
    """Shared RS256 decode against the loaded public key.

    Returns the claims dict on success, None on any decode failure
    (signature invalid, algorithm mismatch, expired, malformed, etc.).
    Caller distinguishes None-as-rejection from None-as-no-key.

    `verify_aud: False` because loom tokens don't use the aud claim —
    we identify tenants via the `tenant_id` custom claim instead.
    """
    try:
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Anonymous-access gate (2026-08-08)
# ---------------------------------------------------------------------------
#
# Before this gate existed, a request with NO Authorization header was served
# SELF_HOST_TENANT_ID by both entry points (services/agent-context/main.py's
# `_resolve_tenant_for_rest` and mcp_self_host_middleware's Case 1). Because
# the tenant is chosen server-side from env, the caller did not even need to
# know the tenant UUID: any anonymous request over the public internet was
# handed the deployment's entire memory store, and RLS then granted every row
# in that tenant regardless of each record's `visibility`.
#
# The anonymous gate and the shared secret are INDEPENDENT switches (see
# anonymous_access_allowed below). During the staged rollout anonymous defaults
# ON so deploying the gate is a no-op; it is flipped off explicitly only after
# every client carries the key, then the HTTP anonymous path is removed.
#
# Resolution order for the shared secret:
#   1. TAPESTRY_MEMORY_API_KEY (canonical)
#   2. LOOM_MEMORY_API_KEY (alias, matches the *_MEMORY_MCP_URL naming pair)
#
# Deliberately read per-call rather than at import: deployments and tests set
# these after module import, and a module-level constant would freeze the
# first value seen.


def _memory_api_key() -> str:
    """The configured shared secret, or '' when none is set."""
    return (
        os.environ.get("TAPESTRY_MEMORY_API_KEY")
        or os.environ.get("LOOM_MEMORY_API_KEY")
        or ""
    ).strip()


def anonymous_access_allowed() -> bool:
    """True iff a request with no (or an empty) Authorization header may be
    served the self-host tenant.

    Governed SOLELY by LOOM_ALLOW_ANONYMOUS_SELF_HOST, and INDEPENDENT of
    whether a shared secret is configured. The independence is required for a
    staged rollout that never drops memory: during migration the key and
    anonymous access must BOTH work — deploy the gate + set the key with
    anonymous still ON gives zero client impact, then anonymous is flipped OFF
    only after every client (across every machine) carries the key. Coupling
    the two ("a configured key closes anonymous") makes "enable the key" and
    "revoke anonymous" the same action, with no overlap window — the exact
    fleet-wide silent memory loss this gate exists to avoid.

    Defaults to ALLOWED (unset -> on) so that merely deploying this gate changes
    nothing until the operator explicitly sets LOOM_ALLOW_ANONYMOUS_SELF_HOST=0
    after provisioning. The HTTP anonymous path (this escape hatch) is removed
    entirely once the rollout completes.
    """
    return os.environ.get("LOOM_ALLOW_ANONYMOUS_SELF_HOST", "1").strip() != "0"


def api_key_matches(token: str) -> bool:
    """Constant-time comparison of a presented bearer token against the
    configured shared secret. False when no secret is configured, so an
    unconfigured deployment can never be unlocked by a guessed empty token."""
    key = _memory_api_key()
    if not key or not token:
        return False
    return hmac.compare_digest(token, key)


def resolve_tenant() -> str:
    """Plain-call accessor for code paths that don't go through the
    FastAPI dependency or MCP TokenVerifier (e.g., background tasks,
    tests, helper utilities).

    Reads `tenant_ctx_var` if set; falls back to `SELF_HOST_TENANT_ID`
    otherwise.

    NOT a substitute for `verify_bearer` on HTTP routes or
    `LoomTokenVerifier` on MCP requests — those are the only paths
    that validate the token signature.
    """
    return tenant_ctx_var.get() or SELF_HOST_TENANT_ID


# ---------------------------------------------------------------------------
# FastAPI dependency (architecture-registry, policy, project-registry)
# ---------------------------------------------------------------------------


async def verify_bearer(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency: validates the Authorization header, sets
    `tenant_ctx_var`, returns the tenant_id (also as the function return
    for handlers that prefer explicit reception).

    Modes:

    1. **Self-host** (no auth header, no public key): returns
       `SELF_HOST_TENANT_ID`. Dev / personal-use path — Liz running
       locally without JWT infrastructure stood up.

    2. **Hosted-multitenant** (Bearer token + public key): verifies
       RS256 signature, extracts `tenant_id` claim, returns it.

    3. **Bearer header present but unverifiable**: 401.
    """
    # Mode 1 — no auth header at all → self-host
    if not authorization:
        tenant_ctx_var.set(SELF_HOST_TENANT_ID)
        return SELF_HOST_TENANT_ID

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise HTTPException(401, "Malformed Authorization header")
    token = parts[1].strip()

    public_key = _load_public_key()
    if not public_key:
        # Bearer header sent but no key configured — caller is asking for
        # auth but server can't provide it. 401 rather than silently
        # falling back to self-host (which would be wrong if the caller
        # explicitly tried to authenticate).
        raise HTTPException(
            401, "JWT verification unavailable (LOOM_JWT_PUBLIC_KEY unset)"
        )

    claims = _decode_rs256(token, public_key)
    if claims is None:
        raise HTTPException(401, "Invalid token")

    tid = claims.get("tenant_id")
    sub = claims.get("sub")
    if not tid or not sub:
        raise HTTPException(401, "Token missing tenant_id or sub claim")

    tenant_ctx_var.set(tid)
    return tid


# ---------------------------------------------------------------------------
# MCP SDK TokenVerifier (agent-context HTTP transport)
# ---------------------------------------------------------------------------


class LoomTokenVerifier(TokenVerifier):
    """Verify RS256 JWTs issued by loom-agent-context's token endpoint.

    Used by the MCP SDK's streamable HTTP transport (mcp_http.py:
    `mount_into`). On successful verify, sets `tenant_ctx_var` with the
    JWT's `tenant_id` claim so the MCP tool handlers downstream see
    per-request tenancy.

    Reject reasons (`verify_token` returns None):
    - Signature invalid / token tampered
    - Token expired (`exp` claim past)
    - Algorithm mismatch (we only accept RS256)
    - Missing `sub` or `tenant_id` claim

    Self-host stdio mode never instantiates this. Stdio sessions never
    set `tenant_ctx_var`, so `resolve_tenant()` falls back to
    `SELF_HOST_TENANT_ID`. The MCP self-host middleware
    (mcp_self_host_middleware.py) handles the HTTP-without-Bearer case
    by setting the contextvar to SELF_HOST_TENANT_ID directly.

    Ported from Make_Skills/platform/api/memory/auth_bridge.py:
    - Renamed MakeSkillsTokenVerifier → LoomTokenVerifier
    - HS256 (shared secret) → RS256 (RSA public/private key pair)
    - AUTH_SECRET env → LOOM_JWT_PUBLIC_KEY env (PEM format)
    """

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        public_key = _load_public_key()
        if not public_key:
            # Env var not provisioned yet. Don't crash; just refuse the
            # token. The MCP SDK's RequireAuthMiddleware will return 401
            # to the client, which is the right loud signal that auth
            # isn't configured. /health remains 200 so Render's health
            # check passes.
            return None

        claims = _decode_rs256(token, public_key)
        if claims is None:
            return None

        user_id = claims.get("sub")
        tenant_id = claims.get("tenant_id")
        if not user_id or not tenant_id:
            return None

        # Set the contextvar for downstream tool handlers. The MCP SDK
        # runs each request in its own asyncio task, so the contextvar
        # is request-local — no cross-request leakage.
        tenant_ctx_var.set(tenant_id)

        return AccessToken(
            token=token,
            client_id=user_id,
            scopes=[],
            expires_at=claims.get("exp"),
        )
