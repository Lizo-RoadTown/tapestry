---
title: Verify it worked
description: Four quick checks confirming the platform is wired correctly. Each check has a one-line fix path when it fails, plus a link into the relevant Systems page for deeper troubleshooting.
---

Four checks. Each takes under a minute. If any fails, the next-action link goes straight to the right page.

## 1. Memory MCP is reachable

In a fresh Claude Code session, start typing. The session header should include an auto-recall block (it may be empty if the project has no memories yet — empty is fine; the block being present is what matters).

If the session header shows `[loom-memory · MCP UNREACHABLE: HTTP 404]`:

- **First** — wait 30-60s and restart Claude Code. The Memory MCP runs on Render; cold starts take a moment.
- **Still failing** — see [Memory troubleshoot](/systems/memory/#troubleshoot).

## 2. Discipline hooks are firing

Send any prompt in the Claude Code chat. The agent's response context should include a `[loom-discipline] Discipline check:` line — that's the `UserPromptSubmit` hook injecting PROBE rules.

If the line doesn't appear:

- **First** — check `.claude/settings.json` has both `tapestry-discipline` and `tapestry-patterns` plugins enabled (re-run `tapestry onboard` to merge them in if absent).
- **Still failing** — restart Claude Code (the plugin loader binds at session start; mid-session installs don't hot-swap hooks).
- See [Recover from common failures](/how-to/recover-from-common-failures/) for the full diagnostic flow.

## 3. Plugins are loaded

Type `/plugin list` in the Claude Code chat. Output should include `tapestry-discipline@tapestry` and `tapestry-patterns@tapestry`.

If they're missing:

```text
/plugin marketplace add Lizo-RoadTown/tapestry
/plugin install tapestry-discipline@tapestry
/plugin install tapestry-patterns@tapestry
```

Then reload the VS Code window.

## 4. (Optional) OTel telemetry is emitting

This is optional — local `~/.claude/logs/hooks.jsonl` writes are unconditional; OTel emission is the cross-machine extension.

If you've set `OTEL_EXPORTER_OTLP_ENDPOINT` + `OTEL_EXPORTER_OTLP_HEADERS` in your `.env`:

- Trigger any tool call in Claude Code.
- Check `~/.claude/logs/hook-otel-errors.log` — empty (or absent) means OTel pushes are succeeding.
- If your operator has shared Grafana Cloud access, open Loki and query `{service_name="tapestry-discipline"}`; recent entries should appear within seconds.

If `hook-otel-errors.log` has entries, see [Telemetry troubleshoot](/systems/telemetry/#troubleshoot).

## All four passed — what's next

You're ready for your [first Observatory visit](/start/first-observatory-visit/).

## All four failed at once

This usually means one of three things:

- `tapestry onboard` was never run, or was run from the wrong directory. Re-run from the project root.
- Claude Code wasn't reloaded after the install. `Cmd+Shift+P` → `Developer: Reload Window`.
- The platform itself is down. Check [tapestry-khaki.vercel.app](https://tapestry-khaki.vercel.app/) — if the docs site loads, the platform is up. If it doesn't, the operator running the platform needs to investigate Render dashboard.

## Related

- [Recover from common failures](/how-to/recover-from-common-failures/) — the full diagnostic catalog
- [Memory](/systems/memory/), [Telemetry](/systems/telemetry/) — component-level troubleshooting
- [Load-bearing files](/reference/load-bearing-files/) — what each config file in your repo holds
