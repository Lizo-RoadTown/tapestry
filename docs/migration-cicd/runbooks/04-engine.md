# Step 04 — engine (skill-compiler + skill-making bridge)

**Owner:** Liz (operator)
**Source repo:** Make_Skills (steward: ms-agent)
**Source paths:** `core/skill_making/compiler.py` + `services/skill_making/`
**Destinations:** `engine/skill-compiler/python/skill_compiler/` + `services/skill-making/python/skill_making/`
**Decision:** [x] **Refactor** (lifted + import paths rewritten — the FIRST non-verbatim step)
**Status:** **migration-complete (code-lift) 2026-06-21** — code refactored + verified (compile + import resolution green; bridge contract byte-identical). **NO prod cutover owed:** operator confirmed `make-skills-api` was a host for a DIFFERENT app and does NOT migrate (`feedback_make_skills_api_is_host_for_other_app_not_a_migration_target_2026_06_21`). The lifted engine logic is canonical Tapestry; it deploys fresh/standalone when the product needs it (the "deploy shape" section below is superseded — there is nothing to re-source/cut over).
**ADR:** [ADR-0003](../../adr/0003-shared-postgres-schema-source-of-truth.md) (schema source-of-truth)

## Why Refactor (not Lift)
The engine code uses absolute Make_Skills import paths (`core.skill_making.compiler`, `services.skill_making.*`) and a type-only `core.runtime.runtime.StudentSkill`; the slot dirs are hyphenated. So a verbatim copy would break imports. Rewrites applied:
- `services.skill_making.X` → `skill_making.X`
- `core.skill_making.compiler` → `skill_compiler.compiler`
- TYPE_CHECKING `core.runtime.runtime.StudentSkill` → `typing.Any as StudentSkill` (engine runtime not lifted in Step 4)
- `skill_making/__init__.py` adds `engine/skill-compiler/python` to `sys.path` so `skill_compiler` resolves (`parents[4]` bootstrap).

**Function bodies UNCHANGED.** Verified 2026-06-21: `python -m py_compile` clean on all modules; `importlib.util.find_spec('skill_compiler.compiler')` + `skill_making.models` both resolve via the bootstrap; grep for `core.skill_making|services.skill_making|core.runtime` = ZERO.

## Bridge wire contract — PRESERVED byte-identical
`hmac_verify.py` (HMAC sign/verify, `WINDOW_SECONDS=300`, Stripe `t=,v1=` format) + `models.py` (`PromotionCandidatePayload`/`RegistrationAck`, `extra="forbid"`) are **byte-identical to source** (drift-watcher `cmp`-verified). The bridge is the wire contract with the-loom — `lesson_third_spec_drift_payload_schema_2026_06_13` forbids drift. Do NOT edit these bodies in any future change.

## ⚠️ Open item — deploy shape (decide at staging, not now)
`bridge_receiver` is **library code mounted into make-skills-api** in Make_Skills — NOT a standalone Render service. Tapestry deploy options:
1. Thin standalone FastAPI wrapper → `skill-making` as its own Render service.
2. Mount into a Tapestry api gateway or the engine deploy.
Plus: the compiler↔skill-making cross-package path needs `PYTHONPATH` (or the bootstrap) covering both `python/` dirs at runtime. Resolve before any staging deploy. Requirements (when wrapped): `langchain_core`, `psycopg`/`psycopg_pool`, `pydantic`, `httpx`, `fastapi`.

## Staging / parity (when deploy shape is decided)
- Apply `000_init_platform.sql` (tenant_id_mapping) + the bridge tables (`bridge_idempotency`, `promoted_skills` — these were deferred from Step 1's `000`; forklift from `Make_Skills/core/db/migrations.py:452+` when Step 4 deploys).
- Smoke: HMAC-signed bridge POST → compile `kind=skill` → ack (the `bridge_closed_end_to_end` proof, inside Tapestry).

## Production rollout
Re-source / mount preserving the bridge endpoint contract + `LOOM_SKILL_BRIDGE_SECRET` (byte-identical both sides). Rollback = revert to Make_Skills' mounted version.

## Sign-off
- [ ] Operator @ ____ · [ ] Tapestry-agent (code refactor done @ 2026-06-21) · [ ] ms-agent (source steward) @ ____

## Retirement (after 7d clean)
- [ ] Make_Skills skill_making/compiler tagged `migrated-04`; mounted version frozen; source read-only.
