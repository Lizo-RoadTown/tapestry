-- 007_init_candidates.sql
--
-- Architecture Registry candidate slice — the promotion-candidate store for
-- services/architecture-registry/ (migrated from the-loom, CORE DIRECTIVE 2).
--
-- ============================================================================
-- CONSOLIDATION NOTE — read before touching this file
-- ============================================================================
-- In the-loom this schema arrived in THREE migrations that evolved the
-- candidate_type CHECK over time:
--
--   the-loom/003_init_candidates.sql          -- table + 4-kind CHECK
--                                                ('skill','workflow','decision','pattern')
--   the-loom/005_alter_candidate_type.sql     -- rename to 4 kinds
--                                                ('skill','tool','architecture_pattern','service')
--   the-loom/006_expand_candidate_type_to_9_kinds.sql
--                                             -- 'tool'->'inline_tool' + expand to 9 kinds
--
-- Those numbers CANNOT be reused in Tapestry: infra/migrations/005 and 006 are
-- already taken (005_init_telemetry.sql, 006_init_observation_signals.sql). So
-- the candidate schema is renumbered to the next free Tapestry number: 007.
--
-- It is CONSOLIDATED into this single migration (not three renumbered files)
-- ON PURPOSE. The intermediate 4-kind CHECK from the-loom's 003/005 cannot be
-- safely replayed against the already-migrated live DB: the live loom-postgres
-- already holds 9-kind rows (e.g. candidate_type='inline_tool'), so a replayed
-- "ADD CONSTRAINT ... CHECK (candidate_type IN (<4 kinds>))" would either FAIL
-- validation on those rows or (worse) downgrade the constraint. Consolidating
-- straight to the terminal 9-kind state makes a fresh replay a NO-OP, not an
-- error — the safety property the migration MUST have.
--
-- ============================================================================
-- LIVE-DB STATE — this migration is for PARITY / FRESH DEPLOYS
-- ============================================================================
-- The deployed service `loom-architecture-registry` is LOAD-BEARING RIGHT NOW
-- against the shared loom-postgres: both observers POST candidates to it and
-- the dashboard reads/writes it. That live DB is ALREADY at the state this
-- file describes (the-loom migration 006 = the 9-kind CHECK).
--
-- Therefore, running this file against the LIVE DB must be a clean no-op:
--   - CREATE TABLE IF NOT EXISTS          -> table exists -> skipped
--   - CREATE INDEX IF NOT EXISTS          -> indexes exist -> skipped
--   - ENABLE/FORCE ROW LEVEL SECURITY     -> idempotent
--   - DROP POLICY IF EXISTS + CREATE      -> re-creates identical policies
--   - CREATE OR REPLACE FUNCTION          -> idempotent
--   - DROP TRIGGER IF EXISTS + CREATE     -> re-creates identical trigger
--   - the guarded constraint block below  -> re-asserts the SAME 9-kind CHECK,
--                                            all live rows already satisfy it
--
-- GATE BEFORE CUTOVER: verify the live DB's candidates_type_check matches the
-- 9 kinds below (and models.py CANDIDATE_TYPE) BEFORE repointing the Render
-- service at Tapestry. See services/architecture-registry/README.md "Cutover".
--
-- ============================================================================
-- Two-mode commitment
-- ============================================================================
-- Self-host: candidates land under the resolved SELF_HOST_TENANT_ID (env-driven
-- in Tapestry, falling back to the all-zeros UUID that the COALESCE default in
-- the RLS policies below also uses — so an unset GUC fails closed to that same
-- tenant). Hosted-multitenant: tenant_id comes from the JWT claim. RLS policies
-- enforce isolation identically either way.
--
-- Schema choices (unchanged from the-loom):
--   - CHECK constraints (NOT Postgres ENUMs) — easier to evolve.
--   - JSONB for evidence_refs + signals — shapes evolve with the observer.
--   - FK project_id -> projects(id) ON DELETE CASCADE (needs 002_init_projects).
--   - Cross-tenant FK guard at the app layer (main.py is_project_visible),
--     because Postgres FK validation bypasses RLS.
--
-- Apply order:  psql "$LOOM_DB_URL" -f 007_init_candidates.sql
--   Depends on 002_init_projects.sql (projects table + pgcrypto).
--
-- Idempotent: CREATE ... IF NOT EXISTS + DROP POLICY/TRIGGER IF EXISTS + a
-- guarded constraint (re)assertion. Safe to re-run against the live 9-kind DB.

BEGIN;

-- pgcrypto is created in 002_init_projects.sql; re-CREATE-IF-NOT-EXISTS here is
-- defensive so this script can run standalone.
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ---------------------------------------------------------------------------
-- candidates table (created directly at the terminal 9-kind CHECK)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS candidates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Which project this candidate emerged in. FK ensures we don't keep
  -- orphaned candidates after a project is deleted.
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  -- The .project-intelligence/ folder content hash that emitted this
  -- candidate. Empty string for Path B candidates (platform-generated).
  instance_id VARCHAR(128) NOT NULL DEFAULT '',

  -- Path A = local observer; Path B = platform observatory.
  source_path VARCHAR(8) NOT NULL,

  -- What KIND of structure the candidate represents (9-kind taxonomy).
  candidate_type VARCHAR(24) NOT NULL,

  -- draft -> observed -> recurring -> stable -> promotion_requested
  --                                          -> promoted | rejected
  status VARCHAR(24) NOT NULL DEFAULT 'draft',

  -- JSONB array of evidence pointers backing this candidate.
  evidence_refs JSONB NOT NULL DEFAULT '[]',

  -- JSONB object holding computed promotion-threshold signals.
  signals JSONB NOT NULL DEFAULT '{}',

  -- Tenant envelope. RLS reads current_setting('app.tenant_id').
  tenant_id UUID NOT NULL,

  -- Epoch seconds, same shape as projects.created_at.
  created_at DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()),
  updated_at DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()),

  CONSTRAINT candidates_source_path_check CHECK (
    source_path IN ('path_a', 'path_b')
  ),
  -- Terminal 9-kind taxonomy (the-loom 006). MUST match models.py CANDIDATE_TYPE.
  CONSTRAINT candidates_type_check CHECK (
    candidate_type IN (
      'skill',                  -- §4.1
      'inline_tool',            -- §4.2
      'external_tool',          -- §4.3
      'architecture_pattern',   -- §4.4
      'service',                -- §4.5
      'machine_support',        -- §4.6
      'process',                -- §4.7
      'agent',                  -- §4.8
      'orchestration'           -- §4.9
    )
  ),
  CONSTRAINT candidates_status_check CHECK (
    status IN (
      'draft', 'observed', 'recurring', 'stable',
      'promotion_requested', 'promoted', 'rejected'
    )
  )
);


-- ---------------------------------------------------------------------------
-- Guarded constraint (re)assertion — parity safety net
-- ---------------------------------------------------------------------------
-- On a FRESH deploy the CREATE TABLE above already installed the 9-kind CHECK,
-- so this block is redundant-but-harmless. On a PRE-EXISTING table whose
-- candidates_type_check somehow differs (defense-in-depth; the live DB is
-- already 9-kind so this is a no-op there), re-assert the canonical 9-kind
-- constraint. This is SAFE against the live DB because every live row already
-- satisfies the 9-kind set — unlike replaying the-loom's intermediate 4-kind
-- ALTER, which would reject 'inline_tool' rows.
DO $$
BEGIN
  ALTER TABLE candidates DROP CONSTRAINT IF EXISTS candidates_type_check;
  ALTER TABLE candidates ADD CONSTRAINT candidates_type_check CHECK (
    candidate_type IN (
      'skill',
      'inline_tool',
      'external_tool',
      'architecture_pattern',
      'service',
      'machine_support',
      'process',
      'agent',
      'orchestration'
    )
  );
END $$;


-- ---------------------------------------------------------------------------
-- Indexes (dominant query patterns)
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS candidates_tenant_status_idx
  ON candidates (tenant_id, status);

CREATE INDEX IF NOT EXISTS candidates_tenant_project_idx
  ON candidates (tenant_id, project_id);

CREATE INDEX IF NOT EXISTS candidates_tenant_source_idx
  ON candidates (tenant_id, source_path);

CREATE INDEX IF NOT EXISTS candidates_created_at_idx
  ON candidates (created_at DESC);

CREATE INDEX IF NOT EXISTS candidates_signals_gin
  ON candidates USING gin (signals jsonb_path_ops);


-- ---------------------------------------------------------------------------
-- Row-Level Security — same envelope as projects + records
-- ---------------------------------------------------------------------------

ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidates FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS candidates_tenant_read ON candidates;
CREATE POLICY candidates_tenant_read ON candidates
  FOR SELECT
  USING (
    tenant_id = COALESCE(
      NULLIF(current_setting('app.tenant_id', true), ''),
      '00000000-0000-0000-0000-000000000000'
    )::uuid
  );

DROP POLICY IF EXISTS candidates_tenant_insert ON candidates;
CREATE POLICY candidates_tenant_insert ON candidates
  FOR INSERT
  WITH CHECK (
    tenant_id = COALESCE(
      NULLIF(current_setting('app.tenant_id', true), ''),
      '00000000-0000-0000-0000-000000000000'
    )::uuid
  );

DROP POLICY IF EXISTS candidates_tenant_update ON candidates;
CREATE POLICY candidates_tenant_update ON candidates
  FOR UPDATE
  USING (
    tenant_id = COALESCE(
      NULLIF(current_setting('app.tenant_id', true), ''),
      '00000000-0000-0000-0000-000000000000'
    )::uuid
  );

DROP POLICY IF EXISTS candidates_tenant_delete ON candidates;
CREATE POLICY candidates_tenant_delete ON candidates
  FOR DELETE
  USING (
    tenant_id = COALESCE(
      NULLIF(current_setting('app.tenant_id', true), ''),
      '00000000-0000-0000-0000-000000000000'
    )::uuid
  );


-- ---------------------------------------------------------------------------
-- updated_at trigger — keep the timestamp current on UPDATE
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION candidates_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = EXTRACT(EPOCH FROM NOW());
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS candidates_updated_at_trigger ON candidates;
CREATE TRIGGER candidates_updated_at_trigger
  BEFORE UPDATE ON candidates
  FOR EACH ROW
  EXECUTE FUNCTION candidates_set_updated_at();


COMMIT;
