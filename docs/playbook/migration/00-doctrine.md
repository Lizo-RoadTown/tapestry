# 00 — Doctrine

Binding rules for any migration into Tapestry, including future client-forks. These are the rules that, when broken, have produced the biggest course-corrections so far.

## Rule 1 — Tapestry is the canonical product system

Legacy source repos (today: the-loom, Make_Skills; future: a client's prior monorepo) are **sources**, not permanent product boundaries.

Language to avoid:

- "X stays [source-side]"
- "Tapestry catches up to the source"
- "Tapestry subscribes to [source]"
- "[Source] is the heavy-lifting support module"

Language to use:

- "Tapestry is the canonical product system"
- "[Source] is the source prototype for [capability]"
- "During migration, [source] remains live as a legacy compatibility/source repo — temporarily"
- "Once [capability] reaches parity in Tapestry, the legacy version is frozen"

**Why this matters:** the wrong language compounds. If you call something "loom-side ownership" once, the next agent reading the doc treats it as a permanent product boundary and won't propose moving it.

## Rule 2 — Parallel-build governs pace, not destination

Migration is incremental — no big-bang, no pause-and-port. But the destination is not optional. Every prototype change should carry a declared import path into Tapestry.

This rule looks contradictory until you separate **pace** (incremental, source can keep building) from **destination** (always Tapestry, no permanent forks). The operator's standing rule *"we keep building in the [prototype] repo until the new one it built fully, a lot of the information isn't yet known. I am still experimenting"* is a pace rule, not a destination rule.

## Rule 3 — Source-stabilize → migrate → freeze legacy → archive

Per capability:

1. **Stabilize** in source — get it working, smoke-verified, contract clear
2. **Migrate** into Tapestry — typically `git mv` + import-path rewrite + extract duplicated helpers + config externalization
3. **Freeze legacy** — once parity in Tapestry is verified, the source version stops receiving changes
4. **Archive** — once all useful capabilities from a source repo have migrated, the source repo is archived or made read-only

**No final runtime dependency** should remain on any source repo as a separate system.

## Rule 4 — Capability names stay Tapestry names, regardless of deployed-service count

v1 may deploy fewer physical services for operational simplicity (e.g., 3 deploys instead of 9). But the internal Tapestry repo MUST preserve clean modules for every named capability: project-registry, candidate/architecture-registry, policy, audit, telemetry-ingestion, project-observatory, skill-making, local-observer, adapters, CLI/SDK, integrations.

If a v1 deploy bundles `policy/` inside `architecture-registry/`'s pod, both modules still exist as separate directories with separate import paths. Future splits become `render.yaml` edits, not refactors.

## Rule 5 — Two prep PRs before any cross-repo lift

Before moving code from a source repo into Tapestry:

- **Prep-1 (source side)**: extract or normalize anything that's about to gain a new home. Externalize hardcoded URLs to config. Extract duplicated modules to local `packages/` first. Both moves are reversible **inside the source repo** and make the Tapestry lift mechanical.
- **Prep-2 (Tapestry side)**: confirm the destination slot exists, has a README, and is wired into `render.yaml` placeholders.

The lift itself then becomes `git mv` + import-path rewrite. Surprises happen during prep, not during the cross-repo move. See [03-auth-bridge-duplication-trigger.md](03-auth-bridge-duplication-trigger.md).

## Rule 6 — Customers experience ONE product

Buyer/product framing: ONE product, Tapestry. Not "Tapestry plus loom." Not "Tapestry built on the loom platform." Not "Mem0 competitor with extras." The differentiation is the loop: *agency becomes structure*.

This rule applies to docs, marketing, dashboard copy, error messages, and the public API surface. If a customer would see a phrase that references the source repo by name, that's a bug.

## Related

- Loom-memory rulebook: `feedback_tapestry_is_canonical_loom_and_make_skills_are_legacy_source_2026_06_13`
- Loom-memory pace rule: `feedback_tapestry_parallel_build_not_pause_and_migrate_2026_06_12`
- Loom-memory application record: `tapestry_canonical_framing_applied_2026_06_13`
- Architecture: [`../../architecture/UMBRELLA.md`](../../architecture/UMBRELLA.md)
- v1 plan: [`../../proposals/2026-06-13-v1-scope-and-roadmap.md`](../../proposals/2026-06-13-v1-scope-and-roadmap.md)
