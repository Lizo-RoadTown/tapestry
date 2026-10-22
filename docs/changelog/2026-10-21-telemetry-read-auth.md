---
date: 2026-10-21
kind: feature
area: services/telemetry-ingestion
prs: [184]
memory: [decision-telemetry-deployment-all-recommended-2026-10-21, adoption-requirements-personal-loop-2026-10-21]
---

# Telemetry reads authenticated; deploy block, cutover runbook, migrations ledger (A1)

**What:** Every `/telemetry/*` read route now requires a bearer credential (`TAPESTRY_TELEMETRY_READ_KEY` or an RS256 JWT with a `tenant_id` claim); no anonymous read path exists. The service gets its first tests (12, offline, covering auth, tenant isolation, and the 0-vs-None contract), a CI leg, a gated repoint block in `infra/deploy/render.yaml` (service name `loom-telemetry-ingestion` preserved), the cutover runbook `docs/migration-cicd/runbooks/05-telemetry-ingestion.md`, and the migrations ledger `infra/migrations/APPLIED.md`.

**Why it matters:** This is workstream A1 of the personal-loop master plan — the agent-side half of the telemetry cutover. Once the operator steps in runbook 05 run (apply 005/006, provision env, repoint), events stop being discarded and the path to milestone M1 opens.

**Follow-ups / gates:** operator steps A2–A4 per runbook 05; nothing deploys from this change until those gates pass.
