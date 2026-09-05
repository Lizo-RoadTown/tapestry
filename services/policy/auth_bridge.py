"""Thin shim: re-exports the canonical `loom_auth.auth_bridge`.

The actual implementation lives at
`packages/auth/python/loom_auth/auth_bridge.py` (canonical per PR-prep-2b
consolidation 2026-06-19; migrated into Tapestry). This file remains so
existing `import auth_bridge` + `auth_bridge.verify_bearer` patterns in
main.py + storage.py + tests continue to work without modification.

Two-mode commitment preserved verbatim from the canonical: self-host
(no Authorization → `SELF_HOST_TENANT_ID`) + hosted-multitenant (Bearer
JWT + `LOOM_JWT_PUBLIC_KEY`). Bearer-but-unverifiable → 401 (no silent
self-host fallback). See the canonical for full docstring.

Identical to services/architecture-registry/auth_bridge.py — both resolve
the canonical package at the repo root's packages/auth/python.
"""
import sys
from pathlib import Path

# Add packages/auth/python to sys.path so `loom_auth` is importable
# without pip install. Render's deploy model checks out the whole repo;
# this resolves correctly on Render and locally.
#
# parents[0]=policy/, parents[1]=services/, parents[2]=<repo root>
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
