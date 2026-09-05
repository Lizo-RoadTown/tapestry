"""
Invariant tests for the Architecture Registry's candidate slice.

These tests don't touch the database — they verify the BOUNDARY contracts
between layers that, if drifted, would silently break both self-host and
hosted-multitenant modes:

  1. The self-host tenant fallback is consistent between the auth layer
     (auth_bridge.SELF_HOST_TENANT_ID / resolve_tenant) and the RLS policy
     default baked into the migration (the all-zeros UUID in each COALESCE).
     Drift here = an unset GUC and the auth fallback disagree, so self-host
     queries scope to a different tenant than the rows were written under and
     RLS silently returns empty result sets.

  2. Pydantic Literal enums match the SQL CHECK constraint values exactly
     (source_path, candidate_type [9 kinds], status). Drift here = clients can
     submit a value Pydantic accepts but Postgres rejects with a CheckViolation
     — or vice versa. The 9-kind candidate_type sync is the load-bearing
     contract for the deployed loom-architecture-registry.

  3. Pydantic models reject `tenant_id` in request bodies (CandidateCreate
     and CandidateStatusUpdate use extra="forbid"). If this regresses,
     hosted-multitenant lets clients spoof tenants by setting tenant_id
     in the body.

## Tapestry note (differs from the-loom)

In the-loom, SELF_HOST_TENANT_ID was a hardcoded canonical UUID
(1d8ec1b3-…) pinned identical across the fleet. Tapestry's packages/auth
resolves it from env (SELF_HOST_TENANT_ID, then the LOOM_SELF_HOST_TENANT_ID
alias) and FALLS BACK to the all-zeros UUID — the same default the RLS
policies' COALESCE uses when app.tenant_id is unset (fail-closed). So the
Tapestry invariant is "auth fallback == RLS COALESCE default", not "everyone
hardcodes 1d8ec1b3". Integration tests (POST/GET/PATCH against a real DB) are
deferred — they need a running Postgres + applied migrations.
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


_REPO_ROOT = _SVC.parent.parent
_MIGRATION = _REPO_ROOT / "infra" / "migrations" / "007_init_candidates.sql"

# The all-zeros UUID that both the auth fallback and the RLS COALESCE default
# use as the fail-closed self-host tenant.
NIL_TENANT_ID = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Invariant 1: self-host tenant fallback consistent with the RLS default
# ---------------------------------------------------------------------------


def test_self_host_tenant_id_is_a_valid_uuid_string():
    """auth_bridge.SELF_HOST_TENANT_ID must be a well-formed UUID string —
    it is stamped straight onto app.tenant_id::uuid in every RLS transaction,
    so a malformed value would blow up every query at cast time."""
    from uuid import UUID

    # Raises ValueError if not a valid UUID.
    UUID(auth_bridge.SELF_HOST_TENANT_ID)


def test_self_host_fallback_matches_migration_rls_default():
    """When SELF_HOST_TENANT_ID is unset in env, the auth layer must fall back
    to the SAME all-zeros UUID that the migration's RLS COALESCE default uses.

    If these disagree, self-host writes land under one tenant while an unset
    GUC scopes reads to another — RLS returns empty and the failure is silent.

    We read the fallback via a fresh import with the env cleared, so the test
    doesn't depend on how the operator's shell happens to be configured.
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
        "007_init_candidates.sql RLS policies must COALESCE to the all-zeros "
        "UUID so an unset app.tenant_id fails closed to the same tenant the "
        "auth layer falls back to."
    )


# ---------------------------------------------------------------------------
# Invariant 2: Pydantic Literal enums match SQL CHECK constraints
# ---------------------------------------------------------------------------


def _extract_check_values(sql_text: str, check_name: str) -> set[str]:
    """Parse a CHECK constraint of the form:
        CONSTRAINT <name> CHECK ( <col> IN ('a','b','c') )
    Returns the literal values as a set. Tolerant of multi-line whitespace
    and inline comments between the values."""
    pattern = (
        rf"CONSTRAINT\s+{check_name}\s+CHECK\s*\(\s*\w+\s+IN\s*\(([^)]+)\)\s*\)"
    )
    match = re.search(pattern, sql_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return set()
    inner = match.group(1)
    return set(re.findall(r"'([^']+)'", inner))


def test_source_path_pydantic_matches_sql():
    """models.SOURCE_PATH Literal must exactly equal candidates_source_path_check."""
    sql_text = _MIGRATION.read_text(encoding="utf-8")
    sql_values = _extract_check_values(sql_text, "candidates_source_path_check")
    py_values = set(models.SOURCE_PATH.__args__)
    assert sql_values == py_values, (
        f"SOURCE_PATH drift: Python={py_values}, SQL={sql_values}"
    )


def test_candidate_type_pydantic_matches_sql():
    """models.CANDIDATE_TYPE Literal must exactly equal candidates_type_check.

    This is the load-bearing 9-kind contract for the deployed
    loom-architecture-registry. The consolidated 007 migration declares the
    CHECK twice (inline in CREATE TABLE + the guarded re-assertion); both are
    the same 9 values. _extract_check_values matches the first (inline) one.
    """
    sql_text = _MIGRATION.read_text(encoding="utf-8")
    sql_values = _extract_check_values(sql_text, "candidates_type_check")
    py_values = set(models.CANDIDATE_TYPE.__args__)
    assert sql_values == py_values, (
        f"CANDIDATE_TYPE drift: Python={py_values}, SQL={sql_values}"
    )
    # Belt-and-braces: exactly the 9 ratified kinds.
    assert len(py_values) == 9, f"expected 9 kinds, got {len(py_values)}: {py_values}"


def test_status_pydantic_matches_sql():
    """models.STATUS Literal must exactly equal candidates_status_check."""
    sql_text = _MIGRATION.read_text(encoding="utf-8")
    sql_values = _extract_check_values(sql_text, "candidates_status_check")
    py_values = set(models.STATUS.__args__)
    assert sql_values == py_values, (
        f"STATUS drift: Python={py_values}, SQL={sql_values}"
    )


# ---------------------------------------------------------------------------
# Invariant 3: Models forbid client-supplied tenant_id
# ---------------------------------------------------------------------------


def test_candidate_create_rejects_tenant_id_in_body():
    """A hosted-multitenant client must NOT be able to spoof tenant_id by
    setting it in the body. extra='forbid' is the guarantee."""
    from uuid import uuid4

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        models.CandidateCreate(
            project_id=uuid4(),
            source_path="path_a",
            candidate_type="skill",
            tenant_id=str(uuid4()),  # spoofing attempt
        )


def test_candidate_status_update_rejects_tenant_id_in_body():
    """Same protection on the PATCH body."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        models.CandidateStatusUpdate(
            status="recurring",
            tenant_id=NIL_TENANT_ID,
        )


def test_candidate_create_minimal_valid():
    """Smoke: a minimal CandidateCreate with only the required fields
    constructs cleanly."""
    from uuid import uuid4

    c = models.CandidateCreate(
        project_id=uuid4(),
        source_path="path_a",
        candidate_type="skill",
    )
    # Defaults applied:
    assert c.status == "draft"
    assert c.instance_id == ""
    assert c.evidence_refs == []
    assert c.signals == {}


def test_candidate_create_rejects_invalid_enum_values():
    """source_path / candidate_type / status all reject values not in
    the Literal set."""
    from uuid import uuid4

    from pydantic import ValidationError

    base = {
        "project_id": uuid4(),
        "source_path": "path_a",
        "candidate_type": "skill",
    }
    with pytest.raises(ValidationError):
        models.CandidateCreate(**{**base, "source_path": "path_c"})
    with pytest.raises(ValidationError):
        models.CandidateCreate(**{**base, "candidate_type": "magic"})
    with pytest.raises(ValidationError):
        models.CandidateCreate(**{**base, "status": "transcended"})


def test_candidate_create_accepts_all_9_kinds():
    """Every ratified kind must construct cleanly through the request model."""
    from uuid import uuid4

    for kind in models.CANDIDATE_TYPE.__args__:
        c = models.CandidateCreate(
            project_id=uuid4(),
            source_path="path_b",
            candidate_type=kind,
        )
        assert c.candidate_type == kind


# ---------------------------------------------------------------------------
# Invariant 4: auth_bridge resolve_tenant fallback
# ---------------------------------------------------------------------------


def test_resolve_tenant_falls_back_to_self_host_when_unset():
    """Code paths that don't go through verify_bearer (background tasks,
    tests) get the service's SELF_HOST_TENANT_ID, not None."""
    assert auth_bridge.resolve_tenant() == auth_bridge.SELF_HOST_TENANT_ID
