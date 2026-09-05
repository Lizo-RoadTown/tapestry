"""Dispatch a promoted candidate to the Make_Skills engine via the bridge.

Per the spec at Make_Skills `docs/proposals/2026-05-25-skill-making-bridge.md`
+ Loom-agent's 5 ratification adjustments + MS-agent's PR #69 incorporation.
PR B of the loom-side bridge build (parallel sequencing ratified
2026-06-12 evening).

## What this module does

Given a candidate_id + tenant_id:

1. Fetch the candidate row from storage
2. Derive `capability_tags` + `triggers` from observer signals
   (adjustment #2: NOT from the source frontmatter)
3. Build the `PromotionCandidate` payload (bridge_models.PromotionCandidate)
4. Serialize to JSON via Pydantic
5. HMAC-sign the (timestamp + body) via bridge_hmac.sign
6. POST to `{LOOM_ENGINE_BASE_URL}/access/webhook/skill-promotion`
7. Return the engine's parsed response

## What this module does NOT do

- Make the trigger automatic (v1.0 = explicit endpoint; auto on status
  transition lands later)
- Retry on transient failure (caller decides; engine spec has retry
  semantics for the OTHER direction)
- Handle non-skill kinds with full compilation (those get ack-deferred
  per PR #69; we still SEND, the engine ack-defers — that path works)

## Dual-mode

- Self-host: `tenant_id` passed in by caller from `auth_bridge.verify_bearer`,
  which resolves to SELF_HOST_TENANT_ID. The bridge payload's tenant_id
  carries that UUID across the wire (adjustment #1: non-nullable).
- Hosted-multitenant: same path; caller passes the JWT-claim UUID.
- The HMAC layer (bridge_hmac) is mode-agnostic — shared secret
  authenticates the deployment pair, not the tenant.

## Configuration

| Env var | Purpose | Default |
|---|---|---|
| `LOOM_ENGINE_BASE_URL` | Where to POST candidates | `https://make-skills-api.onrender.com` |
| `LOOM_SKILL_BRIDGE_SECRET` | HMAC shared secret (used via bridge_hmac) | (must be set) |
| `LOOM_REGISTRATION_ACK_URL` | Override for the ack callback in payload | `https://loom-architecture-registry.onrender.com/skill-registered` |
| `LOOM_TELEMETRY_CALLBACK_URL` | Override for telemetry callback in payload | `https://loom-telemetry-ingestion.onrender.com/skill-used` |
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

import httpx

import bridge_hmac
import bridge_models
import storage


class CandidateNotFoundError(Exception):
    """Raised when the candidate_id doesn't resolve under the caller's
    tenant scope. The endpoint handler maps to HTTP 404.

    DISTINCT from DispatchError(404, ...) which signals the ENGINE
    returned 404 (e.g., the bridge URL was wrong). Same numeric status,
    different semantics — exception-type discrimination prevents the
    misleading "Candidate not found" error message when the actual cause
    is engine-side."""


class DispatchError(Exception):
    """Raised by dispatch_promotion() on ENGINE-side failures. Carries the
    upstream HTTP status (or -1 for transport failures) + the response body
    so the endpoint handler can shape the appropriate HTTP response.

    DOES NOT cover local "candidate not found in registry" — use
    CandidateNotFoundError for that."""

    def __init__(self, status: int, body: str, message: str = ""):
        self.status = status
        self.body = body
        super().__init__(message or f"Dispatch failed ({status}): {body[:200]}")


def _engine_url() -> str:
    return os.environ.get(
        "LOOM_ENGINE_BASE_URL", "https://make-skills-api.onrender.com"
    )


def _registration_ack_url() -> str:
    return os.environ.get(
        "LOOM_REGISTRATION_ACK_URL",
        "https://loom-architecture-registry.onrender.com/skill-registered",
    )


def _telemetry_callback_url() -> str:
    return os.environ.get(
        "LOOM_TELEMETRY_CALLBACK_URL",
        "https://loom-telemetry-ingestion.onrender.com/skill-used",
    )


# ---------------------------------------------------------------------------
# Derivation: observer signals → capability_tags + triggers
# ---------------------------------------------------------------------------


def derive_capability_tags(row: dict[str, Any]) -> list[str]:
    """Derive capability_tags from a candidate row's observer signals.

    Adjustment #2: these come from observer-side analysis on the loom,
    not from the human-authored source frontmatter. v1.0 derivation is
    intentionally minimal — the kind + the skill_name if present. The
    engine refines them at compile time.

    Returns a deduped, sorted list of kebab-case tags.
    """
    tags: set[str] = set()
    tags.add(row["candidate_type"])  # e.g., "skill"

    signals = row.get("signals") or {}
    skill_name = signals.get("skill_name")
    if isinstance(skill_name, str) and skill_name:
        tags.add(skill_name)

    # Future: scan evidence_refs[].kind for additional categorical tags
    # (e.g., "session_boundary", "promotion_idea"). Held back from v1.0
    # to avoid speculative shape.

    return sorted(tags)


def derive_triggers(row: dict[str, Any]) -> list[str]:
    """Derive "when X happens" trigger phrasings from the candidate's
    evidence + signals.

    v1.0 derivation: emit one trigger summarizing the observed pattern.
    Engine refines on compile.
    """
    triggers: list[str] = []
    signals = row.get("signals") or {}
    skill_name = signals.get("skill_name")
    sessions_seen = signals.get("sessions_seen")

    if isinstance(skill_name, str) and skill_name:
        if isinstance(sessions_seen, int) and sessions_seen > 0:
            triggers.append(
                f"agent invokes '{skill_name}' (observed in {sessions_seen} sessions)"
            )
        else:
            triggers.append(f"agent invokes '{skill_name}'")

    short_desc = signals.get("short_description")
    if isinstance(short_desc, str) and short_desc:
        triggers.append(short_desc[:200])

    return triggers


# ---------------------------------------------------------------------------
# Payload assembly
# ---------------------------------------------------------------------------


def _pattern_signature(row: dict[str, Any]) -> str:
    """Stable hash of (candidate_type + project_id + a stable signals key).
    Used by the engine to dedup re-promotions of the same observed pattern."""
    signals = row.get("signals") or {}
    key = (
        f"{row['candidate_type']}|"
        f"{row['project_id']}|"
        f"{signals.get('skill_name', '')}"
    )
    return "sha256:" + sha256(key.encode("utf-8")).hexdigest()[:40]


def _source_body(row: dict[str, Any]) -> str:
    """Construct the markdown source for the engine. v1.0 = a minimal
    SKILL.md scaffold derived from signals. The human / agent fills in
    real body later via the engine's `queued_human_review` path or via
    a follow-up re-promotion with richer source."""
    signals = row.get("signals") or {}
    skill_name = signals.get("skill_name") or "unnamed-skill"
    short_desc = (
        signals.get("short_description")
        or f"Promoted from observer-detected pattern: {skill_name}"
    )
    return (
        f"# {skill_name}\n\n"
        f"{short_desc}\n\n"
        f"_(Stub source emitted by the-loom's promote_dispatcher; engine may "
        f"flag this `queued_human_review` if the body is too thin.)_\n"
    )


def build_promotion_candidate(
    row: dict[str, Any],
    tenant_id: str,
    *,
    promotion_id: UUID | None = None,
) -> bridge_models.PromotionCandidate:
    """Assemble the PromotionCandidate payload from a candidate row.

    `promotion_id` is generated fresh per call unless provided (tests + the
    idempotent-retry pattern pass an explicit one).
    """
    signals = row.get("signals") or {}
    evidence_refs = row.get("evidence_refs") or []

    occurrence = 0
    for ref in evidence_refs:
        if isinstance(ref, dict):
            count = ref.get("count")
            if isinstance(count, int):
                occurrence += count
    if occurrence == 0:
        # Always at least 1 (the candidate itself); spec requires ≥1.
        occurrence = max(1, signals.get("sessions_seen", 1) or 1)

    skill_name = signals.get("skill_name") or "unnamed-skill"
    short_desc = (
        signals.get("short_description")
        or f"Promoted from observer-detected pattern: {skill_name}"
    )

    # Build evidence_refs list (engine's canonical shape: list of
    # {kind, ref, captured_at} dicts, NOT the old structured `evidence` object).
    # Carry each observer-collected ref forward with a stringified ref + the
    # observed_at timestamp if present.
    new_evidence_refs: list[bridge_models.EvidenceRef] = []
    for ref in evidence_refs:
        if not isinstance(ref, dict):
            continue
        kind = ref.get("kind")
        if not isinstance(kind, str):
            continue
        # `ref` field carries a compact identifier; we use session_id when
        # available, otherwise fall back to a synthesized string from the count.
        ref_str = ref.get("session_id") or f"count={ref.get('count', '')}"
        captured = ref.get("observed_at")
        captured_str: Optional[str] = None
        if isinstance(captured, (int, float)):
            captured_str = datetime.fromtimestamp(
                captured, tz=timezone.utc
            ).isoformat()
        elif isinstance(captured, str):
            captured_str = captured
        new_evidence_refs.append(
            bridge_models.EvidenceRef(
                kind=kind,
                ref=str(ref_str)[:256],
                captured_at=captured_str,
            )
        )

    # Build signals — engine's Signals model has extra='allow' so we forward
    # the observer's raw signals dict directly (it'll accept skill_name,
    # repeat_count, count_this_session, sessions_seen, etc.).
    new_signals = bridge_models.Signals(
        skill_name=signals.get("skill_name"),
        repeat_count=signals.get("count_this_session") or signals.get("sessions_seen"),
    )

    # Frontmatter caps match engine (name ≤120, description ≤500).
    return bridge_models.PromotionCandidate(
        promotion_id=promotion_id or uuid4(),
        pattern_signature=_pattern_signature(row),
        tenant_id=UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id,
        source_system="loom",
        is_global=False,
        candidate_kind=row["candidate_type"],
        source=bridge_models.CandidateSource(
            body_md=_source_body(row),
            frontmatter=bridge_models.CandidateSourceFrontmatter(
                name=skill_name[:120],
                description=short_desc[:500],
            ),
        ),
        evidence_refs=new_evidence_refs,
        signals=new_signals,
        capability_tags=derive_capability_tags(row),
        triggers=derive_triggers(row),
        callbacks=bridge_models.CandidateCallbacks(
            registration_ack=_registration_ack_url(),
            telemetry=_telemetry_callback_url(),
        ),
    )


# ---------------------------------------------------------------------------
# Dispatch (HTTP POST to engine)
# ---------------------------------------------------------------------------


async def dispatch_promotion(
    candidate_id: UUID,
    tenant_id: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """End-to-end: fetch candidate → build payload → HMAC-sign → POST → return ack.

    Caller is responsible for tenant resolution (typically via
    auth_bridge.verify_bearer). This function trusts the supplied tenant_id.

    Returns the engine's parsed JSON response. Raises DispatchError on:
    - Candidate not found (status=404, body=...)
    - Engine returns non-2xx (status=N, body=engine response)
    - Network/transport error (status=-1, body=exception message)

    `http_client` is exposed so tests can inject a mock without monkey-
    patching the module-level httpx.
    """
    row = await storage.get_candidate(candidate_id, tenant_id)
    if not row:
        # CandidateNotFoundError (NOT DispatchError(404)) — distinct from
        # an engine-returned 404. The endpoint maps to HTTP 404 with a
        # clear "candidate not found in registry" message.
        raise CandidateNotFoundError(str(candidate_id))

    # v1.0 design choice: use candidate_id AS promotion_id. Each candidate has
    # one canonical promotion_id (its own UUID); re-dispatch of the same
    # candidate hits the engine's 409 Conflict path which returns the existing
    # skill_id — correct re-promotion semantics without a separate mapping
    # table. The registration_handler in PR C exploits this to look up the
    # candidate from the echoed promotion_id.
    candidate = build_promotion_candidate(
        row, tenant_id, promotion_id=candidate_id
    )
    body = candidate.model_dump_json()
    sig = bridge_hmac.sign(body)
    # Engine path per MS-agent's PR #70 implementation
    # (loom-memory: ms_agent_phase_4_pr_a_landed_pr_70_2026_06_12). The
    # original 2026-05-25 wire spec said /access/webhook/skill-promotion;
    # implementation diverged. See
    # loom-memory: lesson_engine_url_drifted_from_spec_2026_06_13.
    url = f"{_engine_url()}/bridge/promotion-candidate"

    headers = {
        "Content-Type": "application/json",
        "X-Loom-Signature": sig,
    }

    if http_client is None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await _do_post(client, url, body, headers)
    else:
        return await _do_post(http_client, url, body, headers)


async def _do_post(
    client: httpx.AsyncClient, url: str, body: str, headers: dict[str, str]
) -> dict[str, Any]:
    try:
        resp = await client.post(url, content=body, headers=headers)
    except httpx.HTTPError as e:
        raise DispatchError(-1, str(e), f"Transport error: {e}")

    if resp.status_code >= 400:
        raise DispatchError(
            resp.status_code,
            resp.text,
            f"Engine returned {resp.status_code}",
        )

    try:
        return resp.json()
    except ValueError:
        # 2xx but non-JSON — shouldn't happen per spec but be loud if it does.
        raise DispatchError(
            resp.status_code,
            resp.text,
            "Engine returned non-JSON response",
        )
