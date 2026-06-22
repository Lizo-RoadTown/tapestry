# `adapters/development/default-seed/`

Canonical seed for projects attaching the `development` adapter. See [`../../default-seed-contract.md`](../../default-seed-contract.md) for the cross-adapter contract.

## What this seed materializes into

When the scaffolder spawns a project with `-Adapter development`, this directory is copied as `.project-intelligence/` in the new repo. Placeholders (`{{project-slug}}`, etc.) get filled. The result is a project that the engine can immediately consume as a Layer-3 instance of the development adapter.

## Adapter-specific values baked in

| File | Adapter-fixed value |
|---|---|
| `{{instance-slug}}/attached-adapters.json` | `"name": "development"` |
| `{{instance-slug}}/project-type.json` | `"project_type": "software-development"` |
| `{{instance-slug}}/observatory-config.json` `pattern_detection_triggers` | `repeated_correction`, `repeated_dev_task_shape`, `agent_mistake_class_repeats`, `naming_inconsistency_repeats` (from this adapter's `pattern-triggers.json` planned shape) |
| `{{instance-slug}}/agent-profile.json` `system_prompt_seed` | development-companion persona (PROBE / cite file:line / dev-vs-runtime / friction-as-memory / layered-explanation) |

## What the operator fills after spawn

- `{{instance-slug}}/project-context.json` `stack.*` — the actual tech stack (frontend, backend, deploy)
- `{{instance-slug}}/project-context.json` `current_state_*` — what's working / what's pending today
- `{{instance-slug}}/project-context.json` `active_dev_focus` — one sentence on what's being worked on right now

## When this adapter is the right choice

Per [`../README.md`](../README.md): software-development repos where the agent helps a developer build/refactor/debug/document code. One developer (or small team), repo as the primary org unit, developer-facing agency. Most consuming projects get a `-dev` instance of this adapter even if their primary adapter is something else.
