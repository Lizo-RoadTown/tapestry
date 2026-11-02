---
name: device-coordination
description: Use when about to make a change that differs per machine or crosses the operator's devices — bumping/updating a Claude Code plugin, running a machine catch-up, editing installed_plugins.json / ~/.claude.json / ~/.claude/settings.json / a project .mcp.json, or any per-repo config — on a repo shared across two or more machines (e.g. tapestry on MINIPC-T9CJY + Poppytart), and at session start on such a shared repo. Symptoms: "the other machine", "my laptop vs pc", plugins stale or mismatched between devices, "plugins aren't working on this laptop", an update on one device breaking the other, coordinating two sessions via loom-memory.
---

# Device coordination

## Core principle

The operator runs the same repo (`tapestry`) on **multiple machines** — e.g. `MINIPC-T9CJY` (user `Liz`) and `Poppytart` (user `LizO5`). Some state is **shared via git**; some is **per-machine and invisible to the other device**. A change made on one device silently breaks or diverges the other unless it is coordinated. loom-memory is the shared channel: **PROBE device state → DECIDE if the change crosses devices → ACT safely → RECORD a handshake.**

## Shared vs per-machine (the crux)

| Shared via git (both devices get it) | Per-machine, NOT shared |
|---|---|
| Repo contents, tracked `.claude/settings.json`, plugin **source** + version in the marketplace | Installed plugin versions (`installed_plugins.json`, user scope), the marketplace **clone**, `~/.claude/settings.json` env (the 43-char key), `~/.claude.json`, `.env`, plugin **cache** |

A plugin bump merges into git instantly but is **not live** on any machine until that machine runs `catch-up-machine.ps1` + restarts. That gap is where devices diverge.

## PROBE — read device state before deciding

```bash
hostname                                              # WHICH machine am I? (never identify by username)
git -C <repo> rev-list --count HEAD..origin/main      # repo commits behind
grep -h '"version"' <repo>/integrations/claude-code/*/.claude-plugin/plugin.json   # target plugin versions
# installed vs target: read ~/.claude/plugins/installed_plugins.json (per-plugin, per-scope version)
# ~/.claude.json loom-memory Authorization: env-ref ${TAPESTRY_MEMORY_API_KEY} (good) vs literal JWT (check expiry)
```
Then `memory_recall(context="device coordination handshake", project_tags=["tapestry"])` and read the newest `coord-<device>-<date>` record for what the **other** device changed or is mid-doing.

## DECIDE

| Question | If yes |
|---|---|
| Does the change differ per machine or touch shared plugin/marketplace/config? | It **crosses devices** — coordinate + record. |
| Is another device mid-work on the same surface (per the latest `coord-*` handshake)? | **Stop** — sequence behind it (see Stop conditions). |
| Is this device behind (repo or plugins)? | Catch it up first (`git pull`; `scripts/catch-up-machine.ps1` + restart). |

## ACT

- **Per-machine drift** (stale repo/plugins) → `git pull`; `scripts/catch-up-machine.ps1`; restart Claude Code. Follow **`docs/maintenance/keeping-in-sync.md`** — the canonical propagation checklist.
- **Registry hygiene** (stale/case-duplicate rows in `installed_plugins.json`) → back it up, keep user-scope rows only; project rows regenerate at the current version on restart. See the runbook memory below.
- **A plugin bump you are shipping** → bump BOTH `.claude-plugin/marketplace.json` and the plugin's `plugin.json` (the `plugin-version-check.yml` guard requires they match), add a `docs/changelog/` entry, open the PR — **then RECORD** that every other device must catch up.

## Stop conditions — coordinate, don't barrel through

- Another device's latest handshake says it is **mid-work** on the same plugin/config → sequence behind it; don't ship a concurrent bump.
- A change that would leave the **other device stale in a breaking way** (e.g. a bump the other device needs but hasn't pulled) → land it, but RECORD the required catch-up loudly.
- Irreversible or global-blast changes (rotating the shared key, a Render flip like `LOOM_ALLOW_ANONYMOUS_SELF_HOST`) → confirm both devices are ready first.

## RECORD — always write a handshake

After any device-crossing change, `memory_write` a `coord-<device>-<date>` record (`record_type: project`, `project_tags: ["tapestry"]`):

- **This device** (hostname + user), **what changed** (repo commit, plugin versions, config edits), **what's PENDING** (e.g. restart), and **what the other device must / must not do** concurrently.

The other device's session reads it via `memory_recall` and acts on it. This is the whole coordination loop.

## Anti-patterns (each caused a real incident — see memories)

| Anti-pattern | Why it bit |
|---|---|
| Identify a machine by Windows username | `LizO5` is the user on `Poppytart`, not a machine name — mislabels handshakes. |
| Assume a merged plugin bump is live everywhere | Installs are per-machine; the other device stays stale until catch-up + restart. |
| Hand-bump a `version` in `installed_plugins.json` only | `installPath`/`gitCommitSha` still point at the old cache → old code loads. |
| Trust `/plugin update` after a bump | Resolves against a possibly-stale marketplace **clone**; refresh the clone first. |
| Leave case-duplicate project rows (`c:` vs `C:`) | A stale lower-version row shadows the update. |
| Literal JWT in `~/.claude.json` Authorization | Expires silently and 401s memory on that one machine; use `${TAPESTRY_MEMORY_API_KEY}`. |

## Cross-references

- **`docs/maintenance/keeping-in-sync.md`** — the propagation checklist this skill drives.
- **`scripts/catch-up-machine.ps1`** — the per-machine plugin catch-up.
- **`tapestry-patterns:concrete-rule`** — when the coordinated thing is a load-bearing invariant.
- loom-memory: `runbook-clean-stale-plugin-installs-before-anon-flip-2026-08-22`, `gotcha-plugin-case-duplicate-project-installs-shadow-updates-2026-08-22`, `loom_memory_expired_literal_jwt_global_config_2026_09_05`, `coord-poppytart-catchup-2026-09-13`.
