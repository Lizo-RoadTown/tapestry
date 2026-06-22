import type { APIRoute } from "astro";
import { buildEpisodes, summarize, type HookEvent } from "../../lib/episodes";
import sample from "../../data/events-sample.json";

export const prerender = false;

/**
 * Coordination episodes feed.
 *
 * Data source, in priority order — the central live feed is the goal; the
 * bundled real snapshot is the fallback so the console is never empty:
 *   1. COORDINATION_EVENTS_URL  — the central store the hooks wire into (live)
 *   2. local .claude/logs/hooks.jsonl  — when running on a dev machine
 *   3. bundled events-sample.json  — a real snapshot, sanitized (deployable)
 */
async function loadEvents(): Promise<{ events: HookEvent[]; source: string }> {
  // 1. central live store (set this env once the hooks POST to it)
  const url = import.meta.env.COORDINATION_EVENTS_URL || process.env.COORDINATION_EVENTS_URL;
  if (url) {
    try {
      const r = await fetch(url, { headers: { accept: "application/json" } });
      if (r.ok) return { events: (await r.json()) as HookEvent[], source: "live:central-store" };
    } catch {
      /* fall through */
    }
  }
  // 2. local hook log (dev only — node fs, not present on Vercel)
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
        try {
          const e = JSON.parse(s);
          if (e.phase === "end") evs.push(e);
        } catch {
          /* skip */
        }
      }
      if (evs.length) return { events: evs.slice(-1500), source: "dev:hooks.jsonl" };
    }
  } catch {
    /* fall through */
  }
  // 3. bundled real snapshot
  return { events: sample as HookEvent[], source: "snapshot:events-sample" };
}

export const GET: APIRoute = async () => {
  const { events, source } = await loadEvents();
  const episodes = buildEpisodes(events);
  const summary = summarize(episodes);
  return new Response(JSON.stringify({ source, summary, episodes }, null, 0), {
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
};
