# Plan: fix the seed + close the upskilling-audit loophole

**Date:** 2026-08-20
**Author:** primary agent, synthesized from 3 research agents + 3 verification/drift agents
**Status:** Draft — pending operator sign-off + second drift check

This plan fixes two coupled problems the operator surfaced:
1. `tapestry init` under-seeds projects (no docs/, no CLAUDE.md, no skills home, and it's hard-broken on the retired `the-loom` repo).
2. The `tapestry-discipline` Stop hook's upskilling/skills audit has a loophole that made it silently never fire in the tapestry repo.

Everything below is grounded in file:line research (see the three research reports this session). "Required" vs "new convention" is called out explicitly per [[feedback-dont-fabricate-design-structure-when-operator-hasnt-decided]].

---

## Workstream A — Close the hook loophole + make the audit actually produce output
Ships in **tapestry-discipline 0.1.18**.

### A1. Fix the false-positive detector (`stop_audit.py`)
The detector counts a report as "done" if the phrases `skills invoked this session` + `promotion candidates` appear anywhere in assistant text — which happens whenever the codebase is discussed. It false-fired in **163/166** in-scope sessions. Fix (exact edits from research):
- Delete `UPSKILLING_REPORT_MARKERS` (stop_audit.py:125-128) and `UPSKILLING_MEMORY_WRITE_REGEX` (:131-133).
- Add anchored constant `UPSKILLING_REPORT_NAME_REGEX = re.compile(r"^upskilling_report_session_\d{4}_\d{2}_\d{2}$")`.
- In the `tool_use` branch (:199-212): set `upskilling_report_seen = True` only when the tool **block name** contains `memory_write` AND `input["name"]` matches the anchored regex. (Old code never checked the tool name — a `memory_read`/`memory_delete` of a prior report also tripped it. Closes that too.)
- Remove the `text_concat_for_marker_scan` accumulator (:173, :218-226) and the `all(...)` detection.

### A2. Update the test
`tests/test_stop_audit_upskilling.py:106-118` (`test_upskilling_report_detected_via_canonical_phrases`) asserts prose-only detection — retire it or convert to a memory_write case. The existing `test_upskilling_report_detected_via_memory_write_tool_call` already satisfies the new predicate.

### A3. Author the missing report-format spec
Root cause of the `obs_detected=0` streak (observer parsed zero skills in all 149 runs): **the report format is undocumented.** Every citation points at `skills_private/agentic-upskilling/SKILL.md:92-113`, a dead Make_Skills-era path. Create a real spec — recommended: a "Report format" section in `docs/CORE_DIRECTIVES.md` Directive 3 (which today lists only section names) plus a canonical `SKILL.md`. The canonical format (chosen so the current observer parser matches it unchanged):

```markdown
## Agentic-upskilling report — session <YYYY-MM-DD>
### Skills invoked this session
- <skill-slug> (<N> uses)
### Tools called this session
- Read (30)
### Promotion candidates
- <name> — <one-line rationale>   (or: None)
### Demotion candidates
- None
### Recommendations
- <text>
```
Persisted via `memory_write(name="upskilling_report_session_<YYYY_MM_DD>", record_type="lesson", content=<body>, project_tags=[<LOOM_PROJECT_ID>])`.

### A4. Repoint dead citations
`skills_private/agentic-upskilling/SKILL.md` → the new spec, in: `stop_audit.py:123,142-143` (UPSKILLING_WARNING text), `observer.py:136,238`, `test_observer.py:64`, `skills/periodic-architectural-checkin/SKILL.md:129`. Also the parallel dead `skills_private/concrete-rule/SKILL.md` in `session_start.py:184` → `integrations/claude-code/skills/concrete-rule/SKILL.md` (already tracked in the audit doc S3).

### A5. Harden the observer anchor (defense-in-depth)
Loosen the skills-section anchor `"skills invoked this session"` → `"skills invoked"` (observer.py:272,281) so a natural `## Skills invoked` header doesn't silently drop skills, and fix the inconsistent test fixture `test_observer.py:553`.

### A6. Fold in two audit items already scoped for 0.1.18
- S2: `docs_mcp` MCP server in `plugin.json:34-37` won't resolve for external installs (bundle it or ship as dependency).
- Bump `plugin.json` + `marketplace.json` 0.1.17 → 0.1.18.

---

## Workstream B — Redesign the `init` seed (the "full skeleton")
Ships in **tapestry-cli 0.1.5**. Operator confirmed: full skeleton + telemetry from env vars.

### B1. Decouple from `the-loom` (required — init is currently hard-broken without it)
- Rewrite `_write_env_file` to source the 5 `OTEL_*` vars from `os.environ` (else commented placeholders); drop the `loom_env` param.
- Delete the `render.yaml` hard-fail (init.py:378-381), `_read_loom_env` (:56-76), and the `--loom-repo` arg (:359-361) — all dead once env-sourced.
- Update next-steps text (:458-459).

### B2. Fix the architecture-snapshot gap — Option 2, CORRECTED (drift-check #2)
The SessionStart hook runs **project-local** `cwd/scripts/architecture_snapshot.py`; if absent it silently skips. `init` never creates it → **no project ever generates snapshots.** Operator chose Option 2 (plugin-side, no per-project copies, fixes already-seeded projects).
**Correction from drift-check #2:** the canonical `architecture_snapshot.py`/`architecture_diff.py` live in **tapestry-patterns** (`integrations/claude-code/tapestry-patterns/scripts/`), NOT tapestry-discipline. So the discipline hook must **resolve the tapestry-patterns scripts dir** and run them with `--repo-root=<project cwd>` (canonical defaults repo_root to cwd and writes to `repo_root/docs/architecture-snapshots`). Lift the proven fallback-chain resolver already in `tapestry/scripts/architecture_snapshot.py:26-54`. This is a `session_start.py` change in 0.1.18. Declare the cross-plugin dependency (tapestry-discipline now needs tapestry-patterns present for snapshots). `init` seeds NO snapshot scripts.
**Consequence for Workstream D:** machine 2 must have tapestry-**patterns** installed (not only discipline), or snapshots silently no-op there.

### B3. Seed the skeleton (content from research, grounded in Biosensors/tapestry)
- `CLAUDE.md` — parameterized template, inlines CORE DIRECTIVE 1 (does not reference a docs file a fresh repo lacks).
- `.gitignore` — `.env`, python/OS junk, `.claude/logs/`, `.mcp.json`, the `docs/architecture-snapshots/*` + `!.gitkeep` block.
- `docs/architecture-snapshots/.gitkeep` (load-bearing dir, gitignored contents).
- `docs/architecture/README.md`, `docs/decisions/README.md` (see open decision on name).
- `skills/README.md` — **NEW convention** (no script requires it; distinguishes skills/ vs `.project-intelligence/local-skills/` vs the plugin).
- Adjust the now-dead `.gitignore`-missing warning (init.py:436).

### B4. Keep what already works
`.mcp.json` (with the 0.1.4 auth header), `.env` (LOOM_PROJECT_ID — the master scope gate), `.project-intelligence/project-context.json` (valid UUID — required by the observer).

### B5. Tests + docstring de-loom; bump `pyproject` 0.1.4 → 0.1.5; release via the trusted-publishing tag.

---

## Workstream C — Small correctness (from verification)
- C1: `main.py` vs MCP middleware order their auth guards oppositely — a value-less non-Bearer header returns anonymous in REST but 401 in MCP. Align `main.py` to check scheme-before-empty-token for parity. Not a security hole; ride in a small PR or fold into an existing one.

---

## Workstream D — The real finish line: second machine + the flip (operator-gated)
Per the drift-watcher: **do not flip `LOOM_ALLOW_ANONYMOUS_SELF_HOST=0` until the second machine is provisioned + verified.** Sequence:
1. On Poppytart/LizO5: set `TAPESTRY_MEMORY_API_KEY` in `~/.claude/settings.json` env; disable the two legacy plugins; install tapestry-discipline 0.1.18. (Exact steps to be provided.)
2. Verify BOTH machines read memory with the key present.
3. Flip anon off on Render. Rollback = unset the flag (instant).
4. Separately: rotate the plaintext Render API token in `the-loom/.mcp.json`.

---

## Resolved decisions (operator, 2026-08-20)
1. **B2 snapshot fix: Option 2** — the tapestry-discipline SessionStart hook runs its OWN canonical scripts via `${CLAUDE_PLUGIN_ROOT}/scripts/`; no project carries copies. Fixes already-seeded projects too. `init` does NOT seed snapshot scripts.
2. **Decision-record dir name: `docs/adr/`** — matches the rest of the fleet. The seeded README + CLAUDE.md reference `docs/adr/` (not `docs/decisions/`).
3. **CORE DIRECTIVE 1: inline in the seeded CLAUDE.md** — do NOT seed a `docs/CORE_DIRECTIVES.md` into consumer projects.

## Suggested PR / execution structure
- **PR-1 (tapestry-discipline 0.1.18):** A1-A6 + B2 Option 2 (hook uses own scripts). Plugin-only.
- **PR-2 (tapestry-cli 0.1.5):** B1, B3, B4, B5. CLI-only. Depends on B2 decision.
- **PR-3 (tiny):** C1 auth parity.
- **D** is operator-executed after PR-1/PR-2 ship + release.
