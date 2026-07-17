# Promotion Categorization — what gets promoted, by what criteria, to where

**Written:** 2026-06-12. **Status:** Draft for Liz to ratify. **Reason:** Liz flagged on 2026-06-12 that we have a promotion LIFECYCLE (`draft → observed → recurring → stable → promotion_requested → promoted | rejected`) but no categorization or destination mapping. This proposal closes that gap.

> **Inheritance from existing canon:** This doc builds on the candidate slice in `infra/migrations/003_init_candidates.sql:87-92`, the Policy Service decisions schema in `infra/migrations/004_init_policy.sql:103-117`, the Phase-0→6 sequence ratified in [[loom_agent_to_ms_agent_pillar_2_sequence_ratified_2026_06_12]], and the bounded contexts in `docs/proposals/2026-05-25-platform-data-model.md`. It does NOT supersede them — it categorizes what flows through them.

---

## 1. ELI5

The recursive-skill engine observes Liz working, notices when she does the same thing repeatedly across projects, and promotes those repeated things into something the platform "remembers." But "the same thing" can mean different KINDS of things — a skill, a tool, an architecture pattern, an entire service. Each kind has its own promotion path: different criteria, different destination, different decision-maker. Today we have ONE lifecycle for all of them, which means we can't actually promote any of them cleanly because we don't know what kind we're promoting or where it goes.

This proposal defines four kinds, four sets of criteria, four destinations.

## 2. Quick reference

| Kind | What it is | Promotion destination | Decision-maker |
|---|---|---|---|
| **Skill** | A methodology / behavioral pattern an agent invokes when needed (e.g. `layered-explanation`, `lessons-learned`) | `Make_Skills/skills/` (engine) — distributed to every project via `loom init` / canonical seed | Liz approves via the upskilling dashboard |
| **Tool** | A `@tool`-decorated Python function the agent CALLS to do work (e.g. `roadmap-maintenance` tool, `open-pr-with-test-plan` tool) | `Make_Skills/services/skill_making/compiled_tools/` (engine) — registered via the skill-making bridge | Liz approves via the upskilling dashboard; also requires security review for any tool that touches FS / network / shell |
| **Architecture pattern** | A repeatable shape applied to multiple projects (e.g. `.project-intelligence/<instance-id>/` folder convention, two-mode auth, RLS+set_config tenant scoping) | `Make_Skills/adapters/<project-type>/default-seed/` (engine) — re-seeds existing projects, seeds new ones | Liz approves; pattern review for cross-type generality |
| **Service** | A whole new platform capability (e.g. `services/policy/`, future `services/agency-optimizer-coordinator/`) | `the-loom/services/` (platform) — Render auto-deploys | Liz approves; architecture review against bounded contexts |

## 3. The unified lifecycle (already exists; this proposal does NOT change it)

```
draft  →  observed  →  recurring  →  stable  →  promotion_requested  →  promoted | rejected
```

Status meanings per `infra/migrations/003_init_candidates.sql:87-92`:

- **draft** — observer caught a signal but only once
- **observed** — observer caught it more than once in a session
- **recurring** — observer caught it across N sessions in one project (Path A)
- **stable** — observer caught it across N projects (Path B) OR Liz manually elevated
- **promotion_requested** — Policy Service has filed an `approve` decision; awaiting destination work
- **promoted** — the candidate has been APPLIED to its destination
- **rejected** — Policy Service filed a `reject` decision OR it stayed at observed/draft for N expiry cycles

This lifecycle is kind-agnostic. The kind determines what happens at each transition.

## 4. The nine kinds, in depth

> **Revised 2026-06-12 (afternoon) per Liz's expansion ask.** The original draft of this proposal named 4 kinds (skill / tool / architecture_pattern / service). Liz pointed out that real promotion targets are richer: external applications, machine-support scripts, formalized processes, new agent roles, and full orchestrations all need places to land. Ratified expansion: **9 kinds**, each with a SHAPE signature so the observer can auto-route candidates without human oversight in the common case.
>
> **Routing principle:** each kind has a SHAPE — a fingerprint expressed as metatags / signal patterns. The observer matches incoming signals against shapes and routes the candidate to the right bucket automatically. Operator review (via the upskilling dashboard) is the exception, triggered when shape detection is ambiguous, when a candidate matches multiple shapes, or when the kind requires it explicitly (e.g. security-reviewed tools).

### 4.1 Skill

**Definition:** a methodology / behavioral pattern an agent invokes when needed. Has a `SKILL.md` with frontmatter (name, description), a body explaining when to use + how to operate. May reference other skills via `[[name]]` wikilinks.

**Shape (observer signals):**

- The candidate is a NAMED reusable pattern the agent already invoked via `Skill` tool ≥3 times in one project, OR ≥2 projects
- Signals carry `skill_name` field; agent's transcript shows explicit `Skill` tool calls with the same name
- The pattern is BEHAVIORAL (about how to think / approach work), not a callable function with typed I/O
- Metatag: `kind=skill`, `surface=methodology`, `executes=no` (skills are read by the agent, not called)

**Examples currently in the fleet:** `agentic-skill-design`, `lessons-learned`, `layered-explanation`, `agentic-upskilling`, `deep-research-pattern`, `roadmap-maintenance`, `proposal-authoring`, `periodic-architectural-checkin` (this one was promoted on 2026-06-12).

**Promotion criteria:**
1. Pattern recurred across ≥3 sessions in one project (recurring) OR across ≥2 projects (stable)
2. The pattern is generalizable — not specific to one project's domain
3. The pattern produces measurable improvement when followed (faster work, fewer corrections, fewer mistakes)
4. Liz validates: "yes, this should be a skill"

**Promotion destination:**
- **Public methodology** → `the-loom/skills/` (visible to consuming projects)
- **Internal methodology** → `the-loom/skills_private/` (the-loom-only; private from consumers)
- After ratification, `Make_Skills/skills/` (the engine's canonical catalog) gets a copy via the bridge

**Decision-maker:** Liz, through the upskilling dashboard's promotion candidate review. The dashboard shows the candidate + evidence + suggested destination; Liz clicks "promote."

**What "promoted" means in code:** a `SKILL.md` exists at the destination path; the loom-discipline observer's invocation-detection picks it up by name in subsequent sessions.

---

### 4.2 Inline tool

**Definition:** a `@tool`-decorated Python function the agent CALLS to do work, in-process via the agent SDK's tool registry. Has typed inputs + outputs, a docstring, a security/permissions surface. Distinct from a skill: a skill tells an agent HOW to think; an inline tool DOES something the agent invokes. Distinct from an external tool (§4.3): inline runs in the same process as the agent loop.

**Shape (observer signals):**

- Agent transcript shows the same MECHANICAL action ≥5 times the same way (e.g. "open PR with title T body B branch B") — the action has clear typed inputs + outputs
- The action does NOT touch FS outside the project / network beyond known whitelists / shell — if it does, security-review agent gates the promotion
- Signals carry `tool_call_signature` (action name + arg shape) repeating
- Metatag: `kind=inline_tool`, `surface=function`, `executes=in_process`, `security_surface=<low|medium|high>`

**Examples (current and planned):**
- A `roadmap_maintenance` tool that takes a feature description + completion status and patches ROADMAP.md
- An `open_pr_with_test_plan` tool that takes title + body + branch and runs `gh pr create`
- A `seed_project` tool that takes a project type + slug and materializes `Make_Skills/adapters/<type>/default-seed/`

**Promotion criteria:**
1. The underlying skill has already been promoted (tools build on stable skills)
2. The pattern has executed ≥5 times the same way (more recurrence than skill promotion needs — tools are heavier)
3. The pattern has clear inputs / outputs / side effects (no ambiguity about what to parameterize)
4. **Security review:** any tool that touches filesystem outside the project, makes network calls beyond known whitelisted endpoints, or invokes the shell needs explicit Liz approval + permission scoping
5. Liz validates: "yes, this should be a tool"

**Promotion destination:** `Make_Skills/services/skill_making/compiled_tools/<tool_name>/` — compiled Python file + tests + registration metadata. Registered via the skill-making bridge per `docs/proposals/2026-05-25-skill-making-bridge.md`.

**Decision-maker:** Liz approves via the upskilling dashboard; security-sensitive tools also require a fresh re-review by the **security-review agent** (ratified by Liz on 2026-06-12 per §7-Q2 below) before going live. The security-review agent has veto power: any tool that touches FS / network / shell cannot be promoted without its approval, even if Liz has clicked "promote" in the upskilling dashboard.

**What "promoted" means in code:** the tool is loadable via the agent SDK's tool registry; the agent can call it in subsequent sessions.

---

### 4.3 External tool / application

**Definition:** a SEPARATE runnable program — CLI, GUI app, web app, daemon — that runs in its own process. Humans use it directly OR the agent invokes it via shell. Distinct from §4.2 (inline tool): external runs out-of-process, has its own deploy + version, can be used without the agent.

**Shape (observer signals):**

- Agent repeatedly INVOKES the same external program (`gh`, `git`, a CLI script) via Bash with a consistent argument pattern
- OR operator repeatedly describes a workflow that needs a standalone UI / CLI / daemon to solve
- The work has a CLEAR boundary: input → program → output, with the program living separately from any one project
- Signals carry `external_invocation_pattern` (command + arg shape) repeating OR explicit operator request for a standalone tool
- Metatag: `kind=external_tool`, `surface=runnable`, `executes=out_of_process`, `language=<python|node|rust|...>`, `interface=<cli|gui|web|daemon>`

**Examples (current and planned):**

- `loom-cli` for project init (`loom init <slug>`) — would replace the PowerShell scaffolder
- A directory-watching daemon that captures filesystem events into telemetry

**Promotion criteria:**

1. The shape has recurred ≥5 times the same way OR the operator has explicitly asked for it
2. The boundary is clean (input, output, runtime are well-specified)
3. Security review: same gating as inline tools when the program touches FS / network / shell — security-review agent has veto power
4. Liz validates: "yes, this should be a separate program"

**Promotion destination:**

- Separate repo: `Lizo-RoadTown/<tool-name>` (when the tool is significant enough to evolve independently)
- OR `the-loom/scripts/<tool-name>/` (when it's small and lives with the platform)
- Registered via Tapestry's umbrella architecture once that doc is populated

**Decision-maker:** Liz; Tapestry-agent advises on whether new repo vs in-fleet; security-review agent for any FS/network/shell surface.

**What "promoted" means in code:** the program is installable (a release exists, a `pip install` works, a Docker image is published, etc.) AND a usage doc exists at the canonical location.

---

### 4.4 Architecture pattern

**Definition:** a repeatable shape applied to multiple projects. Not code; structure. Examples: a folder convention, a config file shape, a deployment pattern, a testing pattern.

**Shape (observer signals):**

- The SAME structural decision (file layout, config shape, function signature pattern) appears in ≥2 project types
- Observer notices the pattern via code-similarity scan OR via human "I keep setting this up the same way"
- The pattern is STRUCTURAL not behavioral (a skill is behavioral)
- Signals carry `pattern_fingerprint` (e.g. SHA of a file shape, regex of a config block) repeating across projects
- Metatag: `kind=architecture_pattern`, `surface=structure`, `applies_to=<project_types>`, `code_or_doc=structure`

**Examples:**
- `.project-intelligence/<instance-id>/` folder convention (per [[project_agency_optimizer_capability_vs_instance]])
- The two-mode auth pattern (self-host fallback + JWT, mirrored across 6 fleet locations)
- Migration shape: `BEGIN; CREATE TABLE IF NOT EXISTS ... ENABLE RLS ... FORCE RLS ... DROP/CREATE POLICY ... COMMIT;` (mirrored across migrations 001-004)
- Test shape: invariant tests that pin Pydantic ↔ SQL CHECK + cross-service enum sync + body-spoof rejection

**Promotion criteria:**
1. Pattern applies to ≥2 project types (development, classroom, research-project) — confirms cross-type generality
2. Pattern has been APPLIED in code in ≥3 places without breaking — confirms it actually works
3. Pattern is documented (a comment in code is insufficient; needs a SKILL.md or proposal doc)
4. Liz validates: "yes, every project of these types should have this"

**Promotion destination:** `Make_Skills/adapters/<project-type>/default-seed/` — the canonical seed for that project type. PR #67 (canonical default-seed) is the recent example. Re-seeding existing projects from the new seed is a separate operator action.

**Decision-maker:** Liz; cross-type generality may require Tapestry-agent review once that role exists.

**What "promoted" means in code:** the next `new-loom-project.ps1 -ProjectType <type>` invocation includes the pattern; existing projects can `re-seed` to pick it up.

---

### 4.5 Service

**Definition:** a whole in-fleet platform capability deployed to Render. A Python service with its own bounded context, database tables, REST endpoints, lifecycle. Distinct from §4.3 (external tool): a service IS part of the platform and depends on the platform's deploy infrastructure; an external tool is standalone.

**Shape (observer signals):**

- The need is named TOP-DOWN in a ratified proposal or memory (services are designed, not just observed)
- An existing service's bounded context has reached capacity / a new context needs a home
- Pattern: cross-service contract definition (a new shape of data needs to flow between agents / projects)
- Signals carry `service_proposal_ref` (link to the proposal doc / memory) — services are DOCS-FIRST candidates, not invocation-pattern-first
- Metatag: `kind=service`, `surface=platform`, `executes=render_service`, `bounded_context=<name>`

**Examples:**

- `services/policy/` (Phase 5, shipped 2026-06-12)
- `services/architecture-registry/` (Phase 1)
- Future `services/agency-optimizer-coordinator/`

**Promotion criteria:** services aren't usually "promoted from observations" the way skills/tools/patterns are — they're DESIGNED top-down per the Phase-0→6 build sequence. The promotion question for services is: **"should this service be added to the fleet?"** and the criteria are:

1. The need is named in a ratified proposal (`docs/proposals/`) or in [[loom_agent_to_ms_agent_pillar_2_sequence_ratified_2026_06_12]]-style memory
2. The service fits an existing bounded context (per `docs/proposals/2026-05-25-platform-data-model.md`) OR adds a new context with explicit justification
3. The service does not duplicate an existing service's capability
4. Liz approves the bounded context placement

**Promotion destination:** `the-loom/services/<name>/` — Render Blueprint auto-creates the service on merge to main.

**Decision-maker:** Liz, advised by loom-agent (for bounded-context fit).

**What "promoted" means in code:** Render is running it; the migration is applied; the invariant tests pass; smoke tests confirm both modes work.

---

### 4.6 Machine support / infrastructure

**Definition:** code that supports the DEVELOPER'S MACHINE (or a CI runner), not the running product. Shell scripts, env loaders, scheduled local jobs, backup utilities, IDE configs, dev daemons. Distinct from §4.3 (external tool): machine-support is platform-internal, not a product the operator distributes.

**Shape (observer signals):**

- The operator (Liz) keeps running the SAME setup / maintenance command sequence on their machine
- OR a recurring local-machine task (backup, snapshot, env refresh) has emerged that nobody owns
- The code runs LOCALLY on Liz's machine OR in CI; never on Render
- Signals carry `local_command_pattern` (shell command + arg shape) OR `local_recurring_action`
- Metatag: `kind=machine_support`, `surface=script`, `executes=local_machine`, `trigger=<manual|cron|hook>`

**Examples:**

- `scripts/apply_migration.py` (one-off DDL runner per migration)
- `scripts/keep_warm.py` (cron'd Render keep-warm)
- `scripts/architecture_snapshot.py` (loom-discipline snapshot generator)
- The `.env` loader in `_observability.py`

**Promotion criteria:**

1. The need has recurred ≥3 times the same way
2. The script is small (< ~200 lines) — if larger, it's probably an external tool (§4.3)
3. The script is dev-machine-safe (no destructive operations without confirmation)
4. Liz validates: "yes, codify this script"

**Promotion destination:** `the-loom/scripts/<name>` OR (if it belongs to a single service's lifecycle) `services/<svc>/scripts/<name>`.

**Decision-maker:** Liz; for cross-machine portability concerns, loom-agent advises.

**What "promoted" means in code:** the script exists, has a usage docstring, and the recurring action's docs reference it.

---

### 4.7 Process / workflow

**Definition:** a formalized PROCEDURE that wasn't code before. A checklist, a CI pipeline, a runbook, a scheduled job, an incident-response playbook. Process candidates are usually surfaced when "we keep doing this informally and getting it wrong" patterns emerge.

**Shape (observer signals):**

- The operator describes the SAME multi-step procedure ≥3 times informally OR has run into the same incident shape ≥3 times
- The procedure has steps that touch multiple repos / services / humans
- The procedure has a clear TRIGGER (event / condition / cadence)
- Signals carry `recurring_procedure_outline` (steps + actors) OR `incident_pattern_recurrence`
- Metatag: `kind=process`, `surface=procedure`, `executes=<manual|cron|github_actions|ci>`, `trigger=<event|cadence|incident>`

**Examples:**

- A "release checklist" before tagging a Tapestry release
- An incident-response runbook for "MCP appears dead"
- A GitHub Actions workflow that runs invariant tests on PRs
- The daily memory-snapshot pass

**Promotion criteria:**

1. The procedure has recurred ≥3 times OR has been requested as a recurring need
2. The steps are SPECIFIC (no "do the thing" hand-waves)
3. The trigger is specifiable (an event, a cron expression, an incident shape)
4. Liz validates: "yes, formalize this"

**Promotion destination:**

- Manual procedures → `docs/runbooks/<name>.md`
- Cron'd / CI'd procedures → corresponding automation (GitHub Actions yaml, render cron job, scripts/) + linked from the runbook

**Decision-maker:** Liz; for CI / cross-repo procedures, MS-agent or Tapestry-agent advises depending on scope.

**What "promoted" means in code:** the runbook exists at the canonical path AND (if automated) the automation is wired and verified.

---

### 4.8 Agent (new role)

**Definition:** a new agent PERSONA in the fleet with its own ownership domain, decision authority, and (often) its own repo. Examples already ratified: loom-agent, MS-agent, Tapestry-agent (not spawned), security-review-agent (not spawned).

**Shape (observer signals):**

- A coordination boundary has emerged that one of the existing agents keeps stepping on OR can't see clearly enough
- An expertise gap exists: a domain that needs sustained agent attention but isn't any current agent's domain
- The proposed role passes a NECESSITY filter (we're not just adding agents for fun)
- Signals: typically surfaced via the **periodic-architectural-checkin** skill rather than the observer's pattern detection — agent-role candidates are noticed via DRIFT analysis, not invocation counting
- Metatag: `kind=agent`, `surface=role`, `decision_authority=<scope>`, `requires_spawn_repo=<true|false>`

**Examples:**

- security-review-agent (ratified 2026-06-12; not spawned yet)
- Tapestry-agent (ratified 2026-06-12; spawns when the Tapestry repo is created)
- Potential future: triage-agent, doc-curator-agent, on-call-agent

**Promotion criteria:**

1. The role is named in a ratified `docs/architecture/UMBRELLA.md` ownership-matrix entry OR equivalent loom-memory project record
2. The role's domain doesn't overlap with an existing agent's domain (unless the overlap is explicitly carved)
3. The role's decision authority is enumerated (what it can approve / veto / advise on)
4. Liz validates: "yes, spawn this role"

**Promotion destination:**

- New repo (`Lizo-RoadTown/<role-name>`) with its own CLAUDE.md, skills/, and seed
- OR persona scoped inside an existing repo (e.g. a security-review persona inside Tapestry)

**Decision-maker:** Liz; loom-agent + MS-agent + Tapestry-agent advise on whether the role's domain is real or imagined. UMBRELLA.md ownership matrix is updated as part of the promotion.

**What "promoted" means in code:** the role's repo exists OR its persona is configured; UMBRELLA.md names it; an agent of the matching shape can be opened and immediately knows what it owns.

---

### 4.9 Orchestration

**Definition:** a composed MULTI-AGENT pattern — N subagents in a defined topology. Examples: planner → researcher → writer → reviewer (sequential); tournament-bracket review (parallel + reduction); judge-panel synthesis. Lives in Make_Skills' engine layer per the three-layer model.

**Shape (observer signals):**

- The agent has repeated the SAME multi-subagent invocation topology ≥3 times
- The topology has clear stages (sequential / parallel / branching)
- Each stage has a clear input → output contract
- Signals carry `orchestration_topology` (graph of subagent roles + dependencies) repeating
- Metatag: `kind=orchestration`, `surface=composition`, `executes=multi_agent`, `topology=<sequential|parallel|tournament|judge_panel|custom>`

**Examples (current + planned):**

- "Find bugs → judge each via N adversarial verifiers → synthesize" (the canonical adversarial-verify pattern from the Workflow tool)
- "Research problem → propose N designs → score via judge panel → synthesize from winner" (judge-panel pattern)
- "Migration audit: scan call sites → propose patch per site (parallel) → review (parallel) → apply"

**Promotion criteria:**

1. The topology has executed ≥3 times the same way
2. The stages have clear input/output contracts (no ambiguity at boundaries)
3. The orchestration's TOTAL token cost is bounded (anti-runaway-loop)
4. Liz validates: "yes, codify this orchestration"

**Promotion destination:** `Make_Skills/orchestrations/<name>/` — MS-agent's domain. Compiled into a reusable Workflow script (per the Workflow tool's script format).

**Decision-maker:** Liz approves the codification; MS-agent owns the implementation + maintenance.

**What "promoted" means in code:** the orchestration is registered as a named Workflow that any agent can invoke; the canonical pattern is documented; cost bounds are enforced.

---

## 5. Decision flow (shape-based auto-routing)

Per Liz's ratify on 2026-06-12: each kind has a SHAPE (signal pattern + metatags). The observer matches signals against shapes and routes the candidate to the right bucket automatically. Operator review is the EXCEPTION, not the default.

```
Signal observed
    │
    ▼
Shape detection: which kind's signature does this match?
    │
    ├── one clear match ──→ candidate_type = <kind>; auto-promote via kind-specific destination work when criteria met
    ├── multiple matches ─→ candidate flagged ambiguous; surfaces in the upskilling dashboard for operator to pick
    └── no match ────────→ candidate stored with kind='unclassified'; surfaces in the upskilling dashboard for operator (potential new kind discovered)

Threshold check (kind-specific N values from §4.x):
    │
    ├── below threshold ──→ status stays 'draft' / 'observed'
    └── threshold met ────→ status = 'recurring' / 'stable'; eligible for promotion

Promotion decision:
    │
    ├── kinds with required oversight (service, agent, security-surface tool):
    │      Liz reviews via the upskilling dashboard OR via proposal doc; security-review agent vetoes if applicable
    ├── kinds with auto-promotion eligibility (skill, machine_support, process, orchestration):
    │      Auto-promotes when criteria pass; operator can override via demote
    └── all paths record decision in policy_decisions; audit-immutable
```

Note: "auto-promotion eligibility" doesn't mean fully silent. The upskilling dashboard still shows what happened ("3 candidates auto-promoted last week"). It means Liz doesn't have to CLICK approve for every one; the operator-confirm overhead is reserved for the cases that need judgment.

## 6. Audit trail

Every transition is governed by the Policy Service (`infra/migrations/004_init_policy.sql`). The `policy_decisions.extra` JSONB column carries kind-specific metadata:

```jsonc
{
  "kind": "skill",                   // one of the 9 kinds defined in §4
  "destination": "skills_private/",  // where it landed (or will land)
  "shape_signature": {               // the metatags the observer used to route this candidate
    "kind": "skill",
    "surface": "methodology",
    "executes": "no"
  },
  "evidence_threshold_met": ["recurrence_3_sessions", "cross_type_2"],
  "auto_routed": true,               // false = operator manually picked kind in the upskilling dashboard
  "security_reviewed": false,        // true only for tools touching FS/network/shell
  "supersedes": "<old_decision_id>"  // when revising a prior decision
}
```

Decisions are immutable (audit-immutability invariant per migration 004 header). A revision is a new decision row with `extra.supersedes` set, not an UPDATE.

## 6.5 Demotion paths (added 2026-06-12, formalized per §7-Q3)

Demotion mirrors promotion — every promoted thing can be walked back. The Policy Service's `demote` decision kind triggers kind-specific work:

| Kind | Demotion criteria | Demotion destination work | Decision-maker |
|---|---|---|---|
| **Skill** | Not invoked in N sessions across all projects (default N=10) OR superseded by a newer skill OR Liz flags it as harmful | Move `SKILL.md` to `skills/_demoted/<name>/` (preserved for audit, removed from active catalog); the observer's invocation-detection stops listing it as a known skill | Liz via the upskilling dashboard; observer can auto-surface as "demote candidate" |
| **Inline tool** | Not called in N sessions OR replaced by a better tool OR security-review agent flags a CVE / new threat surface OR API contract drift | Unregister from agent SDK's tool registry; mark `compiled_tools/<tool_name>/STATUS.md` as demoted; keep source for audit | Liz via the upskilling dashboard; security-review agent has unilateral demote power for security reasons |
| **External tool / application** | Not invoked in N runs / unused for N weeks OR replaced by a better tool OR security flag OR maintenance cost > value | Mark release as deprecated; redirect docs to replacement; preserve source repo; remove from `loom init` registry | Liz; Tapestry-agent advises on cross-repo impact; security-review agent can force-demote |
| **Architecture pattern** | Better pattern emerged AND old projects have migrated OR pattern caused incidents OR cross-type assumption broke | Remove from `Make_Skills/adapters/<type>/default-seed/`; existing projects keep the pattern unless they opt into re-seed | Liz; Tapestry-agent advises on cross-type impact |
| **Service** | Capability moved into another service OR fundamental design flaw OR rarely-used + cost-of-maintenance > cost-of-removal | Render Blueprint removal; data archived per `docs/proposals/2026-05-25-platform-data-model.md` audit-retention rules; migration revoke if schema is no longer needed | Liz advised by loom-agent; cannot be done by an agent unilaterally |
| **Machine support** | Script no longer needed (workflow it supported is gone) OR replaced by a better script OR environment changed (e.g. PowerShell → WSL) | Move to `scripts/_demoted/`; preserve git history; update any runbook references | Liz; loom-agent flags candidates via periodic-architectural-checkin |
| **Process / workflow** | Trigger no longer fires OR procedure replaced by automation OR incident pattern stopped recurring | Move runbook to `docs/runbooks/_demoted/`; disable automation (cron / GitHub Actions); record the "why it was retired" | Liz; loom-agent or MS-agent depending on scope |
| **Agent (new role)** | Domain absorbed by another agent OR role's decisions never get exercised OR coordination overhead > value | Archive agent's repo (read-only) OR remove persona from host repo; update UMBRELLA.md ownership matrix to redistribute domain | Liz; this is a high-stakes change — requires explicit periodic-architectural-checkin review |
| **Orchestration** | Topology never replicated in real work OR replaced by a better orchestration OR cost-per-run exceeded benefit | Mark Workflow script as deprecated; preserve in `Make_Skills/orchestrations/_demoted/`; remove from canonical catalog | Liz; MS-agent owns the codification + retirement |

Demotion decisions are recorded the same way as promotion decisions (immutable rows in `policy_decisions`). The `extra` JSONB carries the demotion-specific metadata:

```jsonc
{
  "kind": "tool",
  "demotion_reason": "not_invoked_n_sessions",
  "n_sessions_silent": 12,
  "last_invocation_session_id": "...",
  "supersedes": null,                       // null when this is the original demote
  "reverses": "<original_promote_decision_id>"  // links back to the promote that's being walked
}
```

A re-promotion after a demotion is a NEW `approve` decision with `extra.reverses = <demote_decision_id>` (the audit trail shows the full ping-pong).

## 6.6 Observer shape-detection roadmap (added 2026-06-12, deferred implementation)

The 9-kind taxonomy in §4 only works if the observer can ROUTE signals to the right kind. Today's observer ([`adapters/claude-code/loom-discipline/scripts/observer.py:604`](../../adapters/claude-code/loom-discipline/scripts/observer.py#L604)) hardcodes `candidate_type='skill'` for everything it surfaces. The shape-detection logic to fulfill the auto-routing principle is **deferred implementation** — listed here so it's not lost.

**What needs to be built (later, not in this PR):**

1. **Shape registry as code.** A `shapes.py` (or `shapes.yaml`) defining each of the 9 kinds' signal patterns + metatag templates. Single source of truth for routing.
2. **Detector functions.** One per kind: `detect_skill(signals) → confidence`, `detect_inline_tool(signals) → confidence`, etc. Returns 0–1 confidence + metatag candidate.
3. **Router.** Runs all detectors against incoming signals; routes to the highest-confidence kind above threshold; flags ambiguous matches (multiple kinds above threshold within delta) for upskilling-dashboard review; flags low-confidence matches as `unclassified`.
4. **Observer changes.** The observer's `post_candidate()` calls the router instead of hardcoding `"skill"`.
5. **Upskilling-dashboard UI for the exception path.** When the router flags `ambiguous` / `unclassified`, the candidate appears in the upskilling dashboard's "needs operator review" queue.
6. **Per-kind threshold config.** The N-values from §4 (3 sessions / 5 invocations / 2 projects) move to a `policy_thresholds` config table so the upskilling dashboard can tune them without code change.

**When this lands:** after the upskilling dashboard exists (Phase 6 of the Phase-0→6 sequence) — auto-routing is only useful when there's a surface to show its outputs. Until then: observer keeps hardcoding `"skill"`, kinds 4.2-4.9 in §4 are documented destinations the operator can manually pick via direct DB write or via a future upskilling-dashboard "pick kind" interaction.

**Why deferred:** routing without an observation surface is theater. The doc + schema land now (this PR); the runtime routing lands when the upskilling dashboard needs it.

## 7. Open questions — ANSWERED by Liz on 2026-06-12

### Q1: N-thresholds for recurrence — **answered: ratify the proposed numbers; fine-tune in the upskilling dashboard**

Final values (cf. §4.1 / §4.2 / §4.3):

- **Skill:** 3 sessions in one project (recurring) OR 2 projects (stable)
- **Tool:** 5 invocations the same way
- **Architecture pattern:** 2 project types

These ship as DEFAULTS in code. The upskilling dashboard (Phase 6) will expose them as operator-configurable so Liz can tune from real data without a code change. Implementation note for the upskilling-dashboard build: store thresholds in a `policy_thresholds` config table (or a JSONB column on a settings row), read at promotion-criteria evaluation time, default to the values above.

### Q2: Tool security review — **answered: dedicated security-review agent**

A third named agent role is now planned: the **security-review agent**. Scope:

- **Domain:** any candidate of kind=tool that touches FS / network / shell. Possibly extending to: kind=architecture_pattern that proposes new auth shapes, kind=service that opens new attack surfaces. To be refined.
- **Power:** veto on tool promotion (cannot be overridden by Liz's "promote" click in the upskilling dashboard without an explicit override decision recorded in `policy_decisions.extra.security_override = {reason, accepted_risk}`).
- **Triggering:** automatic when a tool candidate's signals show FS/network/shell touchpoints; manual via "request security review" button in the upskilling dashboard otherwise.
- **Spawn timing:** before any tool is promoted via the upskilling dashboard. Until then, manual Liz review per the existing §4.2 criterion #4.
- **Repo:** TBD. Likely `Lizo-RoadTown/security-review-agent` following the dedicated-repo pattern, OR scoped as an agent persona inside Tapestry. Decide when spawning.

The UMBRELLA.md ownership matrix is updated accordingly.

### Q3: Demotion mirror — **answered: formalize it**

Done in §6.5 above. The Policy Service's existing `demote` decision kind is already wired to receive these; the kind-specific destination work is what §6.5 enumerates.

### Q4: Candidate-type schema sync — **answered: more info needed; analysis below**

**PROBE findings (2026-06-12):**

- Production data: **7 rows, all `candidate_type='skill'`**. Zero rows of `workflow | decision | pattern`. Of the proposed new values, only `skill` is currently used.
- Only **one** production caller hardcodes a value: [`adapters/claude-code/loom-discipline/scripts/observer.py:604`](adapters/claude-code/loom-discipline/scripts/observer.py#L604) writes `"skill"`.
- All other references go through the Pydantic `CANDIDATE_TYPE` Literal in [`services/architecture-registry/models.py:22`](services/architecture-registry/models.py#L22). The Literal is the single source of truth in code; the SQL CHECK constraint at [`infra/migrations/003_init_candidates.sql:123`](infra/migrations/003_init_candidates.sql#L123) is its enforcement layer. Tests pin them in lockstep at [`services/architecture-registry/tests/test_candidate_invariants.py:141`](services/architecture-registry/tests/test_candidate_invariants.py#L141).
- Touchpoints if either option lands: 2 prod files (models.py + migration), 1 test file, 1 observer call site. No data migration needed.

**Long-term downstream impact comparison:**

| Concern | (a) ALTER CHECK to new values | (b) Add parallel `promotion_category` column |
|---|---|---|
| **Schema migration cost** | Migration 005: DROP CHECK + ADD CHECK with new values. Atomic; zero rows would violate the new constraint (the only used value `skill` is in both old and new sets). | Migration 005: ADD COLUMN nullable, DEFAULT NULL. Atomic. |
| **Code churn** | Update Pydantic Literal (1 line) + observer (1 line) + test fixtures (~5 lines). | Add new Pydantic field + storage write path + read paths everywhere candidates are surfaced. ~30+ line touches. |
| **Backfilling old rows** | None needed (the only existing value carries forward). | Have to decide what to backfill the 7 existing rows with. Probably "skill" but it's a manual call. |
| **Semantic clarity for future readers** | "candidate_type" is THE category; one column, one taxonomy. Easy to PROBE. | Two parallel columns with overlapping semantics. Future agents have to learn "is `candidate_type` or `promotion_category` the authoritative one for this read?" |
| **Path B handling** | Path B candidates (cross-project pattern detection) use the same column with the same set. No new concept. | Path A populates one column, Path B might populate the other, divergence risks. |
| **Upskilling-dashboard UI complexity** | One field to display, one to filter, one to derive promotion destination from. | Need to handle the case where both are set, neither is set, or they disagree. Defensive code at the UI layer forever. |
| **MS-agent / bridge contract** | Bridge contract evolves once: receive `kind='tool'` instead of `kind='workflow'`. Single deploy coordination. | Bridge contract has to handle both columns OR stay on `candidate_type` and ignore `promotion_category` (which defeats the purpose of adding the second column). |
| **Reversibility** | Reversible via another migration (DROP CHECK + ADD CHECK back to old values) — same cost. | Removing the parallel column later costs as much as adding it. |
| **Risk** | If a hidden caller assumes old values, that caller breaks loudly (CheckViolation → 400). Easier to detect and fix than silent semantic drift. | If a hidden caller writes to one column and not the other, silent state divergence accumulates over months. Hard to detect; hard to fix later. |

**My recommendation flipped from (b) to (a)** based on the PROBE. The original reasoning for (b) was "we have data we don't want to disturb." The PROBE showed the data is one column-value (`skill`) that exists in both proposed sets — there's nothing to disturb.

(a) is now substantially cheaper in code churn (~7 line touches vs. ~30+), simpler in semantics (one column, one taxonomy), and safer long-term (loud-fail on drift vs. silent divergence in a parallel-column design). The only argument for (b) is forward-compatibility "what if we add more categories later" — but ALTER CHECK is reversible at the same cost, so that's not really a benefit.

**Recommended migration 005 sketch (if Liz ratifies (a)):**

```sql
BEGIN;
ALTER TABLE candidates DROP CONSTRAINT candidates_type_check;
ALTER TABLE candidates ADD CONSTRAINT candidates_type_check
  CHECK (candidate_type IN ('skill', 'tool', 'architecture_pattern', 'service'));
COMMIT;
```

Plus 1-line update to `services/architecture-registry/models.py:22`, 1-line update to `adapters/claude-code/loom-discipline/scripts/observer.py:604` (no change — `'skill'` is still valid), and ~5 lines in tests. The Pydantic↔SQL sync invariant test passes naturally.

**Ratify (a)? If yes, I'll draft PR #10 with migration 005 + Pydantic update + test fixture update. If you want to defer, the existing schema continues to work — only `skill` is in use; the proposal's taxonomy can evolve in docs / the upskilling dashboard without schema change until you decide.**

## 8. Related

- `docs/proposals/2026-05-25-platform-data-model.md` — bounded contexts inside the-loom
- `docs/proposals/2026-05-25-skill-making-bridge.md` (in Make_Skills) — how tools cross from the-loom into Make_Skills' compiled catalog
- `docs/architecture/UMBRELLA.md` — Tapestry umbrella stub
- `skills_private/periodic-architectural-checkin/SKILL.md` — the meta-skill that uses this taxonomy
- [[naming_atelier_and_tapestry_2026_06_12]] — names ratified the same day
- [[loom_agent_to_ms_agent_pillar_2_sequence_ratified_2026_06_12]] — the Phase-0→6 sequence this proposal categorizes within
