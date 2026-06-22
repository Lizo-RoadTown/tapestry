# `services/skill-making/`

**Status:** Populated — Step 4 (engine lift), 2026-06-21. Code lifted (**Refactor**); **not deployed** (deploy shape TBD — see below).

The skill-making bridge: receives promotion-candidate messages (HMAC-signed) from the engine/the-loom, dispatches to the compiler, emits registration acks, records telemetry. The closed `kind=skill` loop end (`bridge_closed_end_to_end_2026_06_13`).

## Layout

`python/skill_making/` — the 9 bridge modules + tests. Packaged under `python/<underscore_pkg>/` (hyphenated slot dir). `__init__.py` adds `engine/skill-compiler/python` to `sys.path` so `skill_compiler` resolves.

| Module | Role |
|---|---|
| `bridge_receiver` | handler functions for inbound HMAC POSTs (library — mounted, not a standalone app) |
| `hmac_verify` | HMAC sign/verify (**wire contract — byte-identical to source, do not drift**) |
| `models` | `PromotionCandidatePayload` / `RegistrationAck` (**wire contract — byte-identical**) |
| `compile_worker` | calls `skill_compiler.compiler` → ack |
| `ack_sender`, `idempotency`, `tenant_mapping`, `telemetry_collector`, `telemetry_sender` | bridge plumbing |

## Decision: Refactor (lifted + import paths rewritten)

Source: `Make_Skills/services/skill_making/`. Internal imports rewritten (`services.skill_making.X` → `skill_making.X`; `core.skill_making.compiler` → `skill_compiler.compiler`). **`hmac_verify.py` + `models.py` are byte-identical to source** (the bridge wire contract — preserved verbatim per `lesson_third_spec_drift_payload_schema_2026_06_13`). Function bodies unchanged; verified compile + resolution green.

## ⚠️ Deploy shape TBD (open item for the runbook)

In Make_Skills, `bridge_receiver` is **library code mounted into make-skills-api** — NOT a standalone Render service (no FastAPI `app`/`APIRouter` of its own). So the Tapestry deploy requires deciding: a thin standalone FastAPI wrapper (`skill-making` as its own service) vs mounting into a Tapestry api gateway / the engine. Decided at the Step-4 staging gate, not here.

Deps (when wrapped): `langchain_core`, `psycopg`/`psycopg_pool`, `pydantic`, `httpx`, `fastapi`.

## Related
- Compiler: [`../../engine/skill-compiler/`](../../engine/skill-compiler/)
- Runbook: [`../../docs/migration-cicd/runbooks/04-engine.md`](../../docs/migration-cicd/runbooks/04-engine.md)
