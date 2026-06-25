/**
 * Candidates queue — Phase 6 step 3 (action buttons live).
 *
 * Builds on step 2's read-only listing. Adds three actions per actionable
 * row: Promote (advance status by one step) / Hold (pause) / Reject.
 *
 * Each action does TWO calls in sequence:
 *   1. POST policy-service/decisions  — records the operator decision
 *      (audit-immutable; this is the source-of-truth log)
 *   2. PATCH architecture-registry/candidates/{id}/status — applies
 *      the status change (Hold does NOT do this; status stays put)
 *
 * If (1) fails, (2) is skipped. If (1) succeeds but (2) fails, the audit
 * trail correctly shows the decision was filed; a future operator action
 * (or the demotion path) can recover. Per
 * docs/proposals/2026-06-12-promotion-categorization.md §6.5.
 *
 * Server actions per Next.js 15 pattern. revalidatePath after each call
 * so the row reflects the new state immediately.
 *
 * Dual-mode:
 *   - Self-host: no Authorization header → backend auth_bridge falls
 *     through to SELF_HOST_TENANT_ID → RLS scopes to Liz's tenant.
 *   - Hosted-multitenant: JWT minting lives in step 5+ follow-up; today
 *     the dashboard is intended for the self-host operator only.
 *
 * Per loom-memory dashboard_phase6_progress_2026_06_12_evening.
 */

import { revalidatePath } from "next/cache";

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
  | "rejected";

type CandidateKind =
  | "skill"
  | "inline_tool"
  | "external_tool"
  | "architecture_pattern"
  | "service"
  | "machine_support"
  | "process"
  | "agent"
  | "orchestration";

type Candidate = {
  id: string;
  project_id: string;
  instance_id: string;
  source_path: "path_a" | "path_b";
  candidate_type: CandidateKind;
  status: CandidateStatus;
  evidence_refs: Array<{ kind: string; [k: string]: unknown }>;
  signals: Record<string, unknown>;
  tenant_id: string;
  created_at: number;
  updated_at: number;
};

type CandidateListResponse = {
  candidates: Candidate[];
};

/**
 * Per docs/proposals/2026-06-12-promotion-categorization.md §3 lifecycle.
 * Promote advances by exactly one step. promotion_requested → promoted is
 * the final hop (the architecture-registry PATCH sets status='promoted';
 * the destination work — writing SKILL.md etc. — happens outside this UI).
 */
const NEXT_STATUS: Partial<Record<CandidateStatus, CandidateStatus>> = {
  draft: "observed",
  observed: "recurring",
  recurring: "stable",
  stable: "promotion_requested",
  promotion_requested: "promoted",
};

async function fetchCandidates(): Promise<{
  candidates: Candidate[];
  error: string | null;
}> {
  try {
    const res = await fetch(`${REGISTRY_URL}/candidates?limit=100`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return {
        candidates: [],
        error: `Registry returned HTTP ${res.status}`,
      };
    }
    const data = (await res.json()) as CandidateListResponse;
    return { candidates: data.candidates, error: null };
  } catch (e) {
    return {
      candidates: [],
      error: `Failed to reach registry: ${e instanceof Error ? e.message : String(e)}`,
    };
  }
}

// ---------------------------------------------------------------------------
// Server actions (Next.js 15)
// ---------------------------------------------------------------------------

async function postDecision(
  candidateId: string,
  decisionKind: "approve" | "hold" | "reject",
  targetStatus: CandidateStatus | null,
  reason: string,
): Promise<{ ok: true } | { ok: false; status: number; body: string }> {
  const res = await fetch(`${POLICY_URL}/decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify({
      candidate_id: candidateId,
      decision_kind: decisionKind,
      target_status: targetStatus,
      reason,
      decided_by: "operator:upskilling-dashboard",
    }),
  });
  if (!res.ok) {
    return { ok: false, status: res.status, body: await res.text() };
  }
  return { ok: true };
}

async function patchCandidateStatus(
  candidateId: string,
  newStatus: CandidateStatus,
  reason: string,
): Promise<{ ok: true } | { ok: false; status: number; body: string }> {
  const res = await fetch(`${REGISTRY_URL}/candidates/${candidateId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify({ status: newStatus, reason }),
  });
  if (!res.ok) {
    return { ok: false, status: res.status, body: await res.text() };
  }
  return { ok: true };
}

async function promoteAction(formData: FormData) {
  "use server";
  const candidateId = formData.get("candidate_id") as string;
  const currentStatus = formData.get("current_status") as CandidateStatus;
  const next = NEXT_STATUS[currentStatus];
  if (!next) return;

  const decisionResult = await postDecision(
    candidateId,
    "approve",
    next,
    `Promoted via upskilling dashboard (${currentStatus} → ${next})`,
  );
  if (!decisionResult.ok) {
    // Audit failed; abort the status change. revalidate so the operator
    // can retry from a clean slate.
    revalidatePath("/candidates");
    return;
  }
  await patchCandidateStatus(
    candidateId,
    next,
    `Promoted via upskilling dashboard`,
  );
  revalidatePath("/candidates");
}

async function holdAction(formData: FormData) {
  "use server";
  const candidateId = formData.get("candidate_id") as string;
  await postDecision(
    candidateId,
    "hold",
    null,
    "Held for review via upskilling dashboard",
  );
  // No PATCH — hold doesn't change status, it just records the pause.
  revalidatePath("/candidates");
}

async function rejectAction(formData: FormData) {
  "use server";
  const candidateId = formData.get("candidate_id") as string;
  const decisionResult = await postDecision(
    candidateId,
    "reject",
    "rejected",
    "Rejected via upskilling dashboard",
  );
  if (!decisionResult.ok) {
    revalidatePath("/candidates");
    return;
  }
  await patchCandidateStatus(
    candidateId,
    "rejected",
    "Rejected via upskilling dashboard",
  );
  revalidatePath("/candidates");
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function formatRelativeTime(epoch: number): string {
  const secondsAgo = Math.floor(Date.now() / 1000 - epoch);
  if (secondsAgo < 60) return `${secondsAgo}s ago`;
  if (secondsAgo < 3600) return `${Math.floor(secondsAgo / 60)}m ago`;
  if (secondsAgo < 86400) return `${Math.floor(secondsAgo / 3600)}h ago`;
  return `${Math.floor(secondsAgo / 86400)}d ago`;
}

function evidenceSummary(refs: Candidate["evidence_refs"]): string {
  if (refs.length === 0) return "(no evidence)";
  const first = refs[0];
  const rest = refs.length - 1;
  return rest > 0 ? `${first.kind} + ${rest} more` : first.kind;
}

const STATUS_COLORS: Record<CandidateStatus, string> = {
  draft: "text-loom-500",
  observed: "text-blue-300",
  recurring: "text-yellow-300",
  stable: "text-green-300",
  promotion_requested: "text-amber-300",
  promoted: "text-emerald-400",
  rejected: "text-red-400",
};

export default async function CandidatesPage() {
  const { candidates, error } = await fetchCandidates();

  const actionable = candidates.filter(
    (c) => c.status !== "promoted" && c.status !== "rejected",
  );
  const terminal = candidates.filter(
    (c) => c.status === "promoted" || c.status === "rejected",
  );

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold">Promotion candidates</h2>
        <p className="text-sm text-loom-500 mt-1">
          Operator decisions are filed with <code>policy-service</code>{" "}
          (audit-immutable) and applied via{" "}
          <code>architecture-registry</code>. Hold records a pause
          without changing status; Reject closes the candidate.
        </p>
      </header>

      {error ? (
        <section className="border border-red-700 rounded p-4 bg-red-950/30">
          <h3 className="font-semibold mb-2 text-red-300">Registry unreachable</h3>
          <p className="text-sm">{error}</p>
          <p className="text-xs text-loom-500 mt-2">
            Self-host mode: no auth required. If the registry is awake at{" "}
            <code>{REGISTRY_URL}/health</code>, this page reloads with data.
          </p>
        </section>
      ) : (
        <>
          <section>
            <h3 className="font-semibold mb-3">
              Actionable ({actionable.length})
            </h3>
            {actionable.length === 0 ? (
              <p className="text-sm text-loom-500">No actionable candidates.</p>
            ) : (
              <ActionableTable rows={actionable} />
            )}
          </section>

          {terminal.length > 0 && (
            <section>
              <h3 className="font-semibold mb-3 text-loom-500">
                Terminal ({terminal.length})
              </h3>
              <TerminalTable rows={terminal} />
            </section>
          )}
        </>
      )}

      <section className="text-sm text-loom-500 border-t border-loom-700 pt-4">
        <p>
          The 9 candidate kinds + their shape signatures are defined in{" "}
          <code className="text-xs">
            docs/proposals/2026-06-12-promotion-categorization.md §4
          </code>
          . Audit-immutable: filed decisions cannot be edited; revisions
          happen via NEW decision rows per §6.
        </p>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Table variants (actionable has buttons; terminal doesn't)
// ---------------------------------------------------------------------------

function ActionableTable({ rows }: { rows: Candidate[] }) {
  return (
    <div className="border border-loom-700 rounded overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-loom-900 text-loom-100">
          <tr>
            <th className="text-left px-3 py-2">Kind</th>
            <th className="text-left px-3 py-2">Status</th>
            <th className="text-left px-3 py-2">Source</th>
            <th className="text-left px-3 py-2">Evidence</th>
            <th className="text-left px-3 py-2">Project</th>
            <th className="text-left px-3 py-2">Updated</th>
            <th className="text-left px-3 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => {
            const next = NEXT_STATUS[c.status];
            return (
              <tr key={c.id} className="border-t border-loom-700">
                <td className="px-3 py-2 font-mono text-xs">{c.candidate_type}</td>
                <td className={`px-3 py-2 ${STATUS_COLORS[c.status]}`}>{c.status}</td>
                <td className="px-3 py-2 text-loom-500 text-xs">{c.source_path}</td>
                <td className="px-3 py-2 text-xs">{evidenceSummary(c.evidence_refs)}</td>
                <td className="px-3 py-2 font-mono text-xs text-loom-500">
                  {c.project_id.slice(0, 8)}…
                </td>
                <td className="px-3 py-2 text-xs text-loom-500">
                  {formatRelativeTime(c.updated_at)}
                </td>
                <td className="px-3 py-2">
                  <div className="flex gap-1 flex-wrap">
                    {next && (
                      <form action={promoteAction}>
                        <input type="hidden" name="candidate_id" value={c.id} />
                        <input
                          type="hidden"
                          name="current_status"
                          value={c.status}
                        />
                        <button
                          type="submit"
                          title={`Promote to ${next}`}
                          className="px-2 py-1 text-xs rounded bg-emerald-700 hover:bg-emerald-600 text-white"
                        >
                          Promote → {next}
                        </button>
                      </form>
                    )}
                    <form action={holdAction}>
                      <input type="hidden" name="candidate_id" value={c.id} />
                      <button
                        type="submit"
                        title="Pause (audit-only; status unchanged)"
                        className="px-2 py-1 text-xs rounded bg-amber-700 hover:bg-amber-600 text-white"
                      >
                        Hold
                      </button>
                    </form>
                    <form action={rejectAction}>
                      <input type="hidden" name="candidate_id" value={c.id} />
                      <button
                        type="submit"
                        title="Reject (set status to rejected)"
                        className="px-2 py-1 text-xs rounded bg-red-700 hover:bg-red-600 text-white"
                      >
                        Reject
                      </button>
                    </form>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TerminalTable({ rows }: { rows: Candidate[] }) {
  return (
    <div className="border border-loom-700 rounded overflow-hidden opacity-60">
      <table className="w-full text-sm">
        <thead className="bg-loom-900 text-loom-100">
          <tr>
            <th className="text-left px-3 py-2">Kind</th>
            <th className="text-left px-3 py-2">Status</th>
            <th className="text-left px-3 py-2">Source</th>
            <th className="text-left px-3 py-2">Evidence</th>
            <th className="text-left px-3 py-2">Project</th>
            <th className="text-left px-3 py-2">Updated</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id} className="border-t border-loom-700">
              <td className="px-3 py-2 font-mono text-xs">{c.candidate_type}</td>
              <td className={`px-3 py-2 ${STATUS_COLORS[c.status]}`}>{c.status}</td>
              <td className="px-3 py-2 text-loom-500 text-xs">{c.source_path}</td>
              <td className="px-3 py-2 text-xs">{evidenceSummary(c.evidence_refs)}</td>
              <td className="px-3 py-2 font-mono text-xs text-loom-500">
                {c.project_id.slice(0, 8)}…
              </td>
              <td className="px-3 py-2 text-xs text-loom-500">
                {formatRelativeTime(c.updated_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
