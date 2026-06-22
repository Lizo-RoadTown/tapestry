# Platform-level data model

**Status:** Draft 2026-05-25 from the Make_Skills session, per Liz's request. Open for the Loom-agent (and Liz) to refine.

## Core sentence (load-bearing)

> This platform intentionally unifies agent context, project architecture, and runtime observability in one interface, but each remains a separate bounded context with its own data model, storage rules, and ownership boundary.

## The 13 platform-level objects

Each object has one bounded-context owner. Cross-context references happen by stable id, not by embedding.

### Project Registry domain

| Object | Definition | Key fields | Notes |
|---|---|---|---|
| **Project** | A coherent unit of development work. The top-level scope for everything else. | `id, name, owner_id, created_at, kind` (dev / archived / paused) | Owner of all the other domain rows scoped by `project_id`. |
| **Repo** | A git repository participating in a Project. A Project may have many Repos. | `id, project_id, url, name, default_branch` | One-to-many: Project → Repo. |
| **Machine** | A physical/virtual computer where work happens (Liz's laptop, desktop, dev VM, etc.). | `id, hostname, os, owner_id, last_seen_at` | Sessions reference which Machine they happened on. |

### Agent Context Service domain

| Object | Definition | Key fields | Notes |
|---|---|---|---|
| **Agent** | A specific agent KIND (not a single invocation). Claude Code session class, Copilot class, Cursor class, custom-agent class. | `id, kind, version, capabilities` (the protocol surfaces it speaks) | Agent-agnostic — the platform recognizes many kinds. |
| **Session** | A contiguous period of work between a developer and an Agent in a specific Project+Repo+Machine. | `id, agent_id, project_id, repo_id, machine_id, started_at, ended_at` | Hosts the session's accumulated context. |
| **Artifact** | A produced thing. Could be a file, a commit, a PR, a memory entry, a generated doc, a skill. | `id, session_id, project_id, kind, uri, content_hash, produced_at` | Artifacts are what work crystallizes into. Decisions and Observations can be captured as Artifacts (via `kind` and pointed-at content). |

### Project Observatory Service domain

> **Renamed 2026-05-31 from "Runtime Observability Service"** per the
> third-agent critique ratified by Liz (memory
> `architecture_third_agent_critique_six_corrections_2026_05_31`,
> item 1): the platform watches *project formation* — how agent-user
> pairs work over time, what patterns emerge, what promotes to durable
> structure — not just runtime monitoring. Same data, broader framing.

| Object | Definition | Key fields | Notes |
|---|---|---|---|
| **TelemetryEvent** | A raw low-level event. Hook fire, tool call, model invocation, error, MCP request — anything that happens. | `id, session_id, project_id, ts, source, kind, payload (json), elapsed_ms` | Highest-volume table. The Run and Observation derived rows reference these. |
| **Run** | A specific bounded execution within a Session — a test run, an agent's tool-call cycle, a deploy, a model invocation. | `id, session_id, kind, started_at, ended_at, status` | A Session contains many Runs. Each Run aggregates a slice of TelemetryEvents. |

### Architecture Registry domain

| Object | Definition | Key fields | Notes |
|---|---|---|---|
| **ArchitectureNode** | A recognized module / service / component in a Project's emerging structure. | `id, project_id, name, kind` (module / service / surface / interface), `boundary_signature, first_seen_at, last_seen_at` | Computed from telemetry + artifact analysis. Updated as recognition runs. |
| **ArchitectureEdge** | A recognized relationship between two ArchitectureNodes (depends-on, calls, contains, observes). | `id, project_id, source_node_id, target_node_id, kind, strength` (Simon's bond strength), `first_seen_at, last_seen_at` | Edges + nodes together form the project topology. |
| **Decision** | An architectural or design choice the developer (or agent) made, named explicitly. "Use Postgres, not LanceDB." | `id, project_id, session_id, made_at, summary, rationale, alternatives_considered` | A Decision can produce multiple ArchitectureNodes/Edges. Often captured as a markdown Artifact too. |
| **Observation** | A higher-level interpretation of TelemetryEvents — "the dual-mode hook keeps firing on docs," "this skill recurs in 3 projects," "module X has no callers." | `id, project_id, session_id, observed_at, summary, evidence` (link to TelemetryEvents) | Observations feed the Recognition surface. Some are auto-generated; some are human-authored. |
| **Task** | A unit of work to be done. "Implement the auth bridge." May span multiple Sessions. | `id, project_id, summary, status, opened_at, closed_at, owner_id` | Tasks are coarser than Runs. A Task may be worked across many Sessions and produce many Runs/Artifacts. |

## Relationships (ER overview)

```text
Project ────┬──── Repo
            ├──── Session ──── Agent (kind)
            │         │
            │         ├──── Run ──── TelemetryEvent
            │         │
            │         └──── Artifact (Decision, Observation, file, PR, etc.)
            │
            ├──── Task (spans Sessions)
            │
            └──── ArchitectureNode ──── ArchitectureEdge ──── (other ArchitectureNode)
                       │                       │
                       └─── (derived from) ────┴─── TelemetryEvent + Artifact analysis

Machine ──── (referenced by) Session
```

## Bounded-context ownership summary

| Bounded Context | Owns these objects | Reads (without owning) |
|---|---|---|
| **Project Registry** | Project, Repo, Machine | — |
| **Agent Context Service** | Agent, Session, Artifact | Project (for scoping) |
| **Project Observatory Service** | TelemetryEvent, Run | Session, Project (for scoping) |
| **Architecture Registry** | ArchitectureNode, ArchitectureEdge, Decision, Observation, Task | TelemetryEvent + Artifact (read to recognize); generates Path B promotion candidates (see "Two promotion paths" below) |

Cross-context data flow happens by id reference + read-only queries. Each context's storage is bounded; recognition runs by querying across at the read layer (or via a denormalized read model populated by events).

## Pattern recognition: two detection paths

**Added 2026-05-31** per the third-agent critique (items 2 + 3). Anchor sentence:

> **"Make_Skills detects local agency patterns. the-loom detects and governs cross-project structure."**

Pattern recognition is NOT one thing happening in one place. It happens at two different scopes, by two different systems:

| Scope | Detection by | What it sees | Output |
|---|---|---|---|
| **Local agency** (single project, single agent-user pair, evolving over many sessions) | **Make_Skills core (Agency-to-Structure Engine) running in the project's local instance** at `.project-intelligence/` | Repeated workflows, recurring corrections, user-specific preferences, friction signals from the in-session agent | **Local skill / workflow candidates** held in the project workspace |
| **Cross-project structure** (patterns that recur across multiple projects, multiple agent kinds, multiple developers/users) | **the-loom Architecture Registry + Project Observatory Service** | Aggregated TelemetryEvents + Artifacts across projects; pattern recurrence across project boundaries | **Cross-project structure candidates** generated server-side (Path B below) |

Both kinds feed the same downstream: the platform's promotion + codification machinery in Policy + Architecture Registry. But they're DETECTED differently, in different locations, by different systems.

This is the v3 sharpening of correction 2: detection isn't only what Make_Skills does (local) or only what the-loom does (cross-project) — it's both, in parallel, watching different scopes.

## Promotion: two paths to durable structure

**Added 2026-05-31** per the third-agent critique (item 4). Both paths converge at Policy + Architecture Registry's promotion-governance logic; they differ in *where the candidate originated*:

### Path A — Project-local candidate (bottom-up)

```text
Project's local instance (.project-intelligence/)
  → Make_Skills core detects local pattern
  → forms candidate in promotion-candidates/
  → submits to the-loom Architecture Registry
  → Policy + Architecture Registry decide: ratify, demote, or hold
  → if ratified: candidate becomes durable cross-project structure
```

Example: "Liz keeps writing study sheets in the classroom hub" → local skill candidate → if seen across multiple courses → promotion candidate → Architecture Registry ratifies → "make-study-sheet" becomes a registered platform skill anyone can use.

### Path B — Platform-observatory candidate (top-down)

```text
the-loom Project Observatory Service
  → aggregates signals across projects + agents
  → detects cross-project recurrence
  → the-loom Architecture Registry generates candidate from observatory signals
  → Policy + Architecture Registry decide: ratify, demote, or hold
  → if ratified: candidate becomes durable cross-project structure
```

Example: "5 different projects across 3 agent kinds all show the same correction pattern around environment variable handling" → observatory detects → Architecture Registry generates candidate → platform-wide skill or discipline rule promoted.

### Why both paths matter

Path A requires a project to be self-aware enough to identify its own patterns (Make_Skills core watching the in-project work). Path B requires the platform to be aware of cross-project recurrence the individual projects can't see (only the platform has the cross-cut view).

Together they cover: patterns the agent-user pair notices locally, AND patterns only visible by aggregating across the population of projects.

## Open design questions

1. **Single Postgres database vs. one per bounded context?** Trade-off: one DB is simpler, separate DBs enforce isolation more strictly. Default: one Postgres with strict schema separation + RLS by `project_id`.
2. **Decision and Observation are sometimes captured as markdown Artifacts.** Should they be a SUBTYPE of Artifact (single table, polymorphic kind column) or peer entities that REFERENCE an Artifact? Default: peer entities with optional `artifact_id` foreign key when captured as a file.
3. **Session vs. Run granularity** — both have start/end timestamps. Confirming Session = the whole Claude Code conversation, Run = one tool-call cycle or test run inside it. Open: should there be a "Turn" between them (one user prompt + one agent reply)?
4. **What populates ArchitectureNode/Edge?** Liz's `infrastructure-mapping` methodology defines the rules; the platform needs a recognition engine that runs the rules over TelemetryEvents + Artifacts. That engine is its own subsystem inside the Architecture Registry.
5. **Multi-Project recognition** — when a Skill (Artifact) appears in two Projects, is it one Artifact with two project links or two separate Artifacts that are recognized as related? Default: separate Artifacts; cross-project recognition surfaces in Observations.
6. **Agent agnosticism in practice** — the schema for TelemetryEvent.payload must be agent-kind-aware (Claude Code emits different shapes than Copilot). Either polymorphic JSON with per-kind schemas, or normalized to a common event vocabulary.

## Project-Level Agency Optimizer (added 2026-05-25; revised 2026-05-31)

A third refinement after the data model + MVP layout landed: there is a layer between raw agency and the platform's structure recognition, called the **Project-Level Agency Optimizer**. It operates per-project, watching the agent-user pair work together, generating candidate skills/workflows that may eventually promote to platform-level structure.

> **Revision 2026-05-31** per the third-agent critique (item 5,
> ratified by Liz; memory
> `architecture_third_agent_critique_six_corrections_2026_05_31`):
> the earlier framing placed the optimizer's **engine** inside the-loom
> as a sub-service of Agent Context Service. That was a conflation.
> The engine itself lives in **Make_Skills** (the narrowed core —
> "Agency-to-Structure Engine"). The-loom hosts only the
> **Registry/Coordinator** that tracks which projects have instances
> attached, NOT the engine logic. See [[project_recursive_skill_engine_three_layer_model]]
> for the full three-layer architecture (core + adapters + instances).

### Three levels of existence (revised)

| Layer | Lives where | Owns |
|---|---|---|
| **Engine (core capability)** | **Make_Skills** (the narrowed core: `services/agency-optimizer/` or equivalent in Make_Skills' repo) | The reusable engine logic: pattern detection, skill formation, promotion gates, recursive workflow refinement, agency→structure transitions. This is the "Agency-to-Structure Engine" itself. |
| **Registry/Coordinator** | the-loom (Agent Context Service domain, but distinct from Agent/Session/Artifact data) | Tracks which projects have an optimizer instance attached. Stores instance metadata (agent kind, observatory config, promotion thresholds per project). Routes signals from the project's instance to Make_Skills' engine. Does NOT contain the engine. |
| **Project-type adapters** | **Make_Skills** (`adapters/<type>/`) | Type-specific behavior on top of the engine: classroom-support-app vs software-development vs research-project. Adapters customize what the engine watches for and how it forms candidates per project type. |
| **Project-local instance** | Each consuming project's workspace (`<project-repo>/.project-intelligence/`) | Local project evidence: agent-profile, project-context, observatory-config, local-skills/, workflow-candidates/, lessons-learned/, promotion-candidates/ |

The engine lives in **Make_Skills**. The instance lives in the **consuming project**. The-loom hosts the **Registry/Coordinator** + the memory + the cross-project observatory; it does NOT host the engine itself. This is the boundary that was previously blurred.

### Project instance footprint

When a project is "spawned" or "attached" to the platform, the project's workspace gains a `.project-intelligence/` directory:

```text
<user-project>/.project-intelligence/
├── agent-profile.json           — which agent kind is attached, version, capabilities
├── project-context.json         — project_id (FK to Project Registry), repo + machine refs
├── observatory-config.json      — what events to capture, where to send them
├── local-skills/                — skills crystallized in this project, not yet promoted
├── workflow-candidates/         — repeated workflows the optimizer has detected
├── lessons-learned/             — corrections + validated approaches from this project
└── promotion-candidates/        — candidates the platform is being asked to evaluate
```

**The folder's existence is the registration.** The platform can discover attached projects by querying which workspaces have a valid `.project-intelligence/` (specifically, valid `agent-profile.json` + `observatory-config.json`). No separate registration step required.

### The four connection types between platform and project instance

| Direction | What moves | When |
|---|---|---|
| **Platform → Project**: spawn / attach / configure | Create or attach an optimizer instance to a new project; install/update the `.project-intelligence/` baseline | Project onboarding; capability upgrades |
| **Project → Observatory**: observe / log | Agent conversations, tool calls, repo activity, workflow traces emitted to the platform's `services/telemetry-ingestion/` | Continuously, while the project-facing agent works |
| **Optimizer → Agent/User**: suggest / optimize | Local skill suggestions, workflow improvements, friction reminders delivered to the agent in-session | Per turn / per session, depending on the suggestion type |
| **Project → Platform**: promote / codify | Promotion-candidate skills, workflows, decisions submitted to the platform's `services/architecture-registry/` | When local patterns are stable enough to be considered cross-project |

### Boundary rules

**Quote these in agent dialogue, code comments, and docs:**

> "The optimizer improves agency. The platform codifies structure."

> "Platform owns the reusable capability. Project owns the local instance and evidence. User-facing agent owns agency. Platform owns codified structure."

> "The larger platform spawns a project-local agency optimizer instance. That instance watches the project-facing agent and user work together, then sends stable repeated patterns back to the platform as candidate structure."

### Promotion threshold (when does local become cross-project?)

A candidate is eligible for promotion when it meets several signals:

| Signal | Meaning |
|---|---|
| Repeated across sessions | Not random |
| Repeated across tasks | Not task-specific |
| Repeated across agents or projects | Reusable |
| Has clear triggers | Operationalizable |
| Has stable steps | Can become a workflow |
| Has stable outputs | Can be tested |
| Reduces need for live judgment | Can be codified |

The Optimizer flags candidates that meet the threshold; the platform's `services/architecture-registry/` (specifically its promotion-governance logic) decides what becomes durable structure.

## What this does NOT cover

- API endpoints — that's the next layer (Platform Control Plane spec).
- Auth/JWT schema — also next layer.
- Storage choice (Postgres + pgvector vs. alternatives) — implementation, not data model.
- UI/Dashboard schema — Human surface concern, separate spec.
- Skill compilation pipeline — that's Make_Skills' methodology, not the platform's data model.
