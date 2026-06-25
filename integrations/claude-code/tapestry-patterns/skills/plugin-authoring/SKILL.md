---
name: plugin-authoring
description: Use when a project's shape calls for its own Claude Code plugin — scaffold a personalized plugin (project-specific guards + the user's OWN backend endpoints), test it, and publish it to the user's OWN marketplace. The universal tapestry-discipline plugin is the always-on baseline; this builds the project-specific layer on top of it, pointed at the user's own services. Invoke for "make me a plugin", "publish a plugin", "this project needs its own hooks/guards", or when project intelligence shows a project needs personalized discipline.
---

# Authoring a Claude Code plugin (personalized, self-host)

Tapestry ships ONE **universal** plugin — `tapestry-discipline` — that works for everyone with no backend: PROBE-first reminders, citation enforcement, dev-vs-runtime audit, friction-as-memory prompts. Those hooks make zero network calls.

When a project's *shape* needs more — project-specific guards, or the user's own memory / registry / telemetry backend — you generate a **personalized** plugin pointed at **the user's** services and publish it to **the user's** marketplace. This skill is how an agent does that end to end.

**The one rule that is never negotiable:** a user's plugin points at the **user's** backend. Endpoints come from the user's env (`TAPESTRY_MEMORY_MCP_URL` / `LOOM_MEMORY_MCP_URL` / `TAPESTRY_ARCHITECTURE_REGISTRY_URL` / …) or a placeholder. Never hardcode anyone else's deployment URL, service name, tenant id, or personal identifier into a shipped plugin. (This is the failure the universal plugin was hardened to prevent — see `integrations/claude-code/tapestry-discipline/scripts/session_start.py` `_agent_context_base_url` / `_backend_configured`.)

This is an **agentic** skill: probe, decide, build, publish, report — don't hand the user a checklist. (Authored per `agentic-skill-design`.)

## 1. PROBE — read before deciding

- **Is the universal plugin already there?** `/plugin list`; check `~/.claude/plugins/`. If `tapestry-discipline` is installed, do NOT reinvent its behavior — the personalized plugin *adds* to it, it doesn't replace it.
- **Project shape — what guards does THIS project actually need?** Read the repo: recurring corrections, the project type, `.project-intelligence/` config, what keeps breaking. A research project, a classroom project, and a service repo need different guards. Don't invent guards the project doesn't need.
- **The user's backend:** which endpoints are configured? `env | grep -E 'TAPESTRY_|LOOM_'`. If none, the plugin ships with placeholders + degrades to behavior-only (that's fine — see Self-host rules).
- **The user's GitHub:** `gh auth status`, `gh api user -q .login` — the marketplace is a repo under THEIR account.
- **The starter scaffold:** `tapestry make-plugin --help` (the generator that ships with `tapestry-cli`) produces the skeleton; prefer it over hand-building.

## 2. DECIDE — defensible defaults, no questions

| Decision | Default | Disconfirm if |
|----------|---------|---------------|
| Build on / extend | the universal `tapestry-discipline` (don't duplicate its hooks) | the project needs a fundamentally different hook set |
| Plugin name | `<project>-guard` (project-specific) | the user names it |
| Hooks included | only the ones the project's shape needs (often just PreToolUse guards) | probe shows more are warranted |
| Backend endpoints | from the user's env, placeholder fallback (`your-*.example.com`) | the user has a deployed backend → use their env var, never a literal |
| Marketplace home | a new repo under the user's GitHub account | the user already has a plugins repo |
| Author / identity | the user's own name/handle | — never the platform author |

## 3. ACT — scaffold, personalize, test, publish

1. **Scaffold:** `tapestry make-plugin <name>` → emits `<name>/.claude-plugin/plugin.json`, `hooks/hooks.json`, `scripts/`, and a `.claude-plugin/marketplace.json`. (Or hand-build using the anatomy below.)
2. **Personalize** (copy the patterns from `tapestry-discipline`, don't reinvent):
   - `plugin.json` `mcpServers` URLs use `${LOOM_MEMORY_MCP_URL:-https://your-memory-host.example.com/mcp/memory/}` — env-driven, placeholder fallback.
   - Hook scripts that call a backend must be **best-effort** (never raise from a hook) and **env-gated** (skip the call cleanly when the URL resolves to a placeholder — copy `_backend_configured()`), so the plugin never times out for an unconfigured user.
   - Add the project's guards to `pre_tool_use.py` / a new script. Keep behavior-only guards (no network) where possible — they work for everyone.
   - Author = the user. No platform names/URLs/IDs.
3. **Test:** enable it locally (`/plugin install <name>@<localmarketplace>` or point Claude Code at the dir), trigger each hook, confirm the behavior fires and that with NO backend configured it degrades cleanly (behavior works, no timeout, no scary violation).
4. **Publish to the user's OWN marketplace:**
   - `gh repo create <login>/<name> --public --source . --push` (or push to an existing plugins repo).
   - The repo root needs a `.claude-plugin/marketplace.json` with the user as `owner` (name only — no personal email).
   - Install: `/plugin marketplace add <login>/<name>` then `/plugin install <name>@<name>`.

## 4. STOP CONDITIONS — only these

- `gh auth status` fails → the user must `gh auth login` (interactive).
- Publishing to an org/repo the user hasn't authorized.
- A genuine fork probing couldn't resolve (e.g. two equally-valid hook designs).

Everything else: decide, build, publish, report.

## 5. REPORT

```
Built: <name> — <one-line: what guards, which hooks>
Published: <login>/<name>  (install: /plugin marketplace add <login>/<name>)
Backend: <configured from $VAR | placeholder — behavior-only until the user sets $VAR>

Decisions:
- <only non-defaults, with reason>

Next: <one concrete action or "nothing — installed and working">
```

## Plugin anatomy (reference)

```
<name>/
  .claude-plugin/
    plugin.json        # name, version, author (user), mcpServers (env-driven), keywords
    marketplace.json   # owner (user, name only), plugins[]  — at the marketplace REPO root
  hooks/
    hooks.json         # SessionStart | UserPromptSubmit | PreToolUse | Stop -> command
    run-python.mjs     # node shim that invokes the python hook (copy from tapestry-discipline)
  scripts/
    pre_tool_use.py    # behavior guards (local, no backend) — the universal-safe layer
    session_start.py   # OPTIONAL: memory recall — env-gated + best-effort
    ...                # any project-specific scripts
```

The canonical, hardened reference is `integrations/claude-code/tapestry-discipline/` — copy its `run-python.mjs`, its best-effort/env-gated network pattern, and its graceful-degradation logic. Do not copy any endpoint, name, or id from it; those come from the user.

## Self-host rules (binding)

1. **Endpoints from the user's env, never hardcoded.** Placeholder fallback (`your-*.example.com`), env override (`${VAR:-placeholder}` in JSON; the env-precedence resolver in scripts).
2. **Degrade cleanly with no backend.** Behavior hooks (PROBE/audit) always work; service features (memory/registry/telemetry) skip cleanly when unconfigured — no timeout, no violation. Copy `_backend_configured()`.
3. **No personal identifiers** (names, URLs, service names, tenant ids, machine paths, private repo names) baked into a shipped plugin.
4. **Best-effort hooks.** A hook never raises and never blocks the session on a network failure.

## Pair with

- `superpowers:writing-skills` — frontmatter, naming, triggering (invoke before editing any SKILL.md).
- `superpowers-developing-for-claude-code:developing-claude-code-plugins` — the general mechanics of plugin/hook/marketplace structure.
- `superpowers:verification-before-completion` — required at REPORT: evidence (the hook actually fired) before "done".
- `agentic-skill-design` — the PROBE→DECIDE→ACT→REPORT shape this skill follows.
