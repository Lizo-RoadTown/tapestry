---
name: concrete-rule
description: Use when designing or fixing a system invariant that, if violated, causes a core failure of the whole project. Forces failure-mode anticipation + defense-in-depth + loud visibility into every concrete rule, so a single config drift, a forgotten plugin update, or a service drop cannot silently break the system. Triggered by phrases like "this must always be there", "this is the whole point", "never lose touch with X", "fundamental to the project", or when you identify a load-bearing dependency whose absence has been silently breaking sessions/projects/deploys.
when_to_use: Whenever a single line in one config file, a single env var, or a single service being down would degrade or destroy a core capability of the project — apply this skill BEFORE writing any one-line fix. The one-line fix is a rope tied at one end; this skill is concrete.
---

# Concrete Rule

## What this skill is

A methodology for protecting **system invariants whose absence would cause core project failure**, by anticipating failure modes and building defense-in-depth from the start.

A "concrete rule" is any guarantee whose violation kills a primary product capability. Examples Liz has hit:

- **loom-memory must be wired in every project** — without it, cross-project memory (the whole point of the-loom) is silently absent
- **RLS policies must apply on every tenant-scoped query** — without them, cross-tenant data leakage
- **OTel telemetry must reach Grafana from every hook** — without it, observability is theatre
- **`app.tenant_id` must be set on every Postgres transaction** — without it, RLS returns zero rows silently (the "make_skills says they have no access to memory" pattern)
- **Auto-deploy hooks must fire on every push to main** — without them, code on `main` doesn't match what's running

If you find yourself thinking *"this thing has to be true, otherwise the system doesn't work"*, you've identified a concrete rule. Don't fix it with a one-line config change. Apply this skill.

## The five hallmarks of a concrete rule

A claim is a concrete rule when ALL FIVE of these are true:

1. **Foundational** — a primary product capability stops working when it's absent
2. **Cross-cutting** — it must hold at multiple points in the system (multiple projects, multiple services, multiple deployments)
3. **Easy to forget** — there's no compiler, type checker, or test that automatically catches its absence
4. **Silent on failure** — when it breaks, the system keeps running but the capability is gone (no exception, no loud error)
5. **Recurring** — it will need to be re-established every time a new project, service, or environment is added

If only some are true (e.g., a build-time check catches it), use a lighter mechanism. The full skill is for the cases where ALL five hold.

## The protocol — eight layers of concrete

For every concrete rule, build all eight layers below. Skipping any is the equivalent of leaving one end of the rope untied.

### Layer 1 — The mechanism itself works correctly

Before any defense layers, the underlying thing must actually function. PROBE the source code, verify the runtime behavior, write a positive test. If the mechanism is broken, no defense layer can save it.

**Example:** for loom-memory, this is the MCP server actually returning correct results for `memory_recall` / `memory_write`. Verified before any wiring work.

### Layer 2 — Make the runtime tolerant of common misconfiguration

The server / service should degrade gracefully and predictably when callers misconfigure. Not silent fallback to a wrong value; not crash; loud and correct.

**Example:** the MCP HTTP transport should accept no Bearer (self-host fallback) but reject malformed Bearer (401). Both paths end up with a known tenant; neither silently uses the wrong one.

### Layer 3 — Centralize the invariant in the lowest-coupling place

Where should the rule be enforced so it covers the largest fleet with the smallest change? Often that's a shared plugin, a base class, a middleware, a database default. Not in N copy-pasted configs.

**Example:** add loom-memory to the `loom-discipline` plugin's `mcpServers` block. The plugin is enabled once at user level → every CC session in every project gets it from one place.

### Layer 4 — Defense in depth: independent fallback layers

A single layer can fail. Plugin gets disabled, a config file gets deleted, an env var gets renamed. Build at least ONE more independent layer that re-establishes the invariant.

**Example:** ALSO add loom-memory to each project's `.mcp.json` directly. Plugin disabled? Project config still works. Both layers fail? Skip to Layer 5.

### Layer 5 — Future-proof the seed: scaffolders, init scripts, templates

Any tool that CREATES a new project, service, deployment, or environment must include the invariant by default. New projects are the highest-risk birthplace of drift.

**Example:** `scripts/new-loom-project.ps1` writes `.mcp.json` with loom-memory pre-populated. `loom-cli/loom_cli/init.py` does the same. Every future project ships with the rule satisfied.

### Layer 6 — Make absence LOUD, not silent

If the invariant fails despite Layers 1-5, the system must visibly tell the operator. Health checks that include the invariant. Startup banners that name it. Hook reminders that surface it in agent context. Anything but silent.

**Example:** the SessionStart hook does a 2-second ping to the MCP endpoint. If it doesn't respond, surface a LOUD warning in additionalContext: `"WARNING: loom-memory MCP unreachable. Memory tool calls will fail. Restart CC, check service status."`

### Layer 7 — Codify in a directive document AND in the agent's discipline

Write the rule down where future-you and future-agents will see it before they touch the system. Put it in CORE_DIRECTIVES.md. Reference it in CLAUDE.md. Inject it into UserPromptSubmit hook reminders. Save it as a `user`-type memory in the loom so auto-recall surfaces it every session.

**Example:** `docs/CORE_DIRECTIVES.md` lists "loom-memory access is mandatory in every CC session." The discipline plugin's `pre_tool_use.py` checks for loom-memory tool registration and reminds the agent if absent.

### Layer 8 — Test the invariant. Test the failure modes. Test the recovery.

Write tests that fail loudly if any layer regresses. Integration test the server-side fallback. Static check the plugin.json for the MCP entry. CI check that scaffolder output includes the entry. Don't ship without them.

**Example:** `services/agent-context/tests/test_mcp_self_host_fallback.py` covers the four-case auth table (no-bearer, valid-bearer, malformed, missing-claims). `scripts/audit_concrete_rules.py` walks the fleet and reports any project missing the entry.

## Failure-mode template

For every concrete rule, fill out this table BEFORE shipping:

| Failure | Detection | Recovery |
|---|---|---|
| (e.g. plugin disabled) | (Layer 6 — startup warning) | (Layer 4 — project-level config still works) |
| (e.g. project's .mcp.json corrupted) | (Layer 6 — SessionStart ping fails) | (Layer 3 — plugin provides it) |
| (e.g. server itself down) | (health check + Layer 6 warning) | (auto-recall via REST still works; document the manual recovery) |
| (e.g. config drifts on new project) | (Layer 8 — audit script) | (Layer 5 — scaffolder includes it by default) |
| (e.g. env var renamed) | (startup check + Layer 6 warning) | (single-source-of-truth constant) |

The completeness of this table IS the deliverable. A missing row is a future incident.

## Anti-patterns

These are how concrete rules get violated. Watch for them in your own thinking and other agents' suggestions:

| Anti-pattern | Why it fails |
|---|---|
| "Just add it to the README" | Documentation doesn't enforce anything. Future-you won't read it. |
| "I'll write a one-line fix and we're done" | Single-point-of-failure. The rope tied at one end. |
| "It's working now, ship it" | "Now" is one moment. Tomorrow some other change breaks it silently. |
| "We'll catch it in code review" | Reviews miss config drift constantly. Especially across N projects. |
| "I added a comment explaining it" | Comments rot. Tests don't. |
| "The team knows the rule" | Knowledge in heads doesn't survive churn. |
| "There's a checklist in the wiki" | Same as documentation; doesn't enforce. |
| "If it breaks, we'll notice in production" | The whole point of concrete rules is silent failure mode. You WON'T notice. |
| "It's a temporary workaround" | Temporary workarounds become permanent the day after they're written. |

## When to invoke this skill

- Whenever you find yourself thinking *"this has to be true everywhere"*
- Whenever the user says *"this is the whole point"*, *"the system depends on this"*, or *"don't ever lose this"*
- Whenever you discover a recurring outage / silent failure caused by the same missing thing
- Whenever a new project / service / deployment is being created (apply ALL the project's concrete rules to it from birth)
- Whenever you're about to fix a fundamental issue with a one-line change — STOP, apply this skill instead

## The eight-layer audit checklist

Use this as a literal checklist before declaring a concrete rule satisfied:

- [ ] **Layer 1 — Mechanism works.** PROBE the source. Write a positive test. Verify by running it.
- [ ] **Layer 2 — Runtime tolerates misconfiguration.** Fallbacks are loud and correct, not silent or wrong.
- [ ] **Layer 3 — Centralized.** Lowest-coupling place that covers the fleet.
- [ ] **Layer 4 — Defense in depth.** At least one independent fallback layer.
- [ ] **Layer 5 — Seeded.** Scaffolders / init scripts / templates include it by default.
- [ ] **Layer 6 — Loud absence.** Failure surfaces in startup, health checks, agent context.
- [ ] **Layer 7 — Documented + disciplined.** CORE_DIRECTIVES.md + agent hook reminders + memory record.
- [ ] **Layer 8 — Tested.** Integration tests, static checks, fleet audit script.

If ANY layer is incomplete, the rule is not concrete yet. Don't ship.

## Cross-reference

When invoking this skill, also save a memory record:

```
memory_write(
  name="concrete_rule_<short-name>_<date>",
  record_type="user",
  content="<the rule itself> + the 8 layers built to enforce it.",
  why="Fundamental invariant. Future agents must NEVER let this regress. Anti-patterns listed in concrete-rule SKILL.md.",
  project_tags=["<every project that depends on it>"],
)
```

The `user`-type record will surface at every auto-recall via the SessionStart hook, so the rule is in every agent's context from the start.
