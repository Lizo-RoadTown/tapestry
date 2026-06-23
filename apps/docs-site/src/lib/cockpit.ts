// The cockpit: telemetry modeled as SELECTABLE VARIABLES over time, plus an
// interpretation engine that explains what overlaying two variables can expose.
// Per the variable-overlay-cockpit direction. Honest: variables we don't
// instrument yet are kind:"blind" with null series — selectable, but the view
// says the relationship can't be measured, never faked.
import type { Episode } from "./episodes";
import type { ShapeMovement } from "./observatory";

export type Lens = "Coordination" | "Architecture" | "Memory" | "Friction" | "Observer" | "Upskilling";
export type Variable = {
  id: string;
  label: string;
  lens: Lens;
  kind: "real" | "blind";
  unit: string;
  series: (number | null)[]; // aligned to `days`
};

function dayOf(iso: string | null): string {
  return (iso || "").slice(0, 10);
}

export function buildVariables(mv: ShapeMovement[], eps: Episode[]): { days: string[]; variables: Variable[] } {
  const daySet = new Set<string>();
  for (const e of eps) if (e.start) daySet.add(dayOf(e.start));
  for (const m of mv) if (m.ts) daySet.add(dayOf(m.ts));
  const days = [...daySet].filter(Boolean).sort();
  const idx = new Map(days.map((d, i) => [d, i]));

  const zero = () => days.map(() => 0);
  const archChanges = zero(), episodes = zero(), tools = zero(), candidates = zero();
  for (const m of mv) {
    const i = idx.get(dayOf(m.ts));
    if (i != null) archChanges[i] += m.changes.length;
  }
  for (const e of eps) {
    const i = idx.get(dayOf(e.start));
    if (i == null) continue;
    episodes[i] += 1;
    tools[i] += e.toolCalls;
    candidates[i] += e.durableCandidates;
  }
  const blind = () => days.map(() => null);

  const variables: Variable[] = [
    { id: "time", label: "Time", lens: "Coordination", kind: "real", unit: "day", series: days.map((_, i) => i) },
    { id: "arch_changes", label: "Architecture changes", lens: "Architecture", kind: "real", unit: "changes/day", series: archChanges },
    { id: "episodes", label: "Working episodes", lens: "Coordination", kind: "real", unit: "episodes/day", series: episodes },
    { id: "tool_activity", label: "Tool activity", lens: "Coordination", kind: "real", unit: "calls/day", series: tools },
    { id: "observer_candidates", label: "Observer candidates", lens: "Upskilling", kind: "real", unit: "candidates/day", series: candidates },
    { id: "friction", label: "Friction recurrence", lens: "Friction", kind: "blind", unit: "events/day", series: blind() },
    { id: "memory_miss", label: "Memory misses", lens: "Memory", kind: "blind", unit: "misses/day", series: blind() },
    { id: "corrections", label: "Correction frequency", lens: "Coordination", kind: "blind", unit: "corrections/day", series: blind() },
  ];
  return { days, variables };
}

// Recommend a visualization for the selected x/y/overlay.
export function recommendChart(yId: string, overlayId: string | null): { type: string; why: string } {
  if (overlayId) return { type: "line+overlay", why: "two variables over time — overlay them to look for a relationship between their trends" };
  return { type: "line", why: "one variable over time — a trend" };
}

// The intelligence layer: explain what overlaying these variables can expose.
export type Interp = { looking: string; why: string; patterns: string[]; finding: string; blind: string[] };

const LABEL: Record<string, string> = {
  arch_changes: "architecture changes", episodes: "working episodes", tool_activity: "tool activity",
  observer_candidates: "observer candidates", friction: "friction recurrence", memory_miss: "memory misses", corrections: "correction frequency", time: "time",
};

export function interpret(yId: string, overlayId: string | null, vars: Variable[]): Interp {
  const y = vars.find((v) => v.id === yId)!;
  const o = overlayId ? vars.find((v) => v.id === overlayId) : null;
  const blind: string[] = [y, o].filter((v): v is Variable => !!v && v.kind === "blind").map((v) => v.label);

  // Curated, meaningful pairings.
  const key = [yId, overlayId].filter(Boolean).sort().join("+");
  const curated: Record<string, Partial<Interp>> = {
    "arch_changes+friction": {
      why: "Tests whether project-shape changes are followed by coordination friction.",
      patterns: ["architecture churn causing coordination degradation", "friction dropping after durable structure forms"],
    },
    "friction+memory_miss": {
      why: "Tests whether missing memory increases repeated correction / friction.",
      patterns: ["memory misses preceding friction spikes", "friction dampened when memory recall succeeds"],
    },
    "arch_changes+memory_miss": {
      why: "Tests whether structural changes are followed by memory misses (the system forgetting what just changed).",
      patterns: ["memory misses following structural changes", "observer confidence lagging behind project changes"],
    },
    "episodes+observer_candidates": {
      why: "Tests whether more working activity yields more durable structure.",
      patterns: ["durable structure forming after sustained work", "candidate rate flat despite activity (loop not closing)"],
    },
  };
  const c = curated[key] || {};

  const looking = o ? `${LABEL[yId]} over time, overlaid with ${LABEL[overlayId!]}` : `${LABEL[yId]} over time`;
  const why = c.why || (o ? `Tests whether ${LABEL[yId]} and ${LABEL[overlayId!]} move together over time.` : `Shows how ${LABEL[yId]} is trending.`);
  const patterns = c.patterns || (o ? [`${LABEL[yId]} rising/falling with ${LABEL[overlayId!]}`, "no relationship (the two move independently)"] : [`${LABEL[yId]} increasing or decreasing over time`]);
  let finding: string;
  if (blind.length === 2) finding = "Neither variable is instrumented yet — this relationship cannot be measured. It is shown so you can see what is missing.";
  else if (blind.length === 1) finding = `${blind[0]} is not instrumented yet, so the relationship can't be measured. The other variable is real and plotted.`;
  else finding = "Both variables are real and plotted. The observer does not yet interpret the relationship — that needs transcript-derived signals.";

  return { looking, why, patterns, finding, blind };
}
