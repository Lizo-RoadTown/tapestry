# Coordination Telemetry Contract

**Status:** Spec — operator-directed 2026-06-22. Binding for the OTEL emission (`_observability.py`, loom-agent) and the Observatory dashboard reads (Tapestry-agent).
**Governed by:** [Canon: User-Agent Coordination Reinforcement](../canon/user-agent-coordination-reinforcement.md).

## The framing

> **OTEL carries the signal. Tapestry interprets the signal as coordination reinforcement.**

OTEL is already the telemetry transport. **The problem is not transport.** The problem is that the OTEL events are not yet shaped around the user/agent coordination support model. Today telemetry captures hook/tool activity, session starts, stop events, observer counts, and snapshot filenames — but mostly as unstructured `note` strings, not as typed coordination signals.

Tapestry is **not** trying to make OTEL observe "interfaces" as the primary object. Tapestry uses OTEL as **one reinforcement mechanism** for the user/agent support system. The existing hook telemetry should be **enriched** so it can explain coordination quality across projects. Keep the existing OTLP → Grafana Cloud pipeline. **Do not rebuild telemetry from scratch.**

## Supposed vs. actual (PROBE-verified 2026-06-22)

Transport is live: `OTEL_EXPORTER_OTLP_ENDPOINT` + `OTEL_EXPORTER_OTLP_HEADERS` set (→ grafana.net); `the-loom/adapters/claude-code/loom-discipline/scripts/_observability.py:154+` (`_entry_to_otlp_log`) pushes every hook event as OTLP/HTTP, local mirror at `.claude/logs/hooks.jsonl`.

Actual events today (4 hooks): `PreToolUse` (tool_name + target), `UserPromptSubmit`, `Stop` (observer run stats + stop-audit friction heuristic), `SessionStart` (architecture snapshot emitted). Common fields: `ts, hook, phase, scope_in, action, note, exit_code, elapsed_ms, session_id, project_id` (+`tool_name` on PreToolUse). The `note` is free text.

| Supposed | Actual today |
|---|---|
| `coordination_context_id` anchor | ✗ (anchored on session_id + project_id + service.name=loom-discipline) |
| project_id · session_id | ✓ |
| tool_name | ✓ (PreToolUse) |
| architecture snapshot / diff | ~ filename in `note`, not a typed id |
| observer counts | ~ in `note` (obs_detected/created/updated) |
| friction / correction | ~ stop-audit detects, emits a transient warning, no field |
| agent_id/role · user_intent_id · memory counts · surface · friction_type | ✗ |

The coordination signal **is already watched and flows via OTEL**; it is unstructured and un-anchored. The work is enrichment, not replacement.

## Next step

1. **Add a coordination contract to OTEL events.**
2. **Preserve** current hook/tool/session/snapshot/observer events.
3. **Convert free-text `note` data into structured attributes** where possible.
4. **Add missing attributes only when they can be reliably generated.**

## The contract

### Required anchor
- `tapestry.coordination_context_id`

### Required context
- `tapestry.project_id`
- `tapestry.session_id`
- `tapestry.agent_id` *(if known)*
- `tapestry.agent_role` *(if known)*
- `tapestry.surface_id` or `tapestry.workflow_surface` *(if known)*
- `tapestry.surface_type` *(if known)*

### Mechanism attributes
- `tapestry.hook_name`
- `tapestry.tool_name`
- `tapestry.architecture_snapshot_id`
- `tapestry.diff_report_id`
- `tapestry.observer_ran`
- `tapestry.observer_detected_count`
- `tapestry.observer_created_count`
- `tapestry.observer_updated_count`
- `tapestry.friction_present`
- `tapestry.friction_type`
- `tapestry.correction_present`
- `tapestry.memory_read_count`
- `tapestry.memory_write_count`
- `tapestry.memory_miss`
- `tapestry.upskill_candidate_present`

Many of these are already produced and merely need structuring: `hook_name`/`tool_name` (emitted), `architecture_snapshot_id`/`diff_report_id` (snapshot/diff filenames in `note` → ids), `observer_*` (counts in `note` → typed), `friction_present`/`correction_present` (stop-audit detection → a field). Others (`agent_*`, `user_intent`, `memory_*`, `surface_*`) are added only when reliably derivable — per step 4, no fabrication.

## Health states — do not mark missing instrumentation as healthy

Use explicit states:
- **healthy**
- **degraded**
- **blind** — "we do not have the signal yet," NOT "nothing is wrong"
- **unknown**

A mechanism with no instrumentation is **blind**, never green.

## Dashboard direction

The dashboard reads from OTEL-backed telemetry, but **does not become Grafana**. Grafana is the backend observability substrate. Tapestry's dashboard is the **coordination-support view layered over** that telemetry — fleet → project → coordination_context → event, anchored on `coordination_context_id`, with coordination-quality signals (correction frequency, friction recurrence, memory-miss rate, time-to-durable-structure), not request-rate/latency.

## Ownership

- **Tapestry-agent:** this contract + the dashboard reads.
- **loom-agent:** the emission (`_observability.py` enrichment) + transport (OTLP → Grafana Cloud). Keep the pipeline.

## Sources
- [`docs/canon/user-agent-coordination-reinforcement.md`](../canon/user-agent-coordination-reinforcement.md)
- [`docs/proposals/2026-06-22-project-observatory-console.md`](../proposals/2026-06-22-project-observatory-console.md) — the dashboard that consumes this
- `the-loom/adapters/claude-code/loom-discipline/scripts/_observability.py` (`:154+` OTLP push) + the 4 hook scripts (pre_tool_use, user_prompt_submit, stop_audit, session_start)
- loom memory: `tapestry_to_loom_agent_otel_coordination_context_shape_2026_06_22` (the relay)
