"""loom-sdk: shared runtime primitives for Tapestry services.

Bootstrap module created as part of audit §1.2 (PR-3, 2026-06-22). The
SDK exists to host code that's neither auth-shaped (lives in
``loom_auth``) nor service-specific. First inhabitants:

- ``db`` — ``tenant_conn(ctx)`` async context manager + shared pool helper
- ``secrets`` — pgcrypto BYO-API-key storage (requires ``student_secrets``
  table; see ``secrets`` module docstring for the schema gap)

Future audit §2.2 will add:

- ``providers/model_registry`` — multi-provider LangChain resolver
- ``tools/db`` — read-only Postgres SQL tool for the agent
- ``observability/`` — Make_Skills' observability module

Shape-for-lift mirrors the eventual ``tapestry/packages/sdk/python/`` layout.
"""

__all__: list[str] = []
