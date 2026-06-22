# Skills for {{PROJECT_NAME}} (ui-app variant)

Skills are markdown playbooks Claude Code reaches for when the task fits. This project recommends the set below, organized by tier — install Tier 1 first; add later tiers as the project needs them.

Skills install once per machine at `~/.claude/skills/`. Future Claude Code sessions on any project on this machine will see them. The scaffolder doesn't install skills automatically — the [install-skills script](../../scripts/install-skills.ps1) handles the shell-installable ones; the rest install from inside Claude Code via `/plugin install`.

## Discipline plugin (recommended)

The `make-skills-discipline` plugin enforces PROBE-first behavior, `file:line` citation, dev-vs-runtime distinction, and friction-as-memory writing via Claude Code hooks. Install:

```text
/plugin marketplace add Lizo-RoadTown/claude-skills-marketplace
/plugin install make-skills-discipline@lizo-skills
```

---

## Tier 1 — Discipline (install first; always)

Skills that shape *how* Claude works in this repo regardless of the specific task.

### `lizo-skills/onboarding-psychologist`

Liz Osborn's IDENTITY-TO-HABIT framework for first-time-user flows. Grounded in BJ Fogg's Tiny Habits + Fogg Behavior Model, Nir Eyal's Hook Model, James Clear's identity-based habits. Activates on signup, empty states, welcome screens, reactivation.

```text
/plugin marketplace add Lizo-RoadTown/claude-skills-marketplace
/plugin install onboarding-psychologist@lizo-skills
```

### `superpowers:brainstorming`

Mandatory before any design work per the skill's own trigger. Skipping it ships the wrong thing.

```text
/plugin marketplace add obra/superpowers
/plugin install brainstorming@superpowers
```

### `superpowers:verification-before-completion`

Evidence before claiming done — for UI, this means *visual confirmation*, not just type-checks. Run the app and look at the change.

```text
/plugin install verification-before-completion@superpowers
```

### `verify` (top-level)

Top-level skill that wraps the verification flow — run the dev server, navigate to the affected surface, screenshot or describe what you see, compare against expected.

```text
/plugin marketplace add anthropics/claude-plugins-official
/plugin install verify
```

---

## Tier 2 — Design + current framework versions

The skills that handle the actual UI/visual work.

### `ui-ux-pro-max:ui-ux-pro-max`

67 UI styles, 99 UX guidelines, 161 color palettes, 57 font pairings, anti-patterns. Activates on any UI/UX prompt.

```text
npm install -g uipro-cli
uipro init --ai claude
```

Source: <https://github.com/nextlevelbuilder/ui-ux-pro-max-skill>

### `antigravity-bundle-creative-director:frontend-design`

Design taste — distinctive typography, considered layouts, animation-as-meaning. Pairs well with `ui-ux-pro-max` (which is opinionated about structure) by adding aesthetic ambition.

```text
/plugin marketplace add antigravity-skills/antigravity-bundle-creative-director
/plugin install frontend-design@antigravity-bundle-creative-director
```

### `antigravity-bundle-web-wizard:nextjs-best-practices`

Next.js 16 introduces breaking changes — App Router, partial pre-rendering, async dynamic APIs. The model's training-data defaults are stale. Critical for any Next.js project.

```text
/plugin marketplace add antigravity-skills/antigravity-bundle-web-wizard
/plugin install nextjs-best-practices@antigravity-bundle-web-wizard
```

### `antigravity-bundle-web-wizard:tailwind-patterns`

Tailwind v4 uses `@theme inline` and is configuration-light. Model defaults assume v3. Critical for any Tailwind v4 project.

```text
/plugin install tailwind-patterns@antigravity-bundle-web-wizard
```

### `antigravity-bundle-web-wizard:react-patterns`

React 19 patterns (server components, actions, `use` hook). Pairs with the Next.js skill for full-stack React work.

```text
/plugin install react-patterns@antigravity-bundle-web-wizard
```

---

## Tier 3 — Figma workflow (when relevant)

Skip this tier if your design happens in code or other tools.

### `figma:figma-implement-design`

Design-to-code from a Figma file. Reads the design context, produces React/Tailwind code matching it.

```text
/plugin marketplace add figma/skills
/plugin install figma-implement-design@figma
```

### `figma:figma-create-design-system-rules`

Generates design tokens (colors, spacing, typography) from a Figma file. Pairs with the design-system pattern documented in this variant's `UX_CONTRACT.md`.

```text
/plugin install figma-create-design-system-rules@figma
```

---

## Tier 4 — Public-facing surfaces

Add when the project has marketing pages or public landing content.

### `antigravity-bundle-creative-director:copy-editing`

UI copy quality. Catches marketing-voice drift, awkward CTAs, redundant headings.

```text
/plugin install copy-editing@antigravity-bundle-creative-director
```

### `antigravity-bundle-web-designer:scroll-experience`

Long-scroll page mechanics — section pacing, reveal animations, anchor links. For marketing/landing pages.

```text
/plugin marketplace add antigravity-skills/antigravity-bundle-web-designer
/plugin install scroll-experience@antigravity-bundle-web-designer
```

### `antigravity-bundle-web-wizard:seo-audit`

Pre-launch SEO checks — meta tags, structured data, social cards, accessibility.

```text
/plugin install seo-audit@antigravity-bundle-web-wizard
```

---

## Verify install

After installing, open Claude Code in this project and ask:

```text
Which of the skills referenced in CLAUDE.md and SKILLS.md do you have installed?
```

Claude will check and report. Install any missing ones it flags.

---

## How to remove a recommendation

If a skill doesn't fit your project, edit this file to remove it and delete the corresponding line from `CLAUDE.md`. The references in `CLAUDE.md` are what cause Claude to reach for the skill; without the reference, the skill won't be invoked even if installed.

---

## See also

- [`docs/UX_CONTRACT.md`](docs/UX_CONTRACT.md) — the design discipline every UI PR cites.
