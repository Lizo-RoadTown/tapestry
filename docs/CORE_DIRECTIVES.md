# Core Directives

The canonical, enforced directive set for working in Tapestry. This is the file
the discipline plugin hooks, the `concrete-rule` skill, and the docs-site cite as
`docs/CORE_DIRECTIVES.md`. [`CLAUDE.md`](../CLAUDE.md) summarizes D1 and D2 inline
because it loads into every session; this file is the full set of all three.

**Numbering note.** The currently-installed `loom-discipline` hooks (the-loom
lineage) label the end-of-session upskilling rule "CORE DIRECTIVE 2" in their
reminder strings. Here that rule is **D3** — the reminder text is off by one until
the plugin is updated. The rules themselves are unchanged; only the label lags.

---

## Directive 1 — loom-memory access is mandatory

Every session in this repo MUST have the `loom-memory` MCP server reachable.
Tools: `memory_read`, `memory_write`, `memory_recall`, `memory_search`,
`memory_list`, `memory_delete`. Endpoint:
`https://loom-agent-context.onrender.com/mcp/memory/`. The `.mcp.json` here is
wired with the URL; the loom-agent-context self-host fallback means no JWT header
is needed (each operator gets their own fallback tenant).

**Halt condition.** If `memory_recall` / `memory_write` are unavailable, or the
SessionStart additionalContext shows `*** CONCRETE-RULE VIOLATION DETECTED ***`,
halt all substantive work and report to the operator. Do not proceed silently
using only in-session context.

## Directive 2 — Tapestry is the live system; the-loom and Make_Skills are retired sources

Tapestry is the live system. `the-loom` and `Make_Skills` are **retired legacy
source repos**, not active parallel prototypes. Some capabilities already cut over
and run from Tapestry (the loom-memory MCP at `services/agent-context/`, and
`services/project-registry/`). Others still exist only as working code in the
retired the-loom — observer, telemetry-ingestion, policy, architecture-registry,
self-observer — with README-only stubs in Tapestry.

- **Bringing a retired-source capability home into Tapestry is the normal work
  now** — not something to avoid. When a service you need still lives only in
  the-loom, migrate or rebuild it into its Tapestry home. Do NOT treat the-loom as
  a live place to build.
- **A slot README is a target, not working code** — before assuming a capability
  exists in Tapestry, check whether the real implementation still lives in
  the-loom.
- **Do NOT add any new runtime dependency on the-loom or Make_Skills.** The end
  state is Tapestry standing alone, with no runtime dependency on either as a
  separate system.
- **Scope each migration with the operator** — Lift / Refactor / Rewrite / Retire
  per piece; no big-bang lift-and-shift.

See [`docs/migration/README.md`](migration/README.md) for the migration approach.

## Directive 3 — every substantive session ends with an upskilling report

When a session crosses a substantive boundary, it MUST end with a structured
agentic-upskilling report. Without it, no promotion candidates accumulate and the
upskilling / Agency Optimizer loop has no input.

**A session is substantive iff ANY of these hold** (the boundary heuristic the
Stop hook enforces):

1. At least one git commit / push / merge / tag action, OR
2. ≥ 10 tool calls AND ≥ 3 assistant turns, OR
3. ≥ 30 assistant turns.

**The report** carries these sections (per the `agentic-upskilling` skill): Skills
invoked, Tools called, Promotion candidates, Demotion candidates, Recommendations.

**Where it goes.** Emit the report in the final response, then write it to
loom-memory as a `lesson`-type record named
`upskilling_report_session_<YYYY_MM_DD>` with the relevant `project_tags`. The
Stop hook counts the report as run **only when that `memory_write` happens** —
emitting the text alone is not enough (and is deliberately not enough: the
persisted record is what feeds the loop).

### Report format

This exact shape is what the observer parses to extract skill counts and
promotion candidates. Keep the headers and bullet shapes verbatim.

```markdown
## Agentic-upskilling report — session <YYYY-MM-DD>

### Skills invoked this session
- <skill-slug> (<N> uses)
- superpowers:systematic-debugging (3 uses)

### Tools called this session
- Read (30)
- Bash (25)

### Promotion candidates
- <name> — <one-line rationale>
- None

### Demotion candidates
- None

### Recommendations
- <free-form text>
```

Rules that keep it parseable:

- The skills header MUST contain `Skills invoked this session`.
- Skill bullets are **slug** names (no spaces) with a count: `(N uses)`, `(N)`,
  or `: N`. A bullet with no count is ignored.
- `Promotion candidates` header verbatim; each bullet uses ` — ` (em dash)
  between the name and its one-line rationale; write `None` when there are none.
- Keep `Tools called` / `Promotion candidates` after the skills section so the
  section-boundary scan bounds each correctly.

Then persist:

```
memory_write(
  name="upskilling_report_session_<YYYY_MM_DD>",   # underscores; matches the Stop-hook gate
  record_type="lesson",
  content=<the report body above>,
  project_tags=[<LOOM_PROJECT_ID>],
)
```
