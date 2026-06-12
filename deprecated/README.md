# `deprecated/`

Where retired pieces go when the operator approves their retirement from the prototype repos. NOT a dumping ground — entries here are decisions to preserve provenance.

## What lives here

- Code/docs the operator explicitly retired from a source repo, that's worth preserving as reference rather than deleting outright
- A `RETIRED.md` per entry explaining: what it was, where it came from (source repo + commit), why it was retired, what (if anything) replaced it

## What does NOT live here

- Inactive but maybe-useful code from source repos that haven't been retired yet (those stay in their source repo)
- Auto-generated artifacts (snapshots, build outputs) — those don't migrate anyway
- Anything from a source repo we never imported

## See also

- [`../docs/migration/what-to-retire.md`](../docs/migration/what-to-retire.md)
- [`../docs/migration/README.md`](../docs/migration/README.md)
