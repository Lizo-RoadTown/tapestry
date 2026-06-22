# `templates/research-project/`

**Status:** Populated — Step 5b, 2026-06-21. Two shapes: `ui/` + `agent/`.

Seed template for a research / knowledge-synthesis project — deep literature review, data analysis, and synthesis of findings, where the eventual product may be undefined at the start.

## Pick a shape

| Shape | When | Clone |
|---|---|---|
| [`agent/`](agent/) | The common case at the research phase: an agent-driven research/extraction workspace | `templates/research-project/agent/` |
| [`ui/`](ui/) | When a web/UI surface for the findings materializes later | `templates/research-project/ui/` |

A research project often starts as `agent` (the `-dev` instance) and gains a `ui` (`-app`) instance later — mirroring the two-instance pattern.

## Domain guidance

Read [`RESEARCH_GUIDE.md`](RESEARCH_GUIDE.md) before building — it covers the `research-project` adapter, the `Agent Drafts/` vs `Human validated/` integrity boundary, and the research skill set. The base files in each shape leaf are self-contained (see [`../README.md`](../README.md)).

## Provenance

- Base + shape: `project-starter/templates/_common` + `{ui-app,agent-app}`.
- Domain guidance grounded in `SDE_Extraction` (the `sde-extraction-dev` research instance).
