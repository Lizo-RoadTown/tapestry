---
name: id-rename-blast-radius
description: Before renaming an identifier that is simultaneously a code key, a filesystem path, and a persisted namespace, enumerate everything derived from it. Use when changing a registry key, tenant id, course/project slug, storage prefix, folder name, or route segment - especially when the "rename" looks like a one-line edit. Catches derivations (prefix checks, path joins, storage keys) that break silently rather than loudly.
---

# ID rename blast radius

Some identifiers are load-bearing in more than one system at once. Renaming one is not a
refactor - it is a migration across every system that derives from it. The danger is that
the derivations usually fail **silently**: a filter returns `[]`, a lookup misses, saved
state orphans. Nothing throws.

## When this applies

**Apply before renaming any id that is used as more than one of:**

- a key in a registry / config object
- a directory or file name on disk
- a persisted namespace (localStorage key, cache prefix, S3 path, DB partition)
- a URL segment or route param
- a telemetry / memory tag
- an external system's identifier (deploy service name, bucket, queue)

If it is only one of those, this is an ordinary rename - skip.

## Procedure

### 1. Enumerate the roles

Write the list. An id used in four systems needs four migration answers, and writing them
down is what surfaces the fourth.

### 2. Find DERIVATIONS, not just occurrences

Occurrences are easy and are not the problem. Derivations are code that infers meaning from
the id's *shape* - these survive a find-and-replace intact and break silently:

    # Shape inference - the silent killers
    grep -rnE 'startsWith\(|endsWith\(|split\("-"\)|slice\(0,' src/

    # Interpolation into paths, keys, URLs
    grep -rnE 'path\.join\(|prefix \+|\+ id \+' src/

A grouping like `keys.filter(k => k.startsWith("class-"))` returns an empty array the moment
ids stop starting with `class-`. The UI renders an empty list. No error.

### 3. Decide: rename, or make the derivation explicit

Usually the derivation is the actual bug - it encoded a naming convention as logic. Replace
inference-from-shape with a declared field:

    // before: grouping inferred from the id's prefix
    labs: Object.keys(items).filter(id => id.startsWith("lab-"))

    // after: grouping declared on the item; ids are free to be anything
    labs: Object.keys(items).filter(id => items[id].kind === "lab")

Then the rename is safe *and* the next rename is safe.

### 4. Account for persisted state

Anything already written under the old id does not move: saved user state, cached objects,
uploaded files, memory rows. Choose explicitly and say which:

- **Rename early** - before any real data exists. Cheapest by far. Prefer this.
- **Migrate** - write a one-time remap of old keys to new.
- **Accept the orphan** - fine for regenerable caches, never for user-authored content
  (notes, checkboxes, drafts).

### 5. Verify the derivations, not the grep

A clean grep proves nothing about a `startsWith` you replaced. Run the app and confirm the
derived things still populate: the grouped list, the folder lookup, the restored state.

## Output

A short table: each role the id plays, what derives from it (`file:line`), what happens to
data persisted under the old value, and the verification that the derived behavior still works.

## Why this exists

"Rename the key" reads as a one-line edit. When the key is also a path and a namespace, it is
three migrations, and the two you forget fail without an error message.

Related: `seed-leftover-audit` (the pass that usually surfaces the rename in the first place).
