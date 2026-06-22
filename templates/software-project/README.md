# `templates/software-project/`

**Status:** Populated — Step 5b, 2026-06-21. Two shapes: `ui/` + `agent/`.

Seed template for a general software-dev project. This is the **generic** domain — no domain-specific guide; pick a shape and go.

## Pick a shape

| Shape | When | Clone |
|---|---|---|
| [`ui/`](ui/) | Web / frontend app (has a `docs/UX_CONTRACT.md`) | `templates/software-project/ui/` |
| [`agent/`](agent/) | Agent app with a durable memory backbone | `templates/software-project/agent/` |

Each shape leaf is self-contained (see [`../README.md`](../README.md) for the file inventory). Clone the leaf, fill the `{{PLACEHOLDER}}` tokens, and you have a Tapestry-wired project.

## Provenance

- `project-starter/templates/_common/` (base) + `project-starter/templates/{ui-app,agent-app}/` (shapes).
- Companion: [`../../packages/cli/`](../../packages/cli/) (Step 5a) — the `loom` CLI that wires projects post-clone.
