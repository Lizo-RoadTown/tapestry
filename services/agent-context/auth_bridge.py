"""Thin shim: re-exports the canonical `loom_auth.auth_bridge`.

The actual implementation lives at
`the-loom/packages/auth/python/loom_auth/auth_bridge.py` per PR-prep-2b
consolidation (2026-06-19). This file remains so existing patterns
(`from auth_bridge import LoomTokenVerifier` in mcp_http.py +
mcp/memory-server/main.py, and `from auth_bridge import
SELF_HOST_TENANT_ID` in main.py) continue to work without modification.

Two-mode commitment preserved verbatim from the canonical: self-host
(stdio, or HTTP no-Bearer via mcp_self_host_middleware → tenant_ctx_var
set to SELF_HOST_TENANT_ID) + hosted-multitenant (Bearer JWT +
LOOM_JWT_PUBLIC_KEY → tenant_id claim drives RLS). Bearer-but-
unverifiable → 401 / None (no silent self-host fallback).

At Tapestry migration Step 1, the canonical package moves to
`tapestry/packages/auth/`; this shim disappears (either service is
migrated, or it imports from the Tapestry package directly).
"""
import sys
from pathlib import Path

# Add packages/auth/python to sys.path so `loom_auth` is importable
# without pip install. Render's deploy model checks out the whole repo;
# this resolves correctly on Render and locally.
#
# parents[0]=agent-context/, parents[1]=services/, parents[2]=the-loom/
_PKG_PATH = Path(__file__).resolve().parents[2] / "packages" / "auth" / "python"
if str(_PKG_PATH) not in sys.path:
    sys.path.insert(0, str(_PKG_PATH))

from loom_auth.auth_bridge import (  # noqa: E402, F401
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
