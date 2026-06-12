# Tapestry migration approach

How legacy prototype code becomes Tapestry code.

## The principle

**Curated migration, not lift-and-shift.** Each piece imports to Tapestry when:

1. It has stabilized in its current home (no active feature work in flight on that piece)
2. Its boundaries are clear (we know what it owns and what it doesn't)
3. The operator has approved the migration of this specific piece
4. The destination slot in Tapestry has its scope settled

If any of those is no, the piece stays in its source repo. **Parallel-build, not pause-and-migrate.**

See loom-memory `feedback_tapestry_parallel_build_not_pause_and_migrate_2026_06_12`.

## What gets imported, what gets rewritten

For each source piece, the migration decides one of three:

| Decision | What it means |
|---|---|
| **Lift** | Copy with minimal changes. Suitable for stable services with clean APIs and no personal-history residue. |
| **Refactor** | Import the substance + rewrite the structure to match Tapestry conventions. Suitable for code with mixed concerns or naming drift. |
| **Rewrite** | Treat the source as reference + author fresh in Tapestry. Suitable for code with unsettled architecture or material technical debt. |
| **Retire** | Don't import. Mark the source for archival. Suitable for code that no longer reflects the current architecture. |

## The migration docs

| Doc | What it tracks |
|---|---|
| [`legacy-repo-inventory.md`](legacy-repo-inventory.md) | Per-source-repo: what's there, what's worth keeping, what's worth retiring |
| [`import-map.md`](import-map.md) | Per-source-file (or per-source-directory): destination in Tapestry + decision (Lift / Refactor / Rewrite / Retire) + status |
| [`what-to-keep.md`](what-to-keep.md) | The keep list — anchors the curated migration |
| [`what-to-retire.md`](what-to-retire.md) | The retire list — what doesn't survive review |
| [`naming-corrections.md`](naming-corrections.md) | Names that drifted during prototyping and need correction on import |

## The migration workflow per piece

```text
1. Operator decides "piece P is ready for migration"
2. Update import-map.md: P → tapestry/<destination> with Decision
3. Open a PR in Tapestry: import P
   - If Decision == Lift: copy + minimal Tapestry-isms (CLAUDE.md ref, license header)
   - If Decision == Refactor: import + restructure
   - If Decision == Rewrite: author fresh; reference the source in commit message
4. Update import-map.md: status → Imported, with destination commit ref
5. Optionally: open a follow-up PR in the source repo marking the piece "moved to Tapestry: <link>"
6. Eventually (separate decision): archive or retire the source location
```

## What does NOT happen during migration

- No big-bang imports of whole repos
- No silent naming changes — every rename gets a `naming-corrections.md` entry
- No "while we're at it" refactors — each migration PR has one purpose
- No deletes from source repos until the operator says the source can archive
- No agent self-assigns a migration — operator scopes each one

## Why this approach

- **Experimentation continues** in source repos without interference
- **Architecture solidifies** as each piece moves (the import IS the boundary-clarification moment)
- **Reversibility** — if a Tapestry import isn't working, the source is still authoritative
- **Auditable** — `import-map.md` records what came from where, when, and why

## Initial state (2026-06-12)

- Repo spawned with skeleton + docs
- Zero code imported
- Zero migration PRs opened
- `legacy-repo-inventory.md` is a first-pass audit, not a complete one
- `import-map.md` is empty (no imports yet)
