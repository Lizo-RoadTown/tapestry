"""TenantContext dataclass + LangGraph chokepoint ContextVar.

Ported from Make_Skills core/auth/auth.py + core/auth/tenant_context.py
(audit §1.2). Two surfaces consolidated here:

1. ``TenantContext`` — frozen dataclass carrying (tenant_id, user_id, role).
   Used by code paths that need richer context than the bare tenant_id
   string — admin/member role checks, audit trails, secrets store.

2. ``langgraph_tenant_ctx`` — ambient ContextVar for code paths inside
   LangGraph. The chat endpoint resolves tenant_id from the request and
   sets this before ``agent.ainvoke(...)``. The wrapped PostgresSaver
   reads it inside its ``_cursor()`` override so every checkpoint
   read/write runs under ``SET LOCAL app.tenant_id``.

   Distinct from ``loom_auth.auth_bridge.tenant_ctx_var`` which is the
   FastAPI/MCP request-boundary variable (set by ``verify_bearer`` /
   ``LoomTokenVerifier``). Both ContextVars carry the tenant_id string;
   their lifetimes and producers differ. Renamed from Make_Skills'
   ``current_tenant`` to make the LangGraph role explicit.

   Background tasks and worker queues do NOT inherit ContextVars
   reliably; they take ``tenant_id`` as an explicit argument.

## Provenance

- Make_Skills core/auth/auth.py:40-45 (TenantContext dataclass)
- Make_Skills core/auth/tenant_context.py:24-26 (current_tenant ContextVar,
  renamed to langgraph_tenant_ctx here)

Adaptations applied during lift:
- DEFAULT_TENANT_ID (Make_Skills' "00000000-…") replaced with
  SELF_HOST_TENANT_ID (loom_auth's "1d8ec1b3-…") since this destination
  shares the loom self-host envelope. See
  tapestry_audit_1_2_tenant_id_constant_mismatch_caught_2026_06_22.
- ContextVar renamed: current_tenant → langgraph_tenant_ctx.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from loom_auth.auth_bridge import SELF_HOST_TENANT_ID


@dataclass(frozen=True)
class TenantContext:
    """Per-request tenant envelope.

    - ``tenant_id`` — UUID string. The RLS scope.
    - ``user_id`` — optional UUID string. Identifies the calling user.
      ``"local"`` on self-host (no auth).
    - ``role`` — optional ``"admin"``, ``"member"``, or None. Self-host
      treats local as everything; hosted-multitenant carries the role
      claim from the JWT.
    """
    tenant_id: str
    user_id: str | None = None
    role: str | None = None


langgraph_tenant_ctx: ContextVar[str] = ContextVar(
    "langgraph_tenant_ctx", default=SELF_HOST_TENANT_ID
)
