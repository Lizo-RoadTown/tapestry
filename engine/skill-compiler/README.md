# `engine/skill-compiler/`

**Status:** Populated — Step 4 (engine lift), 2026-06-21. Code lifted (**Refactor**); not deployed.

SKILL.md / promotion-candidate → runnable `langchain` `StructuredTool` (`compile_from_bridge_candidate`).

## Layout

`python/skill_compiler/compiler.py` — the compiler. Packaged under `python/<underscore_pkg>/` (mirrors `packages/auth/python/loom_auth/`) because the slot dir `skill-compiler` has a hyphen. Import as `from skill_compiler.compiler import …` (with `engine/skill-compiler/python` on the path).

## Decision: Refactor (lifted + import paths rewritten)

Source: `Make_Skills/core/skill_making/compiler.py`. The Make_Skills absolute imports were rewritten to Tapestry's layout:
- lazy `from services.skill_making.telemetry_* import …` → `from skill_making.telemetry_*`
- TYPE_CHECKING `from core.runtime.runtime import StudentSkill` → `from typing import Any as StudentSkill` (the engine runtime isn't lifted in Step 4; type-only placeholder).

Function bodies unchanged. Verified: compiles + import resolution green.

## Related
- Consumed by [`../../services/skill-making/`](../../services/skill-making/) (`compile_worker`).
- Runbook: [`../../docs/migration-cicd/runbooks/04-engine.md`](../../docs/migration-cicd/runbooks/04-engine.md)
