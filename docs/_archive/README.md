# docs/_archive/

Provenance archive — content lifted from legacy source repos that's worth preserving but does NOT serve as canonical Tapestry documentation.

When new Tapestry-specific authoritative versions are written, the archived copies remain here as historical reference. Don't link to archive files from canonical docs — link to the GitHub source repo blob instead if a historical citation is needed.

## Current contents

- **`make-skills-architecture.md`** — Make_Skills' top-level ARCHITECTURE.md. Describes the Make_Skills engine, dual-mode commitment, three-layer model. Tapestry's canonical architecture lives in [`docs/architecture/UMBRELLA.md`](../architecture/UMBRELLA.md) + [`MANIFESTO.md`](../../MANIFESTO.md). A Tapestry-specific top-level `ARCHITECTURE.md` is a queued follow-up.

- **`make-skills-contributing.md`** — Make_Skills' CONTRIBUTING.md. References `Make_Skills/platform/deploy` + `Make_Skills/web` paths that don't exist in Tapestry. A Tapestry-specific `CONTRIBUTING.md` is a queued follow-up.

- **`make-skills-agents.md`** — Make_Skills' AGENTS.md (cross-IDE persona file). References `./subagents/` and `./skills/` relative to Make_Skills root. A Tapestry-specific `AGENTS.md` is a queued follow-up.

## Why archive instead of lift-to-root

Lifting these verbatim to `tapestry/{ARCHITECTURE,CONTRIBUTING,AGENTS}.md` would create misleading docs at the root that say "Make_Skills" and reference paths that don't exist. Authoring fresh Tapestry-specific versions is net-new content work (out of audit §2.11's strict scope). Archiving preserves the provenance until that authoring happens.
