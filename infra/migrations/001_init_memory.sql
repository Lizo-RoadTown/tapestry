-- 001_init_memory.sql
--
-- Phase 2 initial schema for loom-postgres.
--
-- Creates the `records` table — the shared multi-agent memory substrate
-- backing the Agent Context Service (per v3 platform-data-model.md).
--
-- Maps from the LanceDB schema at Make_Skills/platform/api/memory/lance.py
-- with the following corrections (Option E, reconciled with MS-agent's
-- forensic audit of Make_Skills memory in INTER_AGENT_DIALOGUE 2026-05-26):
--
--   1. `tenant_id` is UUID NOT NULL (was string in LanceDB; the-loom
--      uses UUID per v3 + memory `reference_phase2_port_specifics`).
--
--   2. `ts` is DOUBLE PRECISION (epoch seconds) to preserve the
--      mcp_server.py code that does `time.time()` and stores raw floats.
--      timestamptz can come in a future migration when no callers
--      depend on the float shape.
--
--   3. `type` enum expanded to TEN values — matches Make_Skills' actual
--      two-path memory model that MS-agent surfaced from forensic dig:
--      RUNTIME EPISODIC (decision | lesson | preference | skill_idea |
--      topic | fact) emitted by recorder.py:49 after each /chat turn,
--      AND SESSION LONG-TERM (user | feedback | project | reference)
--      emitted by the typed-file friction-as-memory protocol. Single
--      table; type column carries the path distinction. No separate
--      memory_class column needed.
--
--   4. NEW columns for the multi-agent / multi-project / orchestration
--      reality (per project_shared_multi_agent_memory_substrate memory):
--        - actor VARCHAR(128) — which agent kind wrote it
--        - ts_last_accessed DOUBLE PRECISION — for recency-weighted
--          retrieval + future decay (writes happen via storage.py)
--        - extra JSONB — forward-compat slot for orchestration_id,
--          run_id, parent_session_id, affected_entities, trigger,
--          outcome etc. without requiring a schema migration to add.
--
-- Multi-agent scoping is handled by the EXISTING fields:
--   - tenant_id (one per user — Liz; shared across all her agents)
--   - project_tags[] (which projects this memory applies to; cross-
--     project default = empty array)
--   - source_thread_id (writing session; provenance origin)
--   - actor (agent kind, including 'subagent:<role>')
--   - extra (orchestration/run/parent metadata)
--
-- Apply order:
--   psql $LOOM_DB_URL -f 001_init_memory.sql
--
-- This file is idempotent: re-running on a populated DB is a no-op
-- (CREATE IF NOT EXISTS everywhere). Migrations are applied in numeric
-- order; never edit a migration after it lands.

BEGIN;

-- ---------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------
-- Table: records
--
-- One row per typed memory entry. The memory `name` (e.g.
-- `feedback_documentation_tone`) IS the row id; the file-protocol
-- convention from Make_Skills' file-based memory is preserved.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS records (
    id                 VARCHAR(256)     PRIMARY KEY,
    type               VARCHAR(32)      NOT NULL,
    content            TEXT             NOT NULL,
    vector             vector(384)      NOT NULL,            -- BAAI/bge-small-en-v1.5 dimension
    project_tags       TEXT[]           NOT NULL DEFAULT '{}',
    source_thread_id   VARCHAR(128)     NOT NULL DEFAULT '',
    ts                 DOUBLE PRECISION NOT NULL DEFAULT 0,
    why                TEXT             NOT NULL DEFAULT '',
    tenant_id          UUID             NOT NULL,
    visibility         VARCHAR(16)      NOT NULL DEFAULT 'private',

    -- Option E additions (per MS-agent's audit + multi-agent substrate)
    actor              VARCHAR(128)     NOT NULL DEFAULT 'unknown',
    ts_last_accessed   DOUBLE PRECISION NOT NULL DEFAULT 0,
    extra              JSONB            NOT NULL DEFAULT '{}',

    -- 10-value type enum carries the episodic-vs-session-long-term path
    -- distinction Make_Skills already uses:
    --   Runtime episodic (recorder.py emits these from /chat turns):
    --     'decision', 'lesson', 'preference', 'skill_idea', 'topic', 'fact'
    --   Session long-term (friction-as-memory typed-file protocol):
    --     'user', 'feedback', 'project', 'reference'
    CONSTRAINT records_type_enum CHECK (type IN (
        'decision', 'lesson', 'preference', 'skill_idea', 'topic', 'fact',
        'user', 'feedback', 'project', 'reference'
    )),
    CONSTRAINT records_visibility_enum CHECK (visibility IN ('private', 'public', 'deleted'))
);

-- ---------------------------------------------------------------------
-- Indexes
--
-- Per Make_Skills' Pillar 0 pattern: btree (tenant_id, visibility) for
-- prefilter pushdown on every query. HNSW on the vector column for
-- fast ANN search. GIN on project_tags for array_contains operations.
-- ---------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS records_tenant_visibility_idx
    ON records (tenant_id, visibility);

CREATE INDEX IF NOT EXISTS records_type_idx
    ON records (type);

CREATE INDEX IF NOT EXISTS records_ts_idx
    ON records (ts DESC);

-- HNSW is preferred for cosine similarity over IVFFlat for our scale
-- (single-user, ~thousands to tens-of-thousands of vectors). Lower
-- maintenance, no rebuild needed on inserts. `vector_cosine_ops` matches
-- the `<=>` operator we use in queries.
CREATE INDEX IF NOT EXISTS records_vector_hnsw_idx
    ON records USING hnsw (vector vector_cosine_ops);

-- GIN supports the @> (array contains) and && (array overlap) operators
-- we use for project_tags filtering.
CREATE INDEX IF NOT EXISTS records_project_tags_gin
    ON records USING gin (project_tags);

-- GIN on the JSONB `extra` column — Option E forward-compat slot for
-- orchestration_id / run_id / parent_session_id / etc. Enables fast
-- containment queries like `WHERE extra @> '{"orchestration_id":"X"}'`
-- and key-existence queries like `WHERE extra ? 'run_id'`. jsonb_path_ops
-- variant trades some operator support for smaller index size + faster
-- containment lookups, which is the dominant access pattern for us.
CREATE INDEX IF NOT EXISTS records_extra_gin
    ON records USING gin (extra jsonb_path_ops);

-- ---------------------------------------------------------------------
-- Row-Level Security (RLS)
--
-- Tenant scope enforced at the database layer using the Pillar 0
-- pattern: services set `app.tenant_id` via SET LOCAL inside a
-- transaction; the RLS policy reads it via current_setting() and
-- compares with the row's tenant_id.
--
-- For inserts/updates: the row's tenant_id must equal app.tenant_id.
-- For reads: same, OR the row is visibility='public' (the future
-- Pillar 3c commons).
-- ---------------------------------------------------------------------

ALTER TABLE records ENABLE ROW LEVEL SECURITY;
ALTER TABLE records FORCE ROW LEVEL SECURITY;  -- applies to table owner too

-- The catch-all read policy. Service-role connections set app.tenant_id;
-- public-visibility rows are readable across tenants.
DROP POLICY IF EXISTS records_tenant_read ON records;
CREATE POLICY records_tenant_read ON records
    FOR SELECT
    USING (
        visibility = 'public'
        OR tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

-- Write policies — only the matching tenant can write.
DROP POLICY IF EXISTS records_tenant_insert ON records;
CREATE POLICY records_tenant_insert ON records
    FOR INSERT
    WITH CHECK (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS records_tenant_update ON records;
CREATE POLICY records_tenant_update ON records
    FOR UPDATE
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

DROP POLICY IF EXISTS records_tenant_delete ON records;
CREATE POLICY records_tenant_delete ON records
    FOR DELETE
    USING (
        tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
    );

-- ---------------------------------------------------------------------
-- Default self-host tenant (per memory reference_phase2_port_specifics)
--
-- For self-host mode (Liz on her own machines), use a stable non-zero
-- UUID. The MS-agent notes warned that the all-zeros UUID triggered a
-- LanceDB filter bug; Postgres has no such bug, but we keep a stable
-- non-zero UUID for consistency with the hosted path (which uses
-- JWT-derived UUIDs).
--
-- This tenant_id is used when the MCP server runs in stdio mode
-- (no auth, single-user) — set as the default in the contextvar in
-- mcp_server.py.
-- ---------------------------------------------------------------------

-- Liz's stable self-host tenant_id (deterministic; reproducible across
-- machines without state). Generated via:
--   python -c "import uuid; print(uuid.uuid5(uuid.NAMESPACE_DNS, 'liz.loom.humancensys.com'))"
-- Value: 1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8
--
-- Don't INSERT into a tenants table — we don't have one yet. The
-- tenant_id is a free-form UUID. A tenants table (with name, owner,
-- created_at) lands in Phase 3 when Project Registry needs it.

COMMIT;
