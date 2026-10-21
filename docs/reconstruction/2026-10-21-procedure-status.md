# Procedure status — two-layer-toolkit-2026-10

Against [../prototype-reconstruction-procedure.md](../prototype-reconstruction-procedure.md) v0.1. States: pending / running / passed / failed / blocked / in_progress (this report uses in_progress for partially evidenced steps; nothing unexecuted is marked passed).

| Step | State | Evidence | What remains |
|---|---|---|---|
| 1. Scope | in_progress | [2026-10-21-scope.md](2026-10-21-scope.md) (versioned; sources + revisions; authorization recorded) | Acceptance scenarios are defined but not yet executable; step 1 exits when `m1-skill-invocation-to-finding` can actually run |
| 2. Inventory | in_progress (largely done) | Three task inventories (2026-10-21 session scratchpad, summarized with citations in [../architecture/2026-10-21-task-division-study.md](../architecture/2026-10-21-task-division-study.md)); [../architecture/2026-10-21-fleet-reality-map.md](../architecture/2026-10-21-fleet-reality-map.md) traces outputs to readers and marks dead ends explicitly | Lens sibling repos inventoried at charter level only; the-loom self-observer double-blueprint runtime state is **unknown** (left unknown, not converted) |
| 3. Decompose by responsibility | in_progress | Anatomy mapping (organ × layer × domain, session scratchpad anatomy-mapping.md); 17 components with stable IDs and 8 connection records with contract fields in [manifest.yaml](manifest.yaml) | Contract fields for lesser connections; some inventory items (engine empty slots, deferred services) map to components but lack full contracts |
| 4. Dispositions | in_progress | manifest.yaml: 18/20 components have destination + treatment from 2026-10-21 decisions (IDs reconciled same day to the canonical pl-/sh-/pr- register; former component-NNN numbers retired unused) | Deferred with reasons: pl-009 (D2), pr-001 (lens-core-owned); open blockers: pl-001 home/rename (step 8), pl-012 canonical copy |
| 5. Contracts + incremental extraction | pending (first increment scoped) | The first extraction increment is scoped: read-auth + render block + runbook + APPLIED.md ledger for pl-002/pl-003 (adopted arrangement) | The PR itself |
| 6. Assemble a working workflow | pending | The required personal path is written into the plan (and matches the procedure's own step-6 path) | Wires X1–X4, identity-in-capture, one classifier run; exits at M1 |
| 7. Operational readiness | pending | Requirements defined in the scope record §Operational requirements | Exercised only after step 6 |
| 8. Finalize names | deliberately deferred (per procedure) | manifest.yaml: every component has a stable ID, provisional name, `final_name: null` | Names chosen only after the full agreed decomposition is reconciled; the operator names things |
| 9. Cut over and retire | pending | Authorized so far: only the the-loom PR removing its telemetry render block | Everything else requires new authorization (scope record §Authorization) |
| 10. Runnable + resumable records | in_progress | This directory: scope record + manifest + this status file; manifest follows the procedure's proposed shape | No runner exists (the procedure says so itself); checkpoints are manual for now |

## Pending item from the procedure itself

The procedure states its canonical home is the decomposition module and its Tapestry location is staging ([../prototype-reconstruction-procedure.md:7](../prototype-reconstruction-procedure.md)). Relocation to the Surveyor repo is **deferred and not performed** — the procedure is shared by versioned reference meanwhile; repos must not keep divergent copies (step 10).

## Reading order for a new agent

1. ../prototype-reconstruction-procedure.md (the method)
2. 2026-10-21-scope.md (what we are doing and under what authorization)
3. manifest.yaml (components, connections, decisions — the working record)
4. ../architecture/2026-10-21-fleet-reality-map.md (what actually runs)
5. ../plans/2026-10-21-master-plan-personal-loop.md (the execution plan)
