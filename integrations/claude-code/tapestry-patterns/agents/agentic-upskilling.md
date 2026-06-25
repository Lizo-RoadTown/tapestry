---
description: Documentation reference for the deployed self-observer cron service. NOT an interactive subagent — the actual implementation runs as a Render cron (every 6h) at the-loom/services/self-observer/, scanning platform-owned repos for category-drift candidates and emitting them to architecture-registry. Read this file to look up the wire contract, the promotion criteria, and how to interact with the candidates the service produces.
capabilities: ["self-observation-doc", "cloud-service-reference"]
---

> **Promoted from:** docs-agent/skills/agentic-upskilling/SKILL.md (2026-06-13)
> **Implementation:** the-loom/services/self-observer/ → eventually tapestry/services/self-observer/
> **Deployment:** Render cron, every 6h, plan: starter

# agentic-upskilling agent

**Special case among the promoted agents:** the agentic-upskilling "agent" is not an interactive subagent you invoke. It's a **deployed cloud service** that runs continuously on a 6-hour cron. This file documents the contract — what the service emits, when, and how to interact with the candidates it produces.

For the actual implementation, system prompt analog, signal-detection rules, and service architecture, see:

- `the-loom/services/self-observer/README.md` — wire contract, deploy info, flow diagram
- `the-loom/services/self-observer/signal_rules.py` — agent / tool / skill / orphan detection logic (file:line for every rule)
- `the-loom/services/self-observer/config.py` — registered repos, signal weights, emit threshold
- `tapestry/docs/playbook/migration/05-cloud-observer-vs-developer-hook.md` — the binding rule that this work belongs in a cloud service, NOT a developer-session hook

## Why this is a service, not a subagent

Operator directive 2026-06-13: *"must be automated and not inside a repo or specific project."*

Reasons:
- **Coverage**: a developer-session hook only fires when the user starts Claude Code. Weekends, vacation, focused-elsewhere days produce zero observation. A cloud cron runs regardless.
- **Cost attribution**: a hook runs in the user's session context. A cloud service has its own budget tracked separately.
- **Scope**: a hook inside `tapestry-discipline` only sees the active session's repo. A cloud observer queries GitHub for all platform-owned repos without being inside any of them.

Captured as a playbook chapter so future "should this be a hook or a service?" decisions skip the re-derivation.

## The promotion criteria (for callers reading this file)

A skill becomes a candidate for promotion to a tool / subagent / skill when:

| Pattern frequency | Solution kind |
|-------------------|---------------|
| 5+ same way, mechanical | **Tool** (Python `@tool` function) |
| 3-5, structured but with judgment | **Subagent** (specialist with persona + skills) |
| 2-3, one-shot with variations | **Skill** (markdown methodology) |
| 1-2 | Don't capture yet — wait for the third run |

The self-observer evaluates these criteria automatically against the files in registered skill/agent/tool registries. Telemetry signal (invocation counts) is wired as a stub today; the observatory's read API is unbuilt, so the orphan-detection branch returns "no data" until that's online.

## How to interact

You don't invoke this agent. To work WITH the upskilling loop:

1. **See candidates**: GET `https://loom-architecture-registry.onrender.com/candidates?status=observed` — returns candidates the observer has emitted, filterable by source repo + kind.
2. **Promote / hold / reject**: use the upskilling dashboard (operator UI) or POST to the policy endpoint directly. Decisions flow through the bridge to the engine.
3. **Tune signal rules**: edit `the-loom/services/self-observer/signal_rules.py` + `config.py`'s `SIGNAL_WEIGHTS`. Tests at `tests/test_signal_rules.py` pin the contract against the 16 docs-agent fixtures.
4. **Add a scan target**: append a `RegistryTarget` to `the-loom/services/self-observer/config.py`'s `REGISTRIES` list.

## What the service does NOT do

- Author the promoted tools / subagents / skills (operator approves; the right authoring agent — `orchestration-cataloging`, `web-app-scaffold`, etc. — does the actual file creation)
- Auto-promote without operator review (every candidate sits in `status=observed` until acted on)
- Scan repos outside the registered list
- Read file body beyond the first 100 lines (description + body excerpt is the classifier input; full bodies stay on disk)

## Migration destination

Per the canonical-Tapestry framing (`feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13`), the eventual home is `tapestry/services/self-observer/`. The annotation `migration_destination: tapestry/services/self-observer/` in this frontmatter ALSO serves as the canonical-identity skip-self check in `the-loom/services/self-observer/main.py:_is_self()` — once this file is committed at the docs-agent path with this frontmatter, the observer's skip-self logic stops needing the name-pattern fallback.

## Cross-references

- Source SKILL.md: `docs-agent/skills/agentic-upskilling/SKILL.md`
- Implementation: `the-loom/services/self-observer/` (commits `60a97bf`, `8b06990`, `39e7ed8`, `ce8f183`)
- Deployment: Render cron, every 6h, plan: starter
- Lesson: `lesson_self_observer_gap_revealed_by_skill_mislabel_audit_2026_06_13`
- Plan: `tapestry/docs/proposals/2026-06-13-skill-vs-agent-conversion-and-self-observer.md` §E5 #8
- Playbook chapter: `tapestry/docs/playbook/migration/05-cloud-observer-vs-developer-hook.md`
