# `engine/local-observer/`

**Status:** Slot. No code yet.

## Purpose

Watches sessions + memory writes + tool calls. Emits candidates to `services/candidate-registry`.

## Source

the-loom/adapters/claude-code/loom-discipline/scripts/observer.py

## When this slot populates

When the source has stabilized AND the operator approves migration. See [`../../docs/migration/README.md`](../../docs/migration/README.md).
