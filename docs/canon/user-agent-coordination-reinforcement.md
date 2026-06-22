# Canon: User-Agent Coordination Reinforcement

## Status

Canonical architecture principle. Binding. Governs what Tapestry is, what the observer is for, how telemetry is shaped, and how the documentation and dashboard are organized. Where this canon and a proposal, ADR, or feature note disagree, this canon wins.

**Date:** 2026-06-22
**Authors:** Liz (canon), agent-relayed.
**Supersedes:** the earlier "user-agent interface as the primary object" framing (the prior draft of this file). That framing was a distortion — it made Tapestry look like an interface observatory and made the mechanisms look secondary. Corrected here. See `feedback_canon_correction_coordination_reinforcement_not_interface_primary_2026_06_22`.

## Core claim

Tapestry is a **user/agent support and reinforcement system**.

Its purpose is to strengthen, stabilize, and evolve **coordination between the operator and agents** over time.

The system uses many reinforcement mechanisms — memory, telemetry, observability, architecture analysis, runtime analysis, friction analysis, correction analysis, upskilling, policy, skill formation. **None of these mechanisms alone defines the system.** They are mechanisms used to reinforce coordination.

## Relationship to projects

Projects are not merely containers. Projects are **environments where coordination occurs**. Different projects create different conditions for coordination, and expose different interfaces, memory requirements, architectural constraints, friction patterns, correction patterns, and learning opportunities.

The observer tracks project shape because **project shape influences the effectiveness of user-agent coordination**.

## Relationship to interfaces

Interfaces are important. Interfaces are **not** the primary object. An interface is **one observable manifestation of coordination**.

The observer may track interface creation, evolution, degradation, and stabilization — but interfaces exist *within* the larger coordination system, alongside the other mechanisms.

## Relationship to telemetry

Telemetry is not infrastructure telemetry alone. Telemetry exists to help understand the **health and evolution of the coordination system**: memory effectiveness, architecture changes, friction emergence, correction frequency, skill reuse, observer findings, runtime behavior. These signals are useful because they describe **coordination quality**.

The telemetry model therefore is not `project → service → trace → span`. It carries coordination context, anchored on a `coordination_context_id` (not `interface_id`); interfaces, workflows, projects, memory, runtime, architecture diffs, and observer findings all attach to that anchor. Every significant event should answer: *did this action strengthen, weaken, or reveal something about user/agent coordination?* (OTEL attribute shape relayed to the telemetry owner: `tapestry_to_loom_agent_otel_coordination_context_shape_2026_06_22`.)

## Documentation and dashboard direction

Do not organize the documentation or the dashboard around projects, interfaces, memory, telemetry, or the observer **alone**.

Organize around **User-Agent Coordination Reinforcement**: describe memory, telemetry, architecture, observability, friction analysis, correction analysis, and upskilling as **reinforcement mechanisms** that strengthen coordination over time. Projects appear as the environments coordination happens in; interfaces appear as one manifestation of coordination, attached to a coordination context — not as the root.

## Canonical statement

Tapestry is a user/agent support and reinforcement system. Projects, interfaces, memory, telemetry, observability, architecture analysis, friction analysis, and upskilling are mechanisms used to **observe, strengthen, stabilize, and evolve coordination between the operator and agents**.

## Binding instruction (how agents must treat this canon)

> Treat this as canon. Do not present Tapestry as an interface observatory, a project monitor, a memory tracker, or generic infrastructure telemetry. Present it as a system that reinforces operator-agent coordination, and present memory, telemetry, observability, architecture analysis, friction analysis, and upskilling as the mechanisms that do the reinforcing. Anchor telemetry and the dashboard on coordination context, not on interface identity.

Any design that makes one mechanism (or the interface) the primary object — rather than coordination itself — is non-conformant with this canon and must be revised.

## Implications already in motion

- The **Observatory dashboard** ([`../proposals/2026-06-22-project-observatory-console.md`](../proposals/2026-06-22-project-observatory-console.md), UI at `apps/docs-site/src/pages/observatory.astro`) is governed by this canon. Its mechanism set (memory / telemetry / architecture / observer / friction / upskilling / policy) is correct as a set of **reinforcement mechanisms**; it must be organized around coordination (per project environment, attached to coordination context), with interfaces shown as one manifestation — not as the first-class root. Both are being realigned.
- The **observer** ([`../adr/0001-observer-topology.md`](../adr/0001-observer-topology.md)) tracks architecture/shape as a means to understanding coordination effectiveness. The "available now / planned / missing" honesty still holds: most coordination-quality signal is not instrumented yet and must be labeled, not faked.

## Sources

- The canon text relayed by the operator, 2026-06-22 (Core claim → Canonical statement + Binding instruction).
- [`../proposals/2026-06-22-project-observatory-console.md`](../proposals/2026-06-22-project-observatory-console.md) — the dashboard design this canon governs.
- [`../adr/0001-observer-topology.md`](../adr/0001-observer-topology.md) — observer roles.
- [`../proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md`](../proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md) — what coordination-quality signal does not exist yet.
- [`../architecture/UMBRELLA.md`](../architecture/UMBRELLA.md) · [`../../MANIFESTO.md`](../../MANIFESTO.md) — the surrounding canonical model.
