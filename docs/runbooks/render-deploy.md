# Render deploy — humancensys.com api + database

Step-by-step for deploying the Make_Skills FastAPI app + managed Postgres + persistent disk on Render. Once this is up, the cross-machine memory endpoint at `/mcp/memory` becomes live and your other repos can connect to it.

## Prerequisites

- A Render account (free tier OK to start, but you'll need to upgrade the api service to **starter ($7/mo)** because persistent disks require it).
- The `Lizo-RoadTown/Make_Skills` repo accessible to Render (you authorize Render to read your GitHub repos during onboarding).
- API keys ready to paste into the Render dashboard (Anthropic at minimum; others optional).
- `AUTH_SECRET` value — must match the one set on Vercel for the Next.js app. If you don't have one yet, generate with `openssl rand -base64 32` or use the existing one in your Vercel env.

## Step-by-step

### 1. Connect the repo via Blueprint

1. Render Dashboard → **New +** → **Blueprint**.
2. Connect your GitHub account if you haven't, then select `Lizo-RoadTown/Make_Skills`.
3. Render reads `render.yaml` at the repo root and proposes:
   - Web service: `make-skills-api` (Docker, Oregon region, starter plan)
   - Database: `make-skills-db` (Postgres free tier — 256MB)
   - Persistent disk: `memory-data` (1 GB mounted at `/data/memory`)
4. **Confirm.** Render starts provisioning.

### 2. Set the secret env vars

Render's dashboard prompts you for every env var marked `sync: false` in `render.yaml`. Fill in the ones you'll actually use:

| Var | What it does | When you need it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API for the agent runtime | **Required.** Without this the agent can't respond. |
| `AUTH_SECRET` | HS256 secret shared with Vercel's Auth.js | **Required for hosted mode** (`PLATFORM_MODE=hosted`). Must match Vercel exactly. |
| `LLAMA_CLOUD_API_KEY` | LlamaParse for PDF parsing | Optional; only if students upload PDFs. |
| `TAVILY_API_KEY` | Web search tool | Optional; only if agents need web search. |
| `LANGSMITH_API_KEY` | LangSmith for tracing | Optional but recommended for observability. |
| `OPENAI_API_KEY` / `GOOGLE_API_KEY` / etc. | Pillar 1 model providers | Optional; only if you want students using non-Anthropic models. |
| `OLLAMA_BASE_URL` + `OLLAMA_AUTH_HEADER` | BYO personal Ollama | Optional; only if you want to point at your own Ollama. |
| `SENTRY_DSN` | Sentry error tracking | Optional; only if you want hosted-mode error telemetry. |

Skip anything you don't need — the code uses lazy loading so missing keys disable the corresponding feature without crashing.

### 3. Flip `PLATFORM_MODE` to `hosted`

By default `render.yaml` sets `PLATFORM_MODE=self_host` (so the api boots even before Vercel is wired). To enable:
- JWT verification on `/chat/{agent_id}` endpoints
- The `/mcp/memory` cross-machine route
- LangSmith tracing
- Sentry init (if `SENTRY_DSN` set)

In the Render dashboard for the `make-skills-api` service → **Environment** → find `PLATFORM_MODE` → change value from `self_host` to `hosted` → **Save Changes**. Render redeploys automatically.

### 4. Wait for the build + healthcheck

First build takes ~5-10 minutes (Docker base image + Python deps including `fastembed` model). Watch the **Logs** tab. Success looks like:
- Build: `Successfully tagged srv-xxx`
- Deploy: `Starting service make-skills-api...`
- Healthcheck: `GET /healthz` returns 200

If healthcheck fails, the most common causes:
- `ANTHROPIC_API_KEY` not set (api crashes at startup)
- Postgres still provisioning (transient; retry in a minute)
- `AUTH_SECRET` not set when `PLATFORM_MODE=hosted` (auth module raises at first request)

### 5. Verify the hosted endpoint

Once green, your service URL is something like `https://make-skills-api-xxx.onrender.com`. Run from any machine:

```bash
# Should return 401 (no auth) — proves the route is mounted
curl -i https://make-skills-api-xxx.onrender.com/mcp/memory/

# Should return 200 healthcheck
curl https://make-skills-api-xxx.onrender.com/healthz
```

If `/mcp/memory/` returns 404, `PLATFORM_MODE` is still `self_host`. Re-check step 3.

### 6. Point your custom domain (optional, but recommended)

If you want `humancensys.com/api/...` instead of the raw Render URL:
1. Render dashboard → make-skills-api → **Settings** → **Custom Domains** → add `humancensys.com` (or `api.humancensys.com`).
2. Render gives you DNS records to add. Update at your registrar.
3. SSL cert provisions automatically.

The `.claude/mcp.json.hosted-example` in the repo assumes `https://humancensys.com/mcp/memory` — update either the example or your DNS to match.

### 7. Connect Claude Code from any machine

Per the runbook section in [docs/runbooks/memory-mcp-local.md](memory-mcp-local.md#hosted-mode-cross-machine-memory):

1. Log into the web UI to get your session JWT (via `/api/auth/token` once that endpoint is added — TODO).
2. Edit `.claude/mcp.json` in any repo:
   ```json
   {
     "memory": {
       "type": "http",
       "url": "https://humancensys.com/mcp/memory",
       "headers": {
         "Authorization": "Bearer YOUR_JWT_HERE"
       }
     }
   }
   ```
3. Restart Claude Code. `/mcp` should show `memory` as connected.

## What's NOT in this runbook

- **Web (Next.js) deploy on Vercel.** Separate process — see Vercel docs and the existing `web/.env.example`.
- **The `/api/auth/token` endpoint** to extract the session JWT. Currently not implemented; first hosted-mode user will need to grab it from browser dev tools / cookie inspection until the endpoint ships.
- **Test fixture for hosted-mode integration tests** — currently `pytest.mark.skip`-marked at `platform/tests/test_memory_mcp_hosted.py`. Production code works (verified via direct curl probes); test fixture needs refactor.
- **DEFAULT_TENANT_ID migration** — first hosted-mode tenant will get a JWT-derived UUID for `tenant_id`; existing self-host data under `tenant_id="default"` stays isolated. See the future B1 migration PR to unify.

## Troubleshooting

**Build fails with `fastembed` download timeout** — Render's build network sometimes hits transient timeouts on the ~80MB model. Retry the deploy. Persistent failures: add a build cache step.

**Postgres connection refused** — Render's managed Postgres takes 30-60 seconds to provision on first deploy. If the api starts before Postgres is ready, it'll crash and retry. Wait 2 minutes, then check logs.

**`/mcp/memory/` returns 500** — likely `AUTH_SECRET` mismatch with Vercel. Decode a known-valid JWT at jwt.io and confirm the `tenant_id` + `sub` claims are present. If decode fails, the secret on api side doesn't match the secret that signed the token.

**Cold-start delays** — Render's free tier sleeps after 15 minutes idle. First request after sleep takes ~30s to wake. The api service is on **starter plan** (not free) so this shouldn't apply, but free-tier Postgres has its own inactivity rules.

## Cost summary

| Service | Plan | Monthly cost |
|---|---|---|
| `make-skills-api` (web service + 1 GB persistent disk) | Starter | $7 |
| `make-skills-db` (managed Postgres) | Free | $0 |
| Bandwidth | Pay-as-you-go | typically <$1 |
| **Total** | | **~$7-10/mo** |

Upgrade Postgres to Starter ($7/mo) when free-tier limits become a problem (256MB RAM, 1GB storage, 30-day inactivity expiry).

## Refs

- `render.yaml` — the blueprint Render reads
- `docs/runbooks/memory-mcp-local.md` — hosted-mode client setup (after this deploy succeeds)
- `docs/proposals/lancedb-memory-mcp.md` — the architecture this deploys
