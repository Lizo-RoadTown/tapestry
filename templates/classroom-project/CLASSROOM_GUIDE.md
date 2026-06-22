# Classroom-project domain guide

Domain-specific context for a classroom / course-hub project. Pair this with the shape scaffold (`ui/` or `agent/`) and the base `CLAUDE.md` in the leaf.

Grounded in `classroom-hub-starter` (reference implementation: `Lizo-RoadTown/summer-2026-hub`).

## What a classroom project is

A **term course hub**: one deployable app holding all of a term's classes, with an embedded Claude study assistant and openable readings. The look is intentionally consistent across terms; what changes per term is the course registry + the bundled readings, not the scaffold.

## Domain skill + adapter

- **`course-setup` skill** — drives the per-class intake (syllabus + Canvas pastes → registry entries). This is a domain skill that stays with the classroom template; it is **not** part of the general `liz-patterns` library.
- **`classroom` adapter** — the project-type adapter that carries the domain judgment (parsing syllabi, Canvas → assignments, dates, accommodations). Domain judgment lives in the skill/adapter, not baked into the app scaffold.

## What you change vs. what's fixed

- **Edit per term/class:** the course registry (e.g. `src/data.js`) and the bundled readings under `public/readings/<course-id>/`.
- **Fixed scaffold — do not redesign:** the theme/design tokens, the app shell, the agent panel, the server, and `render.yaml`.

## Domain rules

- **Readings are links, never dead paths.** Bundle readings into the served `public/readings/` directory; never render a local `C:\...` path as clickable (`file://` is blocked in browsers).
- **Privacy.** Bundled textbook scans are copyrighted. Keep the repo + the deployed service **private**; don't share the URL. There is no auth gate by default.
- **Verify before claiming done.** Build + run + observe in a browser (hub renders, a PDF opens, notes persist) before reporting success.

## Build flow (driven by the `course-setup` skill)

1. Scaffold from this template (clone the chosen shape leaf, fill placeholders).
2. Run `course-setup` intake per class (syllabus + Canvas → registry entries).
3. Bundle readings so they're openable from the served directory.
4. Add each class to the course registry.
5. Install, build, run, and verify in a browser before claiming done.
6. Deploy (set `ANTHROPIC_API_KEY` on the service).
