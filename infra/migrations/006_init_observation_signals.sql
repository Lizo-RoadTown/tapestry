-- 006_init_observation_signals.sql
--
-- Observation-signals store for Phase 1 of the observer-capacity build
-- (docs/plans/2026-08-23-observer-capacity-build-sequence.md) — the output of
-- the runtime-observer (services/project-observatory/).
--
-- Purpose: the runtime-observer reads the Phase-0 telemetry substrate
-- (005_init_telemetry.sql) and computes observation signals — hot_path,
-- orphaned, degrading, blind — per artifact over a window. It writes those
-- signals here; project-observatory serves them.
--
-- Boundary (ADR-0001 docs/adr/0001-observer-topology.md:27-29,42): these are
-- SIGNALS, not candidates. This table has no candidate_kind, no automation
-- level, no activation field. It is never written by policy and never writes
-- to the architecture-registry candidate path. Signals are evidence; the
-- observation-decomposer + policy (later phases) are what turn evidence into
-- candidates and activation.
--
-- Conventions mirror 005_init_telemetry.sql (and 001): tenant_id UUID NOT NULL,
-- RLS ENABLE + FORCE with the app.tenant_id fail-closed policy, ts as
-- DOUBLE PRECISION epoch seconds, evidence JSONB + GIN, CREATE ... IF NOT
-- EXISTS everywhere (idempotent re-run). No visibility='public' branch —
-- signals are never cross-tenant-public.
--
-- Numbering: 000 platform, 001 memory, 002 projects, 005 telemetry; 006 is the
-- next free number (003/004 remain reserved by ratified proposals for
-- candidates/policy). observation_signals has no FK dependency on those.
--
-- Apply order:
--   psql $LOOM_DB_URL -f 006_init_observation_signals.sql

BEGIN;

-- ---------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------

-- gen_random_uuid() is core in Postgres 13+, pgcrypto provides it elsewhere.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------
-- Table: observation_signals
--
-- One row per (artifact, signal_kind) produced in a runtime-observer pass.
-- Each pass is one `run_id` snapshot stamped with `computed_at`; the read
-- layer returns the latest snapshot by default. Snapshots accumulate so a
-- consumer can see a signal's history (e.g. "degrading for three runs");
-- trimming old runs is an ops policy, not enforced here.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS observation_signals (
    id            UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID             NOT NULL,
    run_id        UUID             NOT NULL,               -- one runtime-observer pass
    project_slug  VARCHAR(128)     NOT NULL DEFAULT '',    -- canonical wire identity (matches 005)
    artifact_ref  VARCHAR(512)     NOT NULL DEFAULT '',    -- same domain as telemetry_rollup_daily.artifact_ref

    signal_kind   VARCHAR(32)      NOT NULL,               -- see CHECK below
    score         DOUBLE PRECISION NOT NULL DEFAULT 0,     -- normalized strength 0..1 (for ranking)
    window_days   INTEGER          NOT NULL DEFAULT 30,    -- the observation window this was computed over

    -- The measured inputs behind the signal, so it is self-explaining:
    -- windowed invocations, error-rate delta, latency ratio, known/decayed
    -- flags, etc. Analogue of the self-observer's signals.reasons.
    evidence      JSONB            NOT NULL DEFAULT '{}',

    computed_at   DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()),

    CONSTRAINT observation_signals_kind_enum CHECK (signal_kind IN (
        'hot_path', 'orphaned', 'degrading', 'blind'
    ))
);

-- ---------------------------------------------------------------------
-- Indexes
--
-- Reads are tenant-scoped and want the latest snapshot, optionally filtered
-- by project / artifact / kind. run_id fetches one whole snapshot.
-- ---------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS observation_signals_tenant_computed_idx
    ON observation_signals (tenant_id, computed_at DESC);

CREATE INDEX IF NOT EXISTS observation_signals_tenant_project_computed_idx
    ON observation_signals (tenant_id, project_slug, computed_at DESC);

CREATE INDEX IF NOT EXISTS observation_signals_tenant_artifact_computed_idx
    ON observation_signals (tenant_id, artifact_ref, computed_at DESC);

CREATE INDEX IF NOT EXISTS observation_signals_tenant_kind_computed_idx
    ON observation_signals (tenant_id, signal_kind, computed_at DESC);

CREATE INDEX IF NOT EXISTS observation_signals_tenant_run_idx
    ON observation_signals (tenant_id, run_id);

-- jsonb_path_ops GIN on evidence — same choice + rationale as records.extra
-- and telemetry_events.attrs (fast `evidence @> '{...}'` containment).
CREATE INDEX IF NOT EXISTS observation_signals_evidence_gin
    ON observation_signals USING gin (evidence jsonb_path_ops);

-- ---------------------------------------------------------------------
-- Row-Level Security
--
-- Same pattern as 005: services set app.tenant_id via SET LOCAL inside a
-- transaction; policies compare row tenant_id to it, failing closed to the
-- all-zeros UUID. No visibility='public' branch (signals are never
-- cross-tenant-public), so the read policy is the plain tenant match.
-- ---------------------------------------------------------------------

ALTER TABLE observation_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE observation_signals FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS observation_signals_tenant_read ON observation_signals;
CREATE POLICY observation_signals_tenant_read ON observation_signals
    FOR SELECT
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS observation_signals_tenant_insert ON observation_signals;
CREATE POLICY observation_signals_tenant_insert ON observation_signals
    FOR INSERT
    WITH CHECK (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS observation_signals_tenant_update ON observation_signals;
CREATE POLICY observation_signals_tenant_update ON observation_signals
    FOR UPDATE
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS observation_signals_tenant_delete ON observation_signals;
CREATE POLICY observation_signals_tenant_delete ON observation_signals
    FOR DELETE
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

COMMIT;
