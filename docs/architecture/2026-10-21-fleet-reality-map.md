# Fleet reality map: what actually runs, and the anatomy it maps onto

**Status:** current as of 2026-10-21
**Charts:** https://claude.ai/artifact/921QCC6UGYGXqPpvtmSbxV
**Evidence appendix:** [2026-10-21-task-division-study.md](2026-10-21-task-division-study.md) (per-repo task tables with file:line citations)
**Full mapping table:** `anatomy-mapping.md` in the 2026-10-21 session scratchpad; reproduced in compressed form below.

## 1. Running automatically right now

| Process | Where / trigger | What it concretely does | Output read by | Dead end |
|---|---|---|---|---|
| self-observer cron | Render `tapestry-self-observer-cron`, every 6h | reads file text of skills/agents across every registered repo (12 at first scan 2026-09-06); 11 drift rules | candidates → dashboard queue; memo → every SessionStart | usage lookup returns None (X4) — it never sees behavior |
| discipline hooks | every Claude session | snapshots + diffs, reminders, Stop audits, session reports committed (today: d342f9a), Skill counts → candidates | future sessions, dashboard | hooks.jsonl read by nobody; ingest POST inert — endpoint unset (X1) |
| loom-memory MCP | Render, always on | record/recall for every session | every agent session | — (the one fully closed loop) |
| candidate→decision→skill loop | registry + policy (legacy loom-* names) + dashboard + Make_Skills engine | Liz promotes/holds/rejects; promotion of kind=skill auto-dispatches; engine compiles + acks | Liz, registry | engine's usage telemetry → receiver, which verifies, logs, and discards (X2) |
| project-registry, docs-site, docs-mcp | Render + Vercel | fleet membership; docs for humans + agents | onboard, the cron, readers | — |

## 2. Supposed to run, currently not

- education-lab daily harvest Action (13:00 UTC): skips every day — `HARVEST_TOKEN` secret does not exist.

## 3. Built, dark

- Signal classifiers (hot_path/orphaned/degrading): staging only, autoDeploy off (X3). Nothing feeds them, nothing runs them.
- Telemetry persistence + read API: would store what the receiver discards and answer "0 uses vs never instrumented"; no deploy block.
- Tapestry skill-making bridge + compiler copy; `engine/` slots (local-observer, agency-to-structure, adapters) empty.

## 4. Only when Liz runs it

onboard (last: AWG 2026-10-20) · harvest.py · fleet.yaml edits · correction-triage (one triage logged) · compile_plugins.py (rules file only) · make-plugin / marketplace / PyPI publishes.

## 5. The map

See chart §5 (same content): sessions feed memory (read back), candidates (read by Liz), local jsonl (read by nobody), Grafana (viewable), and the inert ingest POST. The cron feeds candidates + memo. The dashboard feeds policy + the engine, which compiles skills and reports usage into the discarding receiver. The classifiers have no input and no runner. education-lab's loop runs entirely by hand: class repos → harvest → catalog → triage → PRs → education-plugins → class repos.

What is absent is the headline: **no arrow carries anything from sessions to any classifier.** The system sees files change; it does not see anyone work.

## 6. The anatomy matrix (organ × layer)

One agent anatomy — oversee knowledge flow with the same decomposition — instantiated per (layer, domain). Layer rule (Liz, 2026-10-21): education-lab is PERSONAL (its fleet is her class repos: one person, many projects, learning domain). The PROGRAM layer (one project, many people) is today only the approved Lens charter, PROVES first.

| Organ | Personal agent (one person, many projects) | Program agent (one project, many people) |
|---|---|---|
| EQUIP | onboard CLI + project-registry LIVE · templates · patterns plugin · edu settings rollout 7/9 | lens-core launcher CHARTER · access+tenancy repo MISSING (unnamed) |
| DECOMPOSE | SessionStart snapshots LIVE · fleet.yaml (education) DATA — Surveyor method + `architecture_snapshot.py` are the shared standard (BOTH-package) | decomposition.json DATA, nothing reads it yet |
| OBSERVE | hooks + Path A LIVE (event push inert X1) · self-observer cron LIVE (usage-blind X4) · harvest.py MANUAL, Action SKIPPED · receiver LIVE but discards X2 · lens-log LIVE (BOTH-package) | lens-ingest CHARTER · workflow-oversight repo MISSING |
| REMEMBER | loom memory LIVE (BOTH-package) · architecture-registry LIVE (legacy name) · catalog/harvest.json · learner rules (education) DATA · persist substrate DARK (BOTH-package) | spine CHARTER (roadmap phase B, "now") |
| SYNTHESIZE | synthesis memo LIVE · observatory console LIVE · classifiers DARK X3 (BOTH-package once packaged) · correction-triage MANUAL (education epistemics) | lens-observe CHARTER |
| GOVERN | dashboard + policy LIVE · CI gates LIVE · human-merged releases LIVE | lens-review CHARTER |
| CREATE | make-plugin LIVE · promotion→engine loop LIVE for kind=skill (legacy path) · Tapestry bridge+compiler DARK · compile_plugins + rule amendments MANUAL | undefined — whether the program agent creates plugins at all is open |
| DISTRIBUTE | marketplace+PyPI+docs LIVE · education-plugins LIVE | lens-serve CHARTER |

Reading: the personal agent is half-alive (every organ has something live, but OBSERVE→REMEMBER→SYNTHESIZE is severed at X1–X4). The program agent is all charter. education-lab is the proof the full anatomy works — operated by hand, for one domain, on the personal layer.

## 7. Gaps (organ × layer, from the mapping)

- PROGRAM: every organ is charter or missing; spine v1 (phase B) gates REMEMBER; lens-observe has no instance while the finished classifiers sit in Tapestry; CREATE/DISTRIBUTE beyond lens-serve undefined.
- PERSONAL: usage observation dead (X1, X4); event memory dead (X2 + no deploy); synthesis gated (X3); creation split between a live legacy path (skills only) and a dark Tapestry copy; engine slots empty.
- CROSS-LAYER: two launchers (onboard, lens-core) and three tenancy candidates unreconciled; four structure surfaces (Surveyor, snapshots, decomposition.json, fleet.yaml) not yet one standard; two candidate→decision stores (registry vs spine) claiming the same organ.

## 8. One package per organ

| Organ | Package once | Replaces |
|---|---|---|
| EQUIP | onboard + registry, absorbing the injected-connection launcher pattern; tenancy as shared module | manual setup; edu settings distribution |
| DECOMPOSE | Surveyor method + decomposition.json (declared) + architecture_snapshot.py (mechanical) | fleet.yaml's structural fields (its education content stays domain data) |
| OBSERVE | the plugin self-scans + self-reports each repo at session time (skills inventory + usage in the existing Stop-hook POST); the observer cron becomes the sweeper (scans only repos with no recent sessions) + synthesizer | the cron as primary scanner; harvest.py scanner + Action; the log-only receiver |
| REMEMBER | loom memory (knowledge) + persist substrate (events) + ONE candidate standard (D2: merge spine and registry) | catalog-as-store; dual candidate stores |
| SYNTHESIZE | signals.py classifiers packaged scale-neutral + memo-to-memory pattern; lens-observe = the program instance | a second signal engine; hand reports |
| GOVERN | policy audit + dashboard gate + the N-independent-sources rule generalized from correction-triage; lens-review = program instance | ad-hoc approvals |
| CREATE | registry dispatch → bridge → compiler + make-plugin scaffold | compile_plugins mechanics (education keeps payloads) |
| DISTRIBUTE | marketplace mechanics + version guards + docs/llms.txt/docs-mcp; domain marketplaces publish through it; lens-serve = program read surface | per-domain duplicated machinery |

## 9. ADOPTED (Liz, 2026-10-21; revised after skeptical review, verdict GO-WITH-CHANGES): the personal-layer working loop

One complete feedback loop, built from what exists: **Work → Capture → Persist → Analyze → Review → Apply → observe the result in later work**, with loom memory feeding work and a visible status/evidence surface. Setup, the working loop, supporting services (memory, decomposition, evidence, dashboard), and publishing are separate parts; the eight organs are a capability inventory, not one processing sequence. Package-once is a code-organization rule, not a deployment rule: module boundaries stay, deployment boundaries wait until the loop works.

An independent skeptical review (2026-10-21, full report in the session transcript) verified the pieces are real and schema-compatible — persist/dedup/HMAC/0-vs-None/classifiers all exist and agree — but found the plan as originally written would complete all five steps and still produce **zero findings**, because hook events carry no artifact identity while the read API and every classifier key on `artifact_ref` (hook_event_handler.py builds rows without it; signals.py excludes ''/NULL rows by design; the only artifact_ref-emitting sender, the engine's /skill-used, still POSTs to the legacy discarding receiver). The revised order fixes that, plus four more review findings.

Liz's six adoption requirements (2026-10-21) are binding and folded into the rows below; the verbatim record is loom memory `adoption-requirements-personal-loop-2026-10-21`.

Repair order (revised; each step has a required proof):

| Order | Work | Proof |
|---|---|---|
| 0. Deployment identity — assigned to the Tapestry session: investigate and recommend; Liz decides only consequence-bearing choices | Repoint, never duplicate: identify the intended database, migration ownership (incl. reconciling the colliding 005/006 numbering; no applied-state ledger exists), and service naming from existing configuration; resolve the `loom-telemetry-ingestion` collision (the-loom still deploys it autoDeploy:true) under the one-blueprint invariant | a concrete recommended arrangement delivered; Liz's decision recorded; migrations applied to the chosen DB |
| 1. Persist | Deploy Tapestry telemetry-ingestion (persist.py is genuinely idempotent; HMAC on both write routes); set `SELF_HOST_TENANT_ID` identically on writer, reader, and cron (fail-closed chain); authenticate the read routes before any public deployment (requirement, not an option; /telemetry/* is currently open); add tests (today: zero) | an accepted event can be retrieved afterward |
| 2. Deliver | Set `LOOM_INGEST_ENDPOINT` for the hooks (sender and receiver contracts already match, byte-compatible HMAC); delivery is **effectively-once** (DB-side dedup via stable uuid5 + ON CONFLICT), with **manual backfill** via flush_hooks_jsonl.py — fix its default path (misses project-local `.claude/logs/hooks.jsonl`); retention policy is new work | a real session event arrives and is deduplicated across a retry |
| 3. Identity — part of Capture (requirement 1) | Invocation capture resolves each skill invocation to a stable `artifact_ref` at the moment it runs (today a Skill call arrives as tool_name="Skill" with the name in free text). The plugin inventory establishes which skills exist; capture establishes which one actually ran. Unresolved events are preserved, and resolution failures are visible, never dropped. Repoint the engine's /skill-used callback at the persisting receiver | an event with its artifact_ref is retrievable; an unresolved event is visible as unresolved |
| 4. Read | Swap self-observer's telemetry_client None stub for the read API's 0-vs-None contract (interface maps cleanly); retarget its base URL off the legacy default | observed-zero vs never-instrumented distinguished on real data |
| 5. Analyze | Run ONE classifier (hot_path) against the production store — this forces the classifier home/rename decision (only staging blocks exist); note the small-N caveat: within-project percentile needs ~10+ distinct artifacts, which one person's early data may not have | a finding links back via artifact_ref + window to retrievable events |
| 6. Act = the autonomous repair workflow (requirement 4) | A qualifying finding triggers diagnosis → creation or modification of the needed structure → validation → installation → subsequent evaluation; filing a candidate for manual advance does not complete the workflow. The vehicle already has a ratified home: the **observation-decomposer** (ADR-0001, docs/adr/0001-observer-topology.md:22,29) reads signals as evidence and emits candidates with a recommended automation level; candidate state stays in architecture-registry; activation stays policy-gated. **No ADR amendment needed** (requirement 5 satisfied: the signals table keeps its pledge; a separate consumer initiates the workflow). To build: the decomposer itself (a named empty slot), slug→UUID resolution, kind mapping, cross-run dedup, and the deferred policy-daemon-activation design — noting only kind=skill has a destination handler today | a qualifying finding ends in an installed, validated change whose effect is observable in later activity |

Standing simplifications, amended per review: **two write contracts converge at the persist layer** (hooks/backfill vs engine batches — different routes, models, secrets); "one intake contract" is the target, not the present; Grafana keeps its parallel copy. One candidate+decision path for the personal layer = the existing registry + dashboard + policy, operated as repoint-never-duplicate (Tapestry's copies deploy only by repointing the same names at the same DB). Cron = reconciliation.

**Two milestones, verified separately (requirement 6):**

- **M1 — the loop sees.** A real skill invocation reaches storage with its identity and produces an evidence-backed finding. Acceptance: after working in any registered project, what was captured, whether it was stored, what analysis ran, and what resulted are all visible — missing data, unresolved identities, and failed delivery included. (The visibility clause requires the console/dashboard wired to the new store — named here, not presumed.)
- **M2 — the loop acts.** A captured correction produces and installs the appropriate skill or hook, and later activity demonstrates the new guidance was loaded and followed. **Acceptance scenario: the tutoring correction** — the system turns learning into durable behavioral support without requiring another user prompt. Target: working across two projects.

### Remaining open

1. **D2 standards question:** whether the spine's candidates→decisions→verified shape absorbs architecture-registry's schema (the personal layer runs on registry+dashboard meanwhile).
2. **Vocabulary + home + rename** for the classifier package; the project-observatory name goes to the Lens layer.
3. **Staged retirement** of education-lab's generic machinery as each loop stage becomes real; education keeps its domain data and payloads.
4. **Apply beyond kind=skill:** the dispatch→engine path compiles skills only; other improvement types are applied manually until extended.
5. **Program layer** stays with the Lens roadmap (spine v1, repo names, tenancy home) — plus the standing Phase 0 item: rotate the leaked PROVES service_role key.

## Sources

- anatomy mapping (fork agent, 2026-10-21): scratchpad `anatomy-mapping.md`
- per-repo evidence: [2026-10-21-task-division-study.md](2026-10-21-task-division-study.md)
- loom memory: two-level-agent-symmetry-2026-10-21 · feedback-show-what-is-actually-happening-2026-10-21 · feedback-two-layers-not-one-2026-10-21
- lens-core: observatories.md (approved), 2026-10-21 roadmap method proposal
