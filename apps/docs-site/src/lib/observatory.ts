// The observatory's meaning objects — what the telemetry EXPLAINS, not the
// telemetry itself. Built from real signals (architecture diffs, observer runs);
// where the observer can't speak yet, it says so by confidence — never faked.
import type { Episode } from "./episodes";

export type ShapeChange = { cat: string; text: string };
export type ShapeMovement = { ts: string | null; sha: string; shape: string; changes: ShapeChange[] };

// View 1 — Project Shape Timeline: a narrative of how the project evolved.
export type TimelineEvent = { ts: string | null; kind: "shape" | "observer" | "friction"; title: string; detail: string[] };

function humanizeChange(c: ShapeChange): string {
  const m = /`([^`]+)`/.exec(c.text);
  const path = m ? m[1] : c.text;
  if (/^NEW/i.test(c.text)) return `${path} added`;
  if (/^REMOVED/i.test(c.text)) return `${path} removed`;
  if (/^CHANGED/i.test(c.text)) return `${path} changed`;
  return c.text;
}

export function shapeTimeline(mv: ShapeMovement[]): TimelineEvent[] {
  return mv
    .filter((m) => m.changes.length)
    .map((m) => ({
      ts: m.ts,
      kind: "shape" as const,
      title: m.changes.length === 1 ? "Architecture changed" : `Architecture changed (${m.changes.length})`,
      detail: m.changes.map(humanizeChange),
    }))
    .reverse();
}

// View 3 — Observer Feed: the observer speaks, grouped by confidence.
export type Confidence = "high" | "medium" | "low";
export type Observation = { confidence: Confidence; text: string; basis: string };

export function observerFeed(mv: ShapeMovement[], eps: Episode[]): Observation[] {
  const out: Observation[] = [];
  const recent = mv.slice(-3);
  const recentChanges = recent.reduce((a, m) => a + m.changes.length, 0);
  const obsRan = eps.length > 0; // hooks fired this/these sessions
  const durable = eps.reduce((a, e) => a + e.durableCandidates, 0);

  // High confidence — about real GAPS the observer is certain of.
  out.push({
    confidence: "high",
    text: "Memory effectiveness is unmeasured — memory reads/writes/misses are not instrumented, so whether memory is helping coordination cannot be assessed.",
    basis: "0 memory operations present in telemetry",
  });

  // Medium — real, mechanical reads of project shape.
  if (recentChanges > 0)
    out.push({ confidence: "medium", text: "Project shape is actively changing — manifests/services have been added or removed across recent snapshots.", basis: `${recentChanges} architecture change(s) in the last ${recent.length} snapshots` });
  else if (recent.length)
    out.push({ confidence: "medium", text: "Project shape has been stable across recent snapshots — no architecture changes detected.", basis: `0 changes across ${recent.length} snapshots` });

  // Low — weak signals that need evidence.
  if (durable > 0)
    out.push({ confidence: "low", text: `The observer flagged ${durable} potential reusable pattern(s) — possible emerging durable structure. Needs more evidence.`, basis: `obs_created=${durable}` });
  out.push({
    confidence: "low",
    text: "Deeper observations — intent, friction patterns, correction recurrence, memory attachment — require the observer to read the conversation transcript. That interpretation isn't wired yet, so the observer is calculating but not yet communicating those.",
    basis: "observer reads transcripts (observer.py) but intent/friction derivation is not built",
  });

  return out;
}

// View 4 — Project Shape Map: per-mechanism state, with movement.
export type Mechanism = { name: string; state: "changing" | "stable" | "active" | "emerging" | "blind"; note: string };

export function shapeMap(mv: ShapeMovement[], eps: Episode[]): Mechanism[] {
  const recentChanges = mv.slice(-3).reduce((a, m) => a + m.changes.length, 0);
  const durable = eps.reduce((a, e) => a + e.durableCandidates, 0);
  return [
    { name: "Architecture", state: recentChanges > 0 ? "changing" : "stable", note: recentChanges > 0 ? `${recentChanges} recent change(s)` : "stable across recent snapshots" },
    { name: "Observer", state: eps.length ? "active" : "blind", note: eps.length ? "running, emitting candidates" : "no runs seen" },
    { name: "Runtime", state: eps.length ? "active" : "blind", note: "hooks firing; coordination signals not yet attributed" },
    { name: "Memory", state: "blind", note: "not instrumented — help/failure unknown" },
    { name: "Upskilling", state: durable > 0 ? "emerging" : "blind", note: durable > 0 ? `${durable} candidate(s)` : "no candidates / not attributed" },
    { name: "Friction", state: "blind", note: "detected transiently; not measured over time" },
  ];
}

// View 2 — Friction Over Time: blind today (not instrumented). No fake line.
export type FrictionTrend = { instrumented: boolean; series: { period: string; friction: number }[]; note: string };
export function frictionTrend(): FrictionTrend {
  return {
    instrumented: false,
    series: [],
    note: "Not instrumented yet. This is where coordination friction over time will show whether things are getting better or worse — once the observer logs friction/correction per episode.",
  };
}
