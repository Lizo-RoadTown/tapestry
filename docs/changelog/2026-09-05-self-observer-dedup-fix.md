---
date: 2026-09-05
kind: fix
area: services/self-observer
prs: [164]
adrs: []
memory: [legibility_initiative_session_2026_09_05_prs_164_165]
supersedes:
---

# self-observer dedup repair + stub-slot labels

**What:** Fixed `CandidateClient.fetch_open_candidates`, which queried `GET /candidates?status=open` — but `open` is not a valid registry status, so the request 422'd, hit the soft-fail path, and dedup was silently disabled entirely. Dropped the invalid filter so it dedups against all existing candidates. Also labeled two empty service slots: `candidate-registry` = ABSORBED into architecture-registry; `audit-log` = DEFERRED.

**Why it matters:** Every 6-hour observer scan had been re-emitting every candidate it ever found (silent-failure class). The fix also avoids re-surfacing candidates the operator already resolved. The slot labels stop future readers from assuming those services are still planned.

**Follow-ups / gates:** Observable on the next live cron run once the self-observer cron is enabled — the candidate count stops growing on unchanged repos.
