# 01 — Spec drift as a category, not three bugs

## The pattern

When two repos integrate through a written spec doc, **spec drift bugs arrive in threes-or-more**, each individually looking like a one-line fix. Fixing them one at a time burns 3-5 cycles of "smoke fails → diagnose → patch → redeploy → smoke fails on a new field". The pattern is: the spec doc is out of sync with at least one side's implementation, and the implementations may also disagree with each other.

The right move on the SECOND occurrence is to stop patching and audit. The third occurrence means you've already paid the cost of stopping; just hadn't realized it.

## The story (Make_Skills ↔ the-loom skill-making bridge, 2026-06-12 → 2026-06-13)

Three smoke-test failures in a row, each "obvious" in isolation:

1. **HTTP 500 — `'UUID' object has no attribute 'replace'`** in storage layer. Cause: psycopg3 returns UUID columns as `uuid.UUID` instances, not strings. Fixed by type-tolerant casting at the call site. **PR #26 merged 2026-06-13 01:46 UTC.**
2. **HTTP 404 — "Candidate not found"** when dispatching to engine. Cause: the dispatcher posted to `/access/webhook/skill-promotion`, but the engine had moved the endpoint to `/bridge/promotion-candidate`. The spec doc still listed the old path. Plus: the loom-side endpoint code mapped engine's 404 to "candidate not found" instead of "engine doesn't recognize my dispatch URL". Two bugs entangled. **PR #28 merged 2026-06-13 03:00 UTC.**
3. **HTTP 502 — `schema_invalid on source.body_md`**. Cause: I sent `content`, engine expected `body_md`. Audit revealed **eight+ other field-shape differences** between the spec doc and the engine's actual `models.py`. **PR #29 merged 2026-06-13 07:06 UTC** after full schema rewrite to match engine's canonical models.

Three single-symptom fixes ≈ 6 hours wall-clock, three deploy cycles, three smoke retries.

## What I should have done after #2

After #2 fixed an endpoint-URL drift, the warning sign was already there: the spec doc and the engine's actual code were out of sync. Instead of redeploying, I should have:

1. Read the engine's actual `models.py` end-to-end
2. Diffed it against the spec doc
3. Diffed it against my own `bridge_models.py`
4. Rewrite my side to match the engine's `models.py` as canonical (not the spec doc)
5. Mark the spec doc as **superseded** in a single coordinated PR with MS-agent

This is what we eventually did in PR #29 + the coordinated-pair plan with MS-agent. We could have done it after #2.

## The rule

**On the SECOND spec-drift symptom in a row, stop and audit.** Specifically:

1. Stop patching the immediate symptom
2. Read the OTHER side's actual implementation (not just the spec)
3. Diff the spec doc against both implementations
4. Decide which artifact is canonical: usually the side that ships more often, or the side that's harder to change
5. Open ONE coordinated PR that aligns the non-canonical side to the canonical one, AND marks the spec doc as superseded (or moves it to an ADR)
6. Smoke-test only AFTER the coordinated PR lands

The "third symptom" is your free signal that you skipped step 1. The fourth is your free signal that you also ignored the third.

## Signals to watch for during integration

- The spec doc was written before either implementation reached production
- The two sides ship at different cadences (one ships weekly, the other ships when forced)
- The integration smoke test has been "almost passing" for multiple sessions
- A "tiny field-name fix" appears on the diff
- The error message references a field name the spec doesn't mention
- The error code is 4xx from "the other side" — they're rejecting your payload, which means they have an opinion you don't share

## Skills queued for promotion

- `verify-spec-vs-implementation.skill.md` — before any cross-repo integration smoke, PROBE both sides' actual code; treat any disagreement as the canonical issue, not the spec
- `audit-after-second-drift.skill.md` — on the second integration symptom of the same shape, stop and run a full schema/contract audit before another patch

## Related

- Loom-memory: `lesson_third_spec_drift_payload_schema_2026_06_13`
- Loom-memory: `lesson_engine_url_drifted_from_spec_2026_06_13`
- Loom-memory: `lesson_hmac_format_mismatch_pr_70_2026_06_12`
- Loom-memory: `bridge_closed_end_to_end_2026_06_13` (the eventual success)
- Loom-memory: `loom_agent_to_ms_agent_coordinated_alignment_plan_2026_06_13` (the coordinated PR)
