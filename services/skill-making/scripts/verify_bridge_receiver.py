"""Smoke + scenario verification for the skill-making bridge receiver.

Runs against a live DATABASE_URL (Render external URL works). Verifies:

  1. HMAC mismatch  -> 401 hmac_invalid
  2. Schema fail    -> 400 schema_invalid
  3. Happy skill    -> 202 queued, row in promoted_skills with status='queued'
  4. Non-skill kind -> 202 ack_deferred, row with status='kind_not_yet_handled'
  5. Replay         -> 409 (same body as first 202)
  6. Unknown tenant -> 400 unknown_source_tenant

Usage:

    set DATABASE_URL=postgresql://... (or export on POSIX)
    set LOOM_SKILL_BRIDGE_SECRET=test-secret
    python scripts/verify_bridge_receiver.py

The script does NOT touch the running FastAPI server — it invokes the
receiver function directly with a real pool, so the test exercises the
DB layer (mapping lookup, RLS-scoped INSERT, idempotency replay) without
any HTTP plumbing.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

# Allow running from repo root: `python scripts/verify_bridge_receiver.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db.db import close_pool, get_pool, init_pool  # noqa: E402
from core.db.migrations import (  # noqa: E402
    DEFAULT_TENANT_ID,
    LOOM_SELF_HOST_TENANT_ID,
    run_all,
)
from services.skill_making.bridge_receiver import (  # noqa: E402
    receive_promotion_candidate,
)
from services.skill_making.compile_worker import compile_and_ack  # noqa: E402
from services.skill_making.hmac_verify import sign_payload  # noqa: E402


SECRET = os.environ.setdefault("LOOM_SKILL_BRIDGE_SECRET", "verify-script-secret")


def _sign(body: bytes) -> str:
    """Emit a Stripe-style `t=<ts>,v1=<hex>` signature.

    Matches the on-wire format from loom's PR #21 + my hmac_verify.py.
    """
    return sign_payload(body, secret=SECRET)


def _make_payload(
    promotion_id: uuid.UUID | None = None,
    tenant_id: str = LOOM_SELF_HOST_TENANT_ID,
    candidate_kind: str = "skill",
    pattern_signature: str = "test-sig",
    name: str = "test-skill",
) -> dict:
    return {
        "schema_version": "1.0",
        "promotion_id": str(promotion_id or uuid.uuid4()),
        "tenant_id": tenant_id,
        "source_system": "loom",
        "is_global": False,
        "candidate_kind": candidate_kind,
        "pattern_signature": pattern_signature,
        "source": {
            "frontmatter": {"name": name, "description": "verification fixture"},
            "body_md": "# Test\n\nFixture body.\n",
        },
        "evidence_refs": [],
        "signals": {},
        "capability_tags": ["test"],
        "triggers": ["test"],
        "callbacks": {
            "registration_ack": "http://localhost:9999/ack",
            "telemetry": "http://localhost:9999/telemetry",
        },
    }


async def _count_in_promoted_skills(promotion_id: uuid.UUID) -> tuple[int, str | None]:
    """Unscoped read (verification only) of the promoted_skills table.
    Returns (count, status). Uses the engine-side tenant_id to set the
    GUC so RLS lets us see the row."""
    async with get_pool().connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (DEFAULT_TENANT_ID,),
            )
            cur = await conn.execute(
                "SELECT status FROM promoted_skills WHERE promotion_id = %s::uuid",
                (str(promotion_id),),
            )
            row = await cur.fetchone()
            if not row:
                return 0, None
            return 1, row[0]


async def _cleanup(promotion_ids: list[uuid.UUID], skill_ids: list[uuid.UUID] | None = None) -> None:
    """Remove fixture rows so re-runs are clean."""
    async with get_pool().connection() as conn:
        async with conn.transaction():
            # Have to set tenant scope to clear student_skills rows the
            # compile produced (RLS gates DELETE too).
            await conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (DEFAULT_TENANT_ID,),
            )
            for pid in promotion_ids:
                await conn.execute(
                    "DELETE FROM bridge_idempotency WHERE promotion_id = %s::uuid",
                    (str(pid),),
                )
                await conn.execute(
                    "DELETE FROM promoted_skills WHERE promotion_id = %s::uuid",
                    (str(pid),),
                )
            for sid in skill_ids or []:
                await conn.execute(
                    "DELETE FROM student_skills WHERE id = %s::uuid",
                    (str(sid),),
                )


async def _load_student_skill(skill_id: uuid.UUID) -> tuple[str, str] | None:
    """Return (name, description) of a student_skills row, or None.

    RLS-scoped read — sets app.tenant_id to DEFAULT_TENANT_ID first."""
    async with get_pool().connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (DEFAULT_TENANT_ID,),
            )
            cur = await conn.execute(
                "SELECT name, description FROM student_skills WHERE id = %s::uuid",
                (str(skill_id),),
            )
            row = await cur.fetchone()
            return (row[0], row[1]) if row else None


async def _read_compiled_skill_id(promotion_id: uuid.UUID) -> uuid.UUID | None:
    """Return promoted_skills.skill_id for a given promotion_id, or None."""
    async with get_pool().connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (DEFAULT_TENANT_ID,),
            )
            cur = await conn.execute(
                "SELECT skill_id FROM promoted_skills WHERE promotion_id = %s::uuid",
                (str(promotion_id),),
            )
            row = await cur.fetchone()
            return uuid.UUID(str(row[0])) if row and row[0] else None


def _assert(condition: bool, label: str) -> None:
    icon = "PASS" if condition else "FAIL"
    print(f"  [{icon}] {label}")
    if not condition:
        sys.exit(1)


async def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL not set. Aborting.")
        sys.exit(2)

    pool = await init_pool()
    await run_all(pool)
    pool_obj = get_pool()
    pids_to_clean: list[uuid.UUID] = []
    skill_ids_to_clean: list[uuid.UUID] = []

    try:
        # ---- 1. HMAC mismatch ----
        print("\n[1] HMAC mismatch -> 401 hmac_invalid")
        body = json.dumps(_make_payload()).encode("utf-8")
        # "wrong-sig" is malformed (no t=,v1=) — hmac_verify rejects with 401
        # before timestamp/digest check. Tests the same failure path.
        result = await receive_promotion_candidate(
            raw_body=body, signature="t=1,v1=deadbeef", pool=pool_obj
        )
        _assert(result.status_code == 401, f"status_code == 401 (got {result.status_code})")
        _assert(result.body["code"] == "hmac_invalid", "code == hmac_invalid")

        # ---- 2. Schema fail (missing required field) ----
        print("\n[2] Schema fail -> 400 schema_invalid")
        bad_payload = _make_payload()
        del bad_payload["candidate_kind"]
        bad_body = json.dumps(bad_payload).encode("utf-8")
        result = await receive_promotion_candidate(
            raw_body=bad_body, signature=_sign(bad_body), pool=pool_obj
        )
        _assert(result.status_code == 400, f"status_code == 400 (got {result.status_code})")
        _assert(result.body["code"] == "schema_invalid", "code == schema_invalid")

        # ---- 3. Happy path: kind=skill ----
        print("\n[3] Happy skill -> 202 queued + row in promoted_skills")
        pid_skill = uuid.uuid4()
        pids_to_clean.append(pid_skill)
        payload = _make_payload(promotion_id=pid_skill, candidate_kind="skill")
        body = json.dumps(payload).encode("utf-8")
        result = await receive_promotion_candidate(
            raw_body=body, signature=_sign(body), pool=pool_obj
        )
        _assert(result.status_code == 202, f"status_code == 202 (got {result.status_code})")
        _assert(result.body["status"] == "queued", "response status == queued")
        count, status = await _count_in_promoted_skills(pid_skill)
        _assert(count == 1, "1 row in promoted_skills")
        _assert(status == "queued", f"DB status == queued (got {status!r})")

        # ---- 4. Non-skill kind -> ack-defer ----
        print("\n[4] Non-skill kind (architecture_pattern) -> 202 ack_deferred")
        pid_pattern = uuid.uuid4()
        pids_to_clean.append(pid_pattern)
        payload = _make_payload(
            promotion_id=pid_pattern,
            candidate_kind="architecture_pattern",
            pattern_signature="pattern-sig-1",
            name="test-pattern",
        )
        body = json.dumps(payload).encode("utf-8")
        result = await receive_promotion_candidate(
            raw_body=body, signature=_sign(body), pool=pool_obj
        )
        _assert(result.status_code == 202, f"status_code == 202 (got {result.status_code})")
        _assert(
            result.body["status"] == "kind_not_yet_handled",
            f"response status == kind_not_yet_handled (got {result.body['status']!r})",
        )
        _assert(
            result.body["outcome"] == "ack_deferred",
            "response outcome == ack_deferred",
        )
        count, status = await _count_in_promoted_skills(pid_pattern)
        _assert(count == 1, "1 row in promoted_skills")
        _assert(
            status == "kind_not_yet_handled",
            f"DB status == kind_not_yet_handled (got {status!r})",
        )

        # ---- 5. Replay: same promotion_id -> 409 with original body ----
        print("\n[5] Replay (same promotion_id) -> 409")
        payload = _make_payload(promotion_id=pid_skill, candidate_kind="skill")
        body = json.dumps(payload).encode("utf-8")
        result = await receive_promotion_candidate(
            raw_body=body, signature=_sign(body), pool=pool_obj
        )
        _assert(result.status_code == 409, f"status_code == 409 (got {result.status_code})")
        _assert(result.body["status"] == "queued", "replayed body status == queued")

        # ---- 6. Unknown source tenant ----
        print("\n[6] Unknown source tenant -> 400 unknown_source_tenant")
        pid_unmapped = uuid.uuid4()
        pids_to_clean.append(pid_unmapped)
        # A UUID that has no row in tenant_id_mapping.
        unmapped_uuid = "deadbeef-dead-beef-dead-beefdeadbeef"
        payload = _make_payload(
            promotion_id=pid_unmapped, tenant_id=unmapped_uuid
        )
        body = json.dumps(payload).encode("utf-8")
        result = await receive_promotion_candidate(
            raw_body=body, signature=_sign(body), pool=pool_obj
        )
        _assert(result.status_code == 400, f"status_code == 400 (got {result.status_code})")
        _assert(
            result.body["code"] == "unknown_source_tenant",
            f"code == unknown_source_tenant (got {result.body['code']!r})",
        )

        # ---- 7. Compile path: queued -> compiled (PR B) ----
        # Calls compile_and_ack directly (skipping the BackgroundTasks
        # wiring); the unscoped path through the receiver already
        # exercised the route-side scheduling logic.
        # The ack POST will fail (no mock endpoint here) but
        # compile_and_ack swallows AckSendError per its contract —
        # state stays at status='compiled'. We assert the state.
        print("\n[7] Compile path: queued -> compiled + student_skills row written")
        pid_compile = uuid.uuid4()
        pids_to_clean.append(pid_compile)
        payload = _make_payload(
            promotion_id=pid_compile,
            candidate_kind="skill",
            pattern_signature="compile-sig-1",
            name="bridge-compiled-test-skill",
        )
        body = json.dumps(payload).encode("utf-8")
        result = await receive_promotion_candidate(
            raw_body=body, signature=_sign(body), pool=pool_obj
        )
        _assert(result.status_code == 202, f"receiver 202 (got {result.status_code})")
        _assert(
            result.compile_request is not None,
            "compile_request set on ReceiverResult for kind=skill",
        )
        # Drive the background task synchronously here. In production
        # FastAPI BackgroundTasks runs it after the response goes out.
        promo_id, engine_tid = result.compile_request
        await compile_and_ack(pool_obj, promo_id, engine_tid)

        # After compile: status should be 'compiled', skill_id should be set
        count, status = await _count_in_promoted_skills(pid_compile)
        _assert(count == 1, "promoted_skills row exists")
        _assert(status == "compiled", f"DB status == compiled (got {status!r})")
        compiled_skill_id = await _read_compiled_skill_id(pid_compile)
        _assert(compiled_skill_id is not None, "promoted_skills.skill_id is set")
        if compiled_skill_id:
            skill_ids_to_clean.append(compiled_skill_id)
            row = await _load_student_skill(compiled_skill_id)
            _assert(row is not None, "student_skills row exists")
            if row:
                name, _ = row
                _assert(
                    name == "bridge-compiled-test-skill",
                    f"student_skills.name == bridge-compiled-test-skill (got {name!r})",
                )

        print("\n=== All 7 scenarios passed ===")
    finally:
        await _cleanup(pids_to_clean, skill_ids_to_clean)
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
