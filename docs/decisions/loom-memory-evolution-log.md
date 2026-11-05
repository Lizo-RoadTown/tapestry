# loom-memory evolution — decision log

A running log of the choices made while executing
[`docs/plans/2026-11-05-loom-memory-evolution-systematic-plan.md`](../plans/2026-11-05-loom-memory-evolution-systematic-plan.md).
One entry per decision, newest at the bottom. Big structural choices also get a formal ADR under
[`docs/adr/`](../adr/) (proposed: **0006** schema enrichment / supersession, **0007** store move to
Supabase, **0008** self-observer into the DB, optional **0009** retrieval adopt); this log is the
fast index over them + the small decisions that don't warrant an ADR.

## Entry template

```
### DL-NNN — <one-line decision>   (YYYY-MM-DD, <machine/who>)
- **Context:** why this came up; the situation + pressure.
- **Options considered:** A / B / C (one line each).
- **Decision:** the choice, plainly.
- **Consequences:** what it makes easier / harder / locks in. ADR: <0006…> or "none".
- **Status:** proposed | accepted | superseded by DL-MMM.
```

## Open decisions awaiting the operator (from plan §5)

These are logged as PENDING; fill in a DL entry when each is decided.

- **D-B1** — Spend ~$25/mo for Supabase Pro (gets DB visualization + pg_cron-in-DB)? _(biggest unblocker)_
- **D-B2** — Auth model on Supabase: keep app-level JWT/self-host auth at the MCP layer (connect as service role) vs adopt Supabase Auth/RLS? _(don't half-adopt both)_
- **D-A1** — Bi-temporal shape: typed columns (`valid_from`/`invalid_at`/`superseded_by`) — recommended — vs `extra` JSONB?
- **D-E1** — Retrieval: A/B hybrid BM25+vector+rerank before adopting any memory framework?
- **GATE 0** — Verify whether Render `loom-postgres` exposes `pg_cron`/`pg_net` (the premise behind WS-B/WS-C). Free 2-min check.
- _(+ the remaining plan §5 items as they come up)_

## Log

_(no decisions recorded yet — this is the skeleton; first real entry lands when GATE 0 is run or D-B1 is decided on the other machine.)_
