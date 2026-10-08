---
date: 2026-10-07
kind: fix
area: tapestry-patterns
prs: []
adrs: []
memory: bug-architecture-snapshot-render-yaml-path-wrong
supersedes:
---

# Architecture snapshot now finds the Render Blueprint

**What:** `parse_render_yaml` in `integrations/claude-code/tapestry-patterns/scripts/architecture_snapshot.py` only looked for `render.yaml` at the repo root, but Tapestry's Blueprint lives at `infra/deploy/render.yaml`. It now checks the repo root first (the Render convention), then `infra/deploy/`, first hit wins, and records which path it found in the snapshot (`render.path`). Bumped `tapestry-patterns` 0.1.6 → 0.1.7 in both `plugin.json` and `marketplace.json`.

**Why it matters:** The session-start architecture snapshot had been reporting `render.present: false` every session, so the diff was blind to every Render/service change — the exact dimension the pipeline exists to track. With the fix, the snapshot sees all five declared services (agent-context, project-registry, project-observatory web + cron, self-observer cron).

**Verification:** `parse_render_yaml(Path("."))` against the tapestry repo now returns `present: True`, `path: infra/deploy/render.yaml`, and the five service names. `scripts/check_plugin_versions.py` reports both plugins aligned.

**Follow-up:** Re-run the snapshot against current HEAD so future diffs have a non-stale baseline (the session-start snapshots had been taken from a stale git_sha as well).
