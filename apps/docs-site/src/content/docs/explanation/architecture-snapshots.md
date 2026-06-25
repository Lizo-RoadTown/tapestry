---
title: Architecture snapshots
description: What the architecture-snapshot automation is, what it captures, when it fires, and how to recover when it goes missing.
---

The architecture-snapshot automation is one of the more invisible pieces of the discipline stack: it runs at session start, produces a structural picture of your repo, diffs it against the prior baseline, and quietly hands the result to the agent so the agent starts the conversation with a current map of what's been deployed and what changed since last session.

You don't directly interact with it. But two scripts in your `scripts/` directory and one output directory under `docs/` are load-bearing, and if you delete or move them without knowing what they are, the agent loses its architecture awareness at session start.

## What the diff is for

The diff isn't an infrastructure-change report for its own sake. Architecture analysis is one of the **reinforcement mechanisms** Tapestry uses to maintain coordination quality — alongside OTel telemetry (services emit OpenTelemetry → Grafana Cloud), memory, friction analysis, and the rest. The diff's purpose is to surface structural changes that affect coordination — interfaces appearing or disappearing, memory attachment points moving, coordination pathways relocating, friction-prone shapes emerging.

When you read a snapshot diff, the questions to ask are coordination-shaped, not service-shaped:

- What interfaces appeared in this diff? (A new service usually means a new coordination surface the operator and agent will need to learn.)
- What interfaces disappeared? (A removed service usually means a coordination surface the operator was depending on is gone.)
- What interfaces moved? (Code moving between packages often means a coordination surface relocated — agent's mental model may now be wrong.)
- What interfaces split or merged? (A package becoming two packages, or two becoming one, almost always reshapes which agent coordinates with which.)
- What memory attachment points changed? (Memory tagged to a path that no longer exists loses discoverability — the coordination that memory was supporting becomes orphaned.)
- What friction patterns became visible? (Some kinds of drift only show up structurally — a duplicate showing up in two places is a friction signal even before the operator notices it.)
- What coordination pathways changed? (Bridge endpoints, MCP servers, webhooks — these are coordination surfaces, and the diff is where their movement is detected.)

The architecture-analyst narrative (`<timestamp>-narrative.md`) reads the diff and answers these questions in prose. The diff is raw evidence; the narrative is the coordination-shaped interpretation.

## What it produces

Every time you start a Claude Code session in a properly-wired project, the SessionStart hook runs the snapshot pipeline. It produces five files under `docs/architecture-snapshots/`:

| File | What's in it |
|---|---|
| `<timestamp>-snapshot.json` | Machine-readable structural snapshot — deployed services, dependencies, MCP servers, env-var keys, runtime configs. |
| `<timestamp>-snapshot.md` | Human-readable version of the same snapshot, with an embedded mermaid diagram of the system. |
| `<timestamp>-diff.json` | Machine-readable diff against the prior snapshot. |
| `<timestamp>-diff.md` | Human-readable diff. `**No structural changes detected**` when nothing's changed; otherwise a list of what was added/removed/modified. |
| `<timestamp>-narrative.md` | (Sometimes) prose narrative from the `architecture-analyst` agent explaining what changed and why it matters. |

The snapshot pipeline is **deterministic and shape-agnostic** — it auto-detects whether your repo is a monolith, a monorepo, a multi-service backend, a frontend-only site, or some hybrid, and produces a snapshot appropriate to whichever shape it finds. You don't configure it; it figures itself out.

## Where the work actually happens

The thing you have in your repo is NOT the real script. It's a thin wrapper:

```
your-project/scripts/architecture_snapshot.py  ← thin wrapper (~50 lines)
your-project/scripts/architecture_diff.py       ← thin wrapper (~50 lines)
```

Each wrapper looks up the canonical implementation in the `tapestry-patterns` plugin and dispatches to it with your repo root as an argument. The canonical bodies live at:

```
~/.claude/plugins/cache/tapestry/tapestry-patterns/<version>/scripts/architecture_snapshot.py
~/.claude/plugins/cache/tapestry/tapestry-patterns/<version>/scripts/architecture_diff.py
```

This is the Pillar 1 discipline (ONE pattern, ONE home) applied to the snapshot scripts: every project shares the same canonical implementation, so when the canonical evolves, every project gets the improvement on next pull. The per-project wrappers exist only so existing callers (the SessionStart hook, CI, manual `python scripts/architecture_snapshot.py` invocation) keep working — they're a routing layer, not a copy.

If the canonical isn't found, the wrapper writes a clear error pointing you to install the patterns plugin: `/plugin install tapestry-patterns@tapestry`.

## When the snapshot fires

The `tapestry-discipline` plugin's `SessionStart` hook does this on every new conversation:

1. Looks for `scripts/architecture_snapshot.py` in your repo.
2. If it's missing, logs `snapshot_script_absent` and silently no-ops on the snapshot piece. Session still proceeds. **You lose the architecture context but everything else works.**
3. If it's present, runs `python scripts/architecture_snapshot.py`. If the script errors, logs the error and proceeds without the snapshot.
4. If the snapshot succeeded, runs `python scripts/architecture_diff.py` against the most-recent prior snapshot. Diff failure is non-fatal — the new snapshot still exists.
5. If both succeeded, the hook bundles the latest `-narrative.md` (if present) or the `-diff.md` as additional context for the conversation.

The whole pipeline takes 1-3 seconds on a typical repo. It's bounded by a timeout in the hook so it can't hang your session indefinitely.

## Why it's load-bearing

Two reasons:

1. **The agent's architecture awareness compounds over time.** Each session adds another snapshot to `docs/architecture-snapshots/`. The next session's diff has a baseline to compare against. If you delete `docs/architecture-snapshots/` to clean up the directory, the next snapshot has no prior baseline — the diff is empty, and the agent loses the change-detection context. (It still works going forward; you just lose the historical record.)

2. **Drift detection is silent without it.** When you add a new Render service, change a build command, swap an env-var key, or modify the MCP config in `.mcp.json`, the snapshot picks it up automatically and the next session's diff surfaces it. Without the pipeline, those changes happen and the agent has no idea — you're responsible for telling the agent every time. The pipeline is a built-in delta detector that runs without you having to remember.

## What fails (silently) if you remove pieces

| If you delete or move | The pipeline... | The session... |
|---|---|---|
| `scripts/architecture_snapshot.py` | Detects absence, logs `snapshot_script_absent`, no-ops. | Loses snapshot + diff context. Proceeds normally otherwise. |
| `scripts/architecture_diff.py` | Snapshot still runs; diff step is skipped. | Has the snapshot but no diff against prior baseline. |
| `docs/architecture-snapshots/` directory | First post-deletion snapshot recreates the directory. Diff has nothing to compare against (treated as "first ever snapshot"). | Loses historical record. Going forward, the system rebuilds. |
| The canonical scripts in the `tapestry-patterns` plugin cache | Wrapper falls through every fallback path and writes an error. | Hook logs the error and proceeds without snapshot context. |
| The `tapestry-patterns` plugin uninstalled entirely | Wrapper can't find any canonical; errors. | Same as above. Install: `/plugin install tapestry-patterns@tapestry`. |

Each of these is a one-line silent loss. The agent doesn't crash. It just stops seeing the architecture.

## How to set it up

Two thin wrappers + one output directory. Total: under 200 lines, all boilerplate.

The canonical pattern is documented in a real consuming project's PR (commit `2325e67`). Copy the two wrapper files from any existing repo that has them — the reference implementations live in the platform beta repo's `scripts/architecture_*.py` — then commit the empty `docs/architecture-snapshots/` directory with a `.gitkeep`.

First run produces the first snapshot. From there, every session adds another and diffs against the prior.

If you don't have the canonical scripts available (`tapestry-patterns` plugin not installed): `/plugin install tapestry-patterns@tapestry`, then restart the project's Claude Code session.

## How to verify it's working

After a fresh session start:

```sh
ls docs/architecture-snapshots/ | tail -5
```

You should see at least one set of `<timestamp>-snapshot.json/md` files dated to your current session. If they're missing, the SessionStart hook isn't running the pipeline. See [Recover from common failures](/how-to/recover-from-common-failures/) for the diagnosis.

You can also run the snapshot manually any time:

```sh
python scripts/architecture_snapshot.py
python scripts/architecture_diff.py
```

If the wrapper exits 127 with "canonical architecture_snapshot.py not found", install the patterns plugin.

## Related

- [The discipline stack](/explanation/discipline-stack/) — how the snapshot fits with the other pieces
- [The plugins](/explanation/plugins/) — the SessionStart hook in the `tapestry-discipline` plugin is what runs the pipeline
- [Load-bearing files](/reference/load-bearing-files/) — file-by-file reference
- [Recover from common failures](/how-to/recover-from-common-failures/) — symptoms when this breaks
