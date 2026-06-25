/**
 * Landing — the upskilling dashboard overview.
 *
 * Two things only:
 *   1. "Is there work waiting?" → Needs review prompt → /candidates
 *   2. "Did my last clicks register?" → recent decisions list (time / kind /
 *      reason), for verification — NOT for action (actions live on /candidates)
 *
 * Everything else (library size, kind grid, total decision count) was theater
 * shipped in PR #19 and stripped per
 * loom-memory feedback_no_dashboard_theater_real_work_only +
 * feedback_i_shipped_dashboard_theater_step_4.
 *
 * Server component; fetches at request time on Vercel edge.
 *
 * Dual-mode:
 *   - Self-host: no Authorization header → backend auth_bridge falls
 *     through to SELF_HOST_TENANT_ID → RLS scopes to Liz's tenant.
 *   - Hosted-multitenant: JWT minting in Next.js layer is step 5+
 *     follow-up. Today the dashboard is for the self-host operator.
 */

const REGISTRY_URL =
  process.env.NEXT_PUBLIC_LOOM_ARCHITECTURE_REGISTRY_URL ??
  "https://your-architecture-registry.example.com";

const POLICY_URL =
  process.env.NEXT_PUBLIC_LOOM_POLICY_URL ?? "https://your-policy-service.example.com";

type CandidateStatus =
  | "draft"
  | "observed"
  | "recurring"
  | "stable"
  | "promotion_requested"
  | "promoted"
  | "rejected"
  | "kind_not_yet_handled";

type Candidate = {
  id: string;
  status: CandidateStatus;
};

type DecisionKind = "approve" | "reject" | "hold" | "demote";

type Decision = {
  id: string;
  candidate_id: string;
  decision_kind: DecisionKind;
  target_status: CandidateStatus | null;
  reason: string;
  decided_by: string;
  decided_at: number;
};

const ACTIONABLE_STATUSES: CandidateStatus[] = [
  "draft",
  "observed",
  "recurring",
  "stable",
  "promotion_requested",
];

async function fetchNeedsReviewCount(): Promise<number | null> {
  try {
    const res = await fetch(`${REGISTRY_URL}/candidates?limit=500`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { candidates: Candidate[] };
    return data.candidates.filter((c) => ACTIONABLE_STATUSES.includes(c.status))
      .length;
  } catch {
    return null;
  }
}

async function fetchRecentDecisions(): Promise<Decision[]> {
  try {
    const res = await fetch(`${POLICY_URL}/decisions?limit=10`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { decisions: Decision[] };
    return data.decisions;
  } catch {
    return [];
  }
}

function formatRelativeTime(epoch: number): string {
  const secondsAgo = Math.floor(Date.now() / 1000 - epoch);
  if (secondsAgo < 60) return `${secondsAgo}s ago`;
  if (secondsAgo < 3600) return `${Math.floor(secondsAgo / 60)}m ago`;
  if (secondsAgo < 86400) return `${Math.floor(secondsAgo / 3600)}h ago`;
  return `${Math.floor(secondsAgo / 86400)}d ago`;
}

const DECISION_COLORS: Record<DecisionKind, string> = {
  approve: "text-emerald-300",
  reject: "text-red-300",
  hold: "text-amber-300",
  demote: "text-orange-300",
};

export default async function Home() {
  const [needsReview, decisions] = await Promise.all([
    fetchNeedsReviewCount(),
    fetchRecentDecisions(),
  ]);

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-2xl font-semibold mb-2">The upskilling dashboard</h2>
        <p className="text-loom-100">
          The agent observes how you work and surfaces promotion candidates.
          You decide what gets codified.
        </p>
      </section>

      {/* The single actionable prompt */}
      <section>
        {needsReview === null ? (
          <a
            href="/candidates"
            className="block border border-loom-700 rounded p-4 bg-loom-900/50 hover:border-loom-500"
          >
            <span className="text-loom-100 font-medium">
              → Open the candidates queue
            </span>
            <p className="text-xs text-loom-500 mt-1">
              Registry is starting up; counts will appear once it&apos;s
              reachable.
            </p>
          </a>
        ) : needsReview === 0 ? (
          <div className="border border-loom-700 rounded p-4 bg-loom-900/50">
            <span className="text-loom-500">
              No candidates need review right now.
            </span>
          </div>
        ) : (
          <a
            href="/candidates"
            className="block border border-amber-700 rounded p-4 bg-amber-950/30 hover:border-amber-500"
          >
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-semibold text-amber-300">
                {needsReview}
              </span>
              <span className="text-loom-100 font-medium">
                {needsReview === 1 ? "candidate" : "candidates"} waiting for
                review →
              </span>
            </div>
            <p className="text-xs text-loom-500 mt-1">
              Click to triage. Each row has Promote / Hold / Reject.
            </p>
          </a>
        )}
      </section>

      {/* Verification view — what did I just do */}
      {decisions.length > 0 && (
        <section>
          <h3 className="font-semibold mb-3 text-sm text-loom-500">
            Recent decisions (for verification)
          </h3>
          <ul className="space-y-1 text-sm">
            {decisions.map((d) => (
              <li
                key={d.id}
                className="flex items-baseline gap-3 border-b border-loom-700 py-2"
              >
                <span className="text-xs text-loom-500 w-20 shrink-0">
                  {formatRelativeTime(d.decided_at)}
                </span>
                <span
                  className={`font-mono text-xs w-16 shrink-0 ${DECISION_COLORS[d.decision_kind]}`}
                >
                  {d.decision_kind}
                </span>
                {d.target_status && (
                  <span className="text-xs text-loom-500 w-32 shrink-0">
                    → {d.target_status}
                  </span>
                )}
                <span className="text-xs text-loom-100 truncate">
                  {d.reason || "(no reason)"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Nav — small, doesn't dominate */}
      <section className="border-t border-loom-700 pt-4 text-sm">
        <a
          href="/dashboard"
          className="text-loom-500 hover:text-loom-100"
        >
          → Observability (Grafana iframe)
        </a>
      </section>
    </div>
  );
}
