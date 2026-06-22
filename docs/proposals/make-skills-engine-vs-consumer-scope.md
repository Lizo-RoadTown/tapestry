# Make_Skills: engine vs. consumer — what's actually in this repo

**Written:** 2026-05-25. **Status:** Draft for Liz to correct. **Reason:** Same conflation pattern as the-loom extraction. The current `Lizo-RoadTown/Make_Skills` repo mixes two things that should eventually be separate applications.

> **Lesson learned from the-loom extraction:** Liz lives outside VS Code and experiences applications as distinct products with their own boundaries, audiences, and lifecycles. Agents inside the IDE see files in a repo and think it's "all one thing." It isn't. When the file-level view doesn't match the product-level boundaries, the file-level view is wrong.

## What's actually in this repo right now

The `Lizo-RoadTown/Make_Skills` repo contains code, docs, and methodology for TWO different applications:

### Application 1 — Make_Skills (the engine)

**What it is:** A reusable agent platform. Provides per-user AI agent runtime, skill compilation pipeline, skill registry + sharing, multi-model provider registry, BYO API keys per user, per-tenant memory + observability hooks, Pillar 0 tenant isolation.

**Who it's for:** Developers (like Liz) building applications where end-users need personalized AI agents with growing skill catalogs. Make_Skills is the engine they install.

**Distinguishing pattern:** Skills are authored in plain markdown (the "make skills" part). The runtime compiles `.md` → runnable agent capability. Users (or admins) author skills without writing code. That's the unique pattern. Without it, Make_Skills would be "yet another agent SDK."

**What it does NOT include:** any specific student onboarding, lesson content, particular UI layout, particular business logic, particular branding. Those are the consumer's concern.

### Application 2 — humancensys.com (the first consumer)

**What it is:** The student-facing product. Student onboarding journey (the IDENTITY-TO-HABIT framework), lesson content, student identity (Auth.js), the visible Next.js UI, branding, the Render deploy.

**Who it's for:** Students learning AI agents in their education.

**What it consumes:** Make_Skills the engine, the-loom (during development, not in deployed runtime).

**What it does NOT include:** the agent runtime, the skill compiler, the model registry, the memory layer. Those are Make_Skills' concerns.

## Where the conflation has been happening

Same pattern as the-loom inside Make_Skills:

| In Make_Skills repo today | Belongs to (under the split) |
|---|---|
| `platform/api/runtime.py`, `skill_compiler.py`, agent registry, BYO API keys, model registry | Make_Skills engine |
| `platform/api/memory/lance.py` (the LanceDB layer for per-tenant agent memory) | Make_Skills engine |
| `platform/api/auth.py` (JWT verification + tenant resolution) | Make_Skills engine |
| `platform/api/main.py` agent-mgmt endpoints (`/chat/{agent_id}`, `/agents/*`) | Make_Skills engine |
| Multi-model provider integrations (Anthropic / OpenAI / Google / Ollama wiring) | Make_Skills engine |
| Pillar 0 tenant scoping (RLS policies, `current_tenant` ContextVar) | Make_Skills engine |
| `web/` Next.js UI + student onboarding flows | humancensys.com consumer |
| Auth.js Drizzle setup + student identity tables | humancensys.com consumer |
| Lesson content, the IDENTITY-TO-HABIT framework, student journey logic | humancensys.com consumer |
| Branding, copy, visual identity | humancensys.com consumer |
| `render.yaml` (deploys humancensys.com's specific stack) | humancensys.com consumer |
| The Pillar 1/2/3 vision tied to "students making skills" | humancensys.com consumer (engine doesn't presume students) |

## What stays uncoupled (Make_Skills engine boundaries)

The engine must NOT depend on:
- Anything about who the end-users are (students vs. patients vs. researchers vs. players)
- Any specific UI framework choice
- Any specific identity provider beyond a JWT contract
- Any specific deployment target (works on Render, but also Fly, Vercel functions, self-hosted, etc.)
- Any specific brand or copy

If a consumer wants to deploy Make_Skills as the engine behind a health app, they should be able to do so by writing their own UI + onboarding + lesson layer on top, without forking Make_Skills' engine code.

## Where each lives in the long run

```text
Lizo-RoadTown/the-loom            — Liz's dev substrate (separate, already extracted 2026-05-25)
Lizo-RoadTown/Make_Skills         — the engine (this repo, after the split)
Lizo-RoadTown/humancensys-app     — the student-facing consumer (eventually extracted, future)
Lizo-RoadTown/[future-health-app] — another consumer (when Liz builds one)
Lizo-RoadTown/[future-game-app]   — another consumer
```

Each consumer installs Make_Skills the engine the same way (npm package, Python package, Docker image, or whatever distribution mechanism the engine ends up shipping). They provide their own UI, identity layer, onboarding, branding.

## How Make_Skills relates to the-loom

**Both are platforms. Different audiences. Peer applications.**

| | the-loom | Make_Skills |
|---|---|---|
| Audience served | Developers (Liz, future contributors) | End-users' AI agents (inside consumer products) |
| When it operates | During development (Liz's Claude Code sessions, dev work across repos) | At runtime (when a student/patient/etc. is using the deployed consumer product) |
| Lives in the deployed product's runtime? | NO — the-loom never touches deployed products. Code is the only bridge from dev to runtime. | YES — Make_Skills IS the engine inside the deployed consumer's runtime |
| What it owns | Project intelligence, observability, architecture recognition for Liz's work | Agent runtime, skill system, model registry, tenant isolation for end-user agents |

A consumer product (e.g., humancensys.com) consumes BOTH:
- The-loom: during development (Liz building it; the discipline plugin firing in her Claude Code sessions; her cross-machine memory + observability for HER dev work)
- Make_Skills: in deployed runtime (student arrives at humancensys.com; Make_Skills' agent runtime spins up their personal agent; their skill catalog grows via Make_Skills' compilation pipeline)

These don't connect to each other. The-loom is invisible at runtime; Make_Skills is the runtime engine.

## Why this matters now (and what to do about it)

The same problems the-loom extraction solved will recur for Make_Skills if the engine stays mixed with humancensys.com:

1. **A future consumer (a health app) wants to use Make_Skills.** Today they'd have to fork the whole repo and rip out the student journey, the IDENTITY-TO-HABIT framework, the Next.js lesson UI. Wrong shape.
2. **humancensys.com's product evolution gets entangled with engine evolution.** Want to redesign the lesson flow? Risk breaking the agent runtime. Want to add a new model provider? Have to redeploy humancensys.com.
3. **The Pillar 1/2/3 framing** ("Build-agents, Make-skills-together, Observability") was written for the student application. The engine is more general than that — those Pillars are humancensys.com-specific framings.

**What this proposal does NOT commit to:** an immediate code split. That's a future migration effort, similar to the-loom extraction. This doc names the boundary so future agents and future you don't keep blurring it.

**What I'd want to do next, if you agree with this framing:**

1. **Data model for Make_Skills the engine** — analogous to the-loom's `2026-05-25-platform-data-model.md`. Objects like: Tenant, AgentInstance, Skill (compiled from .md), SkillSource (.md file), ModelProvider, MemoryRow, ConversationThread, etc.
2. **MVP repo layout for Make_Skills the engine** — analogous to the-loom's `2026-05-25-mvp-repo-layout.md`. Monorepo? Single-package? Distribution mechanism (Python package + Docker image)?
3. **Make_Skills' own canonical surface table** — what's the engine's API surface (REST? MCP? Both?) and what does a consumer wire up to use it?
4. **Migration roadmap** — phases for extracting humancensys.com from the Make_Skills repo. Probably involves: (a) clarify the engine's API; (b) create `Lizo-RoadTown/humancensys-app`; (c) move `web/` + Auth.js setup + lesson content there; (d) have humancensys.com depend on Make_Skills as a dependency; (e) iterate until clean.

## Confirmed by Liz 2026-05-25 + two additions

**Confirmed:** framing is right. Make_Skills (engine) and humancensys.com (consumer) are two applications, currently mixed in this repo. The student application will become its own separate repo.

**New architectural point added by Liz:** there's a third thing that needs naming — **the skill-making part is the connecting piece between Make_Skills and the-loom.**

### The skill-making bridge (new — added 2026-05-25)

The act of MAKING A SKILL is where the-loom's pattern recognition meets Make_Skills' runtime capability. Specifically:

```text
the-loom (recognizes structure)
   │
   │ "this pattern is stable enough to become a skill — here's the source material"
   │
   ▼
Skill-Making System (the bridge — lives in Make_Skills the engine)
   │ - accepts promotion candidate from the-loom
   │ - compiles candidate into a skill .md (or refines an existing skill .md)
   │ - publishes to the shared skill registry
   │ - makes the runtime capability available to consumer products
   ▼
Consumer products' agents (load skill at runtime)
```

**Where this lives in the architecture:**

| Component | Owns | Lives in |
|---|---|---|
| **Pattern recognition + promotion governance** | Recognizing that a pattern is stable, deciding when it's promotion-ready | the-loom — `services/architecture-registry/` + the Project-Level Agency Optimizer |
| **Skill-making system** | Compiling a promoted candidate into a usable skill, registering it, making it available | Make_Skills (engine) — a new service, working name TBD (`services/skill-forge/`? `services/skill-pipeline/`? `services/skill-compiler/`?) |
| **Skill runtime** | Loading skills into agents, executing skill capability at runtime | Make_Skills (engine) — agent runtime |
| **Skill catalog / registry** | Storing all compiled skills, making them discoverable by consumer products | Shared — either lives in the-loom (as part of architecture registry) or in Make_Skills (as part of skill-making). Open question. |

**The contract between the-loom and Make_Skills:**

| Direction | What moves |
|---|---|
| the-loom → Make_Skills skill-making | Promotion candidate: pattern signature + source material + evidence + suggested name + suggested triggers |
| Make_Skills skill-making → the-loom | Compiled skill: `skill_id`, location of skill `.md`, capability metadata, registration confirmation |
| Make_Skills → consumer products | Runtime: skill available for agents to load |
| Consumer products → Make_Skills observability hooks | Telemetry from agent runtime (which skills got used, how often, in what contexts) |

That telemetry then flows back into the-loom's observability for the cycle to continue: usage of skills feeds new patterns, new patterns feed new promotions, new promotions feed new skill-making.

### What this clarifies about Make_Skills the engine

Make_Skills isn't just "an agent runtime with a skill compiler." It's **the system that takes recognized patterns from the-loom and embodies them as runnable capability** for any consumer product. The skill-making bridge is what makes Make_Skills the right home for an end-user's agent — because the platform (the-loom) and the agent runtime (Make_Skills) talk a clear contract: pattern → skill → runtime.

### What this clarifies about humancensys.com

Once Make_Skills is its own engine repo, humancensys.com becomes "the student-shaped Next.js app that uses Make_Skills' engine." Its job:
- Show students a UI they can use
- Provide student identity (Auth.js)
- Provide the onboarding journey, lesson content, IDENTITY-TO-HABIT framework
- Wire each student to a Make_Skills agent instance

It does NOT need to know anything about pattern recognition (the-loom's job), skill making (Make_Skills' job), or skill compilation internals. It just uses the engine.

## Future work (in order)

1. **Make_Skills data model** — Tenant, AgentInstance, Skill (compiled), SkillSource (.md), ModelProvider, MemoryRow, ConversationThread, etc. Analogous to the-loom's data model proposal.
2. **Make_Skills MVP repo layout** — what services exist in the engine, how it ships (Python package + Docker image), what the consumer integration looks like.
3. **Skill-making bridge spec** — the contract with the-loom in detail. Could be its own ADR.
4. **Migration roadmap for splitting humancensys.com out** — phases to extract `web/` + Auth.js + lesson content into `Lizo-RoadTown/humancensys-app`.

## What I want Liz to correct / confirm

1. Is my framing of Make_Skills (the engine) right?
2. Is my framing of humancensys.com (the first consumer) right?
3. Did I capture all the places I confused them in current code?
4. Is the long-term goal really four+ repos (the-loom, Make_Skills, humancensys-app, future projects), or am I overdecomposing?
5. Should the engine's distribution mechanism be: (a) a Python package + Docker image that consumers `pip install` and run, (b) a hosted SaaS where consumers point at a Render service, (c) both — self-host + hosted modes like Make_Skills currently does?
6. The Pillar 1/2/3 framing — was that always humancensys.com-specific, or is it engine-level? My current read: humancensys.com-specific (engine doesn't presume students or "make skills together" or any particular observability layout).

Waiting for input before drafting the data model + MVP layout + migration roadmap.
