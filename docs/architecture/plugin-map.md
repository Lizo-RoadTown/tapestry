# Plugin map — the operator's Claude Code plugins

One place to see every Claude Code plugin the operator publishes, **which
marketplace it lives in and why**, whether it is coupled to the Tapestry
platform, and the decision behind its placement. If you ever wonder "why does
this plugin live *there* instead of folded into tapestry-patterns?" — the answer
is here, so it doesn't have to be re-derived.

Grounded in the migration record (`docs/migration/`), the MANIFESTO, and the two
marketplace manifests. Researched + ratified 2026-08-21.

## At a glance

| Plugin | Marketplace | Repo | Category | Platform-coupled? | Status |
|---|---|---|---|---|---|
| `tapestry-discipline` | tapestry | Lizo-RoadTown/tapestry | discipline / hooks | **Yes** — hooks, loom-memory MCP, OTel telemetry | active, canonical |
| `tapestry-patterns` | tapestry | Lizo-RoadTown/tapestry | patterns-library | **Yes** — agents call loom-memory + the observe→promote loop | active, canonical |
| `ai-agents-architect` | lizo-skills | Lizo-RoadTown/claude-skills-marketplace | agents (design knowledge) | **No** — tool-agnostic, dependency-free | active, public |
| `onboarding-psychologist` | lizo-skills | claude-skills-marketplace | design (behavioral) | **No** — tool-agnostic, dependency-free | active, public |
| `liz-patterns` | lizo-skills | claude-skills-marketplace | patterns-library | — | **DEPRECATED** → renamed `tapestry-patterns`; stale manifest entry to remove |
| `loom-discipline` | lizo-loom | Lizo-RoadTown/the-loom | discipline | — | **RETIRED** → renamed `tapestry-discipline`; disabled |

## The organizing principle — two channels, two audiences

There are two marketplaces on purpose. They are not redundant:

- **`tapestry` marketplace** ships the plugins that **wire a project into the
  Tapestry platform** (`.claude-plugin/marketplace.json:4`, "the Claude Code
  plugins that wire consuming projects into the platform"). Everything here is
  **platform-coupled**: SessionStart/Stop hooks, the `loom-memory` MCP
  registration, OTel telemetry, and the observe→promote→compile loop. Audience:
  Tapestry operators.
- **`claude-skills-marketplace` (marketplace name `lizo-skills`)** is the
  operator's **public distribution channel** for **tool-agnostic, general-purpose
  skills** that follow the open Agent Skills standard and work across any
  compatible agent (Claude Code, Cursor, Gemini CLI, OpenCode, …). Per the
  `CLAUDE.md` fleet table: *"Public plugin marketplace → Source for `packages/`
  distribution."* Nothing here depends on Tapestry runtime. Audience: anyone.

**MANIFESTO Pillar 1 ("one name, one home") governs the operator's OWN reusable
patterns** — i.e. `tapestry-patterns`. It forbids *duplicated* copies of a
pattern across repos (`MANIFESTO.md:92-104`); it does **not** mandate collapsing
every distinct plugin into one home. The two design skills are not duplicated
anywhere, so Pillar 1 does not pull them into `tapestry-patterns`.

## The decision (migration record)

The Step-8 consolidation (**PR #42, 2026-06-22, commit `2def958`**) moved into the
tapestry monorepo **only** the operator's *platform-coupled* plugins:
`liz-patterns → tapestry-patterns` and `loom-discipline → tapestry-discipline`.
It **consciously left the public general-purpose skills** in
`claude-skills-marketplace` (that repo was listed under "NOT in this PR").

- `docs/migration/what-to-keep.md:36-39` — keeps "the three plugins:
  `tapestry-discipline`, `ai-agents-architect`, `onboarding-psychologist`."
  (`liz-patterns`/`tapestry-patterns` is deliberately *absent* — it is the
  operator's internal patterns, a different category.)
- `docs/migration/what-to-retire.md:23-25` — "the marketplace **stays for
  general-purpose skills**."
- `docs/migration/legacy-repo-inventory.md:94-103` — the one item still **open**:
  whether `claude-skills-marketplace` eventually absorbs into Tapestry's
  `packages/cli` distribution mechanism. Even under that outcome it moves as
  *public distribution*, not merged into `tapestry-patterns`.

Memory: `tapestry_plugin_consolidation_landed_step8_2026_06_22`,
`canonical_patterns_home_landed_liz_patterns_plugin_2026_06_14`.

## Per-plugin

### `tapestry-discipline` — tapestry marketplace
**What it is:** the discipline plugin — 4 lifecycle hooks (SessionStart auto-recall
+ architecture snapshot, UserPromptSubmit PROBE injection, PreToolUse write audit,
Stop upskilling check + observer). Registers the `loom-memory` MCP. Emits OTel.
**Why it lives here:** deeply platform-coupled — it *is* the wiring that makes a
project a Tapestry citizen. Cannot be tool-agnostic.
**Status:** active, canonical. Runtime reminder label is preserved as
`[loom-discipline]` (install-only rename). Renamed from `loom-discipline`.

### `tapestry-patterns` — tapestry marketplace
**What it is:** the operator's canonical library of reusable agents + skills + tools
— the compiled output of the "agency becomes structure" loop (`MANIFESTO.md:77`).
**Why it lives here:** platform-coupled — several agents (`drift-watcher`,
`lessons-learned`, `next-actions-planning`, `orchestration-cataloging`) call the
`loom-memory` MCP, and `agentic-upskilling` documents the deployed self-observer
cron + architecture-registry. It is the sink of the observe→promote→compile loop.
This is the **one home** Pillar 1 refers to.
**Status:** active, canonical. Renamed from `liz-patterns`.

### `ai-agents-architect` — lizo-skills marketplace (PUBLIC)
**What it is:** a decision framework for agent architecture — single vs multi-agent,
ReAct vs Plan-and-Execute vs Tree-of-Thoughts, the autonomy spectrum, when to add
an orchestrator. A single-file methodology skill.
**Why it lives here (not tapestry):** zero platform coupling — no agents, no tools,
no MCP, no memory. Declares cross-tool portability (`SKILL.md:5`, "works across
Claude Code, Cursor, Gemini CLI, OpenCode, and others"). It is *general domain
knowledge*, publishable to anyone — not the operator's captured build workflow.
Folding it into the tapestry-coupled marketplace would change its audience (any
tool → Tapestry operators) and its install story (standalone → arrives with
discipline hooks + loom-memory wiring).
**Status:** active, public. Currently disabled in the operator's settings — enable
if/when wanted.

### `onboarding-psychologist` — lizo-skills marketplace (PUBLIC)
**What it is:** designs first-time-user flows using the IDENTITY→HABIT arc, grounded
in Fogg's Behavior Model + Tiny Habits, Eyal's Hook Model, and Clear's
identity-based habits. A single-file methodology skill.
**Why it lives here (not tapestry):** same as above — tool-agnostic, dependency-free
public design knowledge (category `design`). No Tapestry runtime coupling.
**Status:** active, public. Currently disabled in settings — enable if/when wanted.

### `liz-patterns` — lizo-skills marketplace (DEPRECATED)
**What it was:** the original home of the operator's canonical patterns. Renamed and
moved to `tapestry-patterns` in the tapestry monorepo (Step-8, `2def958`).
**Current state:** a **stale duplicate entry** still sits in
`claude-skills-marketplace/.claude-plugin/marketplace.json:36-45`, and
`tapestry-patterns/README.md:50` still tells users to add the OLD marketplace.
**This — not the two design skills — is the real Pillar-1 cleanup.** Action:
remove the `liz-patterns` entry (and its stray nested dev `marketplace.json`) from
the lizo-skills manifest, and repoint the tapestry-patterns README install line at
the tapestry marketplace. Disabled in settings already.

### `loom-discipline` — lizo-loom marketplace (RETIRED)
Renamed to `tapestry-discipline`; the-loom repo is a retired prototype. Disabled in
settings this session (it double-fired and registered an auth-less memory server).
The `[loom-discipline]` runtime label lives on inside `tapestry-discipline` (a
preserved-identity contract), so nothing was lost.

## Open question (tracked, not decided)

Whether `claude-skills-marketplace` itself eventually absorbs into Tapestry's
`packages/cli` distribution is **open** (`legacy-repo-inventory.md:94-103`). If it
does, it moves as the *public distribution channel*, not as a merge into
`tapestry-patterns`. Until then, the two-channel split above stands.
