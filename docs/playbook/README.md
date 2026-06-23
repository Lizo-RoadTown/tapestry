# Tapestry playbook

A living record of how migrations + structural work actually happen here — what went right, what went wrong, what we'd do differently. Organized so that future migrations (Tapestry-to-client-fork, Tapestry-to-self-host, future capability lifts) can draw on it without rediscovering the same friction.

## The three-layer model

The playbook mirrors Tapestry's own loop: *observe → decide → compile*.

### Layer 1 — Atomic capture (loom-memory)

Raw lessons get written at the moment of friction as `lesson` records in the shared loom-memory MCP. The discipline rule is *"save friction as memory at the moment of correction"*. These records are granular, dated, and capture context the way a code comment or PR description can't.

Examples that already exist:

- `lesson_third_spec_drift_payload_schema_2026_06_13`
- `lesson_engine_url_drifted_from_spec_2026_06_13`
- `lesson_hmac_format_mismatch_pr_70_2026_06_12`
- `lesson_cross_fleet_tenant_id_uuid_mismatch_2026_06_12`

These are the substrate. The playbook chapters in this directory cite them by name.

### Layer 2 — Synthesized narrative (this directory)

When a chunk of work completes — a migration step, a bridge integration, a refactor — we write a playbook chapter that organizes the accumulated `lesson_*` memories into a story. Each chapter covers:

- **The pattern** — what we kept hitting
- **The story** — concrete events, with file:line citations
- **The rule** — what to do next time
- **Backlinks** — `[[lesson_name]]` references to the underlying memories
- **Related chapters** — cross-references to other playbook entries

Chapters live in topical subdirectories (`migration/`, `bridges/`, `infra/`, ...) and are numbered within each topic.

### Layer 3 — Promoted skills

When a playbook rule proves repeatable — same shape appears in 2+ migrations or 2+ bridge integrations — it graduates into an actual `SKILL.md` invokable by agents. Promotion goes through the same candidate → policy → compile loop that Tapestry runs for every other skill. **The migration teaches Tapestry how to teach the next migration.**

Promoted skills live under `tapestry/engine/skills/migration/` (planned) once the migration capability lands. Until then, candidate skills are tracked in the playbook's "Skills queued for promotion" section of each chapter.

## When to write a chapter

- Immediately after a multi-day chunk of work resolves (good or bad)
- When 2+ `lesson_*` memories share a category (the third one is when you suspect a pattern)
- When you catch yourself thinking *"I keep doing this"* — that's a skill candidate
- When a client-fork or new-customer scenario is about to begin and a past lesson applies — write the chapter to capture the rule before you reuse it

## When NOT to write a chapter

- For one-off bugs — those stay as a `lesson_*` memory, not a chapter
- For routine ticket work — chapters are for structural learnings, not feature work
- When the rule isn't clear yet — leave it as a memory; promote later

## Cross-repo discipline

Both `tapestry-discipline` and `make-skills-discipline` plugins enforce *"save corrections as feedback memory immediately"* at every UserPromptSubmit. The playbook is the synthesis layer for those memories. Future agents (including Tapestry-agent) should treat playbook chapters as binding context — they encode lessons the operator and prior agents already paid for.

## Index

### `migration/`

- [00-doctrine.md](migration/00-doctrine.md) — canonical-product framing + parallel-build pacing + capability-ownership rules
- [01-bridge-spec-drift-pattern.md](migration/01-bridge-spec-drift-pattern.md) — when spec drift looks like 3 bugs but is one category problem
- [02-cross-fleet-uuid-mismatch.md](migration/02-cross-fleet-uuid-mismatch.md) — `DEFAULT_TENANT_ID` vs `SELF_HOST_TENANT_ID`, Option B mapping resolution
- [03-auth-bridge-duplication-trigger.md](migration/03-auth-bridge-duplication-trigger.md) — extract on 3-4 verbatim dupes; self-documenting trigger comments
- [04-render-cron-orphans.md](migration/04-render-cron-orphans.md) — script teardown without cron teardown; checklist for any infra retirement
- [05-cloud-observer-vs-developer-hook.md](migration/05-cloud-observer-vs-developer-hook.md) — continuous-observation work belongs in a deployed cloud service, NOT a session hook; smell-tests + pre-flight check

(Future topical subdirectories planned: `bridges/`, `infra/`, `agents/`, `release/`.)
