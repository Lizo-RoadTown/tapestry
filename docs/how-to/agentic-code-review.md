# Agentic code review (advisory)

How the PR-time agentic review works in this repo, and the one step an operator
must do to turn it on.

Grounding: `docs/plans/2026-09-05-legibility-review-and-plan.md` Part C.

## What it is

`.github/workflows/agentic-review.yml` runs two Anthropic-native GitHub Actions on
every non-draft pull request:

1. **`anthropics/claude-code-action@v1`** (automation mode) — reviews the diff for
   correctness, reuse, simplification, and efficiency, and posts **inline** comments
   on the relevant lines. It is prompted to **defer to deterministic CI**: it does
   not restate lint, type, test, or formatting findings, because those are covered
   by separate required checks.
2. **`anthropics/claude-code-security-review`** (pinned to a commit SHA) — a
   diff-aware security pass with false-positive filtering, posting its findings as
   PR comments (`comment-pr: true`).

Triggers: `pull_request` on `opened`, `synchronize`, `ready_for_review`,
`reopened`, guarded to **non-draft PRs only** (`github.event.pull_request.draft ==
false`) to bound cost. A `concurrency` group cancels a stale review when a new
commit is pushed.

## Advisory only — this is not a gate

Both jobs **only comment**. Neither approves, requests changes, nor blocks merge,
and this workflow is **not a required status check**. The deterministic required
checks stay authoritative:

- lint / types / tests
- `plugin-version-check.yml` (marketplace-vs-manifest version alignment)

Humans own merge. The agentic review is a second pair of eyes, not a merge
condition. If the agentic review and a deterministic check disagree, the
deterministic check wins.

## The one operator step

Set the `ANTHROPIC_API_KEY` secret on the repo (or inherit an org-level secret):

```sh
gh secret set ANTHROPIC_API_KEY --repo Lizo-RoadTown/tapestry
```

The command prompts for the value; the key is never written into the workflow.
Until the secret exists, both jobs fail on the missing key — but because the
workflow is advisory and not required, a failed run does not block any PR; it just
means no review is posted.

## Fork / external-PR safety

The workflow uses `pull_request` (not `pull_request_target`), so PRs from forks run
**without** repo secrets and **without** a write token — the jobs no-op on the
missing key rather than leaking it. The security-review action is **not hardened
against prompt injection** from an untrusted diff. Before enabling review on
external/fork PRs, gate it behind maintainer approval:

- Settings > Actions > General > "Require approval for all outside collaborators"
  (or "all external contributors"), or
- a manual label check in the workflow `if:` condition.

Action versions are pinned (the security action to a commit SHA, `claude-code-action`
to the maintained `v1` major tag) so a compromised upstream tag cannot silently
change behavior. For a stricter posture, pin `claude-code-action` to a full SHA too
and bump both deliberately in a PR.

## Next phase — fleet-wide rollout

This is **Phase 0**: dogfood on the Tapestry repo only. The next phase templates
this workflow into `tapestry init` so every scaffolded project gets an
`.github/workflows/agentic-review.yml` by default (Part C / D3 of the legibility
plan, action-menu item #12). Do not copy this file by hand into other repos in the
meantime; the templated version is the intended fleet-wide path.
