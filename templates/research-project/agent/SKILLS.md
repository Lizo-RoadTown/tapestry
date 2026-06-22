# Skills for {{PROJECT_NAME}} (agent-app variant)

Skills are markdown playbooks Claude Code reaches for when the task fits. This project recommends the set below, organized by tier — install Tier 1 first; add later tiers as the project needs them.

Skills install once per machine at `~/.claude/skills/`. Future Claude Code sessions on any project on this machine will see them. The scaffolder doesn't install skills automatically — the [install-skills script](../../scripts/install-skills.ps1) handles the shell-installable ones; the rest install from inside Claude Code via `/plugin install`.

## Memory MCP is built in

This variant ships a LanceDB-backed memory MCP server at `platform/api/memory/`. It's auto-discovered by Claude Code via the project's `.mcp.json`. No separate install. Use it for durable memory across sessions; see [`docs/runbooks/memory-mcp-local.md`](docs/runbooks/memory-mcp-local.md) for operation.

## Discipline plugin (recommended)

The `make-skills-discipline` plugin enforces PROBE-first behavior, `file:line` citation, dev-vs-runtime distinction, and friction-as-memory writing via Claude Code hooks. Install:

```text
/plugin marketplace add Lizo-RoadTown/claude-skills-marketplace
/plugin install make-skills-discipline@lizo-skills
```

---

## Tier 1 — Discipline (install first; always)

Skills that shape *how* Claude works in this repo regardless of the specific task.

### `lizo-skills/ai-agents-architect`

Liz Osborn's decision framework for agent architecture: autonomy spectrum, ReAct vs Plan-and-Execute vs Tree-of-Thoughts, single-vs-multi-agent, when to introduce an orchestrator. Activates on agent-design questions.

```text
/plugin marketplace add Lizo-RoadTown/claude-skills-marketplace
/plugin install ai-agents-architect@lizo-skills
```

### `lizo-skills/agentic-skill-design` — *coming in marketplace v0.3.0*

Liz Osborn's meta-skill on designing agentic-form skills (PROBE → DECIDE → ACT → REPORT) vs passive-form. Companion to `agentic-upskilling`. **Not yet published.** Track [the marketplace](https://github.com/Lizo-RoadTown/claude-skills-marketplace/blob/main/CHANGELOG.md) for v0.3.0; install when available:

```text
/plugin install agentic-skill-design@lizo-skills
```

### `lizo-skills/agentic-upskilling` — *coming in marketplace v0.2.0*

Liz Osborn's headline framework — observe user workflow, identify recurring skill invocations, promote skills to tools when promotion criteria are met. The named framework that makes the project's agent sharper at the user's actual work over time. **Not yet published.** Track [the marketplace](https://github.com/Lizo-RoadTown/claude-skills-marketplace/blob/main/CHANGELOG.md) for v0.2.0; install when available:

```text
/plugin install agentic-upskilling@lizo-skills
```

### `claude-api`

Anthropic's official skill for building apps that call the Claude API. Caching, tool use, streaming, batching, model migration. Auto-loads when your code imports `anthropic` or `@anthropic-ai/sdk`.

Usually bundled with Claude Code. Confirm with `/plugin list`; if missing:

```text
/plugin marketplace add anthropics/skills
/plugin install claude-api@anthropic-agent-skills
```

### `superpowers:brainstorming`

Mandatory before any creative or build work per the skill's own trigger. Skipping it ships the wrong thing.

```text
/plugin marketplace add obra/superpowers
/plugin install brainstorming@superpowers
```

### `superpowers:writing-plans` + `superpowers:executing-plans`

Multi-step work that survives context resets. Plans are typed files; the agent executes them step-by-step with checkpoints.

```text
/plugin install writing-plans@superpowers
/plugin install executing-plans@superpowers
```

### `superpowers:systematic-debugging`

When an agent (or its caller) is stuck. Forces a methodical PROBE before assertion.

```text
/plugin install systematic-debugging@superpowers
```

### `superpowers:verification-before-completion`

Evidence before claiming done. Highest-leverage discipline skill in the public stack — refuses "looks fine" / "should work" reasoning.

```text
/plugin install verification-before-completion@superpowers
```

---

## Tier 2 — LLM-app stack

Skills specific to building applications that call LLMs in production.

### `antigravity-bundle-llm-application-developer:prompt-caching`

Token-economics discipline. Cache hit rates make the difference between viable and unaffordable for any agent that calls Claude.

```text
/plugin marketplace add antigravity-skills/antigravity-bundle-llm-application-developer
/plugin install prompt-caching@antigravity-bundle-llm-application-developer
```

### `antigravity-bundle-llm-application-developer:context-window-management`

Pairs with prompt-caching. Decisions about what stays in context vs what gets retrieved on demand.

```text
/plugin install context-window-management@antigravity-bundle-llm-application-developer
```

### `antigravity-bundle-llm-application-developer:llm-app-patterns`

Generic LLM-app patterns the skill recognizes and recommends.

```text
/plugin install llm-app-patterns@antigravity-bundle-llm-application-developer
```

### `antigravity-bundle-llm-application-developer:langfuse`

Observability — tool-call counts, latency, error patterns, retry loops. Required for any agent app you care about diagnosing.

```text
/plugin install langfuse@antigravity-bundle-llm-application-developer
```

### `episodic-memory:remembering-conversations`

Durable conversation memory. Installable real skill — pairs naturally with this variant's built-in LanceDB MCP for cross-session continuity.

```text
/plugin marketplace add anthropics/skills
/plugin install remembering-conversations@episodic-memory
```

---

## Tier 3 — Situational

Add as the project's needs become specific.

### `ai:building-pydantic-ai-agents` (when Python)

Pydantic AI-specific patterns. Skip if not Python.

```text
/plugin marketplace add antigravity-skills/ai
/plugin install building-pydantic-ai-agents@ai
```

### `agent-sdk-dev:new-sdk-app` (when bootstrapping)

Bootstrap helper for new Agent SDK apps. Use once per project.

```text
/plugin install new-sdk-app@agent-sdk-dev
```

### `superpowers:dispatching-parallel-agents` (when multi-agent is real)

For coordinating multiple parallel agents — handoffs, supervisor/worker, peer-to-peer. Pairs with `ai-agents-architect` for the *decision* about whether to use multi-agent at all.

```text
/plugin install dispatching-parallel-agents@superpowers
```

### `antigravity-bundle-llm-application-developer:rag-implementation` (when RAG is in scope)

RAG-specific patterns. Document loading, chunking, retrieval, re-ranking.

```text
/plugin install rag-implementation@antigravity-bundle-llm-application-developer
```

### `ralph-loop` (when Stop-hook iteration matches)

Anthropic's iterative loop technique. Niche — most agent apps don't need it. Use when you have a clear completion-promise tag and want sessions to auto-iterate.

```text
/plugin marketplace add anthropics/claude-plugins-official
/plugin install ralph-loop
```

---

## Verify install

After installing, open Claude Code in this project and ask:

```text
Which of the skills referenced in CLAUDE.md and SKILLS.md do you have installed?
```

Claude will check and report. Install any missing ones it flags.

---

## How to remove a recommendation

If a skill doesn't fit your project, edit this file to remove it and delete the corresponding line from `CLAUDE.md`. The references in `CLAUDE.md` are what cause Claude to reach for the skill; without the reference, the skill won't be invoked even if installed.
