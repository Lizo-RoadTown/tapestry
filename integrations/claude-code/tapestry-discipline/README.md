# tapestry-discipline

Claude Code plugin. The discipline wrapper for Liz's Claude Code sessions in `Make_Skills`, `the-loom`, `project-starter`-scaffolded repos, and (as of v0.1.12) any repo that sets `LOOM_PROJECT_ID` in its `.env` — the explicit per-project opt-in. Auto-injects PROBE-first behavior, file:line citation enforcement, dev-tooling-vs-runtime distinction, and friction-as-memory writing. Hook scripts inject reminders on every prompt and audit tool args before writes.

**v0.1.6 (this version) also emits each hook event as an OTLP log** to the-loom's Grafana Cloud LGTM stack — cross-machine observability for what your Claude Code sessions are doing.

## History

This plugin has had three canonical homes:

| Period | Name | Source repo | Marketplace |
| --- | --- | --- | --- |
| 2026-05-22 → 2026-05-26 (v0.1.0–0.1.5) | `make-skills-discipline` | `Lizo-RoadTown/claude-skills-marketplace/plugins/` | `lizo-skills` |
| 2026-05-26 → 2026-06-22 (v0.1.6–0.1.15) | `loom-discipline` | `Lizo-RoadTown/the-loom/adapters/claude-code/` | `lizo-loom` |
| 2026-06-22 → today | **`tapestry-discipline`** | `Lizo-RoadTown/tapestry/integrations/claude-code/` (this directory) | `tapestry` |

The 2026-05-26 move folded the plugin into the-loom under the name `loom-discipline` (added OTLP log exporter alongside the existing `hooks.jsonl` local write). The 2026-06-22 consolidation (PR #42) renamed it to `tapestry-discipline` and lifted the source into the tapestry monorepo. The prior install commands (`loom-discipline@lizo-loom`) still resolve during the transition window.

## Install locally

```bash
# In any Claude Code session:
/plugin marketplace add Lizo-RoadTown/tapestry
/plugin install tapestry-discipline@tapestry

# OR symlink directly into Claude's plugin dir for development:
ln -s C:/Users/Liz/tapestry/integrations/claude-code/tapestry-discipline ~/.claude/plugins/tapestry-discipline
```

After install, restart Claude Code so the loader binds the new plugin.

## What it observes

Every hook fire writes to two outputs:

1. **Local** — `~/.claude/logs/hooks.jsonl` (or `${CLAUDE_PROJECT_DIR}/.claude/logs/hooks.jsonl` if set). Append-only JSON lines. Source of truth.
2. **Remote** — OTLP/HTTP log to Grafana Cloud, if `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` are set in env. Best-effort; failures land at `~/.claude/logs/hook-otel-errors.log`.

Each event is one record:

```json
{
  "ts": "2026-05-26T08:00:00+00:00",
  "hook": "PreToolUse",
  "phase": "end",
  "scope_in": true,
  "action": "reminder_injected",
  "exit_code": 0,
  "elapsed_ms": 12,
  "note": "no citation found"
}
```

## Env vars (for OTel export)

Standard OTel SDK env vars. Set anywhere your Claude Code session inherits — `.env`, shell rc, etc. Liz's setup currently:

| Var | Where | What |
| --- | --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `the-loom/.env` (gitignored) + Render env group | The OTLP/HTTP endpoint URL (Grafana Cloud) |
| `OTEL_EXPORTER_OTLP_HEADERS` | same | `Authorization=Basic%20<base64(instance_id:token)>` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | same (inline `http/protobuf` in render.yaml) | The wire protocol — we use JSON though; this var documents the OTel SDK convention for downstream services that DO use the SDK |
| `OTEL_RESOURCE_ATTRIBUTES` | same (inline `service.namespace=loom,deployment.environment=dev`) | Namespace + environment tags |
| `OTEL_SERVICE_NAME` | per-source (`tapestry-discipline` for this plugin) | Distinguishes telemetry streams |

If any of these are unset, the plugin still works — only the OTel export skips. The local jsonl write is unconditional.

## What it does NOT do

- Block any Claude Code action (hooks emit reminders only — no `permissionDecision: deny`)
- Modify the agent's response content (only injects `additionalContext` per `hooks.json` config)
- Phone home for telemetry beyond what you've configured (no hidden endpoints)

## Files

```
tapestry-discipline/
├── .claude-plugin/plugin.json    # plugin manifest (name, version, description)
├── README.md                      # this file
├── hooks/
│   ├── hooks.json                # which hooks fire when (SessionStart, UserPromptSubmit, PreToolUse, Stop)
│   └── run-python.mjs            # Node bridge to invoke Python scripts under Claude Code's hook subprocess pattern
├── scripts/
│   ├── _observability.py         # shared log_event() helper — local jsonl + OTLP push (this is the file v0.1.6 patched)
│   ├── session_start.py          # SessionStart hook
│   ├── user_prompt_submit.py     # UserPromptSubmit hook
│   ├── pre_tool_use.py           # PreToolUse hook (Edit|Write|MultiEdit)
│   └── stop_audit.py             # Stop hook
├── skills/tapestry-discipline/
│   └── SKILL.md                  # discipline rules the harness surfaces on every relevant message
├── agents/
│   └── architecture-analyst.md   # subagent invoked by /architecture-report or SessionStart
├── commands/
│   └── architecture-report.md    # slash command for on-demand architecture report
└── tests/
    └── test_pre_tool_use.py      # 14+ unittest cases (citation regex, dual-mode gating, scope check, subprocess regression)
```

## Tests

```bash
cd integrations/claude-code/tapestry-discipline
python -m unittest tests.test_pre_tool_use -v
```

19/19 should pass (v0.1.5 baseline + future tapestry-discipline-specific additions).

## See also

- `docs/proposals/2026-05-25-mvp-repo-layout.md` — adapter-per-agent-kind pattern under v3
- `docs/plans/2026-05-25-the-loom-roadmap-v2.md` — Phase 1b explanation
- `docs/INTER_AGENT_DIALOGUE.md` — MS-agent's notes on the move + OTel patch rules
