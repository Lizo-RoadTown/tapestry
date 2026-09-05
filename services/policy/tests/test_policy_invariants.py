"""
Invariant tests for the Policy Service Phase 5 decisions slice.

Same shape as services/architecture-registry/tests/test_candidate_invariants.py:
DB-free tests that pin the BOUNDARY contracts between layers. If any of
these drift, both self-host and hosted-multitenant modes degrade silently.

Invariants pinned here:

  1. The self-host tenant fallback is consistent between the auth layer
     (auth_bridge.SELF_HOST_TENANT_ID / resolve_tenant) and the RLS policy
     default in the migration (the all-zeros UUID in each COALESCE). Drift =
     an unset GUC and the auth fallback disagree, so self-host queries scope to
     a different tenant than rows were written under and RLS silently returns
     empty. Tapestry differs from the-loom (which hardcoded 1d8ec1b3 across the
     fleet): Tapestry's packages/auth resolves from env and fails closed to the
     all-zeros UUID.

  2. Pydantic Literal enums match the SQL CHECK constraint values exactly.
     Drift = clients submit a value Pydantic accepts but Postgres rejects
     (or vice versa).

  3. DecisionCreate rejects `tenant_id` in the body (extra="forbid").
     Regress = hosted-multitenant clients can spoof tenants by setting
     tenant_id in JSON.

  4. resolve_tenant falls back to SELF_HOST_TENANT_ID when no contextvar
     is set — protects background/test code paths.

  5. target_status enum matches candidates.status enum across services.
     If these drift, the Policy Service authorizes transitions to states
     the architecture-registry won't accept (or refuses transitions to
     states it would). NOTE: in Tapestry the candidates schema is
     007_init_candidates.sql (consolidated from the-loom's 003/005/006);
     this test reads 007, not 003.

Integration tests (POST/GET end-to-end against a real DB) are deferred
to the smoke-test step against the deployed Render service.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


_SVC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC))

import auth_bridge  # noqa: E402
import models  # noqa: E402


# ---------------------------------------------------------------------------
# Invariant 1: SELF_HOST_TENANT_ID matches everywhere
# ---------------------------------------------------------------------------


_REPO_ROOT = _SVC.parent.parent

# The all-zeros UUID that both the auth fallback and the RLS COALESCE default
# use as the fail-closed self-host tenant.
NIL_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def test_self_host_tenant_id_is_a_valid_uuid_string():
    """auth_bridge.SELF_HOST_TENANT_ID must be a well-formed UUID string — it
    is stamped straight onto app.tenant_id::uuid in every RLS transaction, so a
    malformed value would blow up every query at cast time."""
    from uuid import UUID

    UUID(auth_bridge.SELF_HOST_TENANT_ID)  # raises ValueError if malformed


def test_self_host_fallback_matches_migration_rls_default():
    """When SELF_HOST_TENANT_ID is unset in env, the auth layer must fall back
    to the SAME all-zeros UUID the migration's RLS COALESCE default uses. If
    these disagree, self-host writes land under one tenant while an unset GUC
    scopes reads to another — RLS returns empty and the failure is silent.

    Read the fallback via a fresh import with env cleared, so the test doesn't
    depend on how the operator's shell happens to be configured.
    """
    import importlib
    import os

    saved = {
        k: os.environ.pop(k, None)
        for k in ("SELF_HOST_TENANT_ID", "LOOM_SELF_HOST_TENANT_ID")
    }
    try:
        import loom_auth.auth_bridge as canonical

        importlib.reload(canonical)
        assert canonical.SELF_HOST_TENANT_ID == NIL_TENANT_ID
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
        import loom_auth.auth_bridge as canonical  # noqa: F811

        importlib.reload(canonical)

    # The migration's RLS policies must use the same nil-UUID COALESCE default.
    sql_text = _MIGRATION.read_text(encoding="utf-8")
    assert NIL_TENANT_ID in sql_text, (
        "004_init_policy.sql RLS policies must COALESCE to the all-zeros UUID "
        "so an unset app.tenant_id fails closed to the same tenant the auth "
        "layer falls back to."
    )


# ---------------------------------------------------------------------------
# Invariant 2: Pydantic Literal enums match SQL CHECK constraints
# ---------------------------------------------------------------------------


_MIGRATION = _REPO_ROOT / "infra" / "migrations" / "004_init_policy.sql"


def _extract_check_values(sql_text: str, check_name: str) -> set[str]:
    """Parse a CHECK constraint of the form:
        CONSTRAINT <name> CHECK ( <col> [IS NULL OR] <col> IN ('a','b','c') )
    Returns the literal values as a set. Tolerant of the 'IS NULL OR'
    prefix used for nullable enum columns (target_status)."""
    pattern = (
        rf"CONSTRAINT\s+{check_name}\s+CHECK\s*\(.*?IN\s*\(([^)]+)\)\s*\)"
    )
    match = re.search(pattern, sql_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return set()
    inner = match.group(1)
    return set(re.findall(r"'([^']+)'", inner))


def test_decision_kind_pydantic_matches_sql():
    """models.DECISION_KIND Literal must exactly equal policy_decisions_kind_check."""
    sql_text = _MIGRATION.read_text(encoding="utf-8")
    sql_values = _extract_check_values(sql_text, "policy_decisions_kind_check")
    py_values = set(models.DECISION_KIND.__args__)
    assert sql_values == py_values, (
        f"DECISION_KIND drift: Python={py_values}, SQL={sql_values}"
    )


def test_target_status_pydantic_matches_sql():
    """models.TARGET_STATUS Literal must exactly equal policy_decisions_target_status_check."""
    sql_text = _MIGRATION.read_text(encoding="utf-8")
    sql_values = _extract_check_values(
        sql_text, "policy_decisions_target_status_check"
    )
    py_values = set(models.TARGET_STATUS.__args__)
    assert sql_values == py_values, (
        f"TARGET_STATUS drift: Python={py_values}, SQL={sql_values}"
    )


def test_target_status_matches_candidates_status():
    """The Policy Service's target_status enum MUST equal the
    architecture-registry's candidates.status enum. If they drift, the
    Policy Service authorizes transitions to states architecture-registry
    won't accept (or vice versa).

    In Tapestry the candidates schema lives at 007_init_candidates.sql
    (consolidated from the-loom's 003/005/006), NOT 003."""
    candidates_migration = (
        _REPO_ROOT / "infra" / "migrations" / "007_init_candidates.sql"
    )
    if not candidates_migration.exists():
        pytest.skip("candidates migration not in this checkout")
    sql_text = candidates_migration.read_text(encoding="utf-8")
    candidates_status = _extract_check_values(
        sql_text, "candidates_status_check"
    )
    policy_target_status = set(models.TARGET_STATUS.__args__)
    assert candidates_status == policy_target_status, (
        f"Cross-service enum drift: "
        f"candidates.status={candidates_status}, "
        f"policy.target_status={policy_target_status}"
    )


# ---------------------------------------------------------------------------
# Invariant 3: Models forbid client-supplied tenant_id
# ---------------------------------------------------------------------------


def test_decision_create_rejects_tenant_id_in_body():
    """A hosted-multitenant client must NOT be able to spoof tenant_id by
    setting it in the body. extra='forbid' is the guarantee."""
    from uuid import uuid4

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        models.DecisionCreate(
            candidate_id=uuid4(),
            decision_kind="approve",
            target_status="stable",
            tenant_id=str(uuid4()),  # spoofing attempt
        )


def test_decision_create_minimal_valid():
    """Smoke: minimal DecisionCreate with only required fields constructs
    cleanly."""
    from uuid import uuid4

    d = models.DecisionCreate(
        candidate_id=uuid4(),
        decision_kind="hold",
    )
    # Defaults applied:
    assert d.target_status is None
    assert d.reason == ""
    assert d.decided_by == "operator"
    assert d.extra == {}


def test_decision_create_rejects_invalid_enum_values():
    """decision_kind and target_status reject values not in their Literal sets."""
    from uuid import uuid4

    from pydantic import ValidationError

    base = {"candidate_id": uuid4(), "decision_kind": "approve"}
    with pytest.raises(ValidationError):
        models.DecisionCreate(**{**base, "decision_kind": "banish"})
    with pytest.raises(ValidationError):
        models.DecisionCreate(**{**base, "target_status": "transcended"})


def test_decision_create_allows_null_target_status_for_hold():
    """'hold' and 'demote' decisions may have NULL target_status — this
    is the design intent documented in the migration."""
    from uuid import uuid4

    d_hold = models.DecisionCreate(
        candidate_id=uuid4(),
        decision_kind="hold",
        target_status=None,
    )
    assert d_hold.target_status is None

    d_demote = models.DecisionCreate(
        candidate_id=uuid4(),
        decision_kind="demote",
        target_status=None,
    )
    assert d_demote.target_status is None


# ---------------------------------------------------------------------------
# Invariant 4: auth_bridge resolve_tenant fallback
# ---------------------------------------------------------------------------


def test_resolve_tenant_falls_back_to_self_host_when_unset():
    """Code paths not going through verify_bearer (background tasks, tests)
    get the service's SELF_HOST_TENANT_ID, not None."""
    assert auth_bridge.resolve_tenant() == auth_bridge.SELF_HOST_TENANT_ID


# ---------------------------------------------------------------------------
# Invariant 5: Migration audit-immutability shape
# ---------------------------------------------------------------------------


def test_migration_has_no_update_policy():
    """The audit-immutability invariant — there must be NO CREATE POLICY
    statement for FOR UPDATE on policy_decisions. If a future contributor
    adds one, this test fails and forces them to argue for why audit
    history should be mutable."""
    sql_text = _MIGRATION.read_text(encoding="utf-8")
    update_policy = re.search(
        r"CREATE\s+POLICY\s+\w+\s+ON\s+policy_decisions\s+FOR\s+UPDATE",
        sql_text,
        re.IGNORECASE,
    )
    assert update_policy is None, (
        "Audit-immutability regression: a CREATE POLICY ... FOR UPDATE "
        "appeared on policy_decisions. Decisions must be append-only; "
        "to revise, file a new decision with extra.supersedes set."
    )


def test_migration_enforces_rls():
    """ENABLE + FORCE row level security must both be present — without
    FORCE, the table owner (the loom_db user the service connects as)
    bypasses RLS, which silently breaks isolation in BOTH modes."""
    sql_text = _MIGRATION.read_text(encoding="utf-8")
    assert re.search(
        r"ALTER\s+TABLE\s+policy_decisions\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
        sql_text,
        re.IGNORECASE,
    ), "Missing ENABLE ROW LEVEL SECURITY on policy_decisions"
    assert re.search(
        r"ALTER\s+TABLE\s+policy_decisions\s+FORCE\s+ROW\s+LEVEL\s+SECURITY",
        sql_text,
        re.IGNORECASE,
    ), "Missing FORCE ROW LEVEL SECURITY on policy_decisions"
