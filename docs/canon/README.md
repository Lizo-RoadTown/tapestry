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
| [`user-agent-interface-observatory.md`](user-agent-interface-observatory.md) | The primary object of observation is the **user-agent interface** (not the project). The observer, architecture-diff purpose, and the dashboard design are all organized around interfaces. |
