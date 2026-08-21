# Published-artifacts audit — PyPI packages + Claude Code plugins

**Date:** 2026-08-20
**Scope:** Everything Tapestry has published to the outside world — the PyPI package(s) and the Claude Code plugin marketplaces — audited against current repo state after the loom→tapestry migration and the memory-endpoint auth gate.
**Method:** four parallel auditor agents, one per surface (published `tapestry-cli` wheel diff; PyPI naming/ownership; current `tapestry` marketplace plugins; legacy `lizo-loom` + `lizo-skills` marketplaces).

## Root cause tying most findings together

The memory endpoint (`https://loom-agent-context.onrender.com/mcp/memory/`) just gained an auth gate (clients send `Authorization: Bearer ${TAPESTRY_MEMORY_API_KEY}`). **Every published artifact predates that change**, so the recurring defect is: published code either onboards projects without the auth header, or registers the memory server without auth — both fine while anonymous access is open, both broken the moment it closes. The audit is therefore coupled to the security rollout: the BLOCKER items below should land **before** `LOOM_ALLOW_ANONYMOUS_SELF_HOST=0` is flipped.

---

## BLOCKERS

### B1 — Published `tapestry-cli` 0.1.3 onboards projects with no auth header
The repo's `packages/cli/tapestry_cli/init.py:244-248` adds `"headers": {"Authorization": "Bearer ${TAPESTRY_MEMORY_API_KEY}"}` (commit `7e99eee`, 2026-08-20), but the version was **not bumped** — PyPI 0.1.3 was built from `f4c7b3b` and lacks the header. It is the only content difference between the published wheel and the repo. Both `tapestry init` and `tapestry onboard` (`onboard.py:99`) write header-less `.mcp.json`.
**Consequence:** every project onboarded by the live CLI loses memory access when anonymous is closed.
**Action:** bump `packages/cli/pyproject.toml` to **0.1.4** and republish. Fold in B2.

### B2 — `tapestry version` reports the wrong version (stuck at 0.1.0)
`tapestry_cli/__init__.py:7` is `__version__ = "0.1.0"` (consumed by `cli.py:55`), unchanged in both published and repo. Pre-existing, not drift.
**Action:** set to `0.1.4` in the same republish; ideally read from installed package metadata so it can't drift again.

### B3 — `loom-sdk` cannot be published by the operator (name squatted)
`packages/sdk/python/pyproject.toml:6` declares `name = "loom-sdk"`, but PyPI `loom-sdk` belongs to an unrelated project ("MetaCognition", loom.getmetacognition.com). `twine upload` will 403. A *third* unrelated "Loom" (TeamEcho-AI) owns `loom-memory` too. The `loom-*` PyPI namespace is contested and partly lost.
**Action:** rename distribution to `tapestry-sdk` (available) before any publish; update the dep pin in `engine/agency-to-structure/python/pyproject.toml:15-16`.

### B4 — Legacy `loom-discipline` plugin is auth-less, double-fires, and masks its own failure
`loom-discipline@lizo-loom` (in the retired `the-loom` repo) is enabled alongside `tapestry-discipline` in every Tapestry-scoped session:
- Registers `loom-memory` MCP with **no auth header** (`the-loom/adapters/claude-code/loom-discipline/.claude-plugin/plugin.json:27-32`) → 401 when anon closes. Also collides with tapestry-discipline's `loom-memory` server name.
- Its startup reachability check probes unauthenticated `GET /health` (`session_start.py:93-160`) → prints "memory reachable" while the gated MCP transport actually rejects it. **Masks the CORE DIRECTIVE 1 failure it exists to catch.**
- Byte-identical `hooks.json` to tapestry-discipline → **all four hooks double-fire** (two SessionStart recalls, two observers racing on the same `.project-intelligence/workflow-candidates/*.json`, doubled telemetry).
The `[loom-discipline]` runtime identity is already preserved *inside* tapestry-discipline (`skills/loom-discipline/SKILL.md`), so nothing is lost by disabling the legacy one.
**Action:** disable `loom-discipline@lizo-loom` and `liz-patterns@lizo-skills` in `~/.claude/settings.json`. Keep `onboarding-psychologist` + `ai-agents-architect` (self-contained, no equivalent).

---

## SHOULD-FIX

### S1 — Adopt a single `tapestry-*` PyPI namespace; claim free names before more squatting
Rename before first publish: `loom-auth`→`tapestry-auth` (available), `agency-to-structure`→`tapestry-engine` (available, currently unnamespaced). The auth pyproject itself already flags the rename (`packages/auth/pyproject.toml:16-20`). Defensively claim now (placeholder 0.0.0): `tapestry-sdk`, `tapestry-auth`, `tapestry-engine`, `tapestry-docs-mcp`, `tapestry-loom`, and `loom-agent-context` (still free; the memory-client name `loom-memory` is not). `tapestry-cli` + `tapestry-docs-mcp` are the clean model (operator-owned, complete metadata).

### S2 — `tapestry-discipline` bundles a docs MCP server that won't resolve for external installs
`plugin.json:34-37` declares `"tapestry-docs": {"command":"python","args":["-m","docs_mcp"]}`, but `docs_mcp` lives at `services/docs-mcp/`, not inside the plugin. Any consuming project gets `ModuleNotFoundError`. "End-to-end verified" (`58c5a89`) only held inside the monorepo.
**Action:** bundle `docs_mcp` under the plugin, or ship it as a pip dependency and document it. Bump discipline to 0.1.18 on fix.

### S3 — Dead `skills_private/` citations in operator-facing hook text (`tapestry-discipline`)
`session_start.py:184` (the `*** CONCRETE-RULE VIOLATION DETECTED ***` block operators actually see) cites `skills_private/concrete-rule/SKILL.md` — no such path. `stop_audit.py:123,142,238` and `observer.py:136,238` cite `skills_private/agentic-upskilling/SKILL.md`. Real locations: `integrations/claude-code/skills/concrete-rule/SKILL.md` and `tapestry-patterns/agents/agentic-upskilling.md`.
**Action:** fix the citations; either fold `concrete-rule` into the plugin or repoint the hook. (`docs/CORE_DIRECTIVES.md` citations are now valid — created in `7850a8f`.)

### S4 — Stale "Make_Skills"/"the-loom" branding in the canonical patterns skills (`tapestry-patterns`)
These are the ONE-home skills, so the branding is authoritative and wrong: `skills/proposal-authoring/SKILL.md:3,8,94,150,185`, `skills/design-evaluation/SKILL.md:41,43`, `skills/open-source-documentation/SKILL.md:8,143`. Also `agents/agentic-upskilling.md:7,16-18,49,51-52,68` and `README.md:19,43,74` point at retired `the-loom/services/self-observer/` and `loom-architecture-registry.onrender.com` as live implementations.
**Action:** sweep the branding; repoint or caveat the retired-repo references. Content edit in place; republish optional.

### S5 — `lizo-loom` marketplace metadata is stale/misleading
`the-loom/.claude-plugin/marketplace.json:16-17` pins `loom-discipline` at 0.1.13 (on-disk plugin.json says 0.1.15) and still calls lizo-loom "the canonical marketplace" while CLAUDE.md names `tapestry-discipline` canonical. Source repo (the-loom) is retired but still an enabled marketplace source.
**Action:** rewrite the manifest to redirect to the tapestry marketplace, or remove the plugin entry.

### S6 — `liz-patterns` ships a stray nested dev marketplace + stale registry URL
`claude-skills-marketplace/plugins/liz-patterns/.claude-plugin/marketplace.json` is a second marketplace (`liz-patterns-dev`, v0.1.0) nested inside the plugin — a dev artifact that shouldn't ship. `plugins/liz-patterns/agents/agentic-upskilling.md:49` hardcodes `loom-architecture-registry.onrender.com/candidates`.
**Action:** remove the nested marketplace file; treat liz-patterns as deprecated-with-redirect to tapestry-patterns (it lags at 0.1.1 vs 0.1.2 and duplicates the names).

---

## ALREADY RESOLVED / NO ACTION (reconciliation)

- **Auditor C flagged the unconditional `Bearer ` header as breaking self-host-no-key mode.** This is **already fixed** by PR #127 (merged `12cbb94`, deploying): the server now treats an empty/whitespace-stripped Bearer as anonymous, not malformed. Once #127 deploys, the static manifest header is safe when the key is unset. No plugin change needed for this specific point.
- **tapestry marketplace plugin versions are in sync** — discipline 0.1.17 and patterns 0.1.2 match their manifests (`plugin.json` vs `marketplace.json`).
- **`[loom-discipline]` runtime label is intentional** (preserved-identity contract; every hook string, OTel service.name, observer actor). Do NOT rename.
- **`tapestry-cli` metadata/URLs are clean** — correct name, `Requires-Python >=3.10`, MIT, all three project_urls, doc URL `tapestry-khaki.vercel.app`, no personal endpoint or email.
- **`onboarding-psychologist` + `ai-agents-architect`** (lizo-skills) — self-contained knowledge skills, no dead infra, no tapestry equivalent. Keep.

---

## Recommended sequence

1. **(couples to security rollout, do before the anon flip)** Disable the two legacy plugins in settings.json [B4]; republish `tapestry-cli` 0.1.4 with the auth header + version fix [B1/B2].
2. **Naming decision** [B3/S1]: commit to `tapestry-*`; rename `loom-sdk`/`loom-auth`/`agency-to-structure`; claim free names defensively.
3. **Plugin fixes** [S2/S3]: bundle docs_mcp, fix dead `skills_private/` citations; bump discipline to 0.1.18.
4. **Content sweeps** [S4/S5/S6]: brand/URL cleanup in tapestry-patterns skills; redirect the legacy marketplaces.
5. Separately (already flagged, not part of this audit): rotate the plaintext Render API token in `the-loom/.mcp.json`.
