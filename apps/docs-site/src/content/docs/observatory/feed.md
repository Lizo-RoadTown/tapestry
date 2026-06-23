---
title: The Observatory feed
description: The data contract behind the console — the /api/episodes.json endpoint, the sources it reads from, the event shape a live source must provide, and how to point the console at a central coordination store.
---

The console reads from one endpoint: **`GET /api/episodes.json`**. This page documents what it returns, where it reads from, and how to supply a live source.

## Sources

The endpoint resolves its source in order:

1. `COORDINATION_EVENTS_URL` — a central store (live, across sessions)
2. `~/.claude/logs/hooks.jsonl` — this machine's hooks (local dev only)
3. a bundled sample (deployed fallback)

To run the console on live data, set `COORDINATION_EVENTS_URL` in the Vercel project to a URL that returns the hook events as JSON.

## Event shape

`COORDINATION_EVENTS_URL` returns a JSON array of hook events:

```ts
type HookEvent = {
  ts: string;          // ISO timestamp
  hook: string;        // "UserPromptSubmit" | "PreToolUse" | "Stop" | "SessionStart"
  note?: string;       // free text, or typed attributes as the contract adds them
  tool_name?: string;  // on PreToolUse
  action?: string;
  session_id?: string;
  project_id?: string;
};
```

The console rolls these into coordination episodes and derives the variables. The [OTel coordination contract](/reference/otel-coordination-contract/) defines the typed attributes (`friction_present`, `memory_miss`, `coordination_context_id`, …) the instrumented variables read from.

## Response shape

```ts
{
  source: string;            // which source answered
  cockpit: {
    days: string[];          // the time axis
    variables: Variable[];   // selectable variables over days
  };
  timeline: TimelineEvent[]; // project-shape evolution
  observer: Observation[];   // observer findings, by confidence
  shapeMap: Mechanism[];     // per-part state
  friction: { instrumented: boolean; series; note };
  episodes: Episode[];       // working cycles (drill-down)
  summary: { ... };          // counts (shown in the raw tab)
}
```

A `Variable` is `{ id, label, lens, kind: "real" | "blind", unit, series }`. A `blind` variable has a null series.

## Supply live data

1. Store the hook events somewhere the console can read (a table the discipline plugin writes to, alongside its OTLP export).
2. Expose the recent events as JSON at a URL, in the `HookEvent[]` shape above.
3. Set `COORDINATION_EVENTS_URL` to that URL in the Vercel project and redeploy.
