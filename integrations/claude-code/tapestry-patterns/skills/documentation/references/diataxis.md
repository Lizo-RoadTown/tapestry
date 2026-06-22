# Diátaxis: the four-type framework for documentation

> Source: [diataxis.fr](https://diataxis.fr) by Daniele Procida.

All documentation falls into exactly **four types**, organized along two axes:

| | **Practical (action)** | **Theoretical (cognition)** |
|---|---|---|
| **Acquisition (study)** | Tutorials | Explanation |
| **Application (work)** | How-to guides | Reference |

Conflating types is the #1 cause of bad documentation.

## 1. Tutorials

**For**: a beginner.
**Goal**: learning by doing.
**Voice**: a teacher leading the reader by the hand.

A tutorial is a lesson. It is **not** the place to be exhaustive, accurate, or
comprehensive. It is the place to give the learner a small, complete, satisfying
first experience of using the product.

### Rules

- The tutorial must produce a working result the learner can see
- Every command, every step, must be exact — no "you might want to also try X"
- Don't explain alternatives. The tutorial chooses one path
- Don't link to reference inside the steps — that breaks flow. Link at the end
- Length: as short as possible while still teaching something real

### Smells

- "You can also do X" → cut it
- "Refer to the docs for details" → the tutorial **is** docs; finish the thought
- Multiple options at one step → pick one
- An "advanced section" at the bottom → that's a how-to guide, move it

## 2. How-to guides

**For**: a competent user with a specific goal.
**Goal**: solving a problem.
**Voice**: a recipe.

A how-to guide assumes the reader knows the basics and has a job to do. It
addresses a real-world goal: "How do I deploy this to Railway?", "How do I
back up the database?". Not "How do I use the API in general" — that's reference.

### Rules

- Title is a verb phrase: "How to X"
- Address one goal, not several
- Skip the introduction. The reader is here to act
- Show the steps, not the theory
- Multiple how-to guides for related goals are fine; combining them is not

### Smells

- A how-to guide that's actually a tutorial in disguise
- A how-to guide that ends "and now you understand X" — that's an explanation
- One huge "how to use the system" doc with subsections for every task — split it

## 3. Reference

**For**: someone who already knows what they want, and just needs the details.
**Goal**: accurate description.
**Voice**: neutral, factual, exhaustive.

Reference is the encyclopedia. It tells you what every flag does, what every
endpoint returns, what every config key controls. It does **not** teach.

### Rules

- Match the structure of the thing being described (one page per module, one
  section per function)
- Be exhaustive within scope. Missing a field is a bug
- Do not editorialize. "This option is rarely useful" belongs in explanation
- Code samples should be minimal, demonstrating the surface — not a tutorial

### Smells

- Reference that explains *why* — move that to explanation
- Reference that walks through a workflow — move that to a how-to
- Reference with prose paragraphs longer than the code — you're explaining

## 4. Explanation

**For**: a curious user who wants context.
**Goal**: understanding.
**Voice**: discursive, conceptual.

Explanation is the place for the *why*. Why does the architecture look like this?
Why did we choose this database? Why is this API split into these endpoints?

### Rules

- Stand back and look at the bigger picture
- Talk about alternatives, history, trade-offs
- Don't tell the reader what to do — explanation is not instructions
- It's fine to be long, as long as it's coherent

### Smells

- Explanation that's actually a tutorial — "Here's how to set it up" → wrong type
- Explanation that's actually reference — exhaustive lists belong elsewhere
- Vague hand-wavy text — explanation should still be precise, just discursive

## How to know which type you're writing

Ask: **what is the reader trying to do right now?**

| Reader's state | Type |
|----|----|
| "I'm new and want to try this thing" | Tutorial |
| "I have a specific job to get done" | How-to guide |
| "I need to look something up" | Reference |
| "I want to understand why" | Explanation |

If you can't answer cleanly, the document is mixed — split it.

## Folder structure

A common layout that mirrors the framework:

```
docs/
├── tutorials/
│   └── getting-started.md
├── how-to/
│   ├── deploy.md
│   └── back-up-database.md
├── reference/
│   ├── api.md
│   └── config.md
└── explanation/
    └── architecture.md
```

Some teams flatten this and rely on the file name (e.g. `how-to-deploy.md`)
or section headers in a single index. Either works as long as the *types* are
not mixed within a single file.

## Why this works

The framework is not a style guide. It's a **classifier**. Once you know which
type you're writing, the voice, structure, and rules follow automatically. Most
"documentation problems" are misclassification problems.
