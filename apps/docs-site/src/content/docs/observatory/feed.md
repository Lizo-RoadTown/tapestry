---
title: The Observatory feed
description: The data contract behind the console — the /api/episodes.json endpoint, where it reads from, the event shape a live source must provide, and how to wire a central coordination store into it so the console goes live across sessions.
---

The console reads everything from one endpoint: **`GET /api/episodes.json`**. This page is the contract — what it returns, where it reads from, and how to connect a live source.

## Where the feed reads from

The endpoint resolves its source in priority order, so the console is never empty:

```text
1. COORDINATION_EVENTS_URL  — a central store (live, across sessions)
2. ~/.claude/logs/hooks.jsonl  — this machine's hooks (local dev only)
3. bundled real snapshot  — a sanitized sample (deployed fallback)
```

To take the console **live across all sessions**, set the env var `COORDINATION_EVENTS_URL` (in the Vercel project) to a URL that returns the hook event array as JSON. That's the single connection point — everything else is computed from it.

## The event shape a source must return

`COORDINATION_EVENTS_URL` must return a JSON array of hook events. Each event is what the discipline plugin already emits per hook:

```ts
type HookEvent = {
  ts: string;          // ISO timestamp
  hook: string;        // "UserPromptSubmit" | "PreToolUse" | "Stop" | "SessionStart"
  note?: string;       // free-text today; structured attributes as the contract lands
  tool_name?: string;  // on PreToolUse
  action?: string;
  session_id?: string;
  project_id?: string;
};
```

The console rolls these into coordination episodes and derives the variables. As the [OTel coordination contract](/reference/otel-coordination-contract/) enriches events with typed attributes (`friction_present`, `memory_miss`, `coordination_context_id`, …), the blind variables become real with no console change.

## What the endpoint returns

```ts
{
  source: string;                 // which source answered (above)
  summary: {...};                 // counts (evidence, shown only in the raw tab)
  cockpit: {
    days: string[];               // the time axis
    variables: Variable[];        // selectable variables, real or blind, series over days
  };
  timeline: TimelineEvent[];      // narrative project-shape evolution
  observer: Observation[];        // observer findings, grouped by confidence
  shapeMap: Mechanism[];          // per-part state (changing/active/blind/…)
  friction: { instrumented: boolean; series; note };
  episodes: Episode[];            // the working cycles (drill-down)
}
```

A `Variable` carries `{ id, label, lens, kind: "real" | "blind", unit, series }`. Blind variables have a null series and are rendered as *not instrumented*.

## Wiring checklist (for connecting live data)

1. Stand up a store the hooks write to (a table the discipline plugin POSTs each event into, alongside the existing OTLP → Grafana Cloud push).
2. Expose the recent events as JSON at a URL (the `HookEvent[]` shape above).
3. Set `COORDINATION_EVENTS_URL` to that URL in the Vercel project; redeploy.
4. The console flips from snapshot to live; episodes and the real variables update per session.

This is the seam where the Render / Vercel / OTel wiring meets the console: the same coordination telemetry that flows to Grafana Cloud is also made available to this feed, and the console interprets it.
