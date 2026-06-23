# 05 — Cloud observer vs developer-session hook

## The pattern

A platform builds a "discipline plugin" that fires on every developer session. The plugin handles a mix of work — some genuinely interactive (per-response PROBE rules, cite-files-not-memory checks), some that's supposed to be **continuous observation** (scan all registries, surface drift candidates, score skill invocations over time). The interactive work fires correctly. The observational work never runs because hooks only fire DURING developer sessions, and the observation needs to happen continuously — weekends, vacation, while the developer is focused on a different project.

Weeks pass. Category drift accumulates. The operator eventually notices manually and asks: *"how many of these skills are actually agents?"* — and that question, which the platform was meant to surface as candidates, has been silent for weeks.

## The story (self-observer for docs-agent skills, 2026-06-13)

Operator PROBE'd 16 entries in `docs-agent/skills/`. Verdict: 8 of 16 are agent-shaped (multi-step PROBE → artifact production), not skill-shaped (methodology / output-shape guidance). 1 was tool-shaped (pure I/O transform). The platform should have surfaced these as `agent` and `inline_tool` candidates in the architecture-registry weeks ago. It didn't.

Root cause: `agentic-upskilling`, a skill in `docs-agent/skills/agentic-upskilling/SKILL.md`, has the description: *"Active practice — observe how the user actually works, identify which skills they invoke repeatedly, and promote those into tools when promotion criteria are met. Use continuously, not as a one-shot."*

That description names the missing observer. But the implementation is a methodology doc, not a running service. There is no cron, no daemon, no scheduled job pointing at it. The capability has been described as "continuous" for weeks while no infrastructure runs it.

The current discipline plugins (`tapestry-discipline`, `make-skills-discipline`) handle interactive guardrails correctly on UserPromptSubmit. They were the obvious place to file the observational work too. **That filing was wrong.** Per-response guardrails and continuous observation have different shapes; co-locating them looks ergonomic but produces silent failure.

## The rule

**Any capability that runs CONTINUOUSLY, autonomously, without being prompted by a user action belongs in a deployed cloud service. NOT a hook. NOT a skill. NOT a methodology doc.**

Specifically:

- **Hooks are for INTERACTIVE GUARDRAILS** — per-response checks, real-time PROBE enforcement, output validation. They fire during user activity, by design.
- **Cloud services are for CONTINUOUS OBSERVATION** — registry scans, drift detection, telemetry rollups, scheduled reports. They run on their own clock, regardless of who's working.
- **Skills are for OUTPUT-SHAPE METHODOLOGY** — patterns the parent agent should follow when producing something. They're guidance, not execution.

The three are not interchangeable.

### When the gap exists in any system

Smell-test signals:

- A skill or agent description includes phrases like "continuously", "periodically", "scheduled", "observed across time", "runs on a schedule"
- But the only artifact behind the description is a methodology doc
- No cron, no daemon, no scheduled job points at it
- Grep for the capability name across cron-config files (`render.yaml` cron stanzas, GitHub Actions schedules, etc.) returns nothing
- The capability has been "in the platform" for weeks/months without producing artifacts

That's the smell. Anything supposed to run continuously without a scheduler pointing at it is unwired.

### Pre-flight check before authoring any "smart" capability

1. **Is this invoked synchronously by a user prompt** (skill, methodology) — or does it run **continuously without prompting** (observer, daemon, scheduled service)?
2. **If continuous**: it MUST be a deployed cloud service with its own schedule. NOT a hook. NOT a skill.
3. **Verify with grep**: after authoring the capability, `grep -rE "schedule:|cron|every \d+ (min|hour|day)"` across the deploy configs. If nothing points at it, the capability is misfiled.
4. **Verify with telemetry**: if the capability is supposed to emit artifacts, check the destination 24h after authoring. If no artifact landed, the capability didn't run.

## Why this is worth a playbook chapter

It's a category of failure that's invisible until someone notices manually. Unlike a bug (which produces a visible error), a missing observer produces **silence** — no candidates, no diff, no log entry. The platform looks healthy. The operator feels the gap only when they happen to think *"hey, shouldn't the system have surfaced X by now?"*

This chapter exists so future authoring catches the misfile during DESIGN, not weeks later during MANUAL AUDIT.

The same shape applies to many systems:

- Newsletter platform with a "weekly digest" feature implemented as a UI button instead of a scheduled job
- Monitoring tool with a "trend detection" methodology doc instead of a scheduled scan
- Code review tool with a "duplicate-PR detector" skill that's never wired to a webhook
- Compliance system with a "drift checker" rule that only fires when an admin opens the dashboard

Each is the same misfile.

## How this was fixed (concrete, for cross-reference)

Built `the-loom/services/self-observer/` as a Render Python-cron service:

- Pattern lifted from commit `2731822` (the loom-keep-warm cron precedent — `type: cron` + `runtime: python` + `schedule: "0 */6 * * *"`)
- Walks platform-owned repos via GitHub API
- Reads frontmatter + first ~100 lines of body per entry
- Runs signal-detection rules (agent / tool / skill / orphan)
- POSTs candidates to architecture-registry's existing `POST /candidates/` endpoint using `source_path="path_b"` (platform observatory discriminator) + evidence_refs detail
- Auth: JWT Bearer with self-host fallback (no Authorization header → SELF_HOST_TENANT_ID)
- E1.5 gate: signal rules unit-tested against the 16 docs-agent fixtures. 18/18 passing.

Eventual Tapestry destination: `tapestry/services/self-observer/`. Today's source-of-truth: the-loom (legacy source repo).

The misfiled `agentic-upskilling` skill becomes the **system prompt of this observer**. The description that was correct for weeks finally has an implementation behind it.

## Skills queued for promotion

- `cloud-observer-vs-hook-classifier.skill.md` — pre-flight check that asks "synchronous-user-prompted OR continuous-autonomous?" and routes the capability to the right place during authoring
- `verify-deployed-service-points-at-it.skill.md` — automated grep across cron-config files to detect capability descriptions that have no scheduler pointing at them

## Related

- Lesson: `lesson_self_observer_gap_revealed_by_skill_mislabel_audit_2026_06_13`
- Plan: `tapestry/docs/proposals/2026-06-13-skill-vs-agent-conversion-and-self-observer.md`
- Implementation: `the-loom/services/self-observer/`
- The mislabeled skill at the center: `docs-agent/skills/agentic-upskilling/SKILL.md`
- Bridge (output side): `bridge_closed_end_to_end_2026_06_13` — this chapter is about closing the INPUT side
- Analogous failure: `tapestry/docs/playbook/migration/04-render-cron-orphans.md` — both are "system depended on a human noticing"
