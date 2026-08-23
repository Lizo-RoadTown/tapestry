"""Discipline-hook event ingest — the bare-key -> 005-contract mapper.

Phase 0 **task 4** of the observer-capacity build
(docs/plans/2026-08-23-observer-capacity-build-sequence.md). This is what gives
telemetry PROJECT ATTRIBUTION: the discipline hooks emit flat entries carrying
`project_id` (= LOOM_PROJECT_ID, the canonical slug), and this handler maps
those entries into `telemetry_events` so /telemetry/signals and
/telemetry/counts light up per project.

## Input shape (the flat entry the hooks write)

The entry is exactly what `_observability.log_event` produces
(integrations/claude-code/tapestry-discipline/scripts/_observability.py:395-427):

    ts, hook, phase                          # always
    scope_in, action, note                   # optional
    exit_code, elapsed_ms                     # optional (end phase)
    session_id                                # from CLAUDE_SESSION_ID
    tool_name                                 # from LOOM_HOOK_TOOL_NAME (PreToolUse)
    project_id                                # from LOOM_PROJECT_ID (the SLUG)

plus, once task 5's emitter enriches them, any `tapestry.*` attribute from the
OTel coordination contract
(apps/docs-site/src/content/docs/reference/otel-coordination-contract.md). This
mapper accepts all of them today so the emitter can add them without a server
change.

## bare key -> 005 column (infra/migrations/005_init_telemetry.sql)

    event_kind        'tool' when tool_name present or hook in {PreToolUse,
                      PostToolUse}; else 'hook' (both in the 005 CHECK set)
    project_slug   <- project_id            (LOOM_PROJECT_ID = the slug =
                                             canonical wire identity)
    session_id     <- session_id
    hook_name      <- hook_name or hook
    tool_name      <- tool_name
    phase          <- phase
    exit_code      <- exit_code
    elapsed_ms     <- elapsed_ms
    ts             <- ts (epoch or ISO -> epoch, reusing the skill-usage
                     converter)
    coordination_context_id <- tapestry.coordination_context_id (else NULL/blind)
    coordination_state      <- tapestry.coordination_state (validated; else the
                               005 default 'blind' — "missing instrumentation is
                               blind, not healthy")
    agent_id / agent_role / surface_id / surface_type <- the same-named
                               tapestry.* keys when present

Everything else — `note`, `action`, `scope_in`, and the signal flags the
/telemetry/signals endpoint reads (`tapestry.friction_present`,
`tapestry.memory_miss`, `tapestry.correction_present`,
`tapestry.upskill_candidate_present`, plus `tapestry.friction_type`,
`tapestry.observer_*`, `tapestry.memory_*`, `tapestry.architecture_snapshot_id`,
`tapestry.diff_report_id`, and any other tapestry.* attr) — lands in the `attrs`
JSONB under its ORIGINAL key. The signal flags keep their full `tapestry.`
prefix so `attrs @> '{"tapestry.friction_present": true}'` (read_api.py
_SIGNALS_AGG_SQL:313-332) matches exactly.

## Idempotency (task 7 backfill safe)

Each entry gets a STABLE uuid5 id derived from its stable fields
(session_id + hook_name + phase + tool_name + raw ts). Replaying the same
hooks.jsonl line — which task 7's `flush-hooks-jsonl` backfill does — derives
the same id, so `persist.persist_events`'s ON CONFLICT (id) DO NOTHING dedups it
instead of double-counting the rollup. Same discipline as skill-usage's
batch_id+index id.

## Tenant (fail closed)

Hook events are self-host: the tenant resolves via the SAME helper the write
path uses (`skill_usage_handler._self_host_tenant_id` -> SELF_HOST_TENANT_ID ->
LOOM_SELF_HOST_TENANT_ID -> nil). If it resolves to nil we SKIP + warn rather
than write to the all-zeros tenant. A future hosted deployment may carry an
explicit `tapestry.tenant_id` on the entry; that is honored per-entry and
grouped like the skill-usage path.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import db
import persist
import skill_usage_handler

logger = logging.getLogger("loom.telemetry.hook_event")

# Hooks whose firing IS a tool invocation. tool_name is the stronger signal;
# these cover the case where an entry lacks tool_name but the hook itself is a
# tool-lifecycle hook.
_TOOL_INVOCATION_HOOKS = frozenset({"PreToolUse", "PostToolUse"})

# The four coordination states (005 CHECK + otel-coordination-contract.md:56-63).
_COORDINATION_STATES = frozenset({"healthy", "degraded", "blind", "unknown"})

# tapestry.* keys that have a typed 005 column. These map to the column and are
# NOT duplicated into attrs. (project_id is deliberately absent: the slug is
# carried by the bare `project_id` key -> project_slug; the project_id UUID
# column stays NULL until the registry resolves the slug.)
_TAPESTRY_COLUMN_KEYS: dict[str, str] = {
    "tapestry.coordination_context_id": "coordination_context_id",
    "tapestry.coordination_state": "coordination_state",
    "tapestry.session_id": "session_id",
    "tapestry.hook_name": "hook_name",
    "tapestry.tool_name": "tool_name",
    "tapestry.agent_id": "agent_id",
    "tapestry.agent_role": "agent_role",
    "tapestry.surface_id": "surface_id",
    "tapestry.surface_type": "surface_type",
}

# Bare entry keys consumed into typed columns (never duplicated into attrs).
_CONSUMED_BARE_KEYS = frozenset(
    {
        "ts",
        "hook",
        "hook_name",
        "phase",
        "exit_code",
        "elapsed_ms",
        "session_id",
        "tool_name",
        "project_id",
    }
)


# ---------------------------------------------------------------------------
# Tenant resolution (mirror of skill_usage_handler._resolve_event_tenant)
# ---------------------------------------------------------------------------


def _resolve_hook_tenant(entry: dict[str, Any]) -> str | None:
    """Resolve the tenant this hook entry is written under, or None (fail
    closed). Self-host uses the deployment's SELF_HOST_TENANT_ID; a hosted
    deployment may assert an explicit `tapestry.tenant_id` on the entry.
    """
    asserted = entry.get("tapestry.tenant_id")
    if asserted and str(asserted) != skill_usage_handler.NIL_TENANT_ID:
        return str(asserted)
    fallback = skill_usage_handler._self_host_tenant_id()
    if fallback and fallback != skill_usage_handler.NIL_TENANT_ID:
        return fallback
    return None


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _to_epoch(ts_value: Any) -> float:
    """Hook `ts` -> epoch seconds. Accepts an epoch number, a numeric string, or
    an ISO-8601 string (reusing the skill-usage converter for the ISO branch).
    Raises ValueError on anything unparseable.
    """
    if isinstance(ts_value, bool):  # bool is an int subclass — reject explicitly
        raise ValueError("ts must not be a boolean")
    if isinstance(ts_value, (int, float)):
        return float(ts_value)
    if ts_value is None:
        raise ValueError("ts is required")
    s = str(ts_value).strip()
    if not s:
        raise ValueError("ts is empty")
    try:
        return float(s)  # epoch as a string
    except ValueError:
        return skill_usage_handler._iso_to_epoch(s)  # ISO-8601 -> epoch


def _hook_event_id(
    session_id: str, hook_name: str, phase: str, tool_name: str, ts_raw: Any
) -> str:
    """STABLE uuid5 id from the entry's stable fields. The `hook-event:` prefix
    keeps this id-space disjoint from skill-usage's `batch_id:index` space even
    though both use NAMESPACE_URL. Uses the RAW ts value so a replayed
    hooks.jsonl line (task 7 backfill) derives the identical id and dedups.
    """
    key = f"hook-event:{session_id}|{hook_name}|{phase}|{tool_name}|{ts_raw}"
    return str(uuid.uuid5(skill_usage_handler._EVENT_ID_NAMESPACE, key))


def _entry_to_row(entry: dict[str, Any], tenant_id: str) -> dict[str, Any]:
    """Map one flat hook entry -> a persist_events fact row (column->value).

    Raises ValueError if `ts` is unparseable (caller skips + warns).
    """
    hook_name = (
        entry.get("hook_name")
        or entry.get("hook")
        or entry.get("tapestry.hook_name")
    )
    tool_name = entry.get("tool_name") or entry.get("tapestry.tool_name")
    session_id = entry.get("session_id") or entry.get("tapestry.session_id")
    phase = entry.get("phase")
    # project_id (bare) is LOOM_PROJECT_ID = the canonical slug. This is the
    # whole point of hook ingest: hook events ARE project-attributed.
    project_slug = entry.get("project_id") or entry.get("tapestry.project_id") or ""

    ts_raw = entry.get("ts")
    ts = _to_epoch(ts_raw)  # may raise ValueError

    is_tool = bool(tool_name) or (hook_name in _TOOL_INVOCATION_HOOKS)
    event_kind = "tool" if is_tool else "hook"

    row: dict[str, Any] = {
        "id": _hook_event_id(
            session_id or "", hook_name or "", phase or "", tool_name or "", ts_raw
        ),
        "tenant_id": tenant_id,
        "event_kind": event_kind,
        "project_slug": project_slug,
        "ts": ts,
    }
    if session_id:
        row["session_id"] = session_id
    if hook_name:
        row["hook_name"] = hook_name
    if tool_name:
        row["tool_name"] = tool_name
    if phase is not None:
        row["phase"] = str(phase)
    if entry.get("exit_code") is not None:
        row["exit_code"] = entry["exit_code"]
    if entry.get("elapsed_ms") is not None:
        row["elapsed_ms"] = entry["elapsed_ms"]

    # attrs: every non-consumed key, tapestry.* kept verbatim so the signal
    # flags match the /telemetry/signals containment queries by exact name.
    attrs: dict[str, Any] = {}
    for key, value in entry.items():
        if value is None:
            continue
        if key in _CONSUMED_BARE_KEYS:
            continue
        if key == "tapestry.tenant_id":
            continue  # auth/tenant signal, not a stored attr
        if key in _TAPESTRY_COLUMN_KEYS:
            continue  # handled as a typed column below
        attrs[key] = value

    # Typed coordination columns.
    cc = entry.get("tapestry.coordination_context_id")
    if cc is not None:
        try:
            row["coordination_context_id"] = str(uuid.UUID(str(cc)))
        except (ValueError, AttributeError, TypeError):
            # Malformed anchor — keep the raw value in attrs, column stays NULL.
            attrs["tapestry.coordination_context_id"] = cc

    cs = entry.get("tapestry.coordination_state")
    if cs in _COORDINATION_STATES:
        row["coordination_state"] = cs
    elif cs is not None:
        # Unknown enum value — preserve it in attrs; column defaults to 'blind'.
        attrs["tapestry.coordination_state_raw"] = cs
    # else: omit the column -> 005 default 'blind'.

    for tkey, col in (
        ("tapestry.agent_id", "agent_id"),
        ("tapestry.agent_role", "agent_role"),
        ("tapestry.surface_id", "surface_id"),
        ("tapestry.surface_type", "surface_type"),
    ):
        val = entry.get(tkey)
        if val is not None:
            row[col] = str(val)

    row["attrs"] = attrs
    return row


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def apply_hook_events(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Persist a list of flat hook entries into the telemetry substrate.

    Groups by resolved write tenant (normally one — the self-host tenant) and
    writes each group inside one `db.tenant_transaction` via the shared
    `persist.persist_events`. Returns `{events_processed: N}` where N is the
    count ACTUALLY persisted (replayed duplicates excluded via ON CONFLICT).
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    skipped = 0
    for index, entry in enumerate(entries):
        tenant_id = _resolve_hook_tenant(entry)
        if tenant_id is None:
            skipped += 1
            logger.warning(
                json.dumps(
                    {
                        "event": "hook_event_skipped_no_tenant",
                        "reason": "no tenant on entry and SELF_HOST_TENANT_ID unset",
                        "index": index,
                    },
                    separators=(",", ":"),
                )
            )
            continue
        try:
            row = _entry_to_row(entry, tenant_id)
        except (ValueError, TypeError) as exc:
            skipped += 1
            logger.warning(
                json.dumps(
                    {
                        "event": "hook_event_skipped_bad_entry",
                        "index": index,
                        "error": str(exc),
                    },
                    separators=(",", ":"),
                )
            )
            continue
        groups.setdefault(tenant_id, []).append(row)

    persisted = 0
    for tenant_id, rows in groups.items():
        async with db.tenant_transaction(tenant_id) as conn:
            persisted += await persist.persist_events(conn, rows)

    if skipped:
        logger.info(
            json.dumps(
                {
                    "event": "hook_events_partial",
                    "received": len(entries),
                    "persisted": persisted,
                    "skipped": skipped,
                },
                separators=(",", ":"),
            )
        )

    return {"events_processed": persisted}
