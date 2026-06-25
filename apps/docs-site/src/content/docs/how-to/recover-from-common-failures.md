---
title: Recover from common failures
description: Symptom-to-fix table for the failure modes that happen when a discipline-stack piece goes missing.
---

The discipline stack fails silently. The agent doesn't crash — it just stops doing things you expected it to do. This page is the symptom-to-cause-to-fix table for the failures we've actually hit.

If your symptom isn't in the table, see [The discipline stack](/explanation/discipline-stack/) for the conceptual map and [Load-bearing files](/reference/load-bearing-files/) for the file-by-file reference.

## Quick triage: what's working vs not

Before diagnosing, confirm what the agent CAN see:

| Quick check | What it tells you |
|---|---|
| `/mcp` in Claude Code | Lists active MCP servers. If `loom-memory` is not there, the MCP isn't wired. |
| Look at the top of your most recent message | If you don't see `[loom-discipline] Discipline check: PROBE files before asserting ...`, the UserPromptSubmit hook isn't firing. |
| Look at the very start of the conversation | If you don't see an auto-recall block of past memories, the SessionStart hook isn't firing. |
| `/plugin list` | Shows enabled plugins for this project. If `tapestry-discipline@tapestry` is not there or not enabled, the plugin isn't running. |
| `cat .mcp.json` | Shows declared MCP servers in your project. |
| `cat .claude/settings.json` | Shows enabled plugins for this project. |
| `cat .env \| grep LOOM_PROJECT_ID` | Shows the project ID the hooks scope against. |

## Symptom → fix

### Symptom: The agent says "I don't have memory tools available"

**Cause:** Neither the `tapestry-discipline` plugin nor your `.mcp.json` is wiring the `loom-memory` MCP server.

**Fix:**

1. Verify the plugin is enabled in `.claude/settings.json` — should contain `"tapestry-discipline@tapestry": true`.
2. If not, add it. Then **fully restart Claude Code** in this repo.
3. As belt-and-suspenders, add the MCP block to `.mcp.json` as described in [Set up a new project, Step 4](/how-to/set-up-a-new-project/).
4. Restart Claude Code again to pick up the `.mcp.json` change.

**How to confirm fixed:** `/mcp` in Claude Code lists `loom-memory`. Ask the agent to `memory_recall` something — it should succeed.

### Symptom: The agent doesn't recall any context at session start

**Cause:** The SessionStart hook isn't firing. Most likely the plugin isn't enabled, or the `LOOM_PROJECT_ID` env var is missing.

**Fix:**

1. Check `.claude/settings.json` — plugin enabled?
2. Check `.env` — `LOOM_PROJECT_ID` set to your project ID?
3. If both are present and you still don't see recall, the issue may be that no memories tagged for your project exist yet (this is normal for the first session of a new project — the recall block will be empty until you start writing memories).

**How to confirm fixed:** Start a new Claude Code session. The conversation should begin with an `additionalContext` block showing past memories.

### Symptom: The discipline reminder doesn't appear at the top of my messages

**Cause:** The `UserPromptSubmit` hook isn't firing. Same root causes as SessionStart: plugin not enabled, or LOOM_PROJECT_ID missing, or scope gate not matching.

**Fix:** Same as above. Plugin enabled in settings.json + LOOM_PROJECT_ID set + restart Claude Code.

**How to confirm fixed:** Send any message. The top should show `[loom-discipline] Discipline check: PROBE files before asserting (cite file:line). Distinguish dev-tooling (...) from runtime (...). Save corrections as feedback memory immediately. CORE DIRECTIVE 1 ...`.

### Symptom: The agent stops citing file:line and starts making up things

**Cause:** The PROBE-discipline reminder isn't firing. Same as above. Without the per-turn reminder, the agent can drift toward training-data defaults rather than checking actual files.

**Fix:** Confirm `UserPromptSubmit` hook is firing (look for the reminder line). If not, fix per the previous symptom.

**Additional:** if the reminder IS firing but the agent is still drifting, this is a different problem — the agent isn't internalizing the rule despite seeing it. Save a feedback memory describing the drift and reinforce in conversation. Drift that recurs across sessions can be reinforced by writing a stronger feedback memory.

### Symptom: The agent doesn't know what role it plays in this project

**Cause:** `.project-intelligence/<project-id>/` is missing, deleted, or has the wrong project ID.

**Fix:**

1. Verify the directory exists at the repo root: `ls -la .project-intelligence/`
2. Confirm the subdirectory matches your `LOOM_PROJECT_ID`: `.project-intelligence/your-project-id/`
3. If missing, recreate it per [Set up a new project, Step 6](/how-to/set-up-a-new-project/).

**How to confirm fixed:** Ask the agent "what role do you play in this project?" — it should reference the `agent-profile.json` content.

### Symptom: SessionStart says "snapshot scripts absent" or there's no architecture context at session start

**Cause:** `scripts/architecture_snapshot.py` and/or `scripts/architecture_diff.py` are missing from your repo. The SessionStart hook reads from these and silently no-ops if they're absent.

**Fix:** Add the thin wrapper scripts that dispatch to the canonical implementations in the `tapestry-patterns` plugin. See [the wrapper-pattern reference (consuming project PR)](https://github.com/Lizo-RoadTown/sde-extraction/commit/2325e67) for the canonical example. The wrappers are a few lines each.

**How to confirm fixed:** Start a new session. The SessionStart context should include an architecture narrative (or "no structural changes" diff against the prior baseline).

### Symptom: Memories I write are tagged for the wrong project

**Cause:** `LOOM_PROJECT_ID` in `.env` drifted from the expected value (e.g., `sde-extraction` instead of `sde-extraction-dev`, or empty, or set to a different project's ID).

**Fix:**

1. Open `.env` and confirm the value matches what `.project-intelligence/` and your `agent-profile.json` expect.
2. If you've been writing memories with a wrong tag, those memories exist but are tagged for the wrong project. They will recall in the wrong contexts. Decide whether to:
   - Leave them as-is (low-volume drift, manageable)
   - Migrate them: `memory_recall` them, copy content, `memory_write` with correct tag, `memory_delete` the old (high-volume drift)

**How to confirm fixed:** New memory writes after the fix get the right tag. Verify with `memory_list project_tags=["correct-project-id"]`.

### Symptom: `/v1/recall` REST endpoint returns 401 / 403 / 500

**Cause:** The `loom-memory` MCP HTTP transport requires a Bearer JWT for hosted-multitenant mode. For self-host mode (no JWT), it falls back to a deterministic UUID. A 401 means a malformed bearer was sent OR the server can't verify it (e.g., env var unset on the server side). A 500 means the agent-context Render service is down or degraded.

**Fix:**

1. Check the agent-context service status: `curl https://your-memory-host.example.com/health` should return `{"status":"ok","service":"memory-mcp"}`.
2. If it's down, the issue is on the platform side, not your project. The Tapestry-agent or loom-agent operator needs to look. Report it.
3. If the service is up and you're getting 401, you might be sending a bearer that the server can't verify. Removing the bearer and falling back to self-host mode is the usual fix for individual operators.

### Symptom: After restarting Claude Code, hooks still don't fire

**Cause:** Plugin cache staleness OR settings.json typo OR the marketplace isn't actually registered.

**Fix:**

1. Confirm marketplace registration: `/plugin marketplace list` — `tapestry` should appear.
2. If not: `/plugin marketplace add Lizo-RoadTown/tapestry`.
3. Force re-install the plugin: `/plugin remove tapestry-discipline@tapestry`, then `/plugin install tapestry-discipline@tapestry`.
4. Restart Claude Code again.
5. As a last resort, check the plugin cache directly: `ls ~/.claude/plugins/cache/tapestry/tapestry-discipline/` — should show the latest version directory.

### Symptom: The architecture-snapshot scripts ARE present but the hook still doesn't run them

**Cause:** Could be missing Python dependencies for the canonical scripts in `tapestry-patterns`, or `tapestry-patterns` not installed.

**Fix:**

1. Install the patterns plugin: `/plugin install tapestry-patterns@tapestry`.
2. Confirm the wrappers in your `scripts/` point at the canonical scripts in the patterns plugin cache.
3. Try running the wrapper manually: `python scripts/architecture_snapshot.py` — should produce a JSON+MD snapshot in `docs/architecture-snapshots/`.

## What to do when your symptom isn't here

1. Run the quick triage table at the top of this page. Identify which hook ISN'T firing.
2. Read the relevant section of [The discipline stack](/explanation/discipline-stack/) — it explains what each hook IS supposed to do.
3. Cross-reference [Load-bearing files](/reference/load-bearing-files/) to confirm every load-bearing file is present and correct.
4. If you've identified that something is missing but you don't know how to fix it, ask whoever operates your platform deployment. Diagnostic info that helps: the output of `/mcp`, `/plugin list`, `cat .mcp.json`, `cat .claude/settings.json`, `cat .env | grep LOOM_PROJECT_ID`.

