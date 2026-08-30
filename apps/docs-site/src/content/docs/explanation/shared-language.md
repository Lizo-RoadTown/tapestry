---
title: Shared language
description: The words the docs use, defined once in plain terms. The core eight memory words (friction, record, correction, one-time learning, recall, scope, fingerprint, label), plus the platform's parts and the setup words a newcomer meets. The canonical glossary the other pages link to instead of re-defining.
---

The memory pages — and the wider systems and reference pages — all lean on the same handful of words. This page defines them once, in plain terms, so you can read the rest without guessing what a word means. Every other page links here rather than redefining them.

Throughout these docs, **you are the operator**: the person running the platform or wiring a project into it. When a page addresses "the operator," it means you.

Start with the **core eight** below. If you are setting up your first memory store, read that group top to bottom once — it is the whole vocabulary the memory idea assumes. The two groups after it — **the platform's parts** and **setup and operation** — are a reference. Dip into them when a word on the systems or reference pages is unfamiliar; you do not need them all up front.

## The core eight

### Friction

The repeated cost of working with an agent that forgets: re-explaining the same context, watching it repeat a mistake, losing a correction by the next session. Memory exists to end friction.

It is the thing you are trying to get rid of. If you have never worked with an agent that remembers, friction is the background hum you may not have noticed yet — every session starting from zero. The rest of these words describe how a memory store removes it.

### Record

One memory. A few words worth keeping, a *fingerprint* of their meaning, and a few *labels*.

A record is the unit the store holds. Not a whole conversation, not a file — one small, durable thing: a correction you gave, a decision you made, a fact about a project. The store is a collection of these.

### Correction

When you tell the agent it got something wrong. Saved as a record, it becomes standing guidance it follows from then on.

A correction is the highest-value kind of record. You give it once — "no, we use pnpm here, not npm" — and because it is saved, the agent follows it in every session afterward instead of making you say it again.

### One-time learning

A cost you'd otherwise pay every session, paid once instead: a correction saved once is guidance forever.

This is the shape of the whole payoff. Without memory, the same explanation is a cost you pay every time you sit down. With memory, you pay it once. That conversion — a repeating cost turned into a single one — is what the store is for.

### Recall

The system surfacing the right records by *meaning*, not keyword, the moment they're relevant — automatically.

You do not search for a record by remembering its exact words. When something you once saved becomes relevant again, recall brings it back on its own, matching by what it *means*. This is why the store is useful even when you have forgotten what is in it.

### Scope

Who or what a record belongs to: **you** (a hard wall — never another person's memory), a **project** (a soft sort — a filter, not a barrier), and **machine** (deliberately none — same key, same memory everywhere).

Scope is the answer to "who sees this record?" There are three parts, and they behave differently on purpose:

- **You** is a hard wall. Your records are yours; the store will not hand another person's memory to you or yours to them.
- **Project** is a soft sort. Within your own records, project labels sort things by project — a filter you can lift, not a wall. A record can even belong to two projects at once.
- **Machine** is deliberately absent. There is no "which machine" boundary. Your laptop, your desktop, and a scheduled job all reach the same memory, because reaching it from everywhere is the point.

### Fingerprint

The 384-number stand-in for what a record's words *mean*, so recall can match by meaning instead of exact words.

When a record is saved, a small model on your own machine reads its words and produces 384 numbers that stand for their meaning. That is the fingerprint. Recall compares fingerprints to find records close in meaning, which is how it can surface the right one even when your words this time differ from the words you saved.

### Label

The marks on a record — whose it is, which projects, who wrote it, when — that keep one shared store sorted.

Labels are the bookkeeping on each record. They are what make one shared store usable: because every record carries who it belongs to and which projects it touches, the store can stay sorted by owner and project even though everything lives in one place.

## The platform's parts

These name the moving pieces of the platform. You meet them on the systems and explanation pages once you look past the memory store itself.

### The observer

The part of Tapestry that watches your work for patterns that keep *recurring* and flags them for a closer look — trends, not single events.

Two observers run, and both are plain scripts, not an AI reading your code: a **session observer** at the end of each session (which skills you used, what the session's upskilling report flagged) and a **repo observer** on a schedule (every few hours) that scans your repos for structure that has drifted. What either one flags is called a *candidate*. The observer surfaces; it never decides — promoting a candidate is your call.

### Discipline (the discipline stack)

Tapestry's name for the always-on rules and automation that keep the agent honest — recall memory, check the real files before claiming anything, save a correction the moment you make it.

It ships as a Claude Code plugin (`tapestry-discipline`) that installs four *hooks*. "Stack" just means the whole bundle of rules and hooks taken together, not a piece of infrastructure. Without it the agent reverts to plain Claude Code — no memory, no PROBE reminder, no guardrails.

### Hook

A script Claude Code runs automatically at a fixed moment — not something you call yourself.

The discipline plugin uses four: `SessionStart` (pull your memories into a new chat), `UserPromptSubmit` (add the PROBE reminder to each message you send), `PreToolUse` (a check before an edit), and `Stop` (the end-of-turn upskilling audit). Hooks bind when a session opens, which is why enabling a plugin only takes effect after you restart Claude Code in that project.

### MCP (Model Context Protocol)

The standard way an outside tool or server plugs into Claude Code so the agent can call it.

The memory store you are setting up *is* an MCP server — `loom-memory`, reached over HTTP — and the discipline plugin that wires it in is what gives the agent its `memory_recall` / `memory_write` tools. Because every project shares the one store, it also acts as a *cross-agent channel*: here "channel" means shared memory that agents in other projects can read, not a chat channel.

### Signal, interpretation, pattern

The three stages by which raw events become something worth acting on: a *signal* is one raw event a hook emits; *interpretation* is the observer reading many signals together; a *pattern* is the recurring shape it finds.

The docs write it as "signal → interpretation → pattern," and the slogan "signals are not patterns" means one event proves nothing — only the trend across many does. Telemetry produces the signals; everything downstream is interpretation.

### Candidate and promotion

A *candidate* is a recurring pattern the observer noticed but has not acted on — it waits in a list for a second look. *Promotion* is the deliberate step of turning one into durable structure: a rule, a skill, or an agent.

A candidate carries a status that hardens as evidence repeats (draft → observed → recurring). The observer only ever raises candidates; whether one gets promoted is a decision you make, not the observer.

### Architecture snapshot, diff, drift

A *snapshot* is an automatic structural map of your repo — services, dependencies, MCP servers, env-var keys — taken at each session start. The *diff* lists what changed since the prior snapshot. *Drift* is structure that has moved away from where it belongs (a duplicate showing up in two places, one package that split into two).

The point is that the agent begins each session already knowing what changed, instead of you re-explaining it. If you delete the snapshot output directory to tidy up, you lose only the historical record — the map rebuilds from the next session forward.

### The Observatory

The web dashboard where you watch how you and your agents are working together over time — trends, not live status.

It answers trajectory questions ("is coordination getting smoother or rougher?") rather than point-in-time status like "is the API up right now." The docs sometimes call it the *console*; it is the same surface. It is your own deployment, with a read-only public demo running on sample data.

### Coordination

How well you and the agent are working together over the life of a project — the thing Tapestry watches and tries to improve.

It is the platform's core measure, so the word turns up everywhere the platform describes what it is *for*. One stretch of you-and-agent working on a single thing is a *working episode*; "coordination quality" rising or falling over time is what the Observatory plots.

### Upskilling

Turning a repeated pattern into a reusable skill or rule, so the same thing is not solved from scratch again.

The *upskilling audit* is the end-of-session check (the `Stop` hook) that fires loudly when a substantial session — a commit, or many tool calls and turns — ends without producing such a report. It is the same job the observer does, caught at the moment a session ends rather than across many.

## Setup and operation

These are the words you meet while standing the platform up and wiring a project into it — the setup and reference pages assume them.

### Operator

You — the person running the platform or wiring a project into it.

Nearly every page uses "the operator" to mean the reader. When instructions say "the operator sets `LOOM_PROJECT_ID`," they are telling *you* to do it; the word is not pointing at some other role.

### PROBE

The rule that the agent must actually read or grep the real files — and cite `file:line` — before claiming anything about your code, instead of guessing from memory or training.

It is not an acronym, despite the capitals. You will see it as "PROBE before asserting" or "the agent should be PROBE-ing the code"; if the agent cites a memory as current fact without checking the files, that is this rule being broken.

### Self-host vs hosted

The two ways the platform can run. *Self-host* (the default) is run-it-yourself and single-tenant: everyone lands in one deterministic memory envelope, with no login token needed. *Hosted* (hosted-multitenant) is a shared deployment where each user's data is walled off as its own *tenant*, keyed by a login token.

The mode is set by `PLATFORM_MODE` (`self_host` by default). For a first memory store you are almost certainly self-hosting — which is why the setup steps need no authorization header.

### OTel / OTLP (OpenTelemetry)

*OpenTelemetry* is an industry-standard format for emitting logs and traces; *OTLP* is the wire protocol that ships them.

Tapestry sends its hook events over OTLP to Grafana Cloud (Loki stores the logs, Tempo the traces) so patterns can be seen across machines. This part is optional: the discipline plugin always writes a local log at `~/.claude/logs/hooks.jsonl`, and OTel only adds the cross-machine view. Skip the OTel credentials and nothing else breaks.

### Auto-recall block (additionalContext)

The block of remembered notes the `SessionStart` hook drops at the top of a new chat, before your first message — past decisions, prior corrections, current project state.

`additionalContext` is Claude Code's name for that injected block; the docs call the memory part of it the *auto-recall block*. Watching it appear is how you confirm [recall](#recall) is wired. On a brand-new project it is empty, which is normal — nothing has been saved yet.

### pgvector and embeddings

The database machinery behind meaning-based recall. An *embedding* is the [fingerprint](#fingerprint) — the list of numbers standing for what a memory means. *pgvector* is the Postgres add-on that stores those fingerprints so recall can search by meaning ("semantic search") instead of by exact words.

You install neither; the hosted memory store already runs Postgres with pgvector built in. If you have read *fingerprint* and *recall* above, you already understand what these do — these are just the underlying names for the same idea.

### Why you'll see both "loom" and "tapestry"

"Loom" is the platform's legacy name; "Tapestry" is the current one, and the two overlap on purpose while the rename settles.

So during setup you will meet both. The memory server is `loom-memory`, your project's identity tag is `LOOM_PROJECT_ID`, and the discipline plugin's runtime messages are still tagged `[loom-discipline]` even though you install it as `tapestry-discipline`. The old `loom-` names are kept deliberately — a stable-identity contract, so existing wiring keeps working — and are not mistakes. You do not need to change them.

## Related

- [The memory](/explanation/the-memory/) — the concept, in brief, using these words.
- [Why the memory is built this way](/explanation/why-memory-is-built-this-way/) — the reasons behind the shape, using these words.
- [The memory MCP](/explanation/memory-mcp/) — what accumulates in a running store and how to keep it healthy.
- [The discipline stack](/explanation/discipline-stack/) — how the plugins, hooks, MCP, and observer fit together.
- [The observer](/explanation/the-observer/) — how recurring patterns become candidates and then durable structure.
- [The Observatory](/systems/observatory/) — the console where coordination trends are watched over time.
