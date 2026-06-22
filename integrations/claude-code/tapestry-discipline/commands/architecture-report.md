---
description: Generate a fresh architecture snapshot + diff + narrative report for the current repo state. Runs the deterministic snapshot/diff scripts, then invokes the architecture-analyst subagent to interpret. Outputs land in docs/architecture-snapshots/.
argument-hint: []
---

Run the full architecture-snapshot pipeline and produce a fresh narrative report.

Steps:

1. Run `python scripts/architecture_snapshot.py` from the repo root. This writes `docs/architecture-snapshots/<timestamp>-snapshot.json` and `<timestamp>-snapshot.md`.

2. Run `python scripts/architecture_diff.py` from the repo root. This finds the two most-recent snapshot JSONs, diffs them, pulls git log between the SHAs, and writes `<timestamp>-diff.json` + `<timestamp>-diff.md`.

3. Invoke the `architecture-analyst` subagent with the three paths (snapshot.json, diff.json, diff.md) as input. The subagent reads them, PROBES the repo for verification, and writes `<timestamp>-narrative.md` with TL;DR + what-changed + why-it-matters + diagnosis + recommendations.

4. Show the user the three output paths and the TL;DR from the narrative.

Discipline:
- If the scripts fail (missing dependencies, broken file), surface the error to the user; do not retry without telling them.
- If the diff shows no changes (first snapshot or stable state), the narrative will be minimal — that's correct, not a failure.
- Do not modify any source files. This command is read-only on the codebase; it only writes to `docs/architecture-snapshots/`.
