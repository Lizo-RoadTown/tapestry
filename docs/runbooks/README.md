# Tapestry runbooks

One runbook = one operational task. Named `<verb>-<noun>.md`.

These are operational walkthroughs the operator (or future agent) runs end-to-end. Not background documentation, not architecture explanation — actions.

## Current runbooks

- [`dev-experience-observability.md`](./dev-experience-observability.md) — bring up the Grafana + Loki + Promtail stack locally; verify dashboards load against the local stack.
- [`grafana-dashboard-rebuild.md`](./grafana-dashboard-rebuild.md) — rebuild a Grafana dashboard from its JSON spec; recovers from accidental UI edits or provisioning drift.

## Convention

When adding a runbook:

1. **Title is the action.** "Deploy X", "Rebuild Y", "Investigate Z".
2. **First section is the failure mode the runbook resolves.** Operator should be able to identify "is this my situation?" in one read.
3. **Steps are numbered, copy-pasteable, and verified.** Cite file paths + line numbers where they exist. Cite Render service names verbatim.
4. **End with a "verify success" step.** What's the check that proves the runbook worked?

Runbooks live next to architecture docs (`docs/architecture/`) and proposals (`docs/proposals/`) but serve a different purpose: arch docs explain why, proposals decide what, runbooks tell you how to do the thing right now.
