"""loom-auth: shared JWT auth + tenant resolution for loom services.

Public API:
    verify_bearer       — FastAPI dependency (architecture-registry, policy, project-registry, …)
    LoomTokenVerifier   — MCP SDK TokenVerifier (agent-context HTTP transport)
    SELF_HOST_TENANT_ID — stable self-host tenant UUID
    tenant_ctx_var      — per-request tenant contextvar (FastAPI/MCP boundary)
    resolve_tenant      — plain-call accessor (reads contextvar; falls back to SELF_HOST_TENANT_ID)
    TenantContext       — frozen dataclass carrying (tenant_id, user_id, role)
    langgraph_tenant_ctx — ContextVar for the LangGraph PostgresSaver chokepoint

Shape-for-lift: this package mirrors the eventual tapestry/packages/auth/
destination per the Step 1 auth-consolidation plan. The package name
`loom_auth` becomes the Tapestry name at migration time.
"""
from loom_auth.auth_bridge import (
    LoomTokenVerifier,
    SELF_HOST_TENANT_ID,
    resolve_tenant,
    tenant_ctx_var,
    verify_bearer,
)
from loom_auth.tenant_context import (
    TenantContext,
    langgraph_tenant_ctx,
)

__all__ = [
    "LoomTokenVerifier",
    "SELF_HOST_TENANT_ID",
    "TenantContext",
    "langgraph_tenant_ctx",
    "resolve_tenant",
    "tenant_ctx_var",
    "verify_bearer",
]
