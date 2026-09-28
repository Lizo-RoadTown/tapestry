---
date: 2026-09-27
kind: chore
area: docs
prs: []
adrs: []
memory:
supersedes:
---

# Reconcile stale status across reference docs

**What:** Corrected reference docs that still described built or populated components as empty scaffolds/slots. `services/project-observatory/README.md` now reads "Built — not yet deployed" (signal computation, materialization entrypoint, and read endpoint all present with tests), not "Scaffold". `infra/deploy/README.md` and `infra/docker/README.md` now document the present `render.yaml` Blueprint and the local Loki/Promtail/Grafana docker-compose stack instead of "Slot. No code yet." The root `README.md` services section was rewritten into a live / code-present / slot split (only `audit-log` and `candidate-registry` are truly slot-state), the file-tree labels were corrected, and the "Relationship to other repos" section was reworded to align with CORE DIRECTIVE 2 (the-loom and Make_Skills are retired legacy source repos, not active parallel builds). Added the shipped `tapestry make-plugin` command to `packages/cli/README.md`. Fixed an env-group naming inconsistency in the Render setup guide (`tapestry-shared-secrets`). Added `docs/README.md` as an index of the `docs/` tree.

**Why it matters:** The docs overstated how much was still unbuilt and, in one place, contradicted CORE DIRECTIVE 2 by describing the retired legacy repos as an intentional parallel build. Reconciling the status prevents that drift from misleading future work.

**Follow-ups / gates:** none. `tapestry deploy` how-to and 401-auth-recovery content are intentionally out of scope (gated on other PRs).
