# Permanent session reports + snapshot-resolver fix

**Status:** Approved (design) — implementation in `feat/permanent-session-reports`
**Authors:** Liz, agent-assisted
**Date:** 2026-08-29

## Problem

The agentic-upskilling report (CORE DIRECTIVE 3) is written only to the remote
loom-memory database, as a `lesson` record named `upskilling_report_session_*`
(stop_audit.py:129-131, 143-146). Nothing writes it to disk. Consequences:

- No permanent, human-readable, committed record to sift for documentation or to
  research lessons-learned after something goes wrong.
- Two on-disk homes that `tapestry init` scaffolds — `.project-intelligence/
  lessons-learned/` and `promotion-candidates/` — are populated by **nothing**
  (grep of every plugin script; only the observer writes `workflow-candidates/`).
  They wait on an "agency optimizer" service that does not exist.
- Separately, the SessionStart architecture-snapshot pipeline is silently a no-op
  on installed repos: `_resolve_patterns_scripts_dir` (session_start.py:328-334)
  looks for `~/.claude/plugins/cache/tapestry/tapestry-patterns/scripts` but the
  install has a version segment (`…/tapestry-patterns/0.1.2/scripts`), so the path
  misses → `patterns_scripts_unresolved` (session_start.py:378-381).

This is platform functionality (the `tapestry-discipline` plugin), so it affects
every opted-in repo, not just one.

## Decision

1. **The Stop hook persists the emitted upskilling report to a committed Markdown
   file**, in addition to the existing memory write. Human-readable, greppable, in
   git history. Auto-committed by the hook.
2. **Fix the snapshot resolver** to glob the version segment.
3. **Roll both out** via one plugin version bump; every opted-in repo inherits on
   `/plugin update`.

Out of scope (YAGNI): structured JSON records, and reviving the empty
`lessons-learned/` / `promotion-candidates/` dirs (needs the nonexistent agency
optimizer).

## Component A — report persistence (Stop hook)

The report content already exists in the transcript as the `content` field of the
`memory_write` tool call the hook already detects (stop_audit.py:209-216). No
re-derivation:

- `_scan_session_metrics` also captures that `content` + record `name` (latest wins).
- New `_persist_report_to_disk(cwd, session_id, content, name)`:
  - writes `cwd/docs/session-reports/<YYYY-MM-DD>-<session8>.md` (date parsed from
    the record name, fallback to today; `<session8>` = first 8 chars of session id).
  - prepends a small YAML header (session id, project, mirrored memory record name,
    "generated_by") so the file is self-describing when grepped later.
  - idempotent: if the file already holds identical content, do nothing (prevents
    re-writing/re-committing the same report on later Stop fires in the session).
  - best-effort git: `git -C <cwd> add -- <file>` then
    `git -C <cwd> commit -m <msg> -- <file>` (pathspec commit — touches only this
    file, never the agent's staged work). Wrapped in try/except with a short
    timeout; any failure is swallowed and logged. The file is on disk regardless.
- Called from `main()` only when `upskilling_report_seen` is true — the same gate
  that already runs the observer.

`docs/session-reports/` is not gitignored (init ignores only `architecture-snapshots/*`).

## Component B — snapshot-resolver fix

In `_resolve_patterns_scripts_dir`, add version-globbed candidates:
`~/.claude/plugins/cache/tapestry/tapestry-patterns/*/scripts` (highest version
first) and the equivalent sibling under `CLAUDE_PLUGIN_ROOT`. Existing literal
candidates stay (harmless). Verified target: `…/tapestry-patterns/0.1.2/scripts/
architecture_snapshot.py` exists.

## Failure semantics

The Stop hook must never raise or block (its existing contract). Every new step —
file write, git add, git commit — is wrapped in try/except; on any failure the
hook logs and proceeds. Worst case: a report isn't persisted this session; memory
still has it and the next session retries.

## Rollout

- Changes live in `integrations/claude-code/tapestry-discipline/scripts/`
  (`stop_audit.py`, `session_start.py`) + a new test.
- Version-bump `plugin.json` and the `marketplace.json` tapestry-discipline mirror
  0.1.18 → 0.1.19. **Note:** `marketplace.json` currently carries unrelated
  uncommitted changes from another workstream (tapestry-patterns skills), so the
  mirror bump is coordinated separately rather than bundled into this PR.
- Merge to `main` → every opted-in repo (7 class repos, hub, tapestry) inherits on
  the next `/plugin update`. That update is the operator-controlled rollout gate.

## Testing

New `tests/test_session_report_persist.py`: feed a synthetic transcript containing
a `memory_write` report block → assert the `.md` file is written with the header +
report body, and that a second identical run is a no-op. Resolver fix covered by a
unit test that globs a temp versioned dir.
