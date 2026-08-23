"""Telemetry-batch wire-contract models for the skill-making bridge
(engine → telemetry-ingestion direction).

Subset of the full bridge schema (architecture-registry has the complete
copy for the promotion + ack direction). This file only carries what
telemetry-ingestion's POST /skill-used endpoint needs to receive.

The duplication is deliberate at this phase: each service owns its
import surface, no shared library yet. When the third or fourth service
copies this file, extract to packages/shared/bridge/.

Source spec: Make_Skills `docs/proposals/2026-05-25-skill-making-bridge.md`
§3, with my ratification adjustments (loom-memory:
loom_agent_skill_bridge_ratification_2026_06_12_evening) +
MS-agent's PR #69 incorporation.

## Privacy invariant (NEVER REGRESS)

TelemetryEvent carries STRUCTURAL METADATA ONLY. No message content. No
agent response content. No PII. `trigger_context` is a short CATEGORICAL
tag, NOT the message text. extra='forbid' enforces this at the schema
layer; a future contributor cannot add a `message_content` field without
ValidationError.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"

TELEMETRY_OUTCOME = Literal["success", "error", "timeout"]


class TelemetryEvent(BaseModel):
    """Per-invocation telemetry. Privacy: structural metadata only."""

    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
    thread_id: UUID = Field(
        ...,
        description="Engine's thread, NOT consumer's user_id.",
    )
    tenant_id: UUID = Field(
        ...,
        description="REQUIRED, not nullable. Adjustment #1.",
    )
    invoked_at: str = Field(..., description="ISO 8601 timestamp.")
    outcome: TELEMETRY_OUTCOME
    latency_ms: int = Field(..., ge=0)
    tokens_in: int = Field(..., ge=0)
    tokens_out: int = Field(..., ge=0)
    model: str = Field(
        ...,
        description="Model identifier, e.g. 'claude-opus-4-7'.",
    )
    trigger_context: str = Field(
        ...,
        max_length=64,
        description=(
            "Short CATEGORICAL tag, NOT the message text. e.g. "
            "'user message', 'autonomous loop tick'."
        ),
    )


class TelemetryBatch(BaseModel):
    """engine → the-loom. POST {callbacks.telemetry_endpoint}.

    Signed with HMAC-SHA256. Up to 1000 events per batch per the spec.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = Field(default=SCHEMA_VERSION)
    batch_id: UUID = Field(..., description="Dedup key for the batch.")
    events: list[TelemetryEvent] = Field(
        ...,
        min_length=1,
        max_length=1000,
    )
