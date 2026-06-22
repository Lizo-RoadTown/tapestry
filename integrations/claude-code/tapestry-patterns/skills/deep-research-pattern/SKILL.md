---
name: deep-research-pattern
description: Architectural pattern for multi-agent deep research with strict context isolation. Use when designing or extending the research subagents under subagents/ — covers shallow vs. deep mode, the three-role topology, and context boundaries.
---

# Deep research pattern

Three-role topology drawn from the [NVIDIA AI-Q blueprint](https://github.com/NVIDIA-AI-Blueprints/aiq) and [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research). Use this when adding or refactoring research subagents in `subagents/`.

## Two modes

The agent operates in one of two modes, separated by bound:

| Mode | Bound | When to use |
|------|-------|-------------|
| **Shallow** | max 10 LLM turns, max 5 tool calls | Default. Direct questions, lookups, single-source answers. |
| **Deep** | max 2 outer loops, full planner→researcher topology | Long-form reports, multi-source synthesis, anything the user explicitly asks "research" or "report" for. |

Shallow is one orchestrator + tools. Deep is the three-role topology below. Most queries are shallow.

## Three roles (deep mode)

| Role | Lives at | Reads | Produces |
|------|----------|-------|----------|
| **orchestrator** | `AGENTS.md` (root) | User request | Routes to planner; final assembly + delivery |
| **planner** | `subagents/planner/` | User request only | Structured plan: questions, sources, success criteria |
| **researcher** | `subagents/researcher/` | Planner's plan only (NOT orchestrator reasoning) | Findings + citations, formatted as the final report |

This is the [AI-Q topology](https://developer.nvidia.com/blog/how-to-build-deep-agents-for-enterprise-search-with-nvidia-ai-q-and-langchain/) — three roles, no separate compressor or writer. The researcher returns the report directly.

## Context isolation (the load-bearing rule)

**Each subagent reads only what's listed in the "Reads" column above.** Do not pass orchestrator reasoning, prior turns, or sibling-subagent scratchpads downstream.

This is the strongest architectural claim from AI-Q and worth quoting directly:

> By passing only a structured payload, we reduce the token bloat and prevent the "lost in the middle" phenomenon.

> The researcher agent receives only this plan — not the orchestrator's thinking tokens or the planner's internal reasoning.

In deepagents, enforce this by giving each subagent its own `deepagents.toml` with `memory=["./AGENTS.md"]` only (NOT inheriting parent context) and passing the upstream artifact as a single explicit argument when the orchestrator delegates.

## Tool delegation

- **researcher** is the only role with web/literature tool access. Tools: ToolUniverse MCP (PubMed, ArXiv, Semantic Scholar, etc. via Compact Mode — see [ToolUniverse](https://github.com/mims-harvard/ToolUniverse)), Tavily, plain HTTP fetch.
- **planner** has NO tools. Pure reasoning over the user's request — produces the JSON plan.
- **orchestrator** has the `delegate_to_subagent` primitive only.

## Optional roles (add when warranted)

The three-role topology is the default. Add these only when you have evidence the simpler version is failing:

- **compressor** (`subagents/compressor/`) — interposes between researcher and writer when researcher output exceeds ~10K tokens and the writer is choking on context. Reads researcher findings, produces ranked/deduplicated summary.
- **writer** (`subagents/writer/`) — separates report assembly from research when the output format is complex (templated, multi-section with strict structure). Reads compressed findings + plan, produces final markdown.
- **fact-checker** (`subagents/fact-checker/`) — between researcher and writer for citation grounding. DRB's FACT score targets exactly this. Add if FACT scores are low.

These come from [open_deep_research](https://github.com/langchain-ai/open_deep_research) (which has 4 roles) and DRB's eval criteria (which justifies a fact-checker). They are *not* in AI-Q. Adopt only when measurable.

## When to deviate

- **Skip planner** for shallow mode (< ~5 sources, < ~3 questions). Researcher works directly off user request, bounded to 10 turns / 5 tool calls.
- **Skip the whole topology** for direct questions answerable in one tool call. The orchestrator handles them inline.
- **Add roles back** based on eval signal, not aspirationally. Each extra role is one more LLM call's worth of latency and cost.

## Sources

- [NVIDIA AI-Q blueprint](https://github.com/NVIDIA-AI-Blueprints/aiq) — three-role topology, shallow/deep mode split, context isolation rule, Postgres-for-checkpoints architecture
- [NVIDIA AI-Q blog](https://developer.nvidia.com/blog/how-to-build-deep-agents-for-enterprise-search-with-nvidia-ai-q-and-langchain/) — narrative explanation
- [open_deep_research](https://github.com/langchain-ai/open_deep_research) — alternative role decomposition (summarizer/researcher/compressor/writer), source for the optional roles above
- [deep_research_bench](https://github.com/Ayanami0730/deep_research_bench) — RACE + FACT eval criteria; informs whether to add fact-checker
- [ToolUniverse](https://github.com/mims-harvard/ToolUniverse) — researcher's tool belt

## Pair with the public stack

The topology is yours; the role-level workflows can lean on existing skills:

- **`academic-research-skills:ars-plan`** — Socratic chapter-by-chapter planning the planner role can adopt for its JSON plan
- **`academic-research-skills:ars-lit-review`** — annotated bibliography format for the researcher's output when the task is literature-style
- **`antigravity-bundle-llm-application-developer:context-window-management`** — keeping each role under budget; load-bearing for the "context isolation" rule
- **`firecrawl:firecrawl-search`** + **`firecrawl:firecrawl-scrape`** — alternative web tool belt for the researcher when ToolUniverse isn't enough
- **`huggingface-skills:huggingface-papers`** — when the researcher needs to surface arXiv/HF papers specifically
