---
date: 2026-09-06
kind: fix
area: services/self-observer
prs: []
adrs: []
memory: [self_observer_first_live_run_2026_09_06_coverage_gaps]
supersedes:
---

# self-observer: retry registry discovery through a cold start

**What:** `registry_client._fetch_projects` now retries `GET /projects` on a transport error or 5xx (3 attempts, 5s apart) before soft-failing to static-core. Previously a single failed request dropped the whole pass to the 2 static-core repos.

**Why it matters:** On the live 6-hour cron, the free-tier `loom-project-registry` is reliably asleep at fire time, so the first request times out and the observer sees only 2 repos instead of the full fleet (observed 2026-09-06: run 1 fell back to static-core; run 2 only reached the registry because run 1 had warmed it). The retry absorbs the wake-up, so every run discovers all registered repos — and it lets `loom-project-registry` stay on the **free plan** (sleeping) instead of a paid warm one, cutting Render cost. Mirrors the retry `memory_client` already had.

**Follow-ups / gates:** none. The separate `memory 401` (observer synthesis-memo write) is still parked with the memory-auth work — unrelated to this fix.
