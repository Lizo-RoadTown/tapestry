import type { APIRoute } from "astro";
import { buildEpisodes, summarize, type HookEvent, type Episode } from "../../lib/episodes";
import { shapeTimeline, observerFeed, shapeMap, frictionTrend, type ShapeMovement } from "../../lib/observatory";
import { buildVariables } from "../../lib/cockpit";
import sample from "../../data/events-sample.json";
import shapeMovementRaw from "../../data/shape-movement.json";

const shapeMovement = shapeMovementRaw as unknown as ShapeMovement[];

export const prerender = false;

/** Raw hook events — central live store if wired, else dev hooks, else snapshot. */
async function loadEvents(): Promise<{ events: HookEvent[]; source: string }> {
  const url = import.meta.env.COORDINATION_EVENTS_URL || process.env.COORDINATION_EVENTS_URL;
  if (url) {
    try {
      const r = await fetch(url, { headers: { accept: "application/json" } });
      if (r.ok) return { events: (await r.json()) as HookEvent[], source: "live:central-store" };
    } catch {}
  }
  try {
    const fs = await import("node:fs");
    const os = await import("node:os");
    const path = await import("node:path");
    const p = path.join(os.homedir(), ".claude", "logs", "hooks.jsonl");
    if (fs.existsSync(p)) {
      const evs: HookEvent[] = [];
      for (const ln of fs.readFileSync(p, "utf-8").split("\n")) {
        const s = ln.trim();
        if (!s) continue;
        try { const e = JSON.parse(s); if (e.phase === "end") evs.push(e); } catch {}
      }
      if (evs.length) return { events: evs.slice(-1500), source: "dev:hooks.jsonl" };
    }
  } catch {}
  return { events: sample as HookEvent[], source: "snapshot:events-sample" };
}

// Trends over time. Real where derivable; the meaning trends (friction,
// correction, memory) are blind until the observer/contract land — labeled, not faked.
function trends(eps: Episode[]) {
  const byDay = new Map<string, { episodes: number; durable: number }>();
  for (const e of eps) {
    const day = (e.start || "").slice(0, 10) || "—";
    const r = byDay.get(day) || { episodes: 0, durable: 0 };
    r.episodes += 1;
    r.durable += e.durableCandidates;
    byDay.set(day, r);
  }
  const series = [...byDay.entries()].sort().map(([day, v]) => ({ day, ...v }));
  return {
    series, // real: episodes + durable candidates per day
    blind: ["friction recurrence", "correction frequency", "memory misses"], // not instrumented
  };
}

export const GET: APIRoute = async () => {
  const { events, source } = await loadEvents();
  const episodes = buildEpisodes(events);
  const summary = summarize(episodes);
  const cockpit = buildVariables(shapeMovement, episodes);
  const body = {
    source,
    summary,
    // cockpit: telemetry as selectable variables over time
    cockpit,
    // the meaning objects — the observatory's real content
    timeline: shapeTimeline(shapeMovement),
    observer: observerFeed(shapeMovement, episodes),
    shapeMap: shapeMap(shapeMovement, episodes),
    friction: frictionTrend(),
    // supporting evidence (demoted)
    trends: trends(episodes),
    episodes,
  };
  return new Response(JSON.stringify(body, null, 0), {
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
};
