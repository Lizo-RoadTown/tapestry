# loom-web-dashboard — the upskilling dashboard

The operator-facing surface for loom. Next.js 15 + TypeScript + Tailwind. Deploys to Vercel at `loom.humancensys.com`.

## What this site IS

The upskilling dashboard: the page where the operator (Liz first, then any operator of a the-loom deployment) watches the upskilling loop happen and acts on it. The agent observes how the user works → surfaces promotion candidates → the operator approves / rejects / holds via this site → the system codifies the decision.

This surface is **the-loom's running interface**. Not a product shipped to end-users (that's Tapestry, which is unrelated). See [`docs/architecture/UMBRELLA.md`](../../docs/architecture/UMBRELLA.md) and loom-memory `naming_upskilling_dashboard_supersedes_atelier_2026_06_12` for the full naming + separation history.

## Sections

- **`/`** — overview. Skill library + tool library counts + recent promotions + open candidates queue summary.
- **`/candidates`** — the promotion-candidates queue. Each row shows a candidate (kind, project, evidence) with Promote / Hold / Reject buttons that POST to the policy-service's `/decisions` endpoint.
- **`/dashboard`** — observability view (Grafana iframe of live hook activity). Will be renamed to `/observability` in a future PR; URL preserved during transition.
- **`/api/health`** — Vercel health endpoint.

## Backend services this site consumes

- **architecture-registry** (URL set via env) — `GET /candidates` for the queue, `PATCH /candidates/{id}/status` after a decision applies
- **policy service** (URL set via env) — `POST /decisions`, `GET /candidates/{id}/policy-state`
- **project-registry** (URL set via env) — `GET /projects` for filter dropdowns
- Grafana Cloud — embedded iframe in `/dashboard` (until native observability views replace it)

Auth: self-host mode (no JWT header) gets the canonical `SELF_HOST_TENANT_ID` via the backend services' `auth_bridge` fallback. Hosted-multitenant mode (future): the dashboard will mint + attach a Bearer JWT.

## Phased build sequence (current = step 1)

| Step | What | State |
|---|---|---|
| 1 | Reframe README + landing + nav; stub `/candidates` | THIS PR |
| 2 | Wire `/candidates` to architecture-registry (read-only listing) | next |
| 3 | Wire Promote / Reject / Hold buttons to policy-service | after 2 |
| 4 | Skill + tool library counts + recent promotions on landing | after 3 |
| 5 | `/observability` replaces `/dashboard` (native views replace Grafana iframe via project-observatory) | later |
| 6 | Native architecture map (V2.x) | later |

Backed by loom-memory `upskilling_dashboard_build_starting_2026_06_12`.

## Local dev

```bash
cd apps/web-dashboard
npm install
npm run dev
# → http://localhost:3000
```

For the embedded observability iframe, set `NEXT_PUBLIC_GRAFANA_DASHBOARD_URL` in `apps/web-dashboard/.env.local` to your Grafana Cloud dashboard's public share URL or panel embed URL.

For the candidates queue (step 2+), no env-vars are needed in self-host mode; the backend services are reached at their public Render URLs above.

## Deploy

Vercel project linked to this monorepo with `Root Directory = apps/web-dashboard`. Auto-deploys on every push to `main`. Custom domain `loom.humancensys.com` configured in Vercel.

Env vars to set in Vercel:

- `NEXT_PUBLIC_GRAFANA_DASHBOARD_URL` — Grafana Cloud dashboard or panel embed URL (for the observability section)

More env vars will be added in step 4+ if the hosted-multitenant JWT pattern lands and the dashboard needs to mint tokens.
