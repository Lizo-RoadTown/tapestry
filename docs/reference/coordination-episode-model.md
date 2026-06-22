# Coordination Episode Model

**Status:** Spec — the meaning layer between raw telemetry and the dashboard. 2026-06-22.
**Governed by:** [Canon: User-Agent Coordination Reinforcement](../canon/user-agent-coordination-reinforcement.md). Pairs with [the OTEL coordination contract](./otel-coordination-contract/).

## Why this exists

Raw OTEL events carry no coordination meaning. `PreToolUse, tool=Write, 784ms, note=clean` does not say what the operator wanted, whether the agent helped or stumbled, or whether working-together got better or worse. A dashboard built directly on raw events — Grafana's or our own — is unreadable because the data is meaningless.

So a **meaning layer** sits between the telemetry substrate and the UI: it rolls raw events up into **coordination episodes** the operator can understand. The readable dashboard depends entirely on this layer being good. The hard part is this model and its interpretation rules — not charts.

## The episode

An **episode** is one operator-agent working cycle: `UserPromptSubmit → the agent's actions → Stop`, within a session. Episodes group into a **coordination context** — a thread of episodes toward one intent — anchored on `coordination_context_id`.

The episode is the unit the dashboard renders. Not "231 tool calls" — one line per episode, in plain language.

## Episode fields

What the dashboard shows per episode, and where each comes from (PROBE'd against `.claude/logs/hooks.jsonl` + the hook scripts):

| Field | Meaning | Source today | Needs |
|---|---|---|---|
| **context** | which coordination thread this belongs to | — | contract: `coordination_context_id` (not emitted) |
| **intent** | what the operator was trying to do | only a coarse category in `note` (e.g. `build`) | **new capture** — a prompt summary / labeled intent |
| **agent actions** | what the agent did | `PreToolUse` `tool_name` (derivable) | structuring |
| **friction** | where it snagged | stop-audit detects, transient | contract: `friction_present` / `friction_type` |
| **corrections** | the operator had to correct the agent | stop-audit detects, transient | contract: `correction_present` |
| **memory** | did memory help or fail | **absent** (0 in telemetry) | **new capture** — instrument loom-memory MCP ops (read/write/miss) |
| **shape change** | what changed in the project | `SessionStart` snapshot/diff in `note` (derivable) | structuring (`snapshot_id` / `diff_id`) |
| **durable candidate** | produced reusable structure | observer `obs_created` in `note` (derivable) | structuring |
| **verdict** | strengthened / weakened / neutral | — | computed (below) |

## Interpretation rules (raw events → episode)

1. **Boundary.** Group events by `session_id`; segment at each `UserPromptSubmit`. An episode spans `UserPromptSubmit(end)` → the next `Stop(end)`.
2. **Agent actions.** Collect `PreToolUse` `tool_name` within the episode window.
3. **Friction / corrections.** From stop-audit detections — once the contract emits `friction_present` / `correction_present` as fields.
4. **Memory.** From instrumented loom-memory ops within the window — once captured.
5. **Shape change.** From a `SessionStart` snapshot or any diff produced in the window.
6. **Durable candidate.** `obs_created > 0`.
7. **Verdict** — the assessment that gives the episode meaning:
   - **weakened** if: a correction was present, OR friction recurred (same `friction_type` as an earlier episode in the context), OR memory missed.
   - **strengthened** if: it produced a durable candidate, OR it resolved a prior friction, OR it was clean and memory was used.
   - **neutral** otherwise.

## Rollup → coordination quality

Over episodes, per context / project / fleet: correction frequency, friction recurrence, memory-miss rate, time-to-durable-structure. Health states: **healthy / degraded / blind / unknown** — blind ≠ healthy.

## What this requires (honest)

The model is only as good as its inputs. Three gaps must close before a verdict means anything:

1. **Intent capture** — what the operator wanted. The biggest gap; without it, episodes are anonymous.
2. **Memory instrumentation** — whether memory helped or failed. Absent today.
3. **Friction/correction as structured fields** — detected but not logged.

Until these land, the dashboard shows episodes with mostly-blind verdicts — honest, and still more meaningful than raw counts.

## Open questions

1. **Intent capture:** a prompt summary (privacy/size cost?), an operator-set intent label, or LLM-derived from the turn? This is the load-bearing one.
2. **Episode boundary:** per-prompt cycle (recommended), or a larger intent-spanning context as the atomic unit?
3. **Where the interpretation layer runs:** a job that reads the telemetry store and writes episode rows, or computed on read at query time.

## Sources

- [`./otel-coordination-contract/`](./otel-coordination-contract/) — the attributes episodes are built from
- [`../canon/user-agent-coordination-reinforcement.md`](../canon/user-agent-coordination-reinforcement.md)
- PROBE'd: `.claude/logs/hooks.jsonl`; `the-loom/adapters/claude-code/loom-discipline/scripts/{_observability,pre_tool_use,user_prompt_submit,stop_audit,session_start}.py`
