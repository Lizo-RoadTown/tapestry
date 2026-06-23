// The meaning layer: turn raw hook events into coordination episodes.
// Per docs/reference/coordination-episode-model.md. An episode is one
// operator-agent working cycle (UserPromptSubmit -> agent actions -> Stop).
// Honest: fields we can't derive yet are marked uncertain/blind, never faked.

export type HookEvent = {
  ts?: string;
  hook?: string;
  note?: string;
  tool_name?: string;
  action?: string;
  session_id?: string;
  project_id?: string;
};

export type Verdict = "strengthened" | "weakened" | "neutral" | "unknown";

export type Episode = {
  session: string;
  project: string;
  start: string | null;
  end: string | null;
  durationMs: number | null;
  intent: string; // coarse note today; observer-derived later
  intentCertain: boolean; // false until the observer derives it
  tools: { name: string; count: number }[];
  toolCalls: number;
  snapshot: string | null; // shape change (architecture snapshot)
  durableCandidates: number; // observer obs_created
  memory: "blind"; // not instrumented yet
  friction: "blind"; // detected transiently, not logged yet
  verdict: Verdict;
};

function parseObsCreated(note: string): number {
  const m = /obs_created=(\d+)/.exec(note);
  return m ? parseInt(m[1], 10) : 0;
}

export function buildEpisodes(events: HookEvent[]): Episode[] {
  const ended = events.filter((e) => e && e.hook).slice();
  ended.sort((a, b) => (a.ts || "").localeCompare(b.ts || ""));

  const eps: Episode[] = [];
  let cur: Episode | null = null;
  const toolMap = new Map<string, number>();

  const flush = () => {
    if (!cur) return;
    cur.tools = [...toolMap.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
    cur.toolCalls = [...toolMap.values()].reduce((a, b) => a + b, 0);
    // Verdict: honest. Memory/friction are blind, so we cannot truly assess.
    // The one positive we can see today: a durable candidate was produced.
    cur.verdict = cur.durableCandidates > 0 ? "strengthened" : "unknown";
    eps.push(cur);
    cur = null;
    toolMap.clear();
  };

  for (const e of ended) {
    const h = e.hook;
    const note = e.note || "";
    if (h === "UserPromptSubmit") {
      flush();
      cur = {
        session: (e.session_id || "").slice(0, 8),
        project: e.project_id || "—",
        start: e.ts || null,
        end: null,
        durationMs: null,
        intent: note || "(none)",
        intentCertain: false,
        tools: [],
        toolCalls: 0,
        snapshot: null,
        durableCandidates: 0,
        memory: "blind",
        friction: "blind",
        verdict: "unknown",
      };
    } else if (h === "PreToolUse" && cur) {
      const t = e.tool_name || "?";
      toolMap.set(t, (toolMap.get(t) || 0) + 1);
    } else if (h === "SessionStart" && cur && note.includes("snapshot=")) {
      cur.snapshot = note.split("snapshot=")[1]?.split(";")[0] || null;
    } else if (h === "Stop" && cur) {
      cur.end = e.ts || null;
      cur.durableCandidates = parseObsCreated(note);
      if (cur.start && cur.end) cur.durationMs = Date.parse(cur.end) - Date.parse(cur.start);
      flush();
    }
  }
  flush();
  return eps.reverse(); // most recent first
}

export type FleetSummary = {
  episodes: number;
  sessions: number;
  projects: number;
  withDurable: number;
  toolCalls: number;
  // honest coverage of the meaning layer
  intentBlind: number; // all, until the observer derives intent
  memoryBlind: number;
  frictionBlind: number;
};

export function summarize(eps: Episode[]): FleetSummary {
  return {
    episodes: eps.length,
    sessions: new Set(eps.map((e) => e.session)).size,
    projects: new Set(eps.map((e) => e.project)).size,
    withDurable: eps.filter((e) => e.durableCandidates > 0).length,
    toolCalls: eps.reduce((a, e) => a + e.toolCalls, 0),
    intentBlind: eps.filter((e) => !e.intentCertain).length,
    memoryBlind: eps.length,
    frictionBlind: eps.length,
  };
}
