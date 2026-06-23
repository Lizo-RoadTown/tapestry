---
title: Observer-derived intent
description: Intent is not a telemetry field. Telemetry records events; the observer interprets events and derives intent hypotheses. The distinction is load-bearing — adding intent attributes to telemetry collapses the observer's interpretation layer into the emission layer.
---

Telemetry records events. The observer derives meaning. Intent is observer-derived meaning, not emitted telemetry.

## The shape

```
events
   ↓
observer
   ↓
interpretation
   ↓
intent hypothesis
```

Not this:

```
event
  → intent field
```

## What telemetry reliably captures

- a tool call
- a memory read
- a memory write
- a file modification
- an architecture change
- a correction event

## What telemetry cannot reliably capture

- what the operator was ultimately trying to accomplish
- why a correction occurred
- whether a sequence of actions was successful
- whether the episode strengthened coordination

Those require interpretation. The observer is the layer that interprets.

## Intent as hypothesis

Intent is stored as a hypothesis with confidence + evidence, not as an unquestioned fact. Schema:

| Field | Example |
|---|---|
| `intent_summary` | "Clarify project observatory architecture" |
| `intent_category` | "architecture_design" |
| `confidence` | 0.83 |
| `derivation_method` | "observer" |
| `supporting_evidence` | `[prompt_ref, architecture_diff_ref, memory_entry_ref]` |

## Confidence states

- `high_confidence`
- `medium_confidence`
- `low_confidence`
- `unknown`

Unknown intent is a valid outcome. Uncertainty is preferable to false certainty.

## What the observer combines

When deriving an intent hypothesis, the observer may use any combination of:

- user prompts
- agent responses
- tool activity
- memory activity
- architecture changes
- correction events
- prior observer findings

The set of signals the observer used lands in `derivation_method`.

## Corrections become observer signals

Intent hypotheses may be revised. Repeated revisions are themselves signals — they indicate observer weakness, missing context, memory gaps, project-shape changes, or emerging coordination patterns. Those revisions are themselves observable telemetry.

## What intent supports

The purpose of intent derivation is to help the platform answer:

- What was the operator trying to accomplish?
- What did the agent do?
- What obstacles appeared?
- Did memory help or fail?
- Did coordination strengthen or weaken?
- Did a durable structure emerge?

Without intent, telemetry can only describe what happened. It cannot describe whether coordination succeeded, failed, improved, degraded, or produced durable structure.

## Dashboard implication

The dashboard does not display raw intent fields. It displays observer-generated intent hypotheses and their supporting evidence.

The [OTel coordination contract](/reference/otel-coordination-contract/) defines what gets emitted (the typed attributes). The observer reads those events + memory + transcripts + diffs and produces the intent hypothesis as a separate output layer.

## Canonical statement

Telemetry records events. The observer derives meaning. Intent is observer-derived meaning, not emitted telemetry.

## Related

- [The observer](/explanation/the-observer/) — the component that derives intent
- [OTel coordination contract](/reference/otel-coordination-contract/) — what gets emitted (intent is not on the list)
- [The signal hierarchy](/explanation/signal-hierarchy/) — interpretation lives at the patterns level, not the events level
