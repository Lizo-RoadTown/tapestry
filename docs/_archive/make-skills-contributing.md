# Contributing to Make_Skills

Thanks for thinking about contributing. This project is **dual-mode**: it runs as a self-hosted personal agent platform AND as a multi-tenant hosted service. Every contribution must work in both modes.

Read [`ARCHITECTURE.md`](ARCHITECTURE.md) before making structural changes — it draws the lines you need to respect.

## Quick start (self-host)

```bash
git clone https://github.com/Lizo-RoadTown/Make_Skills.git
cd Make_Skills

# Run the platform stack
cd platform/deploy
cp .env.template .env
# fill in ANTHROPIC_API_KEY (others optional)
docker compose up -d --build

# Run the web UI (separate terminal)
cd ../../web
npm install
npm run dev
```

Open http://localhost:3000. You're talking to a fully-functional agent.

## What you can contribute, where

| Layer | Module | Contribution welcome | Notes |
|-------|--------|---------------------|-------|
| Platform code (Python) | [`platform/api/`](platform/api/) | Yes | Must work in both modes; tenant scoping required |
| UI shell (Next.js) | [`web/`](web/) | Yes | Mode-agnostic; calls api via HTTP |
| Skill library | [`skills/`](skills/) | Yes — high-leverage | Each skill is one folder with `SKILL.md` |
| Subagent templates | [`subagents/`](subagents/) | Yes | One folder per persona |
| Documentation | All `*.md` files | Yes | Especially examples and onboarding |
| Build / deploy config | [`platform/deploy/`](platform/deploy/), [`render.yaml`](render.yaml) | Yes | Both Docker compose AND Render must continue working |

## What's NOT a contribution surface

- **Tenant data** — never modify someone else's `ROADMAP.md`, `AGENTS.md`, or memory contents in a PR.
- **Personal config** — the root `AGENTS.md` and `deepagents.toml` are *defaults*. Don't restructure them in a way that breaks individual tenants who have customized them.
- **Memory / LanceDB volume contents** — these are runtime data, not code.

## The two-mode discipline (read this)

Every PR is reviewed against four questions:

1. **What changes for a self-host user?** Do they need to update env vars, rebuild, run a migration?
2. **What changes for the hosted-multitenant deployment?** Same questions, PLUS: does it touch tenant scoping correctly?
3. **Tests:** unit tests for the change. Integration tests with `tenant_id = "default"` (self-host) AND a non-default `tenant_id` (hosted). At least one test that verifies a non-default tenant cannot see "default" tenant's data.
4. **Docs:** the relevant `README.md` (or specific doc) explains how the change appears to users in BOTH modes.

A PR missing any of those four is incomplete.

### Anti-patterns we reject

- Hardcoded `tenant_id = "default"` outside of the `NoAuthBackend` self-host path
- Direct filesystem reads bypassing the `config_loader` abstraction (when added)
- "Multi-tenancy can come later" — once data is being written without scoping, retrofitting is a migration nightmare
- Tests that only exercise one mode

### Patterns we like

- Use `Depends(current_tenant)` in any new FastAPI endpoint that touches tenant data
- Filter every database query by tenant_id (helper functions encouraged)
- Document the data type's tenant scope in a comment at the top of the model definition
- Provide both a self-host smoke test (`docker compose up && curl /healthz`) and a multi-tenant test (mock auth, verify isolation)

## Submitting changes

1. Fork the repo.
2. Branch off `main`.
3. Make your change. Run tests locally in both modes (instructions in module README).
4. Open a PR with a description that answers the four discipline questions explicitly. There's a PR template (TBD) but for now just fill in the four sections by hand.
5. CI will run lint + tests + smoke tests for both modes (TBD — when CI is wired up).
6. A maintainer reviews against `ARCHITECTURE.md` boundaries.

## Skill contributions specifically

Skills are the highest-leverage contributions. Each skill is one folder with a `SKILL.md` (frontmatter + body) and optional `references/`, `scripts/`, `assets/`. See [`skills/README.md`](skills/README.md) for the format.

A good skill contribution:

- Solves a specific recurring task
- Has a clear `description` field that triggers it correctly
- Follows the [`agentic-skill-design`](skills/agentic-skill-design/SKILL.md) PROBE → DECIDE → ACT → REPORT pattern
- Is self-contained (works without the contributor's specific environment)
- Includes at least one usage example

## Code of Conduct

TBD. Defaulting to the [Contributor Covenant](https://www.contributor-covenant.org/) until we adopt one explicitly. Be kind, give credit, assume good faith, no harassment.

## Questions?

- For architecture questions: open a Discussion (preferred) or a GitHub issue with the `architecture` label.
- For bugs: GitHub issue with the `bug` label, including reproduction steps in self-host mode (most accessible to reproduce).
- For feature ideas: open a Discussion first. Major features should start as a one-page design proposal that addresses the four discipline questions.

## License

This project is licensed under the [Apache License, Version 2.0](LICENSE). By contributing, you agree that your contributions are licensed under the same terms.
