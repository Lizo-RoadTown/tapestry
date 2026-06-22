"""BYO API key storage — tenant-scoped, encrypted at rest.

Tenant-scoped, encrypted-at-rest API keys for LLM providers (and
eventually OAuth tokens for MCP integrations). Encryption uses
pgcrypto's ``pgp_sym_encrypt`` with a deployment-level key set in the
``MAKE_SKILLS_SECRETS_KEY`` env var.

The encryption key is exposed to SQL via the per-connection
``app.secrets_key`` GUC (set in db.py's ``tenant_conn``). Plaintext API
keys never live in application memory longer than the duration of one
write — ``set_secret`` receives the plaintext, hands it to
``pgp_sym_encrypt`` in the same query, never stores it. ``get_secret``
retrieves the decrypted plaintext only when the runtime needs it for an
actual provider call.

## Provenance

Ported from Make_Skills/core/auth/secrets.py (audit §1.2, 2026-06-22).
Import paths adapted: ``core.auth.auth.TenantContext`` →
``loom_auth.TenantContext``; ``core.db.db.tenant_conn`` →
``loom_sdk.db.tenant_conn``.

## SCHEMA GAP — required follow-up

This module READS AND WRITES the ``student_secrets`` table. That table
exists in Make_Skills' Postgres but DOES NOT EXIST in Tapestry's
``infra/migrations/``. Calling any of these functions will raise
``UndefinedTable`` until a migration adds the table.

Required schema (from Make_Skills/core/db/migrations.py):

.. code-block:: sql

    CREATE TABLE student_secrets (
        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        provider_slug TEXT NOT NULL,
        encrypted_value BYTEA NOT NULL,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (tenant_id, provider_slug)
    );
    ALTER TABLE student_secrets ENABLE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON student_secrets
        USING (tenant_id::text = current_setting('app.tenant_id', true));

The migration is intentionally NOT shipped in this PR — audit §1.2 is a
primitives lift, not a schema change. Schema work belongs in a separate
PR per Tapestry's migration-cicd doctrine (idempotent migration with
ADR-recorded rationale).
"""
from __future__ import annotations

import os

from loom_auth import TenantContext
from loom_sdk.db import tenant_conn


def _ensure_key_configured() -> None:
    if not os.environ.get("MAKE_SKILLS_SECRETS_KEY"):
        raise RuntimeError(
            "MAKE_SKILLS_SECRETS_KEY env var not set on this deployment. "
            "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\" "
            "and add to the Render dashboard env (or .env on self-host)."
        )


async def set_secret(ctx: TenantContext, provider_slug: str, plaintext: str) -> None:
    """Encrypt and store a provider API key for the calling tenant.
    Overwrites any existing key for (tenant, provider)."""
    _ensure_key_configured()
    async with tenant_conn(ctx) as conn:
        await conn.execute(
            """
            INSERT INTO student_secrets (tenant_id, provider_slug, encrypted_value)
            VALUES (
                %s::uuid,
                %s,
                pgp_sym_encrypt(%s, current_setting('app.secrets_key'))
            )
            ON CONFLICT (tenant_id, provider_slug)
            DO UPDATE SET
                encrypted_value = pgp_sym_encrypt(
                    %s, current_setting('app.secrets_key')
                ),
                updated_at = now()
            """,
            (ctx.tenant_id, provider_slug, plaintext, plaintext),
        )


async def list_providers_with_keys(ctx: TenantContext) -> list[dict]:
    """Return providers the tenant has stored keys for. Does NOT return
    the key values themselves."""
    async with tenant_conn(ctx) as conn:
        cur = await conn.execute(
            """
            SELECT provider_slug, created_at, updated_at
            FROM student_secrets
            WHERE tenant_id = %s::uuid
            ORDER BY provider_slug
            """,
            (ctx.tenant_id,),
        )
        rows = await cur.fetchall()
        return [
            {
                "provider_slug": r[0],
                "created_at": r[1].isoformat() if r[1] else None,
                "updated_at": r[2].isoformat() if r[2] else None,
            }
            for r in rows
        ]


async def get_secret(ctx: TenantContext, provider_slug: str) -> str | None:
    """Decrypt and return a stored provider API key.

    Used by the agent runtime at /chat time to call the provider with
    the student's own key. Plaintext only lives in the calling code's
    local scope — never logged, never stored.
    """
    _ensure_key_configured()
    async with tenant_conn(ctx) as conn:
        cur = await conn.execute(
            """
            SELECT pgp_sym_decrypt(encrypted_value, current_setting('app.secrets_key'))
            FROM student_secrets
            WHERE tenant_id = %s::uuid AND provider_slug = %s
            """,
            (ctx.tenant_id, provider_slug),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def delete_secret(ctx: TenantContext, provider_slug: str) -> bool:
    """Delete a stored provider API key. Returns True if a row was deleted."""
    async with tenant_conn(ctx) as conn:
        cur = await conn.execute(
            """
            DELETE FROM student_secrets
            WHERE tenant_id = %s::uuid AND provider_slug = %s
            RETURNING id
            """,
            (ctx.tenant_id, provider_slug),
        )
        row = await cur.fetchone()
        return row is not None
