# Skill-vs-agent conversion + self-observer (REVISED)

**Date:** 2026-06-13 (revision 2 — same day; supersedes earlier revisions in this file)
**Status:** Plan awaiting second verification + operator approval
**Triggered by:** Operator prompt asking which `docs-agent/skills/` entries are mislabeled as skills when they're actually agents-with-tools. This question should have surfaced automatically as candidates in the candidate-registry. It did not. This plan addresses both the immediate conversion AND the upstream observer gap.

## Revision history (this file)

- Rev 1 — initial plan: SessionStart-hook-based observer + 8 conversions in arbitrary order
- **Rev 2 (current):** cloud-Docker-on-Render observer (not hook-based, per operator constraint *"must be automated and not inside a repo or specific project"*); execution order REVERSED so observer is built first and validates the manual classifications; 8 verifier findings folded in; explicit legacy-repo-as-source framing throughout

## Controlling rules (binding for this plan)

1. **The observer is a cloud service** — Docker image deployed on Render, runs on a schedule, scans all platform-owned repos via the GitHub API. NOT a hook inside any discipline plugin.
2. **The work happens in legacy source repos** (`the-loom/`, `Make_Skills/`, `docs-agent/`, `claude-skills-marketplace/`) BEFORE Tapestry migration. Per `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13`, Tapestry is the destination; today's authoring lands in legacy repos.
3. **Every artifact authored gets a `migration_destination:` frontmatter** so the eventual Tapestry migration session has no reclassification cost.
4. **Observer is built FIRST, conversions SECOND** — the observer's first run validates (or contests) the manual classification. Disagreements get operator review before conversions land.

## Part 1 — The 16 items in `docs-agent/skills/`, classified

PROBE'd 2026-06-13 by reading the `description:` field of each `SKILL.md`. Verdicts:

### Group A — Stay as SKILLS (6 items, pure methodology)

| Skill | Why it stays | Migration destination |
|---|---|---|
| `agentic-skill-design` | Meta-skill about how skills should behave. Methodology. | `tapestry/engine/skills/agentic-skill-design/` |
| `deep-research-pattern` | Pattern doc for HOW to build research agents. Teaches structure, doesn't BE one. | `tapestry/engine/skills/deep-research-pattern/` |
| `documentation` | Diátaxis framework + docs-as-code methodology. | `tapestry/engine/skills/documentation/` |
| `layered-explanation` | "Use BEFORE every explanation" — output-shape rule. | `tapestry/engine/skills/layered-explanation/` |
| `open-source-documentation` | OSS docs methodology. | `tapestry/engine/skills/open-source-documentation/` |
| `proposal-authoring` | "Author a design proposal in [house] style — fixed section layout" — template-following. | `tapestry/engine/skills/proposal-authoring/` |

### Group B — Stay as skill but mark agentic-pattern (1 item)

| Skill | Why marked | Migration destination |
|---|---|---|
| `design-evaluation` | Produces a tradeoff matrix, but the parent agent benefits from the evaluation context (user is asking "which approach"). Apply the agentic-skill-design PROBE→DECIDE→ACT→REPORT pattern; keep as skill. | `tapestry/engine/skills/design-evaluation/` |

### Group C — Convert to AGENTS (8 items)

For each: author the agent file, leave a thin skill stub with frontmatter `redirect_to:` pointing at the new agent, mark sunset date matching Tapestry migration of that capability.

| Skill → Agent | Migration destination |
|---|---|
| `agentic-upskilling` | `tapestry/services/self-observer/` (this IS the observer; lives as a deployed cloud service, not just an agent file — see Part 3) |
| `eval-deep-research` | `tapestry/engine/agents/eval-deep-research.md` |
| `infrastructure-mapping` | `tapestry/engine/agents/infrastructure-mapping.md` |
| `lessons-learned` | `tapestry/engine/agents/lessons-learned.md` |
| `next-actions-planning` | `tapestry/engine/agents/next-actions-planning.md` |
| `orchestration-cataloging` | `tapestry/engine/agents/orchestration-cataloging.md` |
| `roadmap-maintenance` | `tapestry/services/roadmap/` + `tapestry/engine/agents/roadmap-maintenance.md` (agent lives in engine, tools live in service — per verifier finding #1, tools already exist in `Make_Skills/services/admin/roadmap/tools.py`) |
| `web-app-scaffold` | `tapestry/engine/agents/web-app-scaffold.md` |

### Group D — Convert to TOOL (1 item)

| Skill → Tool | Why | Migration destination |
|---|---|---|
| `document-parsing` | Pure file format conversion, no reasoning. | `tapestry/packages/tools/document-parsing/` (or as `tapestry/integrations/mcp/document-parsing-mcp/` if exposed via MCP) |

### Net (unchanged from rev 1)

- 6 stay as skills
- 1 stays as skill with agentic-pattern annotation
- 8 become agents
- 1 becomes a tool

## Part 2 — Verifier findings folded in (rev 1 → rev 2)

| # | Finding | How folded |
|---|---|---|
| 1 | roadmap-maintenance tools exist at `Make_Skills/services/admin/roadmap/tools.py`, not docs-agent | Agent migration destination split: agent lives in `tapestry/engine/agents/`, tools live in `tapestry/services/roadmap/`. Today's source-repo work: agent authored in `Make_Skills/agents/roadmap-maintenance.md` (close to existing tools), skill stub in `docs-agent/skills/roadmap-maintenance/` redirects there. |
| 2 | Self-observer would recurse on itself; dedup hole | Observer skips its own scan target by name. Candidate identity = `content_hash(SKILL.md|agent.md frontmatter + body)`. Duplicate-across-repos at migration cutover dedups via content_hash, not by path. |
| 3 | Skill bodies don't translate cleanly to system prompts | New step E0.5 (per-skill triage) BEFORE any conversion: each Group C body classified as {agent-voiced / human-conceptual / cross-skill-reference}. Each category gets a different system-prompt scaffold; cross-skill references resolve by inlining the referenced skill's relevant lines. |
| 4 | Stub-file rot — N permanent stubs | Skill stubs get `redirect_to: <agent-path>` frontmatter + `sunset_date: 2026-09-30` (Tapestry migration cutover). At cutover, the migration session deletes all stubs in one pass. |
| 5 | SessionStart cost | MOOT — observer is no longer hook-based. |
| 6 | Asymmetry — only upgrade signals | Observer's signal rules include DEMOTION path: an `agents/` entry whose description is methodology-shaped emits `agent → skill` candidate; tool→skill same way. Long-term, structure ratchets in both directions, not one. |
| 7 | Order of operations | REVERSED. Build observer first (E2). First run validates manual classification (E3). Disagreements go to operator (E4). Conversions land based on the validated classification (E5+). |
| 8 | Tapestry destinations missing | Every artifact gets `migration_destination:` frontmatter (table above + every new file in this plan). |

## Part 3 — The cloud self-observer (the missing infrastructure)

### Why a cloud service, not a hook

Per operator directive *"must be automated and not inside a repo or specific project"*:

- **Coverage**: hooks fire only when a developer starts a session. Weekends, focused-elsewhere days, vacation = no observation. A cloud cron observes every interval regardless of who is working.
- **Cost attribution**: hook runs in developer's session context → token cost lands on the session. Cloud service has its own LLM budget tracked separately, with its own quota.
- **Scope**: hook inside `tapestry-discipline` only sees what the active session's repo gives it. A cloud observer queries GitHub for all platform-owned repos without being inside any of them.
- **Rule that generalizes:** any "observer" or "discipline check" capability that produces candidates / surfaces drift / runs continuously belongs in a deployed cloud service, NOT a developer-session hook. Hooks are for interactive guardrails (per-response checks). Cloud services are for continuous observation.

### Concrete shape

**Service:** `self-observer` (legacy-source name during transition; eventual Tapestry destination `tapestry/services/self-observer/`)

**Runtime:** Python cron on Render. Pattern lifted from commit `2731822`'s post-state — the `loom-keep-warm` cron is the working precedent:

```yaml
- type: cron
  name: loom-self-observer
  runtime: python
  schedule: "0 */6 * * *"           # every 6h
  buildCommand: pip install -r services/self-observer/requirements.txt
  startCommand: python services/self-observer/main.py
  plan: starter                       # free tier rejects cron jobs (per 2731822 commit body)
  envVars:
    - key: GITHUB_TOKEN
      sync: false                     # secret, set in Render dashboard
    - key: CANDIDATE_REGISTRY_URL
      value: https://loom-architecture-registry.onrender.com
    - key: TELEMETRY_QUERY_URL
      value: https://loom-telemetry-ingestion.onrender.com
```

**Docker portability deferred to v2.** Verifier confirmed no working `type: cron` + `runtime: docker` example exists in either repo. `Make_Skills/render.yaml:5-11` is `type: web` (long-running), not cron. Python-cron is what ships day-one. Containerization for customer self-host comes when Tapestry's `infra/docker/` slot gets a real Dockerfile (separate scope).

**Schedule:** every 6h via the `schedule:` field above. Pattern verified against `2731822` post-state (the `+` diff lines, NOT the `-` deleted lines).

**What it scans on each fire:**

1. GitHub API call: list contents of `skills/`, `agents/`, `tools/` (and any equivalent dirs) across registered platform-owned repos: `the-loom`, `Make_Skills`, `docs-agent`, `claude-skills-marketplace`, `tapestry` (once it has them).
2. For each entry: read frontmatter + first 100 lines of body. Compute `content_hash`.
3. Run signal-detection rules:
   - **Agent signals**: description contains verbs like "probes", "produces", "executes", "scaffolds", "walks", "scans", "runs the X harness", "observes... identifies... promotes". Output → candidate of kind `agent` if current location is `skills/`.
   - **Tool signals**: description is a pure input→output transform ("convert X to Y", "validate X against Y schema"). Output → candidate of kind `inline_tool` if current location is `skills/`.
   - **Skill signals (demotion)**: description starts with "Use BEFORE every X" / "Use when authoring Y" / template-following language. Output → candidate of kind `skill` if current location is `agents/` or `tools/`.
4. Read telemetry from `loom-telemetry-ingestion` for invocation count over last 30 days. Zero-invocation entries → candidate of kind `process` with `outcome: archive_suggestion`.
5. Dedup against open candidates by `content_hash`. Skip self (the observer's own agent file).
6. POST candidates to `https://loom-architecture-registry.onrender.com/candidates/` using the EXISTING `models.CandidateCreate` schema (`the-loom/services/architecture-registry/models.py:31, 68`):
   - `source_path: "path_b"` — the existing platform-observatory discriminator value, since self-observer IS platform-observatory work (`models.py:69` defines path_b as "platform observatory")
   - `candidate_type`: one of the 9 taxonomy values (`agent`, `inline_tool`, `skill` for demotion, `process` for orphan/never-invoked)
   - `evidence_refs`: array including `{kind: "self_observation", source_repo: "...", file_path: "...", description_text: "...", signal_match: "...", telemetry_30d_invocations: N}` — the "this came from self-observer" detail rides in evidence, not in the discriminator
   - **Auth**: JWT Bearer via `Authorization: Bearer <token>`. In self-host mode (no Authorization header), `auth_bridge.verify_bearer` at `auth_bridge.py:81-100` returns SELF_HOST_TENANT_ID. For day-one development the observer can run without auth. For production: a service-account JWT minted with the loom-side signing key + a `tenant_id` claim. Token comes from a Render env var `OBSERVER_JWT` (set via dashboard, `sync: false`).
   - **NOT HMAC**. HMAC is the engine-side bridge auth (`/skill-registered` endpoint), a different mechanism. Earlier draft of this plan got the mechanism wrong.
7. Operator sees candidates in the upskilling dashboard, clicks promote / hold / reject. Promotions dispatch through the existing bridge (already smoke-verified 2026-06-13 07:09 UTC).

### What lives where during build

- **Source code authored today**: `the-loom/services/self-observer/` (legacy source repo). Python service, Dockerfile, render.yaml block, GitHub API client, signal-rule module, candidate-emission client.
- **Tapestry destination**: `tapestry/services/self-observer/`. Migrates per the canonical-Tapestry framing once the service is stable + bridge is green for `kind=agent` candidates.

## Part 4 — The infrastructure gap this surfaces (lesson-shaped)

The platform observes consuming projects via `local-observer`. It does not observe ITSELF. Categories that have been silent because of this:

- **Skill that should be an agent** — the immediate trigger
- **Skill that should be a tool** — same gap, less common
- **Agent that should be a skill** — over-engineering drift (the demotion path)
- **Orphan skill never invoked** — telemetry-zero entries
- **Duplicate skill across registries** — same `content_hash` in N places, only one should be canonical
- **Skill whose description has drifted from its body** — signal mismatch between frontmatter and content
- **Plugin hook authored without corresponding cloud-service backend** — the deepest version of the same drift (this very plan's discovery)

Each is a candidate kind already supported by the 9-kind taxonomy or a new sub-kind. The observer surfaces all of them.

This is captured separately as a playbook chapter (`tapestry/docs/playbook/migration/05-cloud-observer-vs-developer-hook.md`) in E7 below, plus a `lesson_` memory in E6.

## Part 5 — Reversed execution plan

In order, smallest commits first. Each step is a separate PR.

### E0 — MS-agent memo (immediate)

Write `ms_agent_notice_self_observer_and_skill_to_agent_conversions_2026_06_13` to loom-memory. Notify MS-agent that:
- 8 skills in docs-agent are being promoted to agents
- `roadmap-maintenance` agent will be authored in Make_Skills (not docs-agent) because tools at `Make_Skills/services/admin/roadmap/tools.py:*` already exist there
- Self-observer service is being scaffolded in the-loom as legacy source
- All artifacts land in legacy repos per the canonical-Tapestry framing; Tapestry migration of these is a future step
- Asks for any pushback on the migration_destination column above

### E0.5 — Per-skill triage (immediate)

For each Group C entry, read its full SKILL.md body (not just frontmatter). Classify each paragraph as:
- **Agent-voiced** (lift verbatim into system prompt)
- **Human-conceptual** (drop or transform into "your context" framing in system prompt)
- **Cross-skill-reference** (inline the referenced skill's relevant lines, or strip the reference)

Triage output is a single doc `docs-agent/agents/_triage-2026-06-13.md` capturing the classification per skill. Drives E5 (agent authoring).

### E1 — Scaffold self-observer service skeleton in the-loom

In `the-loom/services/self-observer/` (NEW DIRECTORY — does not exist; first commit creates it):

- `requirements.txt` — `httpx` (GitHub API), `pydantic` (models), `pytest` (tests). Stdlib `urllib` for the candidate POST (mirrors `2731822` keep_warm.py stdlib-only pattern).
- `main.py` — entrypoint; orchestrates scan loop
- `github_scanner.py` — walks platform-owned repos via GitHub API
- `signal_rules.py` — agent/tool/skill detection regex + scoring; the load-bearing module
- `candidate_client.py` — POSTs to architecture-registry using the validated `CandidateCreate` schema (path_b discriminator, evidence_refs detail, JWT Bearer auth with self-host fallback)
- `telemetry_client.py` — reads invocation counts; v1 may be a stub if project-observatory's read API isn't built yet
- `config.py` — registered repo list, signal weights, schedule
- `tests/test_signal_rules.py` — fixture-based unit tests (see E1.5)
- `tests/test_scanner.py` — fixture-based scanner tests
- `README.md` — what this service does + how to deploy + how to test locally

NO Dockerfile in v1 (Python cron, not Docker; Dockerfile lands in v2 if customer self-host needs it).

### E1.5 — Signal-rule unit tests BEFORE first deploy

Block any deploy of E1 on a passing test suite. Fixtures:

- All 16 `docs-agent/skills/*/SKILL.md` bodies, with the expected verdict per Part 1 (Group A/B/C/D classification) hard-coded
- A handful of `loom-discipline/agents/*.md` files (e.g., `architecture-analyst.md`) — should classify as agent, not as skill candidates for demotion
- A `make-skills-discipline/agents/*.md` file — same expectation

Test passes when the signal_rules verdict matches Part 1's classification for ≥14 of 16 docs-agent items. Disagreements get logged; failing tests block deploy.

This blocks the "50 false candidates on first run" failure mode the second verifier flagged.

### E2 — First observer fire (manual trigger, non-cron)

Deploy to Render via the cron block above BUT set `schedule:` to something far-future (e.g., `"0 0 31 12 *"` — Dec 31, won't fire) so the cron exists but doesn't auto-trigger. Manual invoke via `render run` or by SSH'ing into the deploy and executing `python main.py --once`. Output: a candidate set covering all 16 docs-agent skills + the agent-shaped files in `loom-discipline/agents/` + anything in `make-skills-discipline/agents/`.

### E3 — Validate observer output against manual classification

Compare observer's emitted candidates to the Group C list in Part 1. Three outcomes:

- **Full agreement**: proceed to E5
- **Observer adds NEW candidates I missed**: review, accept or reject each, update Part 1
- **Observer DISAGREES with my Group C**: review, decide which is right, update either Part 1 or the signal rules

### E4 — Operator review (you)

Open the upskilling dashboard. Confirm or reject each candidate. The candidate set becomes the binding work list.

### E5 — Author the 8 agent files

For each Group C entry, based on E0.5 triage + E4 confirmation:

- Create `docs-agent/agents/<name>.md` (or `Make_Skills/agents/roadmap-maintenance.md` for that one)
- System prompt from triage-classified body
- Tool list from Part 1 table
- Exit criteria (artifact shape returned to caller)
- `migration_destination:` frontmatter
- Update existing `docs-agent/skills/<name>/SKILL.md` to:

```markdown
---
name: <name>
description: <original description, with "(promoted to agent)" suffix>
redirect_to: docs-agent/agents/<name>.md
sunset_date: 2026-09-30
migration_destination: tapestry/engine/agents/<name>.md
---

This entry has been promoted to an agent. Invoke via:

    Agent({ subagent_type: "<name>", description: "...", prompt: "..." })
```

### E6 — Move `document-parsing` to a tool

Author `docs-agent/tools/document_parsing/` as Python package OR `docs-agent/tools/document-parsing-mcp/` as MCP server (choose at execution time based on whether other tools need it via MCP). Leave stub at `docs-agent/skills/document-parsing/SKILL.md` with same `redirect_to:` pattern.

### E7 — Annotate `design-evaluation`

Update `docs-agent/skills/design-evaluation/SKILL.md` body to explicitly reference `agentic-skill-design` PROBE→DECIDE→ACT→REPORT pattern.

### E8 — Update `docs-agent/README.md`

Fix the skill count (currently claims 7, actually 16). Document new layout: 7 skills + 8 agents + 1 tool. Add a "When is something a skill vs an agent vs a tool?" rubric using the criteria from Part 1.

### E9 — Wire Render cron for self-observer (flip schedule live)

Schedule was already in render.yaml from E1; E2 set it far-future for safe manual invocation. E9 flips it to the production schedule `"0 */6 * * *"` (every 6h). One-line edit. Confirms first auto-fire happens within 6h of merge.

Cron syntax verified against commit `2731822` post-state (the `+` diff lines):

```yaml
- type: cron
  name: loom-keep-warm
  runtime: python
  schedule: "*/10 * * * *"
  buildCommand: echo "no deps — stdlib only"
  startCommand: python scripts/keep_warm.py
```

That commit body also notes: *"Render MCP rejected free plan for cron jobs: 'valid PaidPlans are [starter, standard, ...]'"* — so the cron MUST run on `plan: starter` (or its renamed equivalent `basic-256mb`). Plan in §Part 3 already specifies `plan: starter`.

### E10 — Address `Make_Skills/agents/` + `docs-agent/tools/` missing directories

Both don't exist today. Two separate scope decisions:

- **`Make_Skills/agents/`**: Make_Skills' agent-loading runs through `core/runtime/agent.py:110-121` which imports LangChain `@tool`-decorated Python functions IN-PROCESS, not arbitrary .md files. So writing `Make_Skills/agents/roadmap-maintenance.md` does NOT make it loadable by the Make_Skills runtime; the file would be a documentation artifact only. **Decision**: leave roadmap-maintenance as a Make_Skills-runtime-internal subagent registered via the existing `load_subagents()` pattern in `core/runtime/`, NOT as a new top-level `agents/` directory. The `.md` file describing the agent lives at `Make_Skills/core/runtime/subagents/roadmap-maintenance.md` (the existing subagents convention), with `migration_destination: tapestry/engine/agents/roadmap-maintenance.md`. Tapestry's eventual destination is still a top-level agents/ — but the in-process coupling resolves via MCP exposure of the tools at migration time, not now.

- **`docs-agent/tools/`**: create the directory as part of E6 (`document-parsing` conversion). Add a `docs-agent/tools/README.md` explaining what tools/ is for so future authors don't reinvent the convention.

### E11 — Save lesson + playbook chapter

### E10 — Save lesson + playbook chapter

- New loom-memory: `lesson_self_observer_gap_revealed_by_skill_mislabel_audit_2026_06_13` — the observer-vs-hook rule + the legacy-repo-as-source rule + why this was invisible for weeks
- New playbook chapter: `tapestry/docs/playbook/migration/05-cloud-observer-vs-developer-hook.md` — captures the cloud-service-not-hook rule as binding doctrine for future observation work

## Open questions for second verifier

1. The triage step (E0.5) adds friction. Is per-paragraph classification actually necessary, or can a simpler heuristic work (e.g., "convert verbs of imperative mood verbatim, drop everything else")?
2. Render cron exact syntax — should this be PROBE'd from commit `2731822` AS PART OF E1, or as part of E9? Cost: if E1 lands without the cron stanza ready, E9 becomes a separate PR. Benefit: E1 ships sooner.
3. The observer reads telemetry to score invocation frequency. Today's project-observatory is a 24-line Phase 0 stub (`the-loom/services/project-observatory/main.py:14-23`). The actual telemetry path goes through `telemetry-ingestion` which forwards to Grafana Cloud LGTM. Does the observer call Grafana directly, or wait for project-observatory to be built?
4. The 8 agent files are sizeable. Should they be authored in a single batch PR or one-per-PR? Trade-off: single batch is faster but harder to review; per-agent PRs are easier to roll back but multiplies CI runs.
5. `agentic-upskilling`-as-self-observer means the OBSERVER itself is the implementation of one of the 8 conversions. The other 7 are just regular agent files. Is there a layering concern — does the self-observer's existence depend on the other 7 being agents? (My read: no — self-observer is a standalone Python service that doesn't invoke the other agents.)

## Cross-references

- `docs-agent/skills/agentic-upskilling/SKILL.md` — the skill being promoted into the cloud observer service
- `docs-agent/skills/agentic-skill-design/SKILL.md` — the methodology that says skills should behave this way
- `Make_Skills/render.yaml:5-11` — the Docker-on-Render pattern this lifts
- `Make_Skills/services/admin/roadmap/tools.py` — where roadmap tools actually live (per verifier finding #1)
- `tapestry/docs/playbook/migration/04-render-cron-orphans.md` — analogous "system depended on a human noticing" failure
- `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13` — destinations are Tapestry, sources are legacy repos
