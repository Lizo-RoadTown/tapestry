# Master plan: the personal-layer working loop, M1 to M2

**Status:** active (adopted by the operator 2026-10-21; deployment decisions all-recommended, loom memory `decision-telemetry-deployment-all-recommended-2026-10-21`)
**Method:** this reconstruction runs under the [prototype reconstruction procedure](../prototype-reconstruction-procedure.md) (v0.1). Lead repository: **tapestry**. The step-1 scope record and step-10 reconstruction manifest live under `docs/reconstruction/` (being built in parallel; authoritative for full component records — this plan references them and does not duplicate them).
**Grounding:** [2026-10-21-fleet-reality-map.md](../architecture/2026-10-21-fleet-reality-map.md) §9 (the adopted sequence and the six requirements), [2026-10-21-telemetry-deployment-recommendation.md](2026-10-21-telemetry-deployment-recommendation.md), [2026-10-21-task-division-study.md](../architecture/2026-10-21-task-division-study.md), ADR-0001 (`docs/adr/0001-observer-topology.md`).

## The end goal (drift is measured against this paragraph)

A two-layer system of agents overseeing knowledge flow with the same decomposition. The **personal agent** (one person, many projects) completes the autonomous loop: capture with identity → persist → analyze → review → act, where act means diagnosis → build → validation → installation → subsequent evaluation, policy-gated — not filing a candidate for the operator to advance. The **program agent** (one project, many people) is the Lens, built on its own roadmap. Any task that does not shorten the path to the acceptance scenarios below, serve the program layer's own roadmap, or keep the two layers coherent is drift.

## Acceptance scenarios (procedure step 1; observable outcomes)

| id | Trigger | Expected outcome | Maps to |
|---|---|---|---|
| `skill-invocation-to-finding` (**M1**) | a real skill invocation in a registered project | the event is stored with its identity and produces an evidence-backed finding; missing identity, missing instrumentation, observed zero activity, and processing failure remain distinguishable | procedure step 6 exit check |
| `correction-to-installed-support` (**M2**) | a captured correction with its context (the tutoring correction) | the appropriate skill or hook is built, validated, installed, and a later session demonstrates the guidance loaded and followed; unsuccessful changes trigger revision or rollback | the procedure's own example scenario; steps 6.1–6.7 and the step-7 behavioral check ("skill creation alone does not establish behavioral success") |

Producing a finding or candidate is an intermediate state (procedure step 6): no extra user prompt advances routine authorized work; decisions outside established authority become explicit exceptions.

## Management method (procedure application)

- **Evidence states (step 2):** every component record carries separate `implementation_state`, `deployment_state`, `trigger_type`; **unknown is a valid state** and is never silently converted to working or absent. Every important output is traced to a reader; discarded outputs and missing transitions are marked.
- **Stable component IDs (step 3):** assigned now, below; they survive renames, moves, and consolidation. The manifest extends this register without renumbering.
- **Two decisions per component (step 4):** destination (retain / extract / consolidate / retire / defer) and implementation treatment (lift / refactor / rewrite / n/a), recorded separately.
- **Checkpoints (step 10):** workstream exits use stage states `pending / running / passed / failed / blocked / not_applicable` (reason required for not_applicable); no check is marked passed without execution; the executing session re-reads "The end goal" above before marking an exit passed.

## Component ID register (initial; full records in `docs/reconstruction/`)

Prefixes: `pl-` personal layer, `pr-` program layer (records owned by lens-core; listed for cross-reference only), `sh-` shared mechanics. Names are **provisional** (step 8: final names only after the full agreed decomposition is reconciled).

| ID | Provisional name | Responsibility | Disposition / treatment (today's decisions) |
|---|---|---|---|
| pl-001 | personal signal engine | classify stored telemetry into hot_path/orphaned/degrading signals | extract into toolkit as scale-neutral package / refactor; release the `project-observatory` name (alias until step-8 rename) |
| pl-002 | telemetry store | persist events + daily rollups; authenticated read API with the 0-vs-None contract | retain in tapestry / lift (deploy) |
| pl-003 | telemetry receiver | accept signed hook and skill-usage writes | consolidate: repoint `loom-telemetry-ingestion` to tapestry source, name preserved / lift |
| pl-004 | session capture | hook events at session time + local retry buffer + backfill | retain / refactor (fix flush default path; retention policy) |
| pl-005 | skill attribution | resolve each skill invocation to a stable artifact_ref at invocation time; unresolved visible | extract (new, in plugin) / rewrite |
| pl-006 | self-report | plugin scans its own repo's skills at session end and pushes inventory | extract (new, in plugin) / rewrite; harvest.py later consolidates into this |
| pl-007 | shape sweep | scheduled scan of repos with no recent self-report; synthesis memo | retain (self-observer cron) / refactor (staleness gate; stub swap) |
| pl-008 | memory | loom-memory MCP + database memory design | retain; moving to its own module per the Loom_MCP proposal (separate track) |
| pl-009 | candidate registry | candidate store + lifecycle + dispatch | retain (live, legacy name) / lift; schema merge with spine deferred (D2) |
| pl-010 | decision gate | operator review surface + immutable policy decisions + automation levels | retain / refactor (policy-daemon-activation design) |
| pl-011 | observation decomposer | read signals as evidence, emit candidates with recommended automation level | extract into its ratified home `services/observation-decomposer/` (ADR-0001) / rewrite |
| pl-012 | skill compiler loop | promotion dispatch → bridge → compile → ack | retain (live for kind=skill via Make_Skills) / refactor later (hook handler for M2) |
| pl-013 | personal console | visible status and evidence over the loop | retain / refactor (wire to pl-002) |
| sh-001 | decomposition method | the Surveyor procedure both layers share | retain in surveyor / n/a |
| sh-002 | equip | onboard + registry + launcher pattern (injected connection) | retain / refactor (absorb launcher pattern later) |
| pr-* | Lens modules (standard, intake, review, read side, exchange signals, oversight, tenancy) | program layer | owned by lens-core's records; not duplicated here |

## Workstreams

Owners: **TA** = tapestry agent sessions, **LZ** = Liz, **LC** = lens-core, **EL** = education-lab, **MS** = Make_Skills touch.

### A — Telemetry cutover (pl-002, pl-003; procedure steps 4–5 and 9)

| # | Item | Owner | Effort | Exit proof |
|---|---|---|---|---|
| A1 | First PR: read-auth on `/telemetry/*` (mirror agent-context bearer resolver, no anonymous branch), gated render block (raw connection string, sync:false), cutover runbook, `infra/migrations/APPLIED.md` ledger + README fix, tests for persist/read paths | TA | 1 session | PR green; auth rejects unauthenticated reads in tests |
| A2 | Apply Tapestry 005+006 to live loom-postgres; record in APPLIED.md | LZ (psql) | minutes | tables exist; ledger row with evidence |
| A3 | Provision env: `SELF_HOST_TENANT_ID` identical on writer/reader/cron, skill secret copied byte-identical, new hook secret minted, read key | LZ (Render) | minutes | env visible in service settings |
| A4 | Merge the-loom PR removing its telemetry render block (one-blueprint invariant); repoint `loom-telemetry-ingestion` to the tapestry repo, name and URL preserved | LZ | minutes | service builds from tapestry |
| A5 | Post-cutover smoke: POST a signed event, read it back authenticated; set `LOOM_INGEST_ENDPOINT` on this machine; fix flush default path; run backfill | TA | 1 session | a real session event retrievable; backfill re-run inserts 0 |

A1 starts immediately. A2–A4 wait on A1's merge. A5 closes wires X1 and X2.

### B — Identity in capture (pl-005, pl-006; requirement 1; procedure step 3's connection rule: "a delivered event with no usable artifact identity is not a working analysis input")

| # | Item | Owner | Effort | Exit proof |
|---|---|---|---|---|
| B1 | Skill attribution in the plugin (pl-005): stable artifact_ref at invocation time; unresolved events preserved and marked | TA | 1–2 sessions | an event with artifact_ref retrievable; an unresolved event visible as unresolved |
| B2 | Self-report in the plugin (pl-006): skills inventory at Stop in the existing POST | TA | same PR | inventory rows retrievable |
| B3 | Repoint the engine's `/skill-used` callback at the persisting receiver | TA + MS | small | engine batch lands in telemetry_events |

B1/B2 parallel with A2–A4; B3 after A4.

### C — Read + analyze (pl-007, pl-001, pl-013; wires X3, X4)

| # | Item | Owner | Effort | Exit proof |
|---|---|---|---|---|
| C1 | Swap pl-007's telemetry stub for the read API 0-vs-None; retarget base URL off the legacy default | TA | small | observed-zero vs never-instrumented distinguished |
| C2 | Run ONE classifier (hot_path) against the production store; prod render block for the cron (forces the pl-001 naming item in the language table); note the small-N percentile caveat | TA | 1 session | a finding links via artifact_ref + window to retrievable events |
| C3 | Wire pl-013 to the new store (the milestone's visibility clause) | TA | 1 session | captured/stored/analyzed/resulted visible for a chosen session |

C needs A5 + B1 data. **M1 (`skill-invocation-to-finding`) = A5 + B1 + C1 + C2 + C3 passed.**

### D — Act = the autonomous repair workflow (pl-011, pl-010, pl-012; requirement 4; procedure steps 6.3–6.7 and 7)

| # | Item | Owner | Effort | Exit proof |
|---|---|---|---|---|
| D1 | Build pl-011 in its ratified home (ADR-0001): signals as evidence → candidates with recommended automation level; slug→UUID, kind mapping, cross-run dedup | TA | multi-session | a qualifying finding becomes a deduplicated candidate with evidence |
| D2 | Policy-daemon-activation design (pl-010): activation within `max_auto_level`; validation, installation, subsequent evaluation; extend beyond kind=skill for hooks (pl-012) | TA, LZ gates | design + build | an approved change is installed without manual advance |
| D3 | M2 acceptance run (`correction-to-installed-support`): a tutoring correction flows capture → finding → built skill/hook → validated → installed → later session shows guidance followed (step-7 behavioral check, not file existence) | TA + EL | run | M2 criteria met without another user prompt |

D1 design can run parallel with C; D2 gated on Liz for automation levels; D3 last.

### E — Coordination

Repo briefs written into lens-core, education-lab, AWG, surveyor (`docs/handoffs/2026-10-21-two-layer-context-and-tasks.md` each, pointing at the procedure as the shared method, by versioned reference per its step 10); loom memory updated; live sessions messaged by the parent session. Exit proof: each repo's next session can state its layer and tasks without this session's context.

### F — The language standard (procedure step 8 governs)

Rules: (1) where the two systems conflict, the term is made unambiguous; (2) where the same function exists at different layers, the term is the SAME base word with a layer qualifier (`project-` / `personal-`) — this applies to provisional names now and final names later; (3) **final responsibility-based names are chosen only after the full agreed decomposition is reconciled** (step 8); until then, stable IDs + provisional names, with old-name aliases where compatibility requires; (4) the operator names things — this table proposes, she disposes; (5) before any rename executes, enumerate imports, routes, service names, persisted namespaces, telemetry labels, and consumers (step 8) — a display rename must not silently change data identity.

Provisional term table (IDs are the stable reference; names may change at step 8):

| Function (one prototype) | Program-layer instance | Personal-layer instance | Resolves |
|---|---|---|---|
| observatory — an agent's instrument over its scope | **project observatory** = the Lens (approved, observatories.md) | **personal observatory** (Tapestry builds it from Lens elements) | "Lens = interface" (superseded); layer confusion |
| signal engine (pl-001 / lens-observe) | project signal engine (lens-observe's instance) | personal signal engine; the `project-observatory` service name is released to the Lens layer, kept as an alias until the step-8 rename executes | the two-signal-engines conflict; one package, two instances |
| observer — never used bare | role names per ADR-0001: shape sweep (pl-007), session capture (pl-004), signal engine (pl-001), oversight (Lens slot) | same role names, layer-qualified when ambiguous | four things named "observer" |
| repo report | project shared-surface intake (lens-ingest) | **self-report** (pl-006, session time) + **sweep** (pl-007, stale repos only) | scan vs harvest; harvest.py consolidates into pl-006 |
| signal = evidence, never a proposal | same word, same meaning, both layers | same | signals ≠ candidates |
| candidate = a proposal for change | spine lifecycle words (candidates → decisions → verified) | registry lifecycle, same words | vocabulary aligns now; schema merge deferred (D2 open item) |

### G — Drift governance

The drift watcher is deployed (watches memory, commits, and plans against "The end goal" above; surfaces concerns as `drift-watch-*` memory records). Checkpoint rule in §Management method applies at every workstream exit.

## Critical path to M1

**A1 → (A2, A3, A4: Liz, minutes) → A5 → C1 → C2 → C3**, with **B1/B2 parallel to A2–A4** and B3 right after A4. Two to three agent working sessions plus Liz's four short operator actions. Workstream D is off the M1 critical path and proceeds in parallel as design.

## Sequence discipline

- No new deployed services before the loop works (module boundaries now, deployment boundaries later).
- Repoint, never duplicate; temporary copies need a named authority, transition plan, and removal condition (procedure step 4).
- Liz evaluates by seeing: each workstream exit produces something runnable or visible, not a document.
