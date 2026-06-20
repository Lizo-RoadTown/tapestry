"""loom-auth: shared JWT auth + tenant resolution for loom services.

Public API:
    verify_bearer       — FastAPI dependency (architecture-registry, policy, project-registry, future)
    LoomTokenVerifier   — MCP SDK TokenVerifier (agent-context HTTP transport)
    SELF_HOST_TENANT_ID — stable self-host tenant UUID
    tenant_ctx_var      — per-request tenant contextvar (shared by both consumers)
    resolve_tenant      — plain-call accessor (reads contextvar; falls back to SELF_HOST_TENANT_ID)

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

__all__ = [
    "LoomTokenVerifier",
    "SELF_HOST_TENANT_ID",
    "resolve_tenant",
    "tenant_ctx_var",
    "verify_bearer",
]
