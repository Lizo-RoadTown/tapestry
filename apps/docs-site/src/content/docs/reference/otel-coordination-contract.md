---
title: OTel coordination contract
description: The attribute schema that Tapestry-emitted OTel events must carry so the observer can interpret them as coordination signals. OTel is the transport. Tapestry interprets the signal as coordination reinforcement.
---

OTEL carries the signal. Tapestry interprets the signal as coordination reinforcement.

OTel is the canonical telemetry transport (OTLP → Grafana Cloud). This page is the attribute contract every Tapestry-emitting event must carry so the observer can read those events as coordination signals — not just hook/tool noise.

## Direction

- Keep the existing OTLP → Grafana Cloud pipeline.
- Preserve current hook / tool / session / snapshot / observer events.
- Convert free-text `note` data into structured attributes where possible.
- Add missing attributes only when they can be reliably generated.

## Required anchor

| Attribute | Purpose |
|---|---|
| `tapestry.coordination_context_id` | The single anchor that ties every event in one coordination episode together. Required on every Tapestry-emitting event. |

## Required context

| Attribute | When set |
|---|---|
| `tapestry.project_id` | Always |
| `tapestry.session_id` | Always |
| `tapestry.agent_id` | If known |
| `tapestry.agent_role` | If known |
| `tapestry.surface_id` *or* `tapestry.workflow_surface` | If known |
| `tapestry.surface_type` | If known |

## Mechanism attributes

| Attribute | Carried by |
|---|---|
| `tapestry.hook_name` | Every hook event |
| `tapestry.tool_name` | PreToolUse / tool-invocation events |
| `tapestry.architecture_snapshot_id` | SessionStart snapshot events |
| `tapestry.diff_report_id` | Snapshot diff events |
| `tapestry.observer_ran` | Observer events |
| `tapestry.observer_detected_count` | Observer events |
| `tapestry.observer_created_count` | Observer events |
| `tapestry.observer_updated_count` | Observer events |
| `tapestry.friction_present` | Any event that surfaces friction |
| `tapestry.friction_type` | When `friction_present=true` |
| `tapestry.correction_present` | Events involving an operator correction |
| `tapestry.memory_read_count` | Events that touch loom-memory |
| `tapestry.memory_write_count` | Events that touch loom-memory |
| `tapestry.memory_miss` | When a recall returned nothing |
| `tapestry.upskill_candidate_present` | Events that surfaced a candidate |

## Explicit states

Coordination-quality signals MUST use one of these four states. Missing instrumentation is **blind**, not healthy.

| State | Meaning |
|---|---|
| `healthy` | Signal present; coordination working as expected |
| `degraded` | Signal present; coordination quality dropping |
| `blind` | Signal not yet instrumented; absence of evidence ≠ evidence of absence |
| `unknown` | Signal expected but unavailable this event (transient) |

## Dashboard direction

The Tapestry dashboard reads from OTel-backed telemetry. It is not Grafana. Grafana is the backend observability substrate; the Tapestry dashboard is the coordination-support view layered over that telemetry.

## Current state

The transport is wired ([`integrations/claude-code/tapestry-discipline/scripts/_observability.py`](https://github.com/Lizo-RoadTown/tapestry/blob/main/integrations/claude-code/tapestry-discipline/scripts/_observability.py)) — OTLP/HTTP push to Grafana Cloud via raw urllib, no SDK dependency. The same source also lives in `the-loom/adapters/claude-code/loom-discipline/scripts/_observability.py` during the transition window; both copies are byte-identical per PR #42.

Current attributes per event: `hook_name`, `event`, `exit_code`, `elapsed_ms`, `action`, `note`. The `note` field carries unstructured strings (`out_of_scope`, `malformed_input`, etc.) that this contract is meant to replace with typed attributes.

## What this contract does NOT include

Intent. Intent is observer-derived, not telemetry-emitted — see [Observer-derived intent](/explanation/observer-derived-intent/). Adding intent attributes here would conflate the interpretation layer with the emission layer. The observer reads these typed attributes (plus memory, transcripts, diffs, prior findings) and produces an intent hypothesis as a separate output.

## Source of truth

This page is the operator-facing surface of the contract. The internal architecture spec lives at [`docs/reference/coordination-telemetry-contract.md`](https://github.com/Lizo-RoadTown/tapestry/blob/main/docs/reference/coordination-telemetry-contract.md) in the repo root (Tapestry-agent owned). If the two diverge, the repo-root spec is canonical.

## Related

- [Load-bearing files — OTel env vars](/reference/load-bearing-files/#otel-otel-telemetry)
- [The observer](/explanation/the-observer/) — consumes OTel telemetry as one of its sensors
- [Architecture snapshots](/explanation/architecture-snapshots/) — one of several mechanisms; snapshot/diff IDs land in the contract via `tapestry.architecture_snapshot_id` / `tapestry.diff_report_id`
- [Observatory console](/observatory) — the operator-facing view that will read these typed attributes once instrumented
