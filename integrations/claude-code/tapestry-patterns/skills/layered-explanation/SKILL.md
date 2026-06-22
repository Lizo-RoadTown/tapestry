---
name: layered-explanation
description: Use BEFORE every explanation of infrastructure, architecture, tooling, library choice, telemetry stacks, CI pipelines, or any technical concept where the user needs to make a decision. Structures the response as four progressively-deeper layers (ELI5 metaphor → quick-reference table or diagram → depth with file:line citations → one-paragraph mental model) so the user can self-select the depth they need instead of being trapped between walls of jargon and condescending oversimplification. Different from `documentation` (which classifies docs by Diátaxis type) and from `agentic-skill-design` (which is about how skills behave). This skill is about the SHAPE of an explanation.
---

# Layered explanation

The problem this skill solves: when an agent explains a technical concept in one continuous prose block, the user either (a) defers and says "yes" because the jargon is too dense to evaluate, or (b) drowns in a wall of text and gives up. Both outcomes look like consent; neither actually IS consent. The user can't choose what they don't understand.

The fix: structure every technical explanation in four layers, from simplest to deepest, so the user can stop reading at whatever depth answers their actual question.

## When to use

**Apply when explaining:**

- Infrastructure choices (auth, storage, hosting, deploy)
- Architecture patterns (modules, interfaces, layering, two-mode design)
- Library or framework comparisons ("should we use X or Y?")
- Telemetry / observability stacks (OpenTelemetry, Grafana, Sentry, LangSmith, etc.)
- CI / release / version-bump pipelines
- Plugin or extension mechanics (hooks, scripts, manifests)
- Any decision where the user needs to evaluate trade-offs they might not have language for

**Skip when:**

- The user asks a one-line factual question ("does X exist?") — answer in one line; layered structure is overhead
- The user explicitly states their knowledge ("I know auth flows, just show me the code")
- Quick acknowledgements during execution (a confirming "yes, done")
- Agent-to-agent communication (other agents don't need the ELI5 layer)
- Inside code comments or docstrings — different pattern (terse, contextual)

## The four layers, in this order

### Layer 1 — ELI5 (Explain Like I'm Five)

A metaphor that maps the technical concept to a real-world object the user already understands. **No jargon.** Three to five sentences max. Builds a mental image.

The test for "Is this actually ELI5?":

- Could a non-technical friend read this and get the gist?
- Did you use ANY of: protocol, schema, endpoint, payload, container, daemon, runtime, instrumentation, telemetry, abstraction, decorator, adapter, middleware, hook, callback, async, lifecycle, semantic conventions, observability?
- If yes to the jargon check, it's NOT ELI5. Rewrite.

**Example (LangSmith):** *"LangSmith is like a recording studio for the AI's conversations. Every time the AI thinks, it sends a copy of the prompt + the response + how long it took + how much it cost to LangSmith, so you can review it later."*

That's three sentences. The metaphor (recording studio) is something everyone has heard of. The mechanics (records what the AI does, lets you review later) are bare. No jargon.

### Layer 2 — Quick reference

A table, diagram, or short bullet list that shows the **concrete pieces and their relationships at a glance**. The "I get it; show me the shape" layer.

This is where you introduce the actual names of things, but each one is paired with a one-line "what it does" so the user doesn't have to look anything up.

**Example (telemetry stack):**

| Layer | Tool | What it does |
|---|---|---|
| Collection | OpenTelemetry SDK | Instruments your code; emits standardized telemetry |
| Storage | Tempo / Loki / Prometheus | Each store handles one telemetry type |
| UI | Grafana | One dashboard queries all the stores |
| Specialized | LangSmith, Sentry | Deep-dive UIs for LLM conversations / errors |

Or a Mermaid diagram if the relationships are visual. The point: the user can grasp the shape without reading paragraphs.

### Layer 3 — Depth

The substantive technical detail. File:line citations from real code. Real commands. Named trade-offs. Specific anti-patterns. The "I'm going to act on this; tell me exactly" layer.

Discipline within this layer:

- Cite `file:path:line` for any claim about how things are wired in this repo
- Name the cost (small / medium / large PR; $X / month; N min of dev work)
- Flag the gotcha (e.g., "but only fires if PLATFORM_MODE=hosted")
- List two alternatives that were considered and rejected, with one-line reasons

**This layer is the longest by design.** That's correct — the user who's drilled in here needs the substance. The ELI5 + reference layers exist precisely so users who DON'T need the substance can stop earlier.

### Layer 4 — Mental model

One paragraph (often one sentence) that compresses the whole topic into a hook the user can carry forward. The "OK, what's the takeaway" layer.

This is what the user will recite to themselves next week when they encounter the topic again. If you can't write it in a sentence, you don't understand the topic well enough to be explaining it.

**Example (Grafana):** *"Grafana is a dashboard that queries OTHER stores; it doesn't store anything itself. Use it when you need cross-source operational views; use the specialized UIs (LangSmith, Sentry) when you need forensic deep-dive."*

That's two sentences. The first defines the thing; the second names when to reach for it. That's all a mental model needs.

## How the layers interact

The user reads them top-down and **stops at the layer that answers their actual question**. The agent does NOT decide for the user how deep to go — the four layers are offered, the user picks.

Visual:

```
ELI5            ← stops here when: "ah, I get the gist, that's enough for now"
   ↓
Reference       ← stops here when: "I see the shape and that's all I need to decide"
   ↓
Depth           ← stops here when: "I'm about to wire this up; show me the specifics"
   ↓
Mental model    ← reads this regardless: it's the takeaway for next time
```

The mental model layer can be read at any depth — it's the bookmark.

## Anti-patterns to refuse

- **Skipping the ELI5 because "it's a simple concept."** The user's read on what's simple may not match yours. Default to including it; let the user say "I know this layer, skip."
- **ELI5 that uses jargon.** Re-read the ELI5 with a non-technical friend in mind. If they'd stumble, rewrite.
- **ELI5 longer than the depth section.** The depth section should always be the longest. If the ELI5 is verbose, you're over-explaining at the wrong layer.
- **Depth without file:line citations.** Claims like "the auth flow uses X" without a `web/auth.ts:19` citation should fail. The depth layer's value is grounded specificity.
- **Skipping the mental model.** Without a takeaway, the depth doesn't compress into anything reusable. The user does the work; the agent must do the compression.
- **Walls of text without visible layer headers.** The layers must be HEADED (`### Layer 1 — ELI5`, etc., or equivalent visual breaks). The headers are how the user navigates.
- **Condescending ELI5.** "Imagine you have a piggy bank..." for a senior engineer asking about JWTs. Read the room. Metaphors should be calibrated to the user's stated context.
- **Burying the mental model in the depth section.** It belongs at the END as its own layer, not as a sentence buried in the middle.

## Recursive application — explaining this skill itself

This skill's own intro followed the pattern: opened with a problem statement (the ELI5 equivalent), then the four layers (reference), then the rules (depth), and the §Mental model below (takeaway). The recursion is intentional — if the skill doesn't follow its own discipline, it has no claim to enforce it.

## Mental model

**Four layers, always: metaphor → reference → depth → takeaway. The user picks the depth. The agent never decides for them.** Walls of jargon and walls of text both look like care; both are actually neglect. Layered explanation is the structural fix.

## Pair with the public stack

- `documentation` — Diátaxis pattern; this skill's "depth" layer often produces material that fits the explanation tier of Diátaxis
- `agentic-skill-design` — PROBE step verifies citations used in the depth layer
- `superpowers:brainstorming` — for finding the right metaphor in the ELI5 layer when the obvious one doesn't land
- `make-skills-discipline` plugin (when installed) — the discipline rules complement this skill; the discipline says "PROBE before asserting", this skill says "explain in layers after PROBing"
- `infrastructure-mapping` — the skill that produces the artifacts this skill explains; mapping outputs feed naturally into layered explanations

## Memory loop (the skill gets sharper over time)

After each session that uses this skill:

- If the user stopped reading at the ELI5 layer and that was correct (their question was satisfied), the metaphor worked — save it for reuse
- If the user said "wait, what is X?" mid-depth-layer, the depth layer's prerequisites were unclear — adjust which terms get defined in the reference layer
- If the user said "this is too much" — the depth layer was probably padded; tighten the next iteration
- If the user said "I don't even know what to ask" — the ELI5 didn't build enough mental image; reach for a better metaphor

Capture metaphors that landed well in a `reference_explanation_metaphors.md` memory file. They compound across sessions.

## References

- Plain-language writing principles: Strunk & White, *The Elements of Style*; available as the public skill `elements-of-style:writing-clearly-and-concisely`
- Diátaxis framework (Daniele Procida): https://diataxis.fr/ — complementary; classifies docs by audience need, doesn't prescribe shape per explanation
- The Feynman technique (explain like to a child as a way to verify your own understanding): widely attributed to Richard Feynman; the ELI5 layer of this skill is structurally identical
- Liz's directive captured in `project_novice_blueprint_observability_first.md` (2026-05-23): the novice-blueprint vision makes this skill load-bearing
- Liz's feedback at `feedback_layered_explanation_default.md` (2026-05-23): the friction-pattern recording that motivated this skill
