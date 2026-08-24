"""Self-host tenant resolution for project-observatory.

Phase 1 of the observer-capacity build. The runtime-observer scopes every
read of the 005 telemetry substrate and every write of observation_signals
(006) to a tenant via db.tenant_transaction. In Phase 1 that tenant is the
deployment's self-host tenant, resolved from the environment.

## Duplicated on purpose (with a single source of truth)

This mirrors the resolver at
services/telemetry-ingestion/read_api.py:78-97 (`_resolve_read_tenant`),
which itself wraps
services/telemetry-ingestion/skill_usage_handler.py:85-98
(`_self_host_tenant_id`) — the SOURCE OF TRUTH for the env order.

It is DUPLICATED rather than imported because project-observatory and
telemetry-ingestion are separately-deployed Render services: neither has the
other on its Python path, so there is nothing clean to import across the
service boundary. The resolution order + the fail-closed rule are the contract
to keep in sync; if the source of truth changes, change it here too.

## The contract

Env order (same as loom_auth.auth_bridge.SELF_HOST_TENANT_ID):
  SELF_HOST_TENANT_ID -> LOOM_SELF_HOST_TENANT_ID -> nil placeholder.

Read from env directly (not by importing loom_auth) so this service does not
pull python-jose + the full auth stack just for one constant. Read per-call so
a deployment/test that sets the env after import is honored.

Fail closed: if resolution yields the all-zeros nil tenant, callers must
REFUSE to proceed rather than read/write the all-zeros tenant — an unscoped
all-zeros read answers "nothing" for every artifact and an all-zeros write
lands signals in a phantom tenant. `require_self_host_tenant()` raises for
that case; task 4/5 surface it as a 503 (read) or a hard error (cron).

## Two-mode

Self-host only in Phase 1. When project-observatory gains hosted-multitenant
read auth, add Bearer-JWT verification alongside this (mirror
services/agent-context/main.py:_resolve_tenant_for_rest — self-host fallback,
RS256 verify, tenant_id claim) and pull in python-jose. Until then the
observer runs single-tenant. db.py stays agnostic either way — it only stamps
app.tenant_id.
"""
from __future__ import annotations

import os

# All-zeros / nil tenant. RLS in 005/006 fails closed to this same value when
# app.tenant_id is unset, so resolving TO it is the "no real tenant" case we
# refuse (see require_self_host_tenant). Kept in sync with
# telemetry-ingestion/skill_usage_handler.py:NIL_TENANT_ID.
NIL_TENANT_ID = "00000000-0000-0000-0000-000000000000"


class TenantUnresolved(RuntimeError):
    """Raised when no real self-host tenant is configured (resolution fell
    through to the nil placeholder). Callers translate this to their own
    fail-closed response (a 503 on a read route, a hard exit on the cron)."""


def self_host_tenant_id() -> str:
    """The deployment's self-host tenant, resolved with the SAME order as the
    telemetry-ingestion source of truth
    (skill_usage_handler._self_host_tenant_id ->
    loom_auth.auth_bridge.SELF_HOST_TENANT_ID):

        SELF_HOST_TENANT_ID -> LOOM_SELF_HOST_TENANT_ID -> NIL_TENANT_ID

    May return NIL_TENANT_ID if neither env var is set; prefer
    `require_self_host_tenant()` when a real tenant is mandatory.
    """
    return os.environ.get(
        "SELF_HOST_TENANT_ID",
        os.environ.get("LOOM_SELF_HOST_TENANT_ID", NIL_TENANT_ID),
    )


def require_self_host_tenant() -> str:
    """Resolve the self-host tenant or fail closed.

    Returns the resolved tenant_id, or raises `TenantUnresolved` when it would
    be the all-zeros nil tenant. Reading/writing the nil tenant is a silent
    false-negative (reads answer "nothing" for every artifact; writes land
    signals in a phantom tenant), so the observer must refuse rather than run
    unscoped. Mirrors read_api._resolve_read_tenant's 503 guard.
    """
    tenant_id = self_host_tenant_id()
    if not tenant_id or tenant_id == NIL_TENANT_ID:
        raise TenantUnresolved(
            "Self-host tenant unresolved: set SELF_HOST_TENANT_ID (or "
            "LOOM_SELF_HOST_TENANT_ID). Refusing to read/write the all-zeros "
            "tenant (would answer/write nothing for every artifact)."
        )
    return tenant_id
