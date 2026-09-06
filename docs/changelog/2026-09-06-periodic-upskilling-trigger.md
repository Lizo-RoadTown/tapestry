---
date: 2026-09-06
kind: fix
area: integrations/claude-code/tapestry-discipline
prs: []
adrs: []
memory: [upskilling_must_be_periodic_not_end_of_session_2026_09_06]
supersedes:
---

# Upskilling audit re-prompts per window, not once per session

**What:** The tapestry-discipline Stop hook's upskilling-pass check now measures substantive work done **since the most recent upskilling report** (turns / tool calls / git actions), instead of over the whole session with a once-per-session marker. Each emitted report resets the window; a fresh boundary of new work re-arms the warning; and it re-nudges after `RE_WARN_TURN_INTERVAL` (30) turns even if the warning was ignored. The marker file now stores a JSON watermark (`reports_at_warn` + `turns_at_warn`) instead of a boolean. tapestry-discipline 0.1.19 → 0.1.20.

**Why it matters:** The operator keeps one Claude Code session alive for weeks, so the old "every substantive session *ends* with a report" trigger — gated on a one-shot marker and on "no report seen this session" — fired at most once and then went silent forever. No upskilling accumulated. The recurring trigger makes long-lived sessions self-prompt for a report each time a boundary of new work builds up.

**Follow-ups / gates:** Plugin change — takes effect after a Claude Code **restart** (helps the next long session, not retroactively). Pre-existing unrelated failures in `test_scope.py`/`test_observer.py` were observed on clean main and are not touched by this change.
