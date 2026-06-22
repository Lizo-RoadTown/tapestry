---
name: loom-discipline
description: "loom Claude Code adapter. Auto-invoked BEFORE every response: PROBE files, cite file:line, save friction as memory. Emits hook telemetry to the-loom's Grafana Cloud LGTM stack."
license: Apache-2.0
metadata:
  author: Liz Osborn (with agent-assisted authoring)
  applies_to: Make_Skills, the-loom, project-starter-scaffolded repos, and any repo that sets LOOM_PROJECT_ID
  risk: low
  source: official
  date_added: 2026-05-22
  renamed: 2026-05-26 (was make-skills-discipline at claude-skills-marketplace)
---

# loom discipline

The wrapper that closes the architectural gap between the discipline Make_Skills built into the running app (`agentic-skill-design`, `lessons-learned`, `agentic-upskilling`) and what actually fires for the developer's Claude Code session. Hook scripts in this plugin force invocation; this skill body documents the rules.

## When to invoke

Apply this skill BEFORE responding when ANY of these are true:

- Working in the Make_Skills repository (path includes `Make_Skills` or repo identifier is `Lizo-RoadTown/Make_Skills`)
- Working in a project scaffolded from `Lizo-RoadTown/project-starter` (presence of `templates/_common/`-derived files, the recommendations doc, or a CLAUDE.md mentioning this plugin)
- Working in any repo that sets `LOOM_PROJECT_ID` in its `.env` — the explicit per-project opt-in (e.g. `SDE_Extraction`). As of v0.1.12 the hook scope gate honors this signal, not just the cwd-substring allowlist above.
- Any task involving a factual claim about a codebase
- Any task describing infrastructure or architectural decisions

## The rules

### 1. PROBE before asserting

For any factual claim about the codebase, the auth/storage/deploy stack, which library is used for X, or where a function lives — **run `Grep` or `Read` on the relevant file FIRST and cite `file:line` in the response**. Never assert from memory or training-data defaults alone. The "obvious" claims are the ones that go wrong.

Concrete failure modes this prevents:
- Claiming a stack uses Supabase when `web/auth.ts` shows Drizzle + Postgres
- Claiming Render containers are ephemeral when `render.yaml` provisions a persistent disk
- Generalizing from training-data defaults when the specific project differs

### 2. Distinguish dev-tooling from runtime

When designing or describing infrastructure, name which audience it serves:

| Consumer | Lives in |
|---|---|
| Running app (end-users) | `platform/api/`, `web/` |
| Developer tooling (Liz, contributors building the app) | `scripts/`, `docs/`, session memory |

For shared infrastructure (LanceDB, Postgres, Render disk), list both access paths explicitly.

### 3. Write friction as memory at the moment of correction

When the user corrects, pushes back, or surfaces an oversight — and especially when the correction reverses a confident claim — save a `feedback_*.md` memory immediately. Don't batch to session-end.

Format: rule first, then `**Why:**` (the specific incident), then `**How to apply:**` (when this rule kicks in).

### 4. Cite skills by name when invoking them

When applying a discipline that lives in `skills/`, `skills_private/`, or this plugin, NAME the skill in the response: "Applying `agentic-skill-design` PROBE step:" or "Per `lessons-learned`, the pattern here is:". Visibility trains the dogfooding loop and makes drift detectable by anyone reading the response.

### 5. Append to test-runs log at substantive task boundaries

Every commit, PR, or multi-step decision → one line in `docs/test-runs/<YYYY-MM-DD>-<topic>.md` capturing: what just happened, what friction surfaced, what was decided. This is the input for `lessons-learned`. Skipping it means patterns get buried in the transcript.

### 6. Files over generalizations for the running app

The running app is real, deployed, code-defined. If asked "does X use Y" / "where does Z live" — the answer is in the files. Open them, quote them. Memory is a pointer; the file is authority.

## How to apply

When this skill triggers (per the conditions above):

1. Read this body to refresh the rules
2. Apply rules 1-6 to the current task
3. If the task involves a deeper discipline (e.g., `lessons-learned` for transcript mining, `design-evaluation` for tradeoff matrices), invoke that specific skill — this wrapper points at the deeper skills, doesn't replace them
4. Name the rule(s) being applied in the response (rule 4 is recursive)

## Why a plugin instead of in-repo files

Earlier attempts placed the discipline as `.claude/settings.json` in each repo or as CLAUDE.md sections. Both have the drift problem: long sessions wander away from the headline; new repos require copy-paste. The plugin shape solves both: harness-side skill-matching surfaces the rules on every relevant message, regardless of session length; one install applies to every repo where the agent works.

## Related skills (the deeper-form disciplines this wrapper points at)

- `agentic-skill-design` — PROBE → DECIDE → ACT → REPORT in full
- `lessons-learned` (private to Make_Skills) — transcript-mining for friction patterns
- `agentic-upskilling` (private) — skill → tool promotion criteria
- `orchestration-cataloging` (private) — recurring-pattern recognition
- `next-actions-planning` — grounded "what to do next" plans
- `design-evaluation` — tradeoff-matrix decisions

The public skills (those without "private to") are published in this marketplace and installable separately. The private skills are kept in `Lizo-RoadTown/Make_Skills` `skills_private/` (gitignored) for now.
