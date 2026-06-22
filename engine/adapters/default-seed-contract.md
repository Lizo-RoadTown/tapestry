# `default-seed/` — the canonical seed contract

Every adapter under `adapters/<type>/` ships a `default-seed/` subdirectory. That subdirectory is the **canonical instance state template** for projects that attach this adapter. When a consuming project gets spawned with `the-loom/scripts/new-loom-project.ps1 -Adapter <type>` (or future `loom init --adapter <type>`), the scaffolder copies this seed into the project's root as `.project-intelligence/`, fills the placeholders, and the project is ready for the engine to consume.

## Why a canonical seed exists

Without one, every consuming project's seed is hand-crafted from whichever previous example was nearest at hand. Different shapes across projects means Phase 3 cross-project pattern detection can't compare candidates apples-to-apples. The canonical seed makes Layer-3 instance state structurally comparable across every project that attaches the same adapter.

## Placeholder syntax

Following the-loom's existing scaffolder convention:

| Placeholder | Filled by | When | Example |
|---|---|---|---|
| `{{project-slug}}` | scaffolder | spawn | `loom-platform` |
| `{{project-display-name}}` | scaffolder | spawn | `The Loom Platform` |
| `{{project-description}}` | scaffolder | spawn | `Official site for the loom platform` |
| `{{instance-slug}}` | scaffolder | spawn | `loom-platform-dev` |
| `{{instance-display-name}}` | scaffolder | spawn | `Loom Platform — Developer Repo Instance` |
| `{{instance-surface}}` | scaffolder | spawn | `developer-facing` |
| `{{instance-description}}` | scaffolder | spawn | one-line per-instance |
| `{{repo-local-path}}` | scaffolder | spawn | `C:\\Users\\Liz\\loom-platform` |
| `{{git-origin}}` | scaffolder | spawn | `https://github.com/...` |
| `{{visibility}}` | scaffolder | spawn | `public` or `private` |

Directory names use the same syntax: `{{instance-slug}}/` becomes `loom-platform-dev/` at spawn time.

## What's static vs templated

| Class | Examples | Owner |
|---|---|---|
| **Static** (adapter-defined, never templated) | `_schema` version strings, `core_engine_source`, `platform`, `adapter` name in `attached-adapters.json`, the `watches` list, the `pattern_detection_triggers` shape, the `events_logged` list | Adapter author (Make_Skills) |
| **Templated** (scaffolder fills at spawn time) | All `{{...}}` placeholders | Scaffolder |
| **Operator-editable after spawn** | `current_state_<date>`, `active_dev_focus`, additional pattern triggers project-specific | Operator |

## Layer-3 instance contract

Per [`docs/proposals/2026-05-31-three-layer-engine-spec.md`](../docs/proposals/2026-05-31-three-layer-engine-spec.md), every `.project-intelligence/` materialized from a `default-seed/` MUST contain:

```
.project-intelligence/
├── README.md                       (generic, explains the folder + boundary)
├── instances.json                  (instance manifest)
├── agent-profile.json              (top-level: configured agents)
├── project-context.json            (top-level: slug, name, hostname)
├── observatory-config.json         (top-level: OTLP destination)
├── lessons-learned/                (top-level candidate dir)
│   └── .gitkeep
├── local-skills/                   (top-level candidate dir)
│   └── .gitkeep
├── promotion-candidates/           (top-level candidate dir)
│   └── .gitkeep
├── workflow-candidates/            (top-level candidate dir)
│   └── .gitkeep
└── {{instance-slug}}/              (per-instance subdirectory)
    ├── project-type.json
    ├── attached-adapters.json
    ├── agent-profile.json          (per-instance system prompt seed)
    ├── project-context.json        (per-instance stack + state)
    ├── observatory-config.json     (per-instance events + dimensions + triggers)
    ├── lessons-learned/.gitkeep
    ├── local-skill-candidates/.gitkeep
    ├── promotion-candidates/.gitkeep
    └── workflow-candidates/.gitkeep
```

Projects with multiple instances (e.g., Summer 2026 Hub's `ime4020-hub-dev` + `ime4020-hub-app`) repeat the `{{instance-slug}}/` block per instance.

## What's in each `default-seed/`

Three exist today, one per stub adapter:

| Adapter | Default surface | Initial consumers |
|---|---|---|
| [`development/default-seed/`](development/default-seed/) | `developer-facing` | Make_Skills, Summer 2026 Hub `-dev`, SDE_Extraction `-dev`, loom-platform `-dev`, the-loom `-dev` |
| [`classroom/default-seed/`](classroom/default-seed/) | `student-facing` | Summer 2026 Hub `-app` |
| [`research-project/default-seed/`](research-project/default-seed/) | `researcher-and-developer-facing` | SDE_Extraction `-dev` (primary), eventually `-app` if it ships |

## Re-seed workflow

When the canonical changes (e.g., a new field added to `project-context.json`), every consuming project's `.project-intelligence/` should re-seed. The recommended approach:

1. **Diff** each consuming repo's `.project-intelligence/` against the adapter's `default-seed/` (post-templating)
2. **Migrate** new structural fields into the consuming repo with operator-set values
3. **Preserve** operator-edited content (`current_state_*`, candidate files, etc.)

A `the-loom/scripts/reseed-project.ps1` script can automate steps 1-2 once it exists. Until then, manual.
