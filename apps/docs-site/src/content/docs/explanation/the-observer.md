---
title: The observer
description: How the platform watches sessions and repos for recurring patterns, converts them into candidates, and lets the recursive miscommunication-becomes-architecture loop actually compound across sessions.
---

The observer is the mechanism that converts cross-session signal into structure. Feedback memories preserve individual corrections; the observer notices when patterns recur across many sessions and emits candidates for the platform to act on. Without the observer, every session's learning stays in that session's transcript — patterns happen but never become architecture.

There are TWO observers cooperating. They watch different surfaces. Together they're the discipline stack's pattern-recognition layer.

For where the observer fits in the conceptual model, see [The discipline stack — the recursive loop](/explanation/discipline-stack/#the-recursive-loop-miscommunication-becomes-architecture).

## The two observers

```mermaid
flowchart TB
  subgraph SESSIONS["Per-session surface (Path A observer)"]
    direction TB
    PA_TRIG["Stop hook fires<br/>(end of each session)"]
    PA_PARSE["Parses upskilling report<br/>+ counts Skill tool calls"]
    PA_STATE["Updates .project-intelligence/<br/>workflow-candidates/<slug>.json"]
    PA_EMIT["POSTs candidate to<br/>architecture-registry"]
    PA_TRIG --> PA_PARSE --> PA_STATE --> PA_EMIT
  end

  subgraph REPOS["Per-repo surface (self-observer cron)"]
    direction TB
    SO_TRIG["Render cron fires<br/>(every 6 hours)"]
    SO_SCAN["Walks registered repos via GitHub API<br/>+ reads frontmatter + body excerpts"]
    SO_RULES["Applies signal rules<br/>(agent / tool / skill / orphan)"]
    SO_EMIT["Emits drift candidates<br/>to architecture-registry"]
    SO_MEMO["Writes synthesis memo<br/>to loom-memory MCP"]
    SO_TRIG --> SO_SCAN --> SO_RULES --> SO_EMIT
    SO_RULES --> SO_MEMO
  end

  PA_EMIT --> REG[(Architecture Registry<br/>candidates table)]
  SO_EMIT --> REG

  REG --> PROMO["Operator or policy daemon<br/>promotes recurring candidates<br/>to durable structure"]
```

The Path A observer watches what HAPPENS in sessions. The self-observer cron watches what EXISTS across repos. Both feed candidates into the same architecture-registry where promotion lifecycle takes over.

## Path A: the local session observer

**Where it lives:** in the `loom-discipline` plugin at `adapters/claude-code/loom-discipline/scripts/observer.py`. It runs as part of the plugin's Stop-hook pipeline — same hook that fires the upskilling audit.

**What it does:**

1. Reads the session's transcript JSONL.
2. Counts explicit `Skill` tool invocations across the session (objective signal; usually under-counts because skills are mostly applied behaviorally without an explicit Skill tool call).
3. Parses the most recent upskilling report in the transcript for the `Skills invoked: <name> (N uses)` pattern (the agent's introspective count — authoritative when present).
4. Merges both signal sources, taking the higher count per skill.
5. For each skill with count >= `MIN_COUNT_TO_CONSIDER`:
   - Loads the per-project longitudinal record from `.project-intelligence/workflow-candidates/<slug>.json`.
   - Dedups by `(session_id, skill_name)` — same skill in same session doesn't re-emit.
   - If new: POSTs a candidate to `/candidates` with `status=draft`.
   - If recurring across multiple sessions: PATCHes the candidate status as `sessions_seen` crosses thresholds — `draft → observed` at 2 sessions, `observed → recurring` at 3+.

**Why per-project longitudinal state:** the observer runs at the end of every session, but candidates only make sense over time. The `.project-intelligence/workflow-candidates/<slug>.json` files keep the count across sessions so the observer can tell "this is the 3rd session this pattern has appeared" without re-reading every prior session's transcript.

**What gets observed beyond skills:** the same Stop hook also surfaces promotion candidates the agent explicitly named in the upskilling report's "Promotion candidates" section. These are agent-surfaced proposals — "I think this pattern could become a reusable skill" — emitted as Path A candidates with `signals.is_new_skill_idea = true` and the agent's short description carried forward.

**What you do as the operator:** nothing. The Path A observer runs automatically when the plugin's Stop hook fires. You see its effect when candidates accumulate in the architecture-registry over multiple sessions.

## The self-observer Render cron

**Where it lives:** in `services/self-observer/` (currently in the-loom; eventual destination is `tapestry/services/self-observer/`). Deployed as Render cron `crn-d8n2q4ernols73d7upbg` running every 6 hours on the starter plan.

**What it does (one scan pass):**

1. `github_scanner.py` walks the registered repos via GitHub API, reading file lists, frontmatter, and the first ~100 lines of each file. Skips `_upstream/`, `deprecated/`, `_archive/` and similar exclude paths.
2. `main._is_self()` skips entries that are the observer itself (avoid recursive scans).
3. `telemetry_client.py` looks up `invocations_30d` for each candidate (v1 stub returns `None`; future versions will query project-observatory for actual usage).
4. `signal_rules.classify()` applies four classes of detection rules:
   - **Agent rules** — files that look like agent files but aren't registered as such; agent definitions in unexpected places
   - **Tool rules** — tool definitions; tool-shaped scripts; tools without canonical home
   - **Skill rules** — skill files; pattern-shaped content; SKILL.md files outside known locations
   - **Orphan check** — files that LOOK like platform components but have no registration anywhere
5. Each surfaced entry becomes a candidate POSTed to the architecture-registry with the observer's signal annotations.
6. `synthesis.py` produces a synthesis memo summarizing the scan run; writes it to the loom-memory MCP as `self_observer_synthesis_latest` so subsequent sessions can read the platform's current health snapshot.

**Why a cron and not a session hook:** session hooks see one session's activity. The self-observer sees the CURRENT STATE of the platform — what exists, what's stale, what's drifted from canonical homes (Pillar 1 violations). That requires a cross-repo scan that's heavier than a session hook can do.

**What you do as the operator:** nothing for normal operation. You read `self_observer_synthesis_latest` from memory when you want to know the platform's current health. You investigate emitted candidates when they accumulate.

## How the observer fits the recursive loop

[The recursive loop diagram on the discipline-stack page](/explanation/discipline-stack/#the-recursive-loop-miscommunication-becomes-architecture) shows two pathways converging at "discipline applied automatically":

- The **memory pathway** — correction → feedback memory → auto-recall → discipline applied
- The **observer pathway** — correction → observer counts in transcript → candidate emitted → discipline applied

The memory pathway works for individual corrections. The observer pathway works for PATTERNS — corrections that aren't a one-off but a recurring shape of friction. The memory pathway makes the AGENT smarter next session; the observer pathway makes the PLATFORM smarter across sessions and across projects.

A pattern that recurs in your project for three sessions becomes an `observed` candidate. If it keeps recurring across more sessions, or appears across multiple projects, the operator (or, eventually, a policy daemon) promotes it into durable structure — a skill, an agent, a runbook, a discipline rule.

## What the observer is not

- **Not an LLM running over your code.** The Path A observer is a pure-Python script that parses transcripts. The self-observer cron uses signal rules, not classification. Neither model nor judgment is involved at this layer.
- **Not real-time.** Path A fires at session-end. The self-observer fires every 6 hours. There's always lag between "the pattern happened" and "the candidate appears."
- **Not the promoter.** The observer emits candidates. Whether a candidate becomes durable structure is a separate decision — currently operator-gated; eventually a Tapestry policy daemon. The observer's job ends at "this pattern is worth looking at."
- **Not the architecture-snapshot pipeline.** The snapshot pipeline (see [Architecture snapshots](/explanation/architecture-snapshots/)) is structural — it records what exists. The observer is behavioral — it records what happens. They're complementary and both feed session/cross-session awareness, but they look at different surfaces.

## What fails if the observer is missing

| Component | If missing | Symptom |
|---|---|---|
| Path A observer in the plugin | Skill invocations and upskilling-report candidates never POST | Architecture-registry candidates table stops growing from session activity. Manual operator POSTs become the only path. |
| `.project-intelligence/workflow-candidates/` directory | Dedup state lost | Same skill in repeated sessions emits as new candidate every time. Status transitions never advance past `draft`. |
| Self-observer Render cron | No cross-repo drift scan | Pillar-1 violations (duplicates of canonical patterns living in non-canonical homes) accumulate undetected. |
| `self_observer_synthesis_latest` memory | Lost synthesis | Sessions can't read the platform's current health snapshot at start. |
| GitHub API access (token expired / rate-limited) | Cron runs error out | Surfaces in cron logs as failure. Investigate via Render dashboard. |

## How to verify the observer is working

For the Path A observer:

```sh
ls .project-intelligence/workflow-candidates/
```

You should see one JSON file per skill the agent has surfaced in any session. Each file's content shows the cumulative `sessions_seen`, the most-recent `status`, and the prior `session_id`s where the skill appeared.

For the self-observer cron:

```sh
# Check the most recent synthesis memo via the MCP
# (substitute your memory client of choice)
memory_read name=self_observer_synthesis_latest
```

Should return a synthesis written within the last 6 hours (cron interval). If older, the cron has failed — check the Render dashboard for `loom-self-observer` service status.

For both: in the architecture-registry, candidates emitted by the observer have a distinguishable `source` annotation. Operator inspection of the candidates table over time shows new candidates appearing without manual POSTs.

## Where the observer is going

The observer is part of the recursive-skill engine the platform is building toward. The current implementation handles two surfaces (session transcripts and repo state). Future additions, all gated on operator authorization:

- **Observation decomposer** (planned, `tapestry/services/observation-decomposer/`): when a recurring behavior is too compound to become one skill, decomposes it into a set of related candidates per a 9-artifact decomposition map.
- **Cross-project signal aggregation**: surface patterns that appear across MULTIPLE projects, not just within one. Stronger evidence than within-project recurrence.
- **Policy-gated auto-promotion**: when a candidate reaches a threshold of evidence and meets policy criteria, automatic promotion to durable structure without per-instance operator review.

None of those exist yet. The current observer is the foundation; future work adds discernment on top.

## Related

- [The discipline stack](/explanation/discipline-stack/) — the recursive loop where the observer pathway joins the memory pathway
- [Plugins](/explanation/plugins/) — `loom-discipline` is what hosts the Path A observer in its Stop hook
- [Memory MCP](/explanation/memory-mcp/) — where the self-observer cron writes synthesis memos
- [Architecture snapshots](/explanation/architecture-snapshots/) — the structural-snapshot complement to the observer's behavioral-snapshot
- [Load-bearing files](/reference/load-bearing-files/) — file-by-file reference of observer components
