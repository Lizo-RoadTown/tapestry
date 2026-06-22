# Research-project domain guide

Domain-specific context for a research / knowledge-synthesis project. Pair this with the shape scaffold (`agent/` or `ui/`) and the base `CLAUDE.md` in the leaf.

Grounded in `SDE_Extraction` (the `sde-extraction-dev` research instance).

## What a research project is

A research-heavy project: the work is deep literature review, data analysis, and synthesis of findings. The eventual product may be undefined at the start — surfacing it is part of what the research does. Expect it to begin as a developer/research instance (`<project>-dev`, the `agent` shape) and gain a product/user-facing instance (`<project>-app`, the `ui` shape) only when a UI surface materializes.

## Domain adapter

- **`research-project` adapter** for the research work, plus the **`development`** adapter for code work. The research instance is researcher- + developer-facing; a later app instance is product-facing.

## The integrity boundary: `Agent Drafts/` vs `Human validated/`

This is the load-bearing convention for a research project. It makes the human-in-the-loop division of labor legible and auditable:

- **`Agent Drafts/`** — everything an LLM/agent/workflow produced that a human has **not** yet checked. Agents and workflows write here. Each artifact gets a provenance header (what generated it, when, from what input, validation pending).
- **`Human validated/`** — artifacts the operator has read, verified, corrected, and stands behind. **Agents never write here.** Only the operator promotes a draft in, with a note on what they validated/changed.

The diff between the two folders is the evidence of the human's contribution. Treat `Human validated/` as an integrity boundary, not a convenience folder.

## Work surfaces

- `research/` — the primary work surface (literature, data, notebooks, findings).
- `research/findings/*.md` — synthesized outputs.
- Any vendored prior-work folders should be treated as **read-only reference** (don't edit, don't commit as embedded-repo pointers) — gitignore them.

## Research skill set

Lean on these (from the `liz-patterns` plugin, by name):

- `deep-research-pattern` — the playbook for heavy literature/data work.
- `eval-deep-research` — evaluating research outputs.
- `document-parsing` — extracting structure from source documents (essential when the corpus is large).
- `documentation` — Diátaxis methodology for writing findings.
- `layered-explanation` — ELI5 → quick reference → depth → mental model.

## Token discipline

Heavy research means many source documents. Read the smallest viable scope, use `document-parsing` to extract structure efficiently, and prefer `Grep` + scoped `Read` over loading whole documents.
