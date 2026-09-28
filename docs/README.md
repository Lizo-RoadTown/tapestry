# `docs/`

The documentation for Tapestry. This page is a map of what lives where.

Start with [`CORE_DIRECTIVES.md`](CORE_DIRECTIVES.md) — the canonical directive set (D1–D3) that governs every session in this repo. The public docs site renders much of this content at [tapestry-khaki.vercel.app](https://tapestry-khaki.vercel.app/) (source under [`../apps/docs-site/`](../apps/docs-site/)).

## Subfolders

| Folder | What's in it |
|---|---|
| [`adr/`](adr/) | Architecture Decision Records — numbered, immutable decisions (e.g. observer topology, cutover sync). |
| [`architecture/`](architecture/) | The canonical system model — start at [`architecture/UMBRELLA.md`](architecture/UMBRELLA.md). |
| [`migration/`](migration/) | The migration approach: legacy-repo inventory, import map, what-to-keep, master checklist. |
| [`migration-cicd/`](migration-cicd/) | Migration CI/CD — pipeline architecture, testing strategy, toolkit design, and per-step runbooks. |
| [`runbooks/`](runbooks/) | Operational runbooks (onboarding a project, MCP clients, observability, incident investigations). |
| [`playbook/`](playbook/) | Repeatable playbooks, including migration playbooks. |
| [`canon/`](canon/) | Canonical framing documents (e.g. user/agent coordination-reinforcement). |
| [`plans/`](plans/) | Dated planning documents for multi-step work (migration readiness, observer-capacity build sequence, etc.). |
| [`proposals/`](proposals/) | Proposals under discussion. |
| [`reference/`](reference/) | Reference material (platform dependencies, lookups). |
| [`how-to/`](how-to/) | Task-oriented how-to guides. |
| [`changelog/`](changelog/) | The change trail — one file per notable change (what/when/why/where it now lives). |
| [`architecture-snapshots/`](architecture-snapshots/) | Generated architecture snapshots + narrative reports. |
| [`audits/`](audits/) | Point-in-time audits. |
| [`research/`](research/) | Research notes backing decisions. |
| [`session-reports/`](session-reports/) | Session-end upskilling reports (CORE DIRECTIVE 3). |
| [`maintenance/`](maintenance/) | Maintenance notes and procedures. |
| [`assets/`](assets/) | Images and other doc assets. |
| [`archive/`](archive/), [`_archive/`](_archive/) | Superseded material kept for reference. |
