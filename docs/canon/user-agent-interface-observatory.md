# Canon: User-Agent Interface Observatory

## Status

Canonical architecture principle. Binding. Governs the observer, the architecture-diff purpose, and the dashboard design. Where this canon and a proposal or feature note disagree, this canon wins.

**Date:** 2026-06-22
**Authors:** Liz (canon), agent-relayed.

## Core Claim

Tapestry does not primarily observe projects for their own sake.

Tapestry observes the **interfaces between the operator and agents**.

Projects matter because each project creates different surfaces where the operator and agents interact. Those surfaces have different shapes, different memory needs, different friction patterns, different runtime behavior, and different failure modes.

The observer tracks project shape because project shape determines where user-agent interaction happens and where friction appears.

## Primary Object

The primary object of observation is the **user-agent interface**.

A user-agent interface is a recurring coordination surface where:

* the operator expresses intent
* an agent interprets or acts on that intent
* project structure constrains or enables the action
* memory is used, missed, written, or corrected
* friction appears or is resolved
* repeated patterns may become durable structure

## Relationship to Projects

A project may contain many user-agent interfaces.

Each interface may differ by:

* project area
* agent role
* operator task
* architecture context
* memory dependency
* runtime path
* friction type
* correction pattern
* upskilling potential

Therefore, project telemetry alone is insufficient. Tapestry must capture **interface telemetry**.

## Why Architecture Diffs Matter

Architecture diff reports are not only for tracking code or system structure.

They exist because changes in architecture change the available user-agent interfaces.

When architecture changes, interfaces may:

* appear
* disappear
* split
* merge
* become unstable
* become stable
* create new friction
* resolve old friction
* expose missing memory
* produce candidates for skills, policy, or durable structure

The observer tracks architecture so it can understand how interface conditions are changing.

## Dashboard Requirement

The UI must represent projects as containers of user-agent interfaces, not merely as repositories, services, or telemetry streams.

For each project, the dashboard should identify and track:

* active interfaces
* emerging interfaces
* changed interfaces
* degraded interfaces
* stable interfaces
* friction at each interface
* memory dependencies at each interface
* agent behavior at each interface
* relevant architecture changes
* candidate skills or policies produced by repeated interaction

## Required UI Model

The dashboard should support this hierarchy:

```text
Operator
  ↓
User-Agent Interfaces
  ↓
Projects
  ↓
Architecture / Runtime / Memory / Observer / Friction / Upskilling
```

or, inside each project:

```text
Project
  ├── Interface
  │     ├── purpose
  │     ├── agent role
  │     ├── operator expectation
  │     ├── architecture context
  │     ├── memory dependencies
  │     ├── runtime signals
  │     ├── friction signals
  │     ├── correction history
  │     └── candidate durable structure
```

## Non-Goal

This is not a generic admin dashboard.

This is not only infrastructure telemetry.

This is not only project monitoring.

This is not only memory tracking.

This is a cross-project observatory for identifying, tracking, and stabilizing the interfaces where operator intent and agent behavior meet.

## Canonical Summary

Tapestry observes project shape because project shape affects user-agent interfaces. The durable structure being built is the coordination layer between operator and agent. Every project expresses that layer differently, so the UI must identify the interfaces inside each project and track their telemetry, friction, memory dependencies, architectural context, and evolution over time.

## Binding instruction (how agents must treat this canon)

> Treat this as canon. Do not reduce the dashboard to project telemetry, admin monitoring, or generic observability. The dashboard must model user-agent interfaces as first-class objects. Architecture diffs, runtime telemetry, memory events, friction signals, and upskilling candidates should be organized around those interfaces.

Any design that organizes the dashboard around projects-as-primary, services, or telemetry streams — rather than around user-agent interfaces — is non-conformant with this canon and must be revised.

## Implications already in motion

- The **Project Observatory console** proposal ([`../proposals/2026-06-22-project-observatory-console.md`](../proposals/2026-06-22-project-observatory-console.md)) is governed by this canon. Its layer model (fleet / shape / runtime / memory / friction / observer / upskilling / policy) is correct as a set of **signal dimensions**, but the canon supersedes its project-as-primary framing: those dimensions must be organized **per user-agent interface**, with projects as containers. The proposal is being realigned to this hierarchy.
- The **observer** ([`../adr/0001-observer-topology.md`](../adr/0001-observer-topology.md)) tracks architecture/shape drift as a means to detecting interface change — not as an end. The "available now / planned / missing" honesty (the observer is a static shape-drift scanner today) still holds: interface telemetry is largely **missing instrumentation** and must be labeled as such, not faked.

## Sources

- The canon text relayed by the operator, 2026-06-22 (verbatim above through "Canonical Summary" + the Binding instruction).
- [`../proposals/2026-06-22-project-observatory-console.md`](../proposals/2026-06-22-project-observatory-console.md) — the dashboard design this canon governs.
- [`../adr/0001-observer-topology.md`](../adr/0001-observer-topology.md) — observer roles (self-observer = static shape-drift; runtime-observer → `services/project-observatory/`).
- [`../proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md`](../proposals/2026-06-18-runtime-observation-deferred-to-tapestry.md) — what runtime/interface signal does not exist yet.
- [`../architecture/UMBRELLA.md`](../architecture/UMBRELLA.md) · [`../../MANIFESTO.md`](../../MANIFESTO.md) — the surrounding canonical model.
