---
name: seed-leftover-audit
description: Sweep a freshly scaffolded or forked repo for strings inherited from the template or the previous instance - placeholder tokens, the old project's slug, last term's names, stale memory-boundary claims. Use immediately after `tapestry init`, after cloning a `*-starter` seed, after forking a working repo to start a new instance, or when a repo "was set up from" another one and nobody has audited it since. Different from template-inheritance-check, which catches inherited *assumptions* rather than inherited *strings*.
---

# Seed leftover audit

A repo scaffolded from a template or forked from a working instance carries the source's
strings until someone removes them. They are cheap to find and expensive to trip over: a
`REPLACE-me` token blocks a deploy, a stale project id in a comment tells the next agent the
wrong memory boundary, last term's instructor names render in this term's UI.

Run this BEFORE the first feature task in a new repo, not after the first bug.

## When this applies

**Apply when:**
- The repo was created by a scaffolder (`tapestry init`, `loom new-*`, `create-*-app`)
- The repo was forked or cloned from a `*-starter` / `*-seed` / `*-template`
- The repo was copied from a *working* instance (last term's app, the last client's site)
- A CLAUDE.md or README describes the repo as "seeded from" something

**Skip when:** the repo has an established commit history from multiple contributors and
someone has already run this.

## Procedure

### 1. Name the sources

List every identifier the source instance used. Get them from the git log's initial commit,
the README's provenance line, and the CLAUDE.md. You are looking for:

| Kind | Examples |
|---|---|
| Placeholder tokens | `REPLACE-`, `TODO-`, `<your-`, `CHANGEME`, `example.com`, `my-app` |
| Previous instance slug | `ime4020-hub-app`, `summer-2026-hub`, `acme-staging` |
| Previous period / cohort | `Summer 2026`, `Q3`, `v1` |
| Previous people | instructor names, client names, author bylines |
| Previous infra ids | project ids, service names, bucket names, memory tags |

### 2. Sweep

    grep -rn "REPLACE|CHANGEME|TODO-|<your-|$OLD_SLUG|$OLD_PERIOD" . -E \
      --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.git --exclude-dir=build

Sweep the config files a code-only grep misses: `*.yaml`, `*.toml`, `*.json`, `Dockerfile`,
CI workflows, and the docs directory. Deploy manifests are where placeholder tokens do the
most damage and where nobody looks.

### 3. Triage by blast radius, not by count

Sort each hit into one of three buckets and report them that way - a flat list of "17
leftovers" reads as busywork and gets deferred wholesale.

- **Blocking** - breaks a deploy, a build, or a credential/scope boundary. Fix now.
  (A `name: REPLACE-term-hub` in a deploy blueprint. A stale project id that scopes memory.)
- **Misleading** - the repo now *asserts something false* about itself. A header comment
  claiming a memory boundary that no longer exists will be believed by the next agent, which
  is worse than no comment. Fix now.
- **Cosmetic** - a log string, a README title. Fix in the same pass; they are one `sed` each
  and they are the ones that make a repo feel un-owned.

### 4. Report, then fix what the operator approves

Give a table of `file:line` -> what it says -> what fixing it means -> why it matters. Let the
operator choose scope. Do not silently fix things in a read-only task.

## Output

A table of findings grouped by blast radius, and - once approved - the fixes applied and
verified (build/deploy check, not just the grep coming back clean).

## Why this exists

The failure it prevents is not "an ugly string shipped." It is an agent reading an inherited
comment as ground truth about the current repo. Provenance strings age into lies.

Related: `template-inheritance-check` (inherited assumptions), `id-rename-blast-radius`
(before renaming what you find here).
