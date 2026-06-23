/**
 * Observability dashboard — Phase 1.
 *
 * Embeds Grafana Cloud panels showing live hook events from the
 * tapestry-discipline plugin. Auth is currently anonymous Grafana panel sharing
 * (Phase 1 open question — tighten to signed-URL embedding before any
 * non-personal use).
 *
 * The GRAFANA_DASHBOARD_URL env var is the Grafana Cloud dashboard URL
 * configured for public sharing (or "panel embed URL" for individual panels).
 * Configure in Vercel project env settings; for local dev set in
 * apps/web-dashboard/.env.local.
 */

const RAW_GRAFANA_DASHBOARD_URL = process.env.NEXT_PUBLIC_GRAFANA_DASHBOARD_URL;

/**
 * Normalize a Grafana embed URL so the iframe always loads, even if the
 * env-var value was pasted with `&kiosk=tv` instead of `?kiosk=tv` (a real
 * paste mistake — query string params with `&` and no leading `?` produce
 * `404` from Grafana). The first `&`-prefixed param becomes `?`; the rest
 * stay `&`. Idempotent on a well-formed URL.
 */
function normalizeGrafanaUrl(raw: string | undefined): string | undefined {
  if (!raw) return raw;
  if (raw.includes("?")) return raw; // already well-formed
  return raw.replace(/&/, "?");
}

const GRAFANA_DASHBOARD_URL = normalizeGrafanaUrl(RAW_GRAFANA_DASHBOARD_URL);

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold">Observability</h2>
        <p className="text-sm text-loom-500 mt-1">
          Live hook activity from your Claude Code sessions, telemetry from
          loom services, and recognized architecture (when available).
        </p>
      </header>

      {GRAFANA_DASHBOARD_URL ? (
        <section className="border border-loom-700 rounded overflow-hidden bg-white">
          <iframe
            src={GRAFANA_DASHBOARD_URL}
            className="w-full"
            style={{ height: "70vh", minHeight: "600px" }}
            title="Grafana Cloud dashboard"
          />
        </section>
      ) : (
        <section className="border border-loom-700 rounded p-6 bg-loom-900/50 text-sm text-loom-100">
          <p className="font-semibold mb-2">Grafana panel not configured yet.</p>
          <p className="text-loom-500">
            Set the <code className="text-loom-100">NEXT_PUBLIC_GRAFANA_DASHBOARD_URL</code>{" "}
            environment variable in Vercel (or in{" "}
            <code className="text-loom-100">apps/web-dashboard/.env.local</code>{" "}
            for local dev) pointing at your Grafana Cloud dashboard or panel
            embed URL.
          </p>
          <p className="text-loom-500 mt-2">
            Until the tapestry-discipline plugin starts emitting telemetry (Phase
            1B), the panel will appear empty even when configured.
          </p>
        </section>
      )}

      <section className="text-xs text-loom-500 border-t border-loom-700 pt-4">
        <p>
          Source: Grafana Cloud LGTM stack (Loki for logs, Tempo for traces,
          Mimir for metrics). Telemetry flows: discipline plugin → Grafana
          Cloud OTLP. Phase 4 adds the loom-telemetry-ingestion enrichment
          layer between them.
        </p>
      </section>
    </div>
  );
}
