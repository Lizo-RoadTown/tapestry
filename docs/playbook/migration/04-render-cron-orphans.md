# 04 — Infra teardown without orphan check (cron + script)

## The pattern

You delete a script + remove its entry from `render.yaml` + commit + push + deploy. You think the cron is gone. **The cron job itself still exists on the Render side** because Render keeps cron jobs you created out-of-band even after you remove them from `render.yaml`. The job fires on its schedule and fails because the script it points at is gone. You discover this weeks later when the failures finally surface in your inbox or in a session.

Same pattern applies to any infra resource that has a "config-as-code" side AND a "manual click" side: Render crons, Vercel cron triggers, GitHub Actions workflow_dispatch entries, Postgres scheduled jobs, etc.

## The story (loom keep_warm.py, caught 2026-06-13)

Commit `4b43248` (2026-05-31): *"keep-warm: drop (superseded by loom-agent-context starter-plan upgrade)"* — removed `scripts/keep_warm.py` AND the keep-warm entry from `render.yaml`. The commit body was correct: starter-tier services don't spin down, so the cron was no longer needed.

But the cron job on Render itself was never deleted. It kept firing every 10 minutes for **13 days** before Liz noticed the failure messages:

```text
==> Running 'python scripts/keep_warm.py'
python: can't open file '/opt/render/project/src/scripts/keep_warm.py': [Errno 2] No such file or directory
❌ Your cronjob failed because of an error: Exited with status 2
```

The deploy logs were noisy but not blocking. The cron's failure didn't impact any live service. So nothing escalated until a human happened to read the log.

## The rule

### When retiring a script that runs on a schedule

Run a 4-step teardown checklist:

1. **Remove the script** from the source repo
2. **Remove the config-as-code entry** (`render.yaml`, GitHub workflow file, etc.)
3. **Delete the actual scheduled resource via API or dashboard** — this is the step that gets skipped
4. **Verify** by listing scheduled jobs in the destination platform and grep'ing for the now-orphaned name

Step 3 is the one most retirement commits skip because steps 1 + 2 LOOK like complete teardown to the agent writing the commit.

### A simple convention to prevent recurrence

Any commit that retires a scheduled job should include in its body:

```text
Teardown checklist:
- [x] Script removed
- [x] render.yaml entry removed
- [x] Render cron job deleted (Render dashboard / MCP)
- [x] Verified absent: mcp__render__list_services | grep keep-warm  →  empty
```

If you can't tick step 3, the retirement isn't done. Leave a `TODO` issue or schedule a follow-up.

### Pre-migration audit

When migrating from a source repo into Tapestry, also run a scheduled-job audit on the source repo:

1. List every scheduled resource on every external platform the source repo deploys to (Render, Vercel, GH Actions, etc.)
2. For each, verify the script-or-handler it points at still exists in the source repo
3. Orphans are red flags: either the source repo has dead crons (delete them) OR the cron was meant to migrate (preserve it explicitly)

## Why this is worth a playbook chapter

It's a special case of "infra-as-code with manual escape hatches" — same pattern shows up with:

- Vercel cron triggers managed via dashboard
- Render disks / databases provisioned manually
- DNS records added via cloud-provider console
- Stripe webhooks registered via dashboard
- WorkOS / Auth0 connection settings clicked through UI

Each one survives a code-side teardown silently. The discipline rule generalizes: **any infra resource that can be created out-of-band must be torn down out-of-band**.

## Skills queued for promotion

- `retire-scheduled-job.skill.md` — full 4-step teardown checklist + verification command, as an invokable skill
- `audit-orphan-scheduled-jobs.skill.md` — periodic sweep that diffs config-as-code crons vs platform-side crons, flags orphans

## Related

- Commit: `4b43248` *"keep-warm: drop"*
- Session 2026-06-13 — the failure surface that triggered this chapter
