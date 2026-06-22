---
name: documentation
description: Plan, write, and audit project documentation using the Diátaxis framework, Architecture Decision Records (ADRs), and the docs-as-code workflow. Use whenever a task involves creating, reviewing, restructuring, or auditing documentation — including READMEs, API references, tutorials, design docs, or in-code docstrings.
license: All-Rights-Reserved
metadata:
  author: Elizabeth Osborn
  version: "1.0"
---

# Documentation skill

You help users plan, write, and audit documentation. You enforce three rules
that, applied together, prevent the most common documentation failures:

1. **Diátaxis** — every document is exactly one of four types
2. **ADRs** — every load-bearing decision is captured as an Architecture Decision Record
3. **Docs-as-code** — docs live in the repo, get reviewed in PRs, and follow language-native docstring conventions

## When to use this skill

- Creating a new README, tutorial, how-to guide, reference page, or explanation
- Restructuring a docs folder that "feels messy"
- Auditing an existing repo's documentation for completeness
- Writing or updating a docstring
- Capturing the rationale for an architectural choice
- Drafting a new ADR
- Reviewing a PR that touches documentation

## When NOT to use this skill

- The task is to write code, not docs (use a coding skill instead)
- The user asked for marketing copy or sales material (different audience, different rules)
- The user is asking for a quick informal note in chat — don't over-engineer

## Core rule: classify before you write

Before writing any documentation, ask: **what is this for?** It must be exactly one of:

| Type | Audience state | Goal | Writing voice |
|------|---------------|------|---------------|
| **Tutorial** | "I'm new" | Learn by doing | Lead the reader by the hand |
| **How-to guide** | "I have a goal" | Solve a specific problem | Goal-oriented recipe |
| **Reference** | "I need to look something up" | Describe accurately | Neutral, exhaustive, structured |
| **Explanation** | "I want to understand" | Provide context and theory | Discursive, conceptual |

If a draft mixes two types, **split it**. That mixing is the #1 cause of bad docs.

For the full theory, see [references/diataxis.md](references/diataxis.md).

## Workflow: writing a new doc

1. **Classify** — pick exactly one Diátaxis type. Name the file accordingly (e.g. `tutorials/getting-started.md`, `how-to/deploy-to-railway.md`, `reference/api.md`, `explanation/architecture.md`).
2. **Write to the type's voice** — see the table above. Mismatched voice is a smell.
3. **Check the lead** — first paragraph should make the type obvious without saying it.
4. **Cross-link** — tutorials link to relevant how-to guides; how-to guides link to reference; explanation links to all three. Never the reverse for tutorials.
5. **Test** — for tutorials and how-to guides, follow your own steps on a clean checkout.

## Workflow: auditing existing docs

Run this checklist against a repo:

- [ ] Is there a top-level README?
- [ ] Does the README answer: what is this, who is it for, how do I install it, how do I get started?
- [ ] Is documentation organized by Diátaxis type (or at least separable)?
- [ ] Are there any documents that mix two types? (Most common: tutorial + reference combined)
- [ ] Are load-bearing decisions captured as ADRs in `docs/adr/`?
- [ ] Do public functions/classes have docstrings in the language's idiomatic format?
- [ ] Are docs in the same repo as code, reviewed in the same PRs?

Use [scripts/audit_docs.py](scripts/audit_docs.py) for an automated first pass.

## Workflow: writing an ADR

When you make a non-obvious architectural decision (choosing a database, a framework, a deployment target, a data format), capture it as an ADR.

1. Run [scripts/new_adr.sh](scripts/new_adr.sh) `<short-title>`
2. Fill in: **Context**, **Decision**, **Consequences**, **Status** (Proposed → Accepted/Rejected/Superseded)
3. Commit alongside the code change that implements it
4. Never edit an accepted ADR — write a new one that supersedes it

ADRs are tiny (often one screen). They age much better than design docs because they capture *why* at the moment of decision.

For the full template and pattern, see [references/adr.md](references/adr.md).

## Workflow: writing docstrings

Match the language convention. Don't invent your own.

- **Python** → PEP 257 + Google style or NumPy style. See [references/docstrings.md](references/docstrings.md).
- **JavaScript/TypeScript** → JSDoc / TSDoc. See [references/docstrings.md](references/docstrings.md).
- **Other languages** → look up the idiomatic standard before writing.

A docstring should answer: what does this do, what are the inputs, what does it return, what raises. Not: how it does it (that's a comment, and probably shouldn't exist either if the code is clear).

## What good documentation looks like

- **Discoverable** — there's an obvious entry point (README) that fans out
- **Single-purpose** — each doc is one Diátaxis type, no mixing
- **Reviewed** — docs flow through PRs like code, not edited in isolation
- **Cited** — internal links use relative paths so they survive renames
- **Maintained** — outdated docs are deleted, not left to rot

## What bad documentation looks like

- A `docs/` folder with 40 markdown files and no index
- A "getting started" page that's actually a reference dump
- API reference that explains *why* the API exists (that's an explanation doc)
- Tutorials that say "see the docs for details" (the tutorial **is** the docs for that learner)
- ADRs written months after the decision (write them at decision time)
- Docstrings copied between functions without updating the parameters

## References (load these on demand)

- [references/diataxis.md](references/diataxis.md) — full Diátaxis theory and per-type writing patterns
- [references/adr.md](references/adr.md) — ADR template, examples, and anti-patterns
- [references/docs-as-code.md](references/docs-as-code.md) — the philosophy and practical workflow
- [references/docstrings.md](references/docstrings.md) — language-specific docstring formats and examples
- [references/readme-standards.md](references/readme-standards.md) — what belongs in a top-level README

## Scripts

- [scripts/new_adr.sh](scripts/new_adr.sh) — create a new numbered ADR file from the template
- [scripts/audit_docs.py](scripts/audit_docs.py) — scan a repo for documentation gaps

## Assets

- [assets/adr-template.md](assets/adr-template.md) — blank ADR
- [assets/readme-template.md](assets/readme-template.md) — minimal README skeleton

## Pair with the public stack

The three rules (Diátaxis / ADRs / docs-as-code) are the discipline. Templates and prose-quality passes are better served by current public skills:

- **`antigravity-bundle-oss-maintainer:documentation-templates`** — current README / CONTRIBUTING / CHANGELOG templates
- **`antigravity-bundle-architecture-design:architecture-decision-records`** — current ADR format; pair with this skill's §ADRs
- **`elements-of-style:writing-clearly-and-concisely`** — prose-quality pass before merging any docs PR
- **`antigravity-bundle-creative-director:copy-editing`** — UI / user-facing copy (different audience than developer docs)
- **`antigravity-bundle-oss-maintainer:changelog-automation`** — CHANGELOG.md generation
