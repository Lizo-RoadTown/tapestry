-- 005_init_telemetry.sql
--
-- Telemetry read-substrate for loom-postgres — Phase 0 of the observer
-- capacity build (docs/plans/2026-08-23-observer-capacity-build-sequence.md).
--
-- Purpose: give the platform a Postgres-backed, self-host-safe store for
-- coordination telemetry, so the runtime-observer and the self-observer can
-- READ signals (invocation counts, coordination quality) without depending on
-- Grafana Cloud. Today the-loom's telemetry-ingestion only logs to Loki via
-- stdout (no persistence, no read API), and the self-observer's telemetry read
-- is a stub returning None. This schema is the substrate that retires both.
--
-- Conventions mirror 001_init_memory.sql deliberately:
--   - tenant_id UUID NOT NULL, RLS ENABLE + FORCE, app.tenant_id via SET LOCAL
--   - ts DOUBLE PRECISION (epoch seconds), matching the memory `ts` shape
--   - JSONB `attrs` forward-compat slot + GIN (jsonb_path_ops), like `extra`
--   - CREATE ... IF NOT EXISTS everywhere; re-running is a no-op
--
-- Numbering: 003 (candidates / architecture-registry) and 004 (policy) are
-- reserved by ratified proposals (docs/proposals/2026-06-12-promotion-
-- categorization.md); telemetry takes 005. Telemetry has no FK dependency on
-- those tables, so 003/004 being absent at apply-time is fine.
--
-- Attribute source of truth: the OTel coordination contract
-- (apps/docs-site/src/content/docs/reference/otel-coordination-contract.md;
-- repo-root canonical spec docs/reference/coordination-telemetry-contract.md).
-- Two-mode: pure Postgres, so self-host has parity; Loki/Grafana stays an
-- optional export target, never a read dependency.
--
-- Apply order:
--   psql $LOOM_DB_URL -f 005_init_telemetry.sql

BEGIN;

-- ---------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------

-- gen_random_uuid() is core in Postgres 13+, but pgcrypto provides it on
-- older servers too; IF NOT EXISTS keeps this a no-op where it's built in.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------
-- Table: telemetry_events
--
-- Append-only fact table: one row per emitted coordination event (a hook
-- firing, a tool call, an engine skill-usage batch item, an observer run).
-- Columns map to the OTel coordination contract's required + mechanism
-- attributes; the rest live in `attrs`. Producers emit slugs (not UUIDs) for
-- project identity, so both `project_slug` (always) and `project_id`
-- (resolved, optional) are carried — the slug is the canonical wire identity.
--
-- Idempotency: `id` is the dedup key. Under at-least-once delivery a producer
-- should supply a STABLE id (e.g. batch_id + item index); the ingest write
-- path then upserts `ON CONFLICT (id) DO NOTHING` so a retried emit does not
-- double-count the rollup. Letting `id` default to a random UUID means retries
-- are counted twice — acceptable only where producers never retry.
--
-- Retention: this fact table is the replayable source of truth. The read
-- layer's "unused vs never-seen (blind)" distinction relies on lifetime
-- history ("has >= 1 event ever"), so any future retention trim must preserve
-- per-artifact "ever seen" state rather than trimming both tables to the
-- observation window.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS telemetry_events (
    id                        UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                 UUID             NOT NULL,

    -- Coordination context (contract: required anchor + always-set context)
    coordination_context_id   UUID,                                   -- NULL = pre-instrument / blind
    project_id                UUID,                                   -- resolved registry id; no hard FK (hot path)
    project_slug              VARCHAR(128)     NOT NULL DEFAULT '',   -- canonical wire identity (LOOM_PROJECT_ID)
    session_id                VARCHAR(128)     NOT NULL DEFAULT '',
    agent_id                  VARCHAR(128),
    agent_role                VARCHAR(64),
    surface_id                VARCHAR(128),
    surface_type              VARCHAR(64),

    -- Mechanism (what happened)
    event_kind                VARCHAR(32)      NOT NULL,              -- discriminator, see CHECK below
    hook_name                 VARCHAR(64),
    tool_name                 VARCHAR(128),
    phase                     VARCHAR(8),                             -- 'start' | 'end'
    artifact_ref              VARCHAR(512),                           -- normalized repo#path or skill/agent name
    skill_id                  UUID,

    -- Quality + cost
    outcome                   VARCHAR(16),                            -- success | error | timeout
    coordination_state        VARCHAR(16)      NOT NULL DEFAULT 'blind',
    exit_code                 INTEGER,
    elapsed_ms                INTEGER,
    tokens_in                 INTEGER,
    tokens_out                INTEGER,
    model                     VARCHAR(64),

    -- Timing
    ts                        DOUBLE PRECISION NOT NULL DEFAULT 0,    -- event wall-clock, epoch seconds
    received_at               DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()),

    -- Provenance + forward-compat
    batch_id                  UUID,
    attrs                     JSONB            NOT NULL DEFAULT '{}',

    CONSTRAINT telemetry_events_event_kind_enum CHECK (event_kind IN (
        'hook', 'tool', 'snapshot', 'observer', 'skill_usage', 'memory', 'friction'
    )),
    CONSTRAINT telemetry_events_outcome_enum CHECK (
        outcome IS NULL OR outcome IN ('success', 'error', 'timeout')
    ),
    CONSTRAINT telemetry_events_coordination_state_enum CHECK (
        coordination_state IN ('healthy', 'degraded', 'blind', 'unknown')
    )
);

-- ---------------------------------------------------------------------
-- Indexes: telemetry_events
--
-- Every read is tenant-scoped and time-windowed (30-day windows). The
-- per-dimension composite indexes back the read API's count queries; the
-- GIN backs containment on the mechanism attrs bag.
-- ---------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS telemetry_events_tenant_ts_idx
    ON telemetry_events (tenant_id, ts DESC);

CREATE INDEX IF NOT EXISTS telemetry_events_tenant_ctx_idx
    ON telemetry_events (tenant_id, coordination_context_id);

CREATE INDEX IF NOT EXISTS telemetry_events_tenant_project_ts_idx
    ON telemetry_events (tenant_id, project_slug, ts DESC);

CREATE INDEX IF NOT EXISTS telemetry_events_tenant_artifact_ts_idx
    ON telemetry_events (tenant_id, artifact_ref, ts DESC);

CREATE INDEX IF NOT EXISTS telemetry_events_tenant_tool_ts_idx
    ON telemetry_events (tenant_id, tool_name, ts DESC);

CREATE INDEX IF NOT EXISTS telemetry_events_tenant_session_idx
    ON telemetry_events (tenant_id, session_id);

-- jsonb_path_ops: smaller + faster for the dominant `attrs @> '{...}'`
-- containment access pattern (same choice + rationale as records.extra).
CREATE INDEX IF NOT EXISTS telemetry_events_attrs_gin
    ON telemetry_events USING gin (attrs jsonb_path_ops);

-- ---------------------------------------------------------------------
-- Table: telemetry_rollup_daily
--
-- Daily invocation-count rollup. Makes invocations_30d() an O(30 rows)
-- lookup instead of a scan of the fact table. Grain: one row per
-- (tenant, day, project, artifact, tool, kind). Maintained by incremental
-- UPSERT on each accepted event — no matview/pg_cron scheduler needed, so
-- self-host has parity. The fact table stays the replayable source of truth:
-- the rollup can be rebuilt with one INSERT ... SELECT ... GROUP BY.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS telemetry_rollup_daily (
    tenant_id         UUID             NOT NULL,
    bucket_day        DATE             NOT NULL,
    project_slug      VARCHAR(128)     NOT NULL DEFAULT '',
    artifact_ref      VARCHAR(512)     NOT NULL DEFAULT '',
    tool_name         VARCHAR(128)     NOT NULL DEFAULT '',
    event_kind        VARCHAR(32)      NOT NULL DEFAULT '',
    invocation_count  BIGINT           NOT NULL DEFAULT 0,
    error_count       BIGINT           NOT NULL DEFAULT 0,
    sum_elapsed_ms    BIGINT           NOT NULL DEFAULT 0,
    last_seen_ts      DOUBLE PRECISION NOT NULL DEFAULT 0,

    CONSTRAINT telemetry_rollup_daily_pk PRIMARY KEY
        (tenant_id, bucket_day, project_slug, artifact_ref, tool_name, event_kind)
);

CREATE INDEX IF NOT EXISTS telemetry_rollup_artifact_day_idx
    ON telemetry_rollup_daily (tenant_id, artifact_ref, bucket_day);

CREATE INDEX IF NOT EXISTS telemetry_rollup_project_day_idx
    ON telemetry_rollup_daily (tenant_id, project_slug, bucket_day);

-- ---------------------------------------------------------------------
-- Row-Level Security
--
-- Same Pillar 0 pattern as records: services set app.tenant_id via SET LOCAL
-- inside a transaction; policies compare row tenant_id to it, failing closed
-- to the all-zeros UUID. Telemetry is never cross-tenant-public, so there is
-- no visibility='public' branch — the read policy is the plain tenant match.
-- ---------------------------------------------------------------------

ALTER TABLE telemetry_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_events FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS telemetry_events_tenant_read ON telemetry_events;
CREATE POLICY telemetry_events_tenant_read ON telemetry_events
    FOR SELECT
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS telemetry_events_tenant_insert ON telemetry_events;
CREATE POLICY telemetry_events_tenant_insert ON telemetry_events
    FOR INSERT
    WITH CHECK (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS telemetry_events_tenant_update ON telemetry_events;
CREATE POLICY telemetry_events_tenant_update ON telemetry_events
    FOR UPDATE
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS telemetry_events_tenant_delete ON telemetry_events;
CREATE POLICY telemetry_events_tenant_delete ON telemetry_events
    FOR DELETE
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

ALTER TABLE telemetry_rollup_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_rollup_daily FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS telemetry_rollup_tenant_read ON telemetry_rollup_daily;
CREATE POLICY telemetry_rollup_tenant_read ON telemetry_rollup_daily
    FOR SELECT
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS telemetry_rollup_tenant_insert ON telemetry_rollup_daily;
CREATE POLICY telemetry_rollup_tenant_insert ON telemetry_rollup_daily
    FOR INSERT
    WITH CHECK (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS telemetry_rollup_tenant_update ON telemetry_rollup_daily;
CREATE POLICY telemetry_rollup_tenant_update ON telemetry_rollup_daily
    FOR UPDATE
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS telemetry_rollup_tenant_delete ON telemetry_rollup_daily;
CREATE POLICY telemetry_rollup_tenant_delete ON telemetry_rollup_daily
    FOR DELETE
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

COMMIT;
