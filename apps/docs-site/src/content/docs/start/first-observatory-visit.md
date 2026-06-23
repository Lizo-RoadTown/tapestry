---
title: First Observatory visit
description: Open the dashboard, learn what's normal for a brand-new project (empty inbox, sparse signals), and hand off to the Observatory section for deeper reading.
---

The verification checks passed. Now look at what the platform sees about your project.

## Open the console

Visit [tapestry-khaki.vercel.app/observatory](https://tapestry-khaki.vercel.app/observatory).

That's the Observatory cockpit — the platform-level surface that exposes patterns through lenses. Nothing project-specific to set up; if your project's signals have reached the platform (which they have, if [Verify it worked](/start/verify-it-worked/) passed), the cockpit reads from the shared registry + memory.

## What you'll see on a brand-new project

A new project's first visit looks sparse — that's correct, not a failure:

| What it shows | Why it's sparse on day one |
|---|---|
| Candidate inbox | The Observer cron runs every 6 hours. Your project hasn't had a cycle yet, so the candidates list is empty or has only general findings. |
| Memory lens | Empty until you've written or accumulated memories. The auto-recall block in your session was empty for the same reason. |
| Architecture lens | Empty until your project starts running `scripts/architecture_snapshot.py` (optional — onboarding doesn't add it; see [Architecture snapshots](/explanation/architecture-snapshots/)). |
| Observer lens | Empty until the cron has interpreted enough signal from your project to surface findings. |

Sparse first-visit is the norm. Patterns accumulate; come back after a few work sessions.

## What changes over time

After a few days of normal use, the cockpit starts populating:

- Corrections you make in chat become **friction patterns** the Observer surfaces.
- Memory writes (your decisions, observer synthesis memos) populate the **memory lens**.
- Architecture-snapshot runs (if you wire the optional scripts in) populate the **architecture lens**.
- Recurring candidates across projects start composing under the **cross-project lens** (planned — currently surfaces as deduplicated findings in the candidate inbox).

See [Observatory lenses](/explanation/observatory-lenses/) for what each lens foregrounds.

## What's the right question to ask the cockpit

The Observatory isn't a status dashboard. It's a *trajectory* dashboard. Ask trajectory questions:

- Is coordination on this project getting smoother or rougher? (Friction recurrence, correction frequency)
- Is anything stabilizing into a candidate worth promoting? (Candidate inbox + observer confidence)
- Has memory been load-bearing, or have I been re-explaining things? (Memory miss rate vs reinforcement)
- Has my project's shape changed in ways I didn't notice? (Architecture diffs)

State questions ("is the API up right now?") belong in a regular operational dashboard, not here. See [Signal → Interpretation → Pattern](/explanation/signal-interpretation-pattern/) for why.

## What to do next

You've completed the Start here workflow. The conceptual foundations come next:

1. [User-agent interface](/start/user-agent-interface/) — the primary object the platform observes.
2. [Project shape](/start/project-shape/) — the substrate that interface evolves in.
3. [What Tapestry is not](/start/what-tapestry-is-not/) — boundary-setting.
4. [What keeps a project on track](/start/what-stays-on-track/) — the platform-level story.

Beyond Start here:

- [How it works](/explanation/signal-hierarchy/) — the architectural concepts (signal hierarchy, observer, intent, lenses, upskilling).
- [Reading the Observatory](/observatory/reading-it/) — the cockpit's controls + chart types + interpretation panel in detail.
- [Systems](/systems/observer/) — each component's setup + verify + troubleshoot.

## Related

- [Observatory — What it is](/observatory/about/) — what the cockpit holds
- [Reading the Observatory](/observatory/reading-it/) — controls, chart types, interpretation
- [Observatory lenses](/explanation/observatory-lenses/) — the lens model
- [Project Intelligence vs Observatory](/explanation/project-intelligence-vs-observatory/) — why onboarding installs the producer but not the surface
