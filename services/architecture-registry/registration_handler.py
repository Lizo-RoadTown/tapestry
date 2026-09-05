"""Receive + apply the Make_Skills engine's registration ack.

PR C of the loom-side bridge build. Endpoint surface in main.py;
core logic here.

## Wire context

Per the spec at Make_Skills `docs/proposals/2026-05-25-skill-making-bridge.md`
§2 + PR #69's ack-defer extension, the engine POSTs `RegistrationAck` to
the callback URL the-loom included in the original promotion candidate's
`callbacks.registration_ack`. The bridge HMAC signature is in the
`X-MakeSkills-Signature` header (mirror of `X-Loom-Signature` going the
other direction).

## What this module does

Given a verified, parsed `RegistrationAck`:

1. Resolve which candidate it belongs to (v1.0: `ack.promotion_id` is
   identically the `candidate_id`, per promote_dispatcher.py's design).
2. Decide the target status based on `ack.outcome`:
   - `compiled` → status = 'promoted'
   - `rejected` → status = 'rejected'
   - `queued_human_review` → leave status as 'promotion_requested';
     append an evidence entry recording the review queue placement
   - `ack_deferred` → leave status as 'promotion_requested'; append an
     evidence entry recording the deferral (kind not yet handled by engine)
3. PATCH the candidate via storage.update_candidate_status, with a
   reason string for the audit trail (evidence_refs append).
4. Return the row.

## What this module does NOT do

- Verify HMAC (endpoint does that before calling apply_ack)
- Parse the raw body to RegistrationAck (endpoint does that)
- Write to a separate "skills index" table (v1.0 doesn't have one;
  the engine owns the catalog per spec §"Q6 catalog ownership")
- Apply tenant resolution from the JWT (caller passes tenant_id;
  v1.0 uses SELF_HOST_TENANT_ID — hosted-multitenant gap tracked)

## Dual-mode

- Self-host: tenant_id = SELF_HOST_TENANT_ID. The candidate naturally
  belongs to Liz's tenant; storage.update_candidate_status uses RLS
  via set_config('app.tenant_id', ...) and finds it.
- Hosted-multitenant FUTURE: the ack body's `skill.tenant_id` (when
  outcome='compiled') carries the original promoter's tenant. For
  rejected / queued_human_review / ack_deferred outcomes the ack
  doesn't carry tenant_id explicitly — need a tenant-mapping
  mechanism (separate from this PR). Tracked as a known gap.

## Failure modes

- `CandidateNotFoundError`: the promotion_id (= candidate_id) doesn't
  resolve under the caller's tenant scope. Endpoint maps to 404.
  Could mean: candidate was deleted, candidate was promoted by a
  different deployment that shares the bridge secret (impossible in
  current setup but worth being defensive), or RLS hides it (privacy
  invariant).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import bridge_models
import storage


class CandidateNotFoundError(Exception):
    """The candidate referenced by ack.promotion_id is not visible to
    the caller's tenant. Endpoint maps to HTTP 404."""


# Map ack outcome → target candidate status, OR None if outcome doesn't
# transition status (queued_human_review, ack_deferred).
_OUTCOME_TO_STATUS: dict[str, str | None] = {
    "compiled": "promoted",
    "rejected": "rejected",
    "queued_human_review": None,
    "ack_deferred": None,
}


def _outcome_reason(ack: bridge_models.RegistrationAck) -> str:
    """One-line audit-trail reason for the candidate's evidence_refs."""
    outcome = ack.outcome
    if outcome == "compiled" and ack.skill is not None:
        return (
            f"Engine compiled skill {ack.skill.skill_id} "
            f"(name={ack.skill.name!r}, version={ack.skill.version})"
        )
    if outcome == "rejected" and ack.compilation_diagnostics is not None:
        n_errors = len(ack.compilation_diagnostics.errors)
        # errors is list[dict[str, str]] per engine's canonical shape (e.g.
        # [{"phase": "compiler", "message": "..."}]). Access with [] not .
        first = (
            ack.compilation_diagnostics.errors[0].get("message", "")[:120]
            if n_errors
            else "no diagnostics provided"
        )
        return (
            f"Engine rejected ({n_errors} error"
            f"{'' if n_errors == 1 else 's'}): {first}"
        )
    if outcome == "queued_human_review":
        return "Engine queued for human review (suspected duplicate or ambiguity)"
    if outcome == "ack_deferred":
        return (
            "Engine ack-deferred (candidate_kind not yet handled by "
            "this engine version)"
        )
    return f"Engine outcome={outcome!r} (no further context provided)"


async def apply_ack(
    ack: bridge_models.RegistrationAck, tenant_id: str
) -> dict[str, Any]:
    """Apply a verified, parsed ack to the candidates table.

    Per the v1.0 design (promote_dispatcher.py): `ack.promotion_id` is
    identically the `candidate_id`. So we can look it up directly.

    Returns the updated row.
    Raises CandidateNotFoundError if the candidate isn't visible.
    """
    candidate_id: UUID = ack.promotion_id

    target_status = _OUTCOME_TO_STATUS.get(ack.outcome)
    reason = _outcome_reason(ack)

    if target_status is None:
        # No status transition; just append an audit entry by calling
        # update_candidate_status with the current status as "new" so the
        # storage layer's audit-append path fires. This is a small hack
        # to keep the audit trail flowing without adding a separate
        # "append_audit" helper. Read current status first.
        row = await storage.get_candidate(candidate_id, tenant_id)
        if not row:
            raise CandidateNotFoundError(str(candidate_id))
        current_status = row["status"]
        updated = await storage.update_candidate_status(
            candidate_id, current_status, tenant_id, reason=reason
        )
        if not updated:
            raise CandidateNotFoundError(str(candidate_id))
        return updated

    updated = await storage.update_candidate_status(
        candidate_id, target_status, tenant_id, reason=reason
    )
    if not updated:
        raise CandidateNotFoundError(str(candidate_id))
    return updated
