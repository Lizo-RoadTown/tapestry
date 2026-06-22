# `templates/classroom-project/`

**Status:** Populated — Step 5b, 2026-06-21. Two shapes: `ui/` + `agent/`.

Seed template for a classroom / course-hub project — a term course hub holding a term's classes, with an embedded study assistant and openable readings.

## Pick a shape

| Shape | When | Clone |
|---|---|---|
| [`ui/`](ui/) | The common case: a deployable course-hub web app | `templates/classroom-project/ui/` |
| [`agent/`](agent/) | An agent-first classroom tool (e.g. an intake/grading assistant) | `templates/classroom-project/agent/` |

## Domain guidance

Read [`CLASSROOM_GUIDE.md`](CLASSROOM_GUIDE.md) before building — it covers the `course-setup` skill, the `classroom` adapter, the readings/privacy rules, and the reference implementation. The base files in each shape leaf are self-contained (see [`../README.md`](../README.md)).

## Provenance

- Base + shape: `project-starter/templates/_common` + `{ui-app,agent-app}`.
- Domain guidance grounded in `classroom-hub-starter` (reference impl: `Lizo-RoadTown/summer-2026-hub`).
