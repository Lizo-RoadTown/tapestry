-- 000_init_platform.sql — platform-level tenant tables (Tapestry Step 1)
--
-- PROVENANCE (faithful forklift, NOT a redesign):
--   tenants          ← Make_Skills/core/db/migrations.py:43-62
--   tenant_id_mapping ← Make_Skills/core/db/migrations.py:420-450
-- These two tables are lifted verbatim-faithful from the engine-side canonical
-- (the tenant_id_mapping table originated there per
-- `decision_tenant_id_mapping_option_b_2026_06_12`). The only deliberate
-- consolidation change is the `platform` schema namespace (per the v1 roadmap's
-- shared-platform-schema design: per-service schemas + one shared `platform.*`
-- readable by all). Any column/RLS redesign is explicitly DEFERRED — this is the
-- conservative forklift so Step 1 unblocks without inventing schema.
--
-- SCOPE: only the two cross-system tenant tables. The sibling tables in the
-- Make_Skills source (bridge_idempotency, promoted_skills) are skill-making
-- concerns and belong to Step 4, not here.
--
-- STATUS: this is a schema FILE awaiting a future Tapestry platform Postgres.
-- It is NOT applied or deployed by this PR (Tapestry has no DB/gateway yet).
--
-- Idempotent (IF NOT EXISTS / ON CONFLICT) — safe to re-run.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS platform;

-- ---- tenants ----
-- The platform tenant registry. Self-host runs as the single default tenant;
-- existing data backfills against it. (Source: migrations.py:43-62.)
CREATE TABLE IF NOT EXISTS platform.tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);

-- Engine-side DEFAULT_TENANT_ID (the row self-host maps TO). Name label mirrors
-- Make_Skills' DEFAULT_TENANT_NAME (a label only; not load-bearing).
INSERT INTO platform.tenants (id, name)
VALUES ('00000000-0000-0000-0000-000000000000', 'default')
ON CONFLICT (id) DO NOTHING;

-- ---- tenant_id_mapping ----
-- Cross-system tenant UUID reconciliation: (source_system, source_tenant_id)
-- -> engine_tenant_id. No RLS — this is operator-configured infrastructure,
-- looked up before tenant scoping is resolved. (Source: migrations.py:420-450.)
CREATE TABLE IF NOT EXISTS platform.tenant_id_mapping (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system     TEXT NOT NULL,          -- 'loom' for now
    source_tenant_id  UUID NOT NULL,
    engine_tenant_id  UUID NOT NULL REFERENCES platform.tenants(id) ON DELETE CASCADE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_system, source_tenant_id)
);

CREATE INDEX IF NOT EXISTS tenant_id_mapping_engine_idx
    ON platform.tenant_id_mapping (engine_tenant_id);

-- No seed mapping is created here. Each deployment populates its own
-- (source_system, source_tenant_id, engine_tenant_id) rows post-migration,
-- using the SELF_HOST_TENANT_ID value the deployment is configured with.
-- Example INSERT for a deployment that wants the loom-source tenant to
-- map to the engine's default tenant:
--
--   INSERT INTO platform.tenant_id_mapping
--       (source_system, source_tenant_id, engine_tenant_id)
--   VALUES ('loom', '<your SELF_HOST_TENANT_ID>', '00000000-0000-0000-0000-000000000000')
--   ON CONFLICT (source_system, source_tenant_id) DO NOTHING;
