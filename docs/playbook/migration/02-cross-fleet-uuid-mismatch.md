# 02 — Cross-fleet UUID mismatch (same-name constant, different value)

## The pattern

Two repos that integrate often each define a "default tenant" or "self-host tenant" UUID constant. **The constants are named similarly. They resolve to different values.** When the bridge passes `tenant_id` verbatim from one side to the other, RLS-scoped queries on the receiving side hide the row. The skill or candidate or memory becomes orphaned: written but invisible to the very agent that would use it.

This is the *verify-values-not-just-names* discipline rule made concrete.

## The story (Make_Skills vs the-loom, caught 2026-06-12)

- **Make_Skills** `core/db/migrations.py:31`: `DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"` (the all-zeros UUID, baked into existing rows since Pillar 0 migration)
- **the-loom** (per bridge ratification adjustment #1): `SELF_HOST_TENANT_ID` — at the time of this incident the value was a hardcoded literal in `packages/auth/python/loom_auth/auth_bridge.py:97`; that constant has since been replaced with an env-var read (`SELF_HOST_TENANT_ID`, deprecated alias `LOOM_SELF_HOST_TENANT_ID`, all-zeros placeholder fallback). Each fleet's deployment now sets its own value via env.

Two different self-host default UUIDs on opposite sides of the wire contract. Caught during PROBE-before-implementation for the bridge_receiver, not by a smoke test, which means we narrowly avoided shipping a feature that would silently orphan every skill the bridge ever wrote.

## Three resolution options weighed

- **Option A — unify the constants.** Pick one UUID, both sides use it. Cleanest semantically but requires data migration on whichever side gives up its existing UUID.
- **Option B — explicit mapping table.** Engine has a config table `tenant_id_mapping` (source_uuid → engine_uuid). Receiver looks up `payload["tenant_id"]`, writes under the engine-side UUID. Self-host gets one row. Hosted-multitenant scales naturally.
- **Option C — receiver treats `payload["tenant_id"]` as authoritative.** Engine swaps its `DEFAULT_TENANT_ID` going forward; existing data behind a "legacy tenant" view.

**Decision: Option B.** Reasons: neither side abandons its existing UUID semantics; cross-fleet relationship becomes explicit, auditable, configurable; hosted-multitenant naturally maps multiple source tenants to multiple engine tenants; self-host is one row of config.

Ratified in the bridge spec adjustment ratification 2026-06-12 evening.

## The rule

When integrating two repos that each have a "default" or "self-host" identity constant:

1. **PROBE both sides' actual literal values.** `grep -E "DEFAULT_TENANT_ID|SELF_HOST_TENANT_ID|default.*tenant.*=.*['\"]" --include="*.py"` in each repo. Read the values, not the names.
2. **If the values differ, do NOT pass `tenant_id` verbatim across the bridge.** Build a mapping table FIRST.
3. **Self-host case: one mapping row at startup.** Source's self-host UUID → engine's self-host UUID.
4. **Hosted-multitenant case: mapping per tenant.** Created at signup time when the source registers a new tenant.
5. **Write the mapping table contract into the spec doc as a CALLED-OUT invariant**, not a footnote. Drift on this invariant orphans rows silently.

## Signals to watch for during integration

- Either side has a `DEFAULT_*_ID`, `SELF_HOST_*`, `SYSTEM_*` UUID constant
- The bridge spec talks about "passing tenant_id through"
- RLS or row-level scoping exists on either side
- The integration "writes" something on the receiver side
- A test fixture hardcodes a tenant UUID without commentary

## Skills queued for promotion

- `verify-tenant-id-literals-across-bridges.skill.md` — before writing a bridge receiver, grep + read both sides' default-tenant literal values and assert they're the same OR a mapping table is planned
- `tenant-id-mapping-table-migration.skill.md` — the Option B schema + the `set_config('app.tenant_id', ...)` GUC pattern as a reusable migration

## Related

- Loom-memory: `lesson_cross_fleet_tenant_id_uuid_mismatch_2026_06_12`
- Loom-memory: `decision_tenant_id_mapping_option_b_2026_06_12`
- Loom-memory: `feedback_verify_values_not_just_names`
- Loom-memory: `feedback_cite_files_not_memory`
