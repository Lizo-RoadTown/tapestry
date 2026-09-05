---
name: changelog-entry
description: Use at the end of substantive work — a migration, a new capability/agent/skill/endpoint, a fix worth remembering, a scope decision (absorbed/deferred/retired), or a version bump consumers act on — to write a `docs/changelog/` entry so the change is findable later without reconstructing it from git. Write the entry in the SAME PR as the change. Skip for trivial edits (typos, comments, formatting). Pairs with roadmap-maintenance (status) and proposal-authoring/ADRs (reasoning); the changelog is the index that links to those, not a duplicate of them.
---

# Change-trail entry

Tapestry keeps a change trail at `docs/changelog/` — one file per notable change, so *what* changed, *when*, *why*, and *where it lives now* is easy to follow. This skill is the procedure for adding an entry. The system itself is defined in [`docs/changelog/README.md`](../../../../docs/changelog/README.md); this skill is how you write into it.

## When to write an entry

Write one when the change is worth finding again later:

- **migration** — a capability moved from a legacy repo into Tapestry, or a cutover happened
- **feature** — a new capability, agent, skill, workflow, or endpoint
- **fix** — a bug fix worth remembering, especially a silent-failure class
- **decision** — a choice recorded as an ADR, or a scope call (absorbed / deferred / retired)
- **version** — a plugin/package version bump consumers act on
- **chore** — tooling/infra that changes how work is done

**Skip** typos, comment-only edits, formatting, and pure refactors with no behavior change. When unsure, write a one-line entry — it's cheap; a lost trail is expensive.

## What NOT to put in the entry

The change trail is the *index*, not the archive. Don't duplicate:

- source→destination migration mapping → link `docs/migration/import-map.md`
- a decision's full reasoning → link the ADR under `docs/adr/`
- roadmap status → that's `ROADMAP.md` (the `roadmap-maintenance` agent owns it)
- durable cross-session context → loom-memory (link the memory `name`)

Point at those; don't restate them.

## Procedure

1. **PROBE.** Confirm what actually shipped: the PR number(s), the files/subsystem touched, any ADR written, any loom-memory `name` you wrote. Don't guess — read the diff / `git log` / the ADR.
2. **Decide the `kind`** from the list above. One kind per entry; if a PR does two genuinely separate things, that's usually two entries.
3. **Name the file** `docs/changelog/YYYY-MM-DD-<kebab-slug>.md`. Date = the change's date; slug = short and specific (`policy-service-migration`, not `update`).
4. **Write the frontmatter + body** (template below). Keep the body to the three labelled lines. Plain, descriptive tone (CLAUDE.md house rules — no marketing voice, no "the unlock", describe what *is*).
5. **Add one index row** to `docs/changelog/README.md` (newest first).
6. **Land it in the same PR** as the change, so the trail is atomic with what it describes.

## Template

```markdown
---
date: YYYY-MM-DD
kind: migration            # migration | feature | fix | decision | version | chore
area: services/<name>      # the primary path/subsystem touched
prs: [NNN]                 # PR numbers ([] if none yet)
adrs: [NNNN]               # related ADR numbers (omit or [] if none)
memory: [<memory-name>]    # loom-memory names (omit if none)
supersedes:                # a prior changelog slug this replaces, or omit
---

# <One-line title: what changed>

**What:** 1–3 sentences. The change, plainly.

**Why it matters:** the consequence — what this unblocks, fixes, or makes findable.

**Follow-ups / gates:** anything left (a cutover step, an operator action), or "none".
```

## Enforcement

`scripts/check_changelog.py` (run by `.github/workflows/changelog-check.yml`) flags a PR that touches runtime (`services/`, `engine/`, `infra/migrations/`, `apps/`, `packages/`, `integrations/`) but adds no `docs/changelog/` entry. It's advisory (not a required merge gate). If a runtime-touching change genuinely warrants no entry, opt out with `[skip changelog]` in the commit subject (first line) — but prefer a one-line entry.

## Anti-patterns

- **Entry that restates the ADR.** Link the ADR; the entry says what changed, not why in full.
- **Entry written in a later PR.** It belongs in the PR that made the change — otherwise the trail lags reality (the exact drift this system exists to prevent).
- **Marketing tone.** "This unlocks a powerful new…" → "Added X. It does Y." State what is.
- **One mega-entry for an unrelated bundle.** Split by concern; each is findable on its own.
- **Skipping the index row.** The index is how the trail is skimmed; an orphan entry file is half-invisible.

## Pair with

- `roadmap-maintenance` — flips ROADMAP.md status; the changelog records the change itself.
- `proposal-authoring` + `docs/adr/` — the reasoning; the changelog links to it.
- `documentation` — Diátaxis; a feature entry often points at the how-to/reference doc it shipped with.
