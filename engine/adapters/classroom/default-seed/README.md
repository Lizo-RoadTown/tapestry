# `adapters/classroom/default-seed/`

Canonical seed for projects attaching the `classroom` adapter. See [`../../default-seed-contract.md`](../../default-seed-contract.md) for the cross-adapter contract.

## What this seed materializes into

When the scaffolder spawns a project with `-Adapter classroom`, this directory is copied as `.project-intelligence/` in the new repo. Placeholders (`{{project-slug}}`, etc.) get filled. The result is a project that the engine can immediately consume as a Layer-3 instance of the classroom adapter.

## Adapter-specific values baked in

| File | Adapter-fixed value |
|---|---|
| `{{instance-slug}}/attached-adapters.json` | `"name": "classroom"` |
| `{{instance-slug}}/project-type.json` | `"project_type": "classroom-support-app"` |
| `{{instance-slug}}/observatory-config.json` `pattern_detection_triggers` | `repeated_confusion`, `study_pattern_recurrence`, `synthesis_request_pattern`, `assignment_workflow_pattern` |
| `{{instance-slug}}/agent-profile.json` `system_prompt_seed` | student-facing learning companion (judgment-light, friction-honest, no autopilot on substance) |

## What the operator fills after spawn

- `{{instance-slug}}/project-context.json` `stack.*` — the actual tech stack (typically a hub/web app)
- `{{instance-slug}}/project-context.json` `class_info.*` — the course details (name, term, schedule, instructors)
- `{{instance-slug}}/project-context.json` `current_state_*` — what's working / what's pending today

## Memory boundary

Classroom instances typically pair with a `development` instance of the same project (e.g., Summer 2026 Hub's `ime4020-hub-app` paired with `ime4020-hub-dev`). The classroom instance MUST NOT read or write to its paired development instance — that's the operator's repo state, not the student's learning context. The default seed leaves `must_not_read` / `must_not_write_to` empty; operator fills the paired instance slug after spawn if applicable.

## When this adapter is the right choice

Per [`../README.md`](../README.md): classroom-support-apps where the agent helps a student learn (take notes, synthesize, ask questions, study). One student or small set, class/course as the primary org unit, student-facing agency. Learning-loop output (study sheets, summaries) is the value.
