# `templates/operations-project/`

**Status:** Slot — **deferred** (operator decision, 2026-06-21). No shape leaves yet.

Intended as the seed template for operations / SRE projects. Unlike the other three domains, **no source repo has been identified** for operations, so this slot is left documented-but-empty rather than synthesized from nothing.

## Why deferred (not built)

The other domains have concrete sources to ground them:

| Domain | Source |
|---|---|
| `software-project` | `project-starter` (`_common` + `ui-app`/`agent-app`) |
| `classroom-project` | `classroom-hub-starter` |
| `research-project` | `SDE_Extraction` |
| **`operations-project`** | **none yet** |

Authoring an operations template from no source would be invention, not curation — so per the operator's call (defer), this slot waits for a source.

## To populate this slot

1. Identify an operations/SRE source repo (or decide to synthesize one).
2. Add `ui/` and/or `agent/` shape leaves following the two-axis pattern in [`../README.md`](../README.md).
3. Add an `OPERATIONS_GUIDE.md` domain guide if there's domain-specific guidance.
4. Update [`../../docs/migration/import-map.md`](../../docs/migration/import-map.md) (Step 5b).
