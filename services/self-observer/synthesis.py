"""Synthesis-memo builder for the self-observer cron.

After each scan run, the cron POSTs a synthesis memo to loom-memory at
the stable name `self_observer_synthesis_latest`. Every Claude Code
SessionStart auto-recall then surfaces observer state without requiring
the operator to visit the dashboard.

Contract per tapestry/docs/research/2026-06-18-outside-review-runtime-
observation-followup.md §3.3:

  Primary metric: actionable_backlog_count
    = open candidates that are stable OR promotion_requested
      AND have a supported destination handler (today: kind=skill only)
      AND have not reached their next lifecycle step

  Secondary counters (surfaced as well):
    - stuck_promotion_requested_count
    - oldest_stuck_candidate_age (seconds)
    - unsupported_candidate_count_by_kind (dict)
    - dispatch_success_count_since_last_scan — DEFERRED (telemetry rollup not built)
    - dispatch_failure_count_since_last_scan — DEFERRED (telemetry rollup not built)

  Health flag:
    GREEN  : actionable_backlog_count <= 5
    YELLOW : > 5 for 2 consecutive scans (requires prior memo read)
    RED    : > 10
             OR any skill candidate stuck in promotion_requested > 24h
             OR (per ms_agent_runtime_observation_decisions_landed §3 #2)
                any non-skill kind > 20 in promotion_requested for > 7 days

This module is mode-agnostic: it consumes already-tenant-scoped candidate
rows (fetched via CandidateClient → architecture-registry which enforces
RLS at storage) and writes via MemoryClient → loom-agent-context REST
which also enforces RLS. Same tenant_id flows end-to-end.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from config import AuthConfig, Endpoints
from memory_client import MemoryClient


SYNTHESIS_MEMO_NAME = "self_observer_synthesis_latest"

# The only candidate kind with a destination handler in the engine as of
# 2026-06-18 (bridge_closed_end_to_end_2026_06_13). Expand when more land.
SUPPORTED_KINDS = frozenset({"skill"})

# Health thresholds per §3.3.
_GREEN_CEILING = 5
_RED_FLOOR = 10
_RED_STUCK_AGE_SECONDS = 24 * 3600          # 24h for skill candidates
_RED_UNSUPPORTED_KIND_CEILING = 20
_RED_UNSUPPORTED_AGE_SECONDS = 7 * 24 * 3600  # 7d for non-skill kinds


@dataclass
class Counters:
    """Snapshot of candidate-registry state at synthesis time."""

    actionable_backlog_count: int = 0
    stuck_promotion_requested_count: int = 0
    oldest_stuck_candidate_age: float = 0.0
    unsupported_candidate_count_by_kind: dict[str, int] = field(default_factory=dict)
    unsupported_oldest_age_by_kind: dict[str, float] = field(default_factory=dict)


@dataclass
class Health:
    flag: str       # "GREEN" | "YELLOW" | "RED"
    reason: str


async def fetch_open_candidates(endpoints: Endpoints, auth: AuthConfig) -> list[dict[str, Any]]:
    """GET /candidates and return full rows. Soft-fail to empty on error."""
    url = f"{endpoints.candidate_registry_url}/candidates"
    headers = {"Content-Type": "application/json"}
    if auth.observer_jwt:
        headers["Authorization"] = f"Bearer {auth.observer_jwt}"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            print(f"WARN: synthesis fetch failed: {exc}")
            return []
        if resp.status_code != 200:
            print(f"WARN: synthesis fetch {resp.status_code}: {resp.text[:200]}")
            return []
        return resp.json().get("candidates", [])


def compute_counters(candidates: list[dict[str, Any]], now: float | None = None) -> Counters:
    """Aggregate raw candidate rows into the §3.3 counter set."""
    now = now if now is not None else time.time()
    c = Counters()
    for cand in candidates:
        status = cand.get("status")
        kind = cand.get("candidate_type", "")
        updated_at = float(cand.get("updated_at", now))
        age = max(0.0, now - updated_at)

        if status in ("stable", "promotion_requested") and kind in SUPPORTED_KINDS:
            c.actionable_backlog_count += 1
        if status == "promotion_requested":
            c.stuck_promotion_requested_count += 1
            if age > c.oldest_stuck_candidate_age:
                c.oldest_stuck_candidate_age = age
            if kind not in SUPPORTED_KINDS:
                c.unsupported_candidate_count_by_kind[kind] = (
                    c.unsupported_candidate_count_by_kind.get(kind, 0) + 1
                )
                if age > c.unsupported_oldest_age_by_kind.get(kind, 0.0):
                    c.unsupported_oldest_age_by_kind[kind] = age
    return c


def compute_health(current: Counters, prior_actionable: int | None) -> Health:
    """Apply §3.3 health rules. `prior_actionable` is from the prior synthesis
    memo (None if no prior or read failed)."""
    actionable = current.actionable_backlog_count
    if actionable > _RED_FLOOR:
        return Health("RED", f"actionable_backlog_count={actionable} > {_RED_FLOOR}")
    if current.oldest_stuck_candidate_age > _RED_STUCK_AGE_SECONDS:
        hrs = current.oldest_stuck_candidate_age / 3600
        return Health(
            "RED",
            f"skill candidate stuck in promotion_requested for {hrs:.1f}h "
            f"(threshold 24h)",
        )
    for kind, count in current.unsupported_candidate_count_by_kind.items():
        age = current.unsupported_oldest_age_by_kind.get(kind, 0.0)
        if count > _RED_UNSUPPORTED_KIND_CEILING and age > _RED_UNSUPPORTED_AGE_SECONDS:
            return Health(
                "RED",
                f"non-skill kind {kind!r} has {count} stuck candidates, "
                f"oldest {age/86400:.1f}d (thresholds: count>{_RED_UNSUPPORTED_KIND_CEILING}, age>7d)",
            )
    if actionable > _GREEN_CEILING:
        if prior_actionable is not None and prior_actionable > _GREEN_CEILING:
            return Health(
                "YELLOW",
                f"actionable_backlog_count={actionable} > {_GREEN_CEILING} "
                f"for 2 consecutive scans (prior: {prior_actionable})",
            )
        return Health(
            "GREEN",
            f"actionable_backlog_count={actionable} > {_GREEN_CEILING} (first occurrence; "
            f"YELLOW on next scan if it persists)",
        )
    return Health("GREEN", f"actionable_backlog_count={actionable} <= {_GREEN_CEILING}")


def build_memo(
    counters: Counters,
    health: Health,
    run_counters: dict[str, int],
    now: float | None = None,
) -> str:
    """Render the synthesis memo body as markdown."""
    now = now if now is not None else time.time()
    unsupported = counters.unsupported_candidate_count_by_kind
    unsupported_str = (
        ", ".join(f"{k}={v}" for k, v in sorted(unsupported.items())) or "none"
    )
    return f"""# self-observer synthesis — auto-generated

**Deferral health: {health.flag}**
**Reason:** {health.reason}

## Last scan run

- scanned: {run_counters.get("scanned", 0)}
- emitted: {run_counters.get("emitted", 0)}
- skipped_self: {run_counters.get("skipped_self", 0)}
- skipped_dedup: {run_counters.get("skipped_dedup", 0)}
- run_finished_at: {now:.0f} (epoch seconds)

## Counters (per §3.3 of 2026-06-18 runtime-observation-followup)

- actionable_backlog_count: {counters.actionable_backlog_count}
- stuck_promotion_requested_count: {counters.stuck_promotion_requested_count}
- oldest_stuck_candidate_age: {counters.oldest_stuck_candidate_age/3600:.1f} hours
- unsupported_candidate_count_by_kind: {unsupported_str}
- dispatch_success_count_since_last_scan: (awaiting telemetry rollup; deferred to Tapestry Step 7a)
- dispatch_failure_count_since_last_scan: (awaiting telemetry rollup; deferred to Tapestry Step 7a)

## What to read for context

- `services/architecture-registry/` — the candidate registry these counters aggregate
- `services/self-observer/synthesis.py` — this memo's source
- `docs/research/2026-06-16-candidate-lifecycle-verified.md` — the 7-state lifecycle
- `tapestry/docs/research/2026-06-18-outside-review-runtime-observation-followup.md` §3.3 — health contract

## How to act on the flag

- GREEN: nothing required; the loop is healthy.
- YELLOW: actionable backlog is growing for two scans running — review the dashboard for the
  oldest promotion_requested candidates and decide promote/reject.
- RED: review immediately. Either close out the stuck skill candidates (auto-dispatch should
  be firing per A3; if it isn't, check architecture-registry logs for auto_dispatch_failed)
  or accept that non-skill kinds are accumulating because their handlers aren't built yet
  (defer per the Tapestry Step 7a roadmap).
"""


async def build_and_write_synthesis(
    memory_client: MemoryClient,
    endpoints: Endpoints,
    auth: AuthConfig,
    run_counters: dict[str, int],
    now: float | None = None,
) -> bool:
    """Top-level call: fetch state, compute counters + health, write the memo.

    Skip-on-empty: if no candidates exist AT ALL and the scan run emitted
    nothing, no memo is written (avoids placeholder churn). If candidates
    exist OR the scan emitted candidates, the memo is written even if the
    actionable_backlog_count is 0 (so the GREEN flag is visible).
    """
    candidates = await fetch_open_candidates(endpoints, auth)
    if not candidates and run_counters.get("emitted", 0) == 0:
        print("synthesis: skip-on-empty (no candidates + nothing emitted)")
        return False

    counters = compute_counters(candidates, now=now)

    prior = await memory_client.read_synthesis_latest(SYNTHESIS_MEMO_NAME)
    prior_actionable = _extract_prior_actionable(prior)

    health = compute_health(counters, prior_actionable)
    body = build_memo(counters, health, run_counters, now=now)
    return await memory_client.write_synthesis(
        name=SYNTHESIS_MEMO_NAME,
        content=body,
        record_type="project",
        actor="self-observer",
        project_tags=["tapestry"],
        why=f"Auto-generated by self-observer cron; health={health.flag}",
    )


def _extract_prior_actionable(prior_memo: dict[str, Any] | None) -> int | None:
    """Pull `actionable_backlog_count` out of the prior memo's content text.
    Returns None if the prior is absent or the field can't be parsed."""
    if not prior_memo:
        return None
    content = prior_memo.get("content", "")
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("- actionable_backlog_count:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None
