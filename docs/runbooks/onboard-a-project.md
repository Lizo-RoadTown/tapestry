# How to onboard a new project to the-loom

**Status:** 2026-05-30. Reflects what works TODAY (manual steps). The `loom init` CLI that will collapse steps 1-5 into one command is Phase 5+ work; not built yet.

The-loom provides four services any project can opt into:

| Service | What you get | Where the wiring lives |
|---|---|---|
| **Memory MCP** | Cross-session, cross-machine, cross-project persistent memory accessible from any agent that speaks MCP | `claude mcp add` (user-scope, per machine) |
| **Discipline plugin** | PROBE-first reminders, file:line citation enforcement, friction-as-memory writes, hook telemetry | Claude Code plugin install (per machine) |
| **Observability pipeline** | Every hook event → Grafana Cloud dashboards (project-scoped) | `.env` in each project + .env loader in the plugin |
| **Project Registry** | The-loom knows your project exists as an entity (not just a tag string); enables proper scoping | One-time POST to `/projects` (today; `loom init` future) |
| **Skills catalog** | Methodology skills (lessons-learned, layered-explanation, agentic-upskilling, etc.) | Today: copy from `the-loom/skills/`; Phase 5: SDK pulls from catalog |

---

## Part 1 — Onboarding a new project (on your primary machine)

Assumes you already have the loom-discipline plugin installed and the memory MCP registered on this machine. If not, jump to Part 2 first.

### Step 1 — Create the repo

```powershell
gh repo create Lizo-RoadTown/<project-slug> --private --clone
cd <project-slug>
```

Pick the slug carefully — it becomes `LOOM_PROJECT_ID`, the Grafana label, and the Project Registry's primary lookup key. Use the same value everywhere.

### Step 2 — Register the project in the-loom's Project Registry

```powershell
# Register the project (self-host mode — no JWT needed for local dev)
curl -X POST https://loom-project-registry.onrender.com/projects `
  -H "Content-Type: application/json" `
  -d '{\"slug\": \"<project-slug>\", \"name\": \"<Human-readable name>\", \"description\": \"<one sentence>\"}'
```

The response includes a UUID — note it; you may want it later. Idempotent check before creating:

```powershell
curl https://loom-project-registry.onrender.com/projects/by-slug/<project-slug>
```

Returns 404 if not yet registered, the row if already there.

### Step 3 — Create the project's `.env` file

```powershell
@'
# Telemetry — copy from the-loom's .env (same Grafana account, just different project_id)
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-west-0.grafana.net/otlp
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_HEADERS=<paste from the-loom/.env>
OTEL_RESOURCE_ATTRIBUTES=service.namespace=loom,deployment.environment=dev
OTEL_SERVICE_NAME=loom-discipline

# Per-project identity — THIS is what differentiates your hook events in Grafana
LOOM_PROJECT_ID=<project-slug>
'@ | Out-File -Encoding utf8 .env
```

Then gitignore it:

```powershell
'.env' | Add-Content .gitignore
```

### Step 4 — Verify the discipline plugin picks up this project

In Claude Code, the plugin's `_observability.py:_load_dotenv()` reads `${CLAUDE_PROJECT_DIR}/.env` automatically on every hook fire. No restart needed. Send a test prompt; check the Grafana dashboard with a `project_id=<your-slug>` filter — events should appear within ~10s.

### Step 5 (optional, today) — Pull skills into the project

Until Phase 5's SDK lands, skills don't auto-install. If you want methodology skills available in this project:

```powershell
# Symlink (preferred — stays in sync with the-loom's catalog)
New-Item -ItemType SymbolicLink -Path skills -Target ..\the-loom\skills

# OR copy (snapshot — won't update when the-loom updates)
Copy-Item -Recurse ..\the-loom\skills .\skills
```

When the SDK lands, this step becomes `loom init` and pulls the canonical set.

### Step 6 — Done

The project now has:
- ✅ Memory MCP available (user-scope, inherited)
- ✅ Discipline plugin firing hooks (with project_id tag)
- ✅ Telemetry flowing to Grafana (filterable by project_id)
- ✅ Registered as a known entity in the-loom's Project Registry
- ✅ (Optional) Skills accessible

---

## Part 2 — Setting up a NEW MACHINE (first time)

You need to do this once per machine. Then all projects on that machine inherit the wiring.

### Step 1 — Copy your JWT signing key from your primary machine

The loom-memory MCP uses RS256 — your machines all need the same private key to mint tokens that the-loom's public key will verify.

On your **primary** machine:
```powershell
# Find the key
Get-Content $env:USERPROFILE\.ssh\loom_jwt | Set-Clipboard
```

Transfer to the new machine via your secure channel of choice (1Password, USB, encrypted email). On the **new** machine:
```powershell
# Paste the key into the standard location
New-Item -ItemType Directory -Force $env:USERPROFILE\.ssh
notepad $env:USERPROFILE\.ssh\loom_jwt   # paste from clipboard, save
```

**Alternative:** generate a NEW keypair on the new machine and update `LOOM_JWT_PUBLIC_KEY` in Render's env group to include both. More work; only needed if you don't want to share private keys across machines.

### Step 2 — Install the loom-discipline plugin

Currently the plugin lives at `<the-loom-repo>/adapters/claude-code/loom-discipline/`. Until it's published to the claude-skills-marketplace, you have two install options:

**Option A — Clone the-loom on this machine and reference the plugin directly:**
```powershell
gh repo clone Lizo-RoadTown/the-loom
cd the-loom

# In Claude Code, add a project-scoped install
# (look up the current syntax in `claude --help`; varies by CC version)
```

**Option B — Install from the marketplace (when published):**
```powershell
# /plugin install loom-discipline  (in Claude Code)
```

Either way, restart Claude Code after install — plugin loader binds at session start.

### Step 3 — Register the memory MCP (user-scope)

Mint a token from the-loom repo on this machine:
```powershell
cd the-loom
python scripts\mint_loom_token.py --hours 720 | Set-Clipboard
```

Then in any directory:
```powershell
claude mcp add --scope user --transport http loom-memory `
  https://loom-agent-context.onrender.com/mcp/memory/ `
  --header "Authorization: Bearer <paste-token-from-clipboard>"
```

Restart Claude Code. Verify with `/mcp` slash command — `loom-memory` should show as connected with 6 tools.

### Step 4 — Set OTel credentials at User scope (optional but convenient)

If you want every project on this machine to inherit the Grafana credentials without copying them into each .env:

```powershell
[Environment]::SetEnvironmentVariable('OTEL_EXPORTER_OTLP_ENDPOINT', 'https://otlp-gateway-prod-us-west-0.grafana.net/otlp', 'User')
[Environment]::SetEnvironmentVariable('OTEL_EXPORTER_OTLP_HEADERS', '<paste from the-loom/.env>', 'User')
```

Then per-project `.env` only needs `LOOM_PROJECT_ID=<slug>` — the OTel vars inherit from User scope, and the plugin's `.env` loader respects "existing env wins" so it doesn't override.

### Step 5 — Clone your projects on this machine

For each project you want to work on:
```powershell
gh repo clone Lizo-RoadTown/<project-slug>
cd <project-slug>

# Copy .env from primary machine (or recreate per Part 1, Step 3)
```

The Project Registry already knows about this project (you registered it from your primary machine); this is just where you put the files locally.

### Step 6 — Done

This machine now has:
- ✅ JWT signing key to mint memory MCP tokens
- ✅ Discipline plugin installed
- ✅ Memory MCP registered at user scope (works in every project)
- ✅ OTel credentials at user scope (inherited by every project's .env)
- ✅ Your project repos cloned

When you start a new session in any of those project directories, you get the full loom experience.

---

## Part 3 — The shortcut these will collapse into (Phase 5+ SDK)

Eventually:

```bash
loom init --slug <project-slug> --name "<Name>"
```

Will do:
1. POST to `/projects` to register
2. Create `.env` with the right values pulled from the-loom's known config
3. Create `.project-intelligence/` folder per the agency-optimizer pattern ([docs/proposals/2026-05-25-platform-data-model.md:103](../proposals/2026-05-25-platform-data-model.md#L103))
4. Pull the canonical skills set from the-loom's catalog
5. Verify the discipline plugin can fire hooks
6. Print a smoke-test confirmation

And on a new machine:
```bash
loom machine init
```

Will:
1. Generate/import the JWT signing key
2. Install the discipline plugin from the marketplace
3. Mint a token + register the MCP at user scope
4. Set OTel env at user scope
5. Print "you're good"

Until then, follow Parts 1 and 2 above manually.

---

## Reference — file:line of the moving parts

- Memory MCP service: [services/agent-context/](../../services/agent-context/) — RS256 JWT, RLS-scoped Postgres + pgvector
- Project Registry service: [services/project-registry/](../../services/project-registry/) — Project/Repo/Machine CRUD
- Discipline plugin: [adapters/claude-code/loom-discipline/](../../adapters/claude-code/loom-discipline/) — hooks + scripts
- `.env` loader: [adapters/claude-code/loom-discipline/scripts/_observability.py:_load_dotenv](../../adapters/claude-code/loom-discipline/scripts/_observability.py) — reads `${CLAUDE_PROJECT_DIR}/.env`
- OTel push: [adapters/claude-code/loom-discipline/scripts/_observability.py:_push_otlp](../../adapters/claude-code/loom-discipline/scripts/_observability.py) — POSTs to `${OTEL_EXPORTER_OTLP_ENDPOINT}/v1/logs`
- Token minter: [scripts/mint_loom_token.py](../../scripts/mint_loom_token.py) — RS256 signing
- Migration runner: [scripts/apply_migration.py](../../scripts/apply_migration.py) — one-off DDL
- Architecture model: [docs/proposals/2026-05-25-platform-data-model.md](../proposals/2026-05-25-platform-data-model.md) — bounded contexts + entities
- Agency optimizer pattern: [docs/proposals/2026-05-25-platform-data-model.md:85-131](../proposals/2026-05-25-platform-data-model.md#L85) — capability vs instance
