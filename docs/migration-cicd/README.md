# Migration CI/CD — Tapestry

The complete documentation set for migrating capabilities from legacy source repos (`the-loom`, `Make_Skills`, future client repos) into Tapestry safely, repeatably, and reusably.

## Why this exists

Liz: *"I want full documentation and diagrams and I want plans, even if it requires creating another module, or even if it doesn't. I want it to be robust because I think we will need to migrate to new clients or new projects more than just this once."*

Result: a 4-document plan + a designed-but-not-yet-built reusable module (`packages/migration-toolkit/`). Every artifact is designed to be COPIED into a fresh Tapestry-fork for the next client migration with minimal customization.

## Doctrine anchor

Every doc here defers to **`docs/playbook/migration/00-doctrine.md`** and the **6 binding framing rules at the top of `docs/architecture/UMBRELLA.md`**. When a doc here disagrees with the doctrine, the doctrine wins.

## The four documents

| # | Document | What it covers |
|---|---|---|
| 01 | [Pipeline architecture](./01-pipeline-architecture.md) | GitHub Actions workflows for migration PRs, staging environments, parity gates, deployment phases, rollback procedure, secrets management, PR template |
| 02 | [Testing strategy](./02-testing-strategy.md) | The 4 test categories every migration must pass (contract, behavior parity, E2E smoke, rollback verification), the **drift-catcher** test that would have caught all 3 spec drifts at CI time, the golden-payload corpus + continuous-parity scheduling |
| 03 | [Migration toolkit module design](./03-migration-toolkit-design.md) | Reusable `tapestry-migrate` Python package + CLI + GitHub Actions templates at `packages/migration-toolkit/`. Designed to ship to future client-forks via `pip install tapestry-migrate` |
| 04 | [Runbook template](./04-runbook-template.md) | Standardized state machine + filled-out-able template every migration step uses. Same shape for every step makes parallel migrations reviewable |

## Quick reads by role

- **Operator (Liz)**: read [04-runbook-template.md](./04-runbook-template.md) §1 (state machine) + §5 (canonical-gate) + §6 (archive-gate). That's the decision surface.
- **Tapestry-agent (when spawned)**: read all 4 end-to-end. You own the migration choreography.
- **Source-stewards (MS-agent, Loom-agent)**: read [01](./01-pipeline-architecture.md) §7 (PR template) + [02](./02-testing-strategy.md) §1 (contract tests) — that's what you ship.
- **Future you (different client migration)**: read [03](./03-migration-toolkit-design.md) §1 (where it lives) + §9 (v0.1.0 / v0.2.0 / v1.0.0 roadmap). Copy + customize.

## What the plan asserts (the contract)

1. **No migration PR merges without all 4 test categories green.** (testing strategy §non-negotiables)
2. **Every production drift becomes a fixture in `tests/fixtures/golden/<contract>/invalid/<reason>/`** in the same PR that fixes it. (testing strategy §non-negotiables)
3. **The drift-catcher is a cross-repo required check.** Either side updating its model alone fails the check until the other side aligns. (testing strategy §non-negotiables)
4. **Rollback verification is part of CI, not part of "incident response."** A migration without a tested rollback is one-way; operator must approve one-way explicitly. (testing strategy §non-negotiables)
5. **Tapestry is the canonical product system; the source prototype is frozen at the `parity-verified → prod-rolling` transition.** (runbook §5)
6. **Source repo is archived only after every per-subsystem runbook reaches `complete` + 30 days of zero traffic.** (runbook §6)
7. **The toolkit ships as `tapestry/packages/migration-toolkit/`, not a separate repo.** Distributable as `pip install tapestry-migrate` from a private index. (toolkit §1)
8. **Per-client customization for future migrations lives in 3 files only:** `docs/migration/legacy-repo-inventory.md`, `docs/migration/import-map.md`, `infra/deploy/service-manifest.yaml`. (pipeline §reuse)

## State of execution

Status (2026-06-13): **plan complete; nothing built yet.**

| Artifact | Status |
|---|---|
| Pipeline workflows (`.github/workflows/migration-*.yml`) | Designed (doc 01). Not implemented. |
| Parity harness (`tools/parity/`) | Designed (doc 01 §3). Not implemented. |
| Test scaffolding (`tests/contract/`, `tests/parity/`, `tests/drift_catcher/`, `tests/fixtures/golden/`) | Designed (doc 02). Not implemented. |
| Migration toolkit package (`packages/migration-toolkit/`) | Designed (doc 03). v0.1.0 scope = 3 PRs (toolkit §9). |
| Runbook template (`docs/migration-cicd/runbooks/NN-<slug>.md`) | Designed (doc 04). No runbooks filled yet. |
| Migration PR template (`.github/PULL_REQUEST_TEMPLATE/migration.md`) | Designed (doc 01 §7). Not committed. |

## Immediate next steps (proposed)

In sequence:

1. **Operator review** of all 4 docs. Push back on anything overscoped or under-scoped.
2. **ADR opened** at `docs/adr/0001-migration-cicd-framework.md` ratifying the plan.
3. **First skeleton PR**: `.github/workflows/migration-pr-shape.yml` + `.github/PULL_REQUEST_TEMPLATE/migration.md` + `docs/adr/0001-*.md`. Smallest viable concrete step. ~1 day.
4. **First contract test scaffold**: `tests/contract/agent_context/test_mcp_invariants.py` against the existing live `loom-agent-context.onrender.com` MCP. Validates the testing strategy is workable before any code migrates.
5. **Migration toolkit v0.1.0** scoped per [toolkit doc §9](./03-migration-toolkit-design.md#9-first-3-prs-roadmap) — 3 PRs.
6. **First real migration step** (per the canonical-framing memo's PR-prep-2 + Step 1): `agent-context` lift, using the toolkit's v0.1.0 + the runbook template.

## Reusability for future client migrations

When a new client appears wanting their own Tapestry-shape platform:

1. Their repo is `fork(tapestry)` OR `Lizo-RoadTown/<client>-tapestry`.
2. Replace `docs/migration/legacy-repo-inventory.md` with their inventory.
3. Replace `docs/migration/import-map.md` with their import map (initially empty).
4. Replace `infra/deploy/service-manifest.yaml` with their service types.
5. Everything else — workflows, toolkit, doctrine, runbook template, drift-catcher, golden corpus framework — copies as-is.

The 4 documents here, the 5 playbook entries at `docs/playbook/migration/`, and the (designed) migration toolkit package together form a **template kit** that turns future client migrations from one-off engineering into a repeatable process.

## Related

- `docs/playbook/migration/00-doctrine.md` — the binding rules every doc here defers to
- `docs/playbook/migration/{01,02,03,04}-*.md` — five real-world patterns that informed this design (spec drift, UUID mismatch, auth duplication, cron orphans)
- `docs/architecture/UMBRELLA.md` — the destination architecture (where migrations land)
- `docs/migration/{README,legacy-repo-inventory,import-map,what-to-keep,what-to-retire,naming-corrections}.md` — the operator-authored migration state
- `docs/proposals/2026-06-13-v1-scope-and-roadmap.md` — the v1 scope this migration framework executes against
- loom-memory `tapestry_canonical_framing_applied_2026_06_13` — the binding framing
- loom-memory `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13` — the rulebook
