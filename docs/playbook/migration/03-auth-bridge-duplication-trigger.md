# 03 — Duplication trigger: "extract on third or fourth dupe"

## The pattern

A helper module gets copied verbatim into a second service. Then a third. Sometimes the file *itself* gets annotated with a comment like *"extract to packages/ when third or fourth service copies this"* — by the same agent who's adding the fourth copy. The annotation is a self-documenting trigger. The extraction doesn't happen because no one's checking the comment.

By the time you're auditing 6 services for migration, you've got 4+ verbatim copies of the same file and no clean extraction path because each copy has slightly diverged.

## The story (the-loom `auth_bridge.py`, caught during Tapestry planning 2026-06-13)

PROBE'd by a planning subagent during the Tapestry architecture fan-out: `services/architecture-registry/auth_bridge.py:11-14` literally says:

> *"extract to packages/shared/auth/ when third or fourth service copies this"*

By the time we noticed, **four+ verbatim copies existed** across `architecture-registry/`, `policy/`, `agent-context/`, `project-registry/`. The threshold the file itself set had been crossed silently. Same with `SELF_HOST_TENANT_ID = "1d8ec1b3-..."` duplicated across 6+ files.

The cost: PR-prep-2 of the Tapestry migration now has to extract first, then lift. If the extraction had happened on dupe #3 as the file's own comment instructed, the migration step would have been a `git mv` instead of a refactor.

## The rule

### Layer 1 — write the trigger into the file when you make dupe #2

When you `cp` a helper module to a second service:

1. Add a comment at the top of BOTH copies: *"Verbatim copy from `<other_service>/<file>` on `<date>`. Extract to `packages/<name>/` on third or fourth occurrence. See playbook/migration/03."*
2. Do NOT silently diverge the two copies. Any change goes to both, same PR.
3. If you can't keep them in sync, that's the trigger — extract NOW, not later.

### Layer 2 — check the trigger when adding any new service

When scaffolding a new service:

1. `grep -rE "Verbatim copy from|extract to packages/" services/` in the destination repo
2. For every hit, count current copies. If 3+, the new service forces the extraction. Open the extraction PR FIRST, the new service PR SECOND.
3. If 2, mark the new service's CLAUDE.md or scaffolding doc with the trigger so the next service-author sees it.

### Layer 3 — pre-migration audit

Before any cross-repo lift:

1. `grep -rl "Verbatim copy from" services/` — find every self-documenting trigger
2. For every triggered file, extract to `packages/` in the SOURCE repo as a prep PR, before the migration lift. This makes the lift mechanical.

## Signals to watch for during integration

- A file appears with the same name in two services and similar SHA
- A comment at the top of the file references "extract" or "consolidate" or "packages/"
- A constant is hardcoded the same way in 3+ places (URLs, UUIDs, retry counts)
- A subagent's PROBE summary uses the phrase "verbatim-duplicated across N services"
- Reviewing a PR that copies a helper into a new service WITHOUT touching the original

## Why this is worth a playbook chapter

This is a special case of DRY, but standard DRY linting wouldn't have caught it because:

1. The files are in different services with different deploy boundaries
2. The duplication is INTENTIONAL on dupe #2 (avoiding premature abstraction)
3. The trigger is human-readable (a comment), not machine-readable

The rule turns a soft preference ("don't repeat yourself") into a hard threshold ("extract on N=3 or N=4") with a self-documenting trigger that any audit can grep for.

## Skills queued for promotion

- `extract-duplicated-module.skill.md` — when N>=3 services share a verbatim file, extract to `packages/<name>/`, leave a one-line `from packages.<name> import *` shim if downstream code can't be updated atomically
- `pre-migration-dupe-audit.skill.md` — before any cross-repo lift, grep for verbatim-copy triggers and resolve them in the source repo first

## Related

- The file itself: `the-loom/services/architecture-registry/auth_bridge.py:11-14`
- Loom-memory: `loom_agent_tapestry_planning_synthesis_2026_06_13` (where the audit surfaced this)
- Tapestry v1 plan: PR-prep-2 in [`../../proposals/2026-06-13-v1-scope-and-roadmap.md`](../../proposals/2026-06-13-v1-scope-and-roadmap.md)
