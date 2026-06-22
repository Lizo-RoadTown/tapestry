# UX Contract

The design discipline every user-facing surface in {{PROJECT_NAME}} must follow. This is the gate every UI PR passes through. If a change can't be defended against this document, it doesn't ship.

Most of this contract is universal; a few sections reference surfaces specific to your project and are marked with `<adapt-this>` placeholders — edit those to match the actual screens, components, or routes in your build.

Two source bodies were synthesized into this contract:

- **The Attention → Question → Commitment → Feedback → Reveal master pattern**, hard-won from interactive-product work — chapters that worked vs chapters where users bounced.
- **`ui-ux-pro-max`** (installed skill), a comprehensive design contract for web and mobile — 99 guidelines, 10 prioritized categories, anti-patterns.

Plus the principles every well-designed product converges on: surfaces are guided journeys not database editors, the user is the protagonist, marketing voice is forbidden.

---

## Rule zero — the master contract

**Attention → Question → Commitment → Feedback → Reveal.**

The user must commit to a decision before the system reveals structure. No auto-advance. No answer-before-input. No forward navigation during reasoning.

Every other rule in this document serves rule zero. When in doubt, ask: *did the user think before the system revealed?*

---

## The onboarding arc — IDENTITY-TO-HABIT

How a user gets from outsider to participant. Adapted from the `onboarding-psychologist` framework (Volpp & Loewenstein 2020, Stawarz et al. 2015, Sheeran et al. 2020).

1. **Define the first win.** The smallest meaningful success that proves value. Anything before that is friction.
2. **Remove unnecessary setup.** Minimize early decisions, fields, feature exposure. No "set up your profile" wall. The user lands in the work itself.
3. **Create ownership through action.** Have the user do something small and meaningful that creates investment. Words they wrote, choices that visibly persist, content they authored.
4. **Attach a stable cue.** Link the desired return-visit behavior to an existing routine. The home page surfaces *one* concrete next thing.
5. **Reinforce identity.** Reflect the user as someone who *does the thing this product supports*. The product's persistent state shows their work; the product references their past contributions; the export bundle is theirs to take.

What this rules out: feature tours, tutorial overlays, "12 things to know before you start," empty-state pages that show a CRUD form. The first-use surface *is* the onboarding.

---

## Two-language coherence

When the user commits to something in one representation, the paired representation updates at the same time. If a paired representation doesn't exist, say so explicitly — silence reads as broken.

Concrete applications (`<adapt-this>` per your surfaces):

- **Choice + consequence**: picking an option should change what's visible about the system's *response to that option* — trade-offs are shown alongside the choice, not behind a docs link.
- **Authoring + result**: as the user creates content, the surface that consumes that content gains visible markers. The thing being written becomes the artifact the system will use.
- **Active state**: any long-running operation shows *what* the system is doing on a side panel — not just *that* it's working.
- **Persistent state**: each saved artifact shows its completion markers (✓ filled, `?` empty) — not as raw JSON.

If two-language coherence is missing on a screen, name it in the PR: "this view has no paired representation because X" — then either build one or accept the gap explicitly.

---

## Empty vs filled — `?` slots and `fill-pop` cards

Empty values render as dashed-border `?` placeholders. Filled values render as solid cards with a `fill-pop` entry animation. The contrast is intentional and load-bearing.

Why this matters: in a builder app, the difference between "I haven't done this yet" and "I did this and here's the result" is the *entire* feedback loop. If both empty and filled look the same, users can't tell whether they're making progress.

Direct applications:

- Lists of artifacts: an entry without required fields shows the missing fields as `?` slots. An entry with all fields shows a `fill-pop` chip per field.
- Progress indicators: filled vs empty, not opaque vs translucent.
- Settings / connections: each item shows "not set" as a `?` slot, "set" as a filled card with the last-updated timestamp.
- Integrations: connected = filled card; available-but-not-connected = `?`.

---

## Hand-crafted, attempt-aware feedback

Hints are written by hand. Per-step, per-attempt. The smart approach eventually does this at runtime via LLM, but the structure stays the same:

| Attempt | Behavior |
|---|---|
| 1 | Minimal — "not quite, try another" |
| 2 | Same minimal nudge with slight rewording |
| 3 | Actual hint — concrete pointer |
| 4+ | "Show reasoning" link — explains the rule, but the user must still click to apply it |

Never auto-generated from a model at runtime *without* the per-attempt structure. The hand-craft is what makes the explanations land.

---

## Wrong-but-valid ≠ wrong-and-invalid

Two distinct failure modes, two distinct visual treatments. Mixing them confuses the user about what's permitted.

- **Suboptimal but valid**: amber tint, two buttons — "Use this anyway" and "Choose again". Log the suboptimal pick; debrief later with a path-taken vs. optimal-path comparison. *Example: picking a slower option for a heavy task. Not wrong — slower, but valid.*
- **Wrong and invalid**: red flash, block. Forces retry. *Example: trying to save with a required field empty. Not a trade-off — a constraint.*

When a UI treats every choice as equally valid, it loses the chance to teach. Surface the trade-off.

---

## Color semantics — six tokens, one meaning each

Reuse consistent tokens. Don't introduce new colors for new states.

| Meaning | Tailwind tokens (suggested) |
|---|---|
| Attention target | `border-zinc-700` + subtle pulse |
| Candidate (selected, unjudged) | `bg-amber-500/10 border-amber-500/40 text-amber-200` |
| Suboptimal but valid | amber + dual-button + note |
| Correct / live | `bg-emerald-500/10 border-emerald-500/40 text-emerald-200` |
| Active column / pivot | `bg-blue-500/10 border-blue-500/40 text-blue-200` |
| Invalid (red flash) | `bg-red-950/40 border-red-900 text-red-300` |
| Skipped / dimmed | `opacity-40` |

When adding a new visual state, map it onto an existing semantic. Don't reach for a new hue.

---

## Animation budget

Animation conveys meaning. Decorative-only animation is forbidden.

- **Duration**: 150–300ms for state changes. Anything longer needs justification.
- **Easing**: `ease-out` for entries, `ease-in-out` for transitions, springs for character/avatar movement.
- **Spatial continuity**: when something moves between two places, animate the path. When something appears, fade + slide from the direction it came from.
- **Reduced motion**: respect `prefers-reduced-motion`. Reduce or disable animations when requested.
- **Never animate width/height** (causes layout thrashing). Animate `transform` and `opacity` only.

If the product has a consistent character (avatar, mascot, persistent visual identity), use motion to convey state (idle → working → reacting). Each state has a distinct subtle loop; not all at once.

---

## Navigation — one place per concern

Surface fragmentation IS itself a violation of the contract. If multiple separate pages exist for what is conceptually one thing (e.g. observability split across sessions / memory / logs / metrics), this is engineer-shaped, not user-shaped.

Rules:

- **One nav item per concern.** If two pages answer the same question, they belong on one page with sections or tabs.
- **The sidebar is not a TODO list.** "Stub" status items are forbidden — either build the surface or remove the link.
- **Every page should feel like the same product.** Header chrome, color tokens, spacing, transitions all match.
- **Persistent identity is present everywhere.** A consistent visual identity (a brand mark, a character, a layout signature) ties surfaces together. The user should never feel they've left the product's body.

When consolidations are needed, surface them as proposals in `docs/proposals/` — don't ship the fragmented state as the long-term shape.

---

## Voice and tone

- Describe what *is*, not what it *isn't*.
- No marketing language. No "the unlock," "exciting," "delightful," "transformative."
- No self-congratulation ("we built a beautiful X").
- No defensive contrasts ("real X not Y").
- No conversation-language in product surfaces ("So, here's how it works...").
- If the product has a voice (character, persona, brand voice) — define it once and apply it consistently. Avoid corporate-onboarding cheer. Avoid mascot-tier whimsy unless the product genuinely is for kids.

Failure mode: copy that performs enthusiasm or expertise. Both are tells of insecure design.

---

## Accessibility — non-negotiable

From `ui-ux-pro-max` priority 1 (CRITICAL). Every PR passes these:

- **Color contrast ≥ 4.5:1** for normal text, ≥ 3:1 for large. Test against a real contrast checker.
- **Focus rings visible** on every interactive element. 2–4px. Never remove with `outline-none` without an alternative.
- **Alt text** on meaningful images. Decorative images get `alt=""`.
- **Aria labels** on icon-only buttons (drawer toggles, avatar buttons, etc.).
- **Keyboard navigation** matches visual order. Tab through every interactive element. No focus traps.
- **`color-not-only`**: status is also conveyed by icon or text, not just color.
- **`prefers-reduced-motion`** respected.

---

## Touch & interaction — also non-negotiable

`ui-ux-pro-max` priority 2 (CRITICAL):

- **Minimum 44×44px** touch targets. Tiny buttons in tight rows are a failure.
- **8px+ spacing** between adjacent touch targets.
- **Loading feedback** within 100ms of every action. Spinner, dots, skeleton, optimistic update — anything but silence.
- **No hover-only affordances.** Touch devices can't hover.
- **No instant state changes** (0ms transitions). At minimum 150ms easing.

---

## Anti-patterns — refuse if asked

If a request matches one of these, name it as a rule violation and confirm before proceeding:

- **Worksheets to read with no interaction.** Long passive lists where the user is a viewer, not a participant.
- **Auto-advance through reveal.** Code that blows past the user's commit before showing the result.
- **Same feedback regardless of attempt.** Scripted reactions identical on every re-run. Acceptable as a placeholder; not acceptable as production.
- **No paired representation.** Input with no view of what the system is doing. A choice with no trade-off comparison. Saving an artifact with no visible change in the persistent state.
- **Calling wrong-but-valid "wrong"** without the suboptimal/invalid distinction.
- **Pre-made solutions hidden from the user.** Whatever the system does on the user's behalf should be inspectable — otherwise it's magic, and magic doesn't teach.
- **Stub status items in the nav.** Either build it or remove it. "Soon" doesn't ship.
- **CRUD forms as features.** Listing things and offering "Add new" buttons is engineering, not product. Surfaces are guided journeys, not database editors.

---

## Review checklist — every UI PR must pass

Before claiming a UI PR complete, run through this explicitly:

1. **Master contract**: does the user commit before the system reveals?
2. **Forward navigation locked** during reasoning?
3. **Paired representation present**, or its absence explicitly named?
4. **Empty vs filled** visually distinct (`?` slot vs `fill-pop`)?
5. **Hints attempt-aware**, or scripted placeholder explicitly labeled as such?
6. **Wrong choices distinguished** invalid (red, block) vs. suboptimal (amber, dual-button)?
7. **Color semantics consistent** with the table above?
8. **Animations purposeful**, within budget, respect reduced-motion?
9. **Accessibility**: contrast, focus rings, aria labels, keyboard nav?
10. **Touch targets** 44px+, spacing 8px+, loading feedback within 100ms?
11. **Voice clean** — no marketing language, no enthusiasm performance?
12. **Sidebar nav** does not gain a new stub?
13. **Persistent identity** present on this surface, or explicitly argued to be absent?

If any item is "no," the implementation doesn't meet the contract. Either fix it or call out the trade-off explicitly in the PR.

---

## Where this lives operationally

- This document is canonical. PRs touching UI cite which sections they comply with and which (if any) they take exception to.
- When the design ages, this document is updated through a proposal in `docs/proposals/`, not edited in place.
- This is a {{PROJECT_NAME}}-specific copy. Edit it freely to match your product's actual rules — the rules above are sensible defaults, not mandates.

The principle is: *one place where the design discipline lives, applied uniformly, evolved deliberately.* The dashboard fragmentation common in shipped products is the result of *not* having this; the next chapter of any product is the result of having it.

---

## Attribution

This template was lifted into project-starter from a working repo where the discipline was hard-won. Generalized for template use; the underlying rules stay the same.
