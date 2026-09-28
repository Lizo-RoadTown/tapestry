---
date: 2026-09-27
kind: docs
area: docs
prs: []
adrs: [0005]
memory:
supersedes:
---

# Document `tapestry deploy` and the SessionStart auth probe

**What:** Added the docs that were gated on the `tapestry deploy` CLI (PR #175) and the SessionStart memory auth probe (PR #177) landing on `main`. New: a how-to [Deploy a service to Render](../../apps/docs-site/src/content/docs/how-to/deploy-a-service.md), a [CLI commands reference](../../apps/docs-site/src/content/docs/reference/cli-commands.md) covering every `tapestry` subcommand, and [ADR 0005](../adr/0005-deploy-imperative-cli-vs-blueprint.md) recording why an imperative `tapestry deploy` exists alongside the declarative `render.yaml` Blueprint. Extended: the recovery how-to gained a symptom entry for the new "AUTH REJECTED" CONCRETE-RULE violation (host reachable but token rejected — the `/health`-only blind spot that hid the August 2026 memory outage), and `packages/cli/README.md` gained the `deploy` command row. Both new docs-site pages were registered in the sidebar.

**Why it matters:** The deploy CLI and the auth probe shipped without operator-facing docs; someone hitting the AUTH REJECTED violation or wanting to deploy a service had no page to turn to. Diátaxis-classified: one how-to (recipe), one reference (exhaustive command list), one ADR (the decision), and an extension to an existing how-to.

**Follow-ups / gates:** none. Deeper explanation-tier additions about the auth probe (discipline-stack / why-memory-is-built-this-way) are deferred as lower priority.
