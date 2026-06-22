# `docs/canon/`

Canonical architecture doctrine. These are binding principles — they state what Tapestry **is** and govern how it is designed.

## Authority

For the questions a canon document settles, it outranks proposals and ADRs. The order:

- **`MANIFESTO.md`** (root) — the pillars.
- **`docs/canon/`** — binding doctrine principles (this directory).
- **`docs/adr/`** — decisions made under the pillars + canon.
- **`docs/proposals/`** — the design space; becomes ADRs once accepted.

A proposal or ADR that conflicts with a canon document is non-conformant and must be revised, not the canon.

## Documents

| Document | Governs |
|---|---|
| [`user-agent-coordination-reinforcement.md`](user-agent-coordination-reinforcement.md) | Tapestry is a **user/agent support and reinforcement system**: it strengthens, stabilizes, and evolves operator-agent coordination. Memory, telemetry, observability, architecture analysis, friction analysis, and upskilling are reinforcement mechanisms; projects are environments where coordination occurs; interfaces are one manifestation. The observer, telemetry shape, docs, and dashboard organize around coordination — not around any one mechanism or the interface. |
