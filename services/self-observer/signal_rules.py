"""Signal-rule engine for self-observer.

Reads a SKILL.md / agent.md / tool description and returns a Verdict:

    {
        "suggested_kind": "skill" | "agent" | "inline_tool" | "process",
        "confidence": float in [0, 1],
        "matched_rules": [str, ...],
        "reasons": [str, ...],  # human-readable explanations
    }

The rule weights live in config.SIGNAL_WEIGHTS. This module's job:
classify a single entry. Aggregation across entries lives in main.py.

Validation: tests/test_signal_rules.py runs this against the 16
docs-agent skills with their hand-classified verdicts from
tapestry/docs/proposals/2026-06-13-skill-vs-agent-conversion-and-self-observer.md
Part 1. The unit tests are the E1.5 gate before any deploy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from config import EMIT_THRESHOLD, SIGNAL_WEIGHTS

Kind = Literal["skill", "agent", "inline_tool", "process"]


# Regex rules. Each rule is (signal_name, compiled_pattern).
# Patterns are deliberately lenient — the weights in config tune precision.
_AGENT_SIGNAL_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Multi-step artifact production — strongest agent signal
    (
        "multi_step_artifact",
        re.compile(
            r"\b(produces? a (tradeoff matrix|report|plan|map|table|module table|diagram)"
            r"|writes? a (plan file|report|artifact))\b",
            re.IGNORECASE,
        ),
    ),
    # Explicit PROBE / scan verbs
    (
        "explicit_probe_verb",
        re.compile(
            r"\b(probes? (the |a |all )?(repo|context|codebase|directory|repos)"
            r"|walks? (back through|the |a )?\w+"
            r"|scans? (all |the )?\w+"
            r"|observes?\.\.\. identif(?:y|ies))\b",
            re.IGNORECASE,
        ),
    ),
    # Description literally names tools
    (
        "tool_list_in_description",
        re.compile(
            r"\b(use the [\w_,. ]+ tools|tools? (called|named) `[\w_]+`)\b",
            re.IGNORECASE,
        ),
    ),
    # Executes external operations
    (
        "executes_external",
        re.compile(
            r"\b(executes? the (build|harness|pipeline|migration)"
            r"|deploys?( where authorized)?"
            r"|run(s|ning)? (the |a )?\w+(?: \([^)]+\))? (harness|bench|suite|benchmark))\b",
            re.IGNORECASE,
        ),
    ),
    # Continuous / autonomous operation cue
    (
        "continuous_operation",
        re.compile(
            r"\b(use continuously, not as a one-shot|runs? on a schedule)\b",
            re.IGNORECASE,
        ),
    ),
    # Identify-and-recommend (orchestration-cataloging style): the agent inspects
    # work patterns and proposes structural moves. Two-step inspection → recommendation.
    (
        "identify_and_recommend",
        re.compile(
            r"\b(identif(?:y|ies|ying) [\w\s,'`-]+ and recommend"
            r"|identif(?:y|ies|ying) recurring \w+)\b",
            re.IGNORECASE,
        ),
    ),
    # Observer-self shape (agentic-upskilling pattern): "observe X, identify Y,
    # promote Z" — three sequenced verbs that describe an autonomous loop.
    # Loose comma-and-spaces tolerance for natural prose.
    (
        "observe_identify_promote_loop",
        re.compile(
            r"\b(observ(?:e|es|ing)[\w\s,'`-]+"
            r"identif(?:y|ies|ying)[\w\s,'`-]+"
            r"(?:promote|promot(?:e|ing) (?:those|them|these)) (?:into|to|as))\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)


_TOOL_SIGNAL_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Pure I/O transform — strong tool signal. Loosened to accept multi-word
    # items in comma-separated lists ("Convert PDFs, Word docs, ... into markdown").
    (
        "pure_io_transform",
        re.compile(
            r"\b(convert(s|ing)? [\w ,]+ (into|to) [\w-]+"
            r"|render(s|ing)? \w+ as \w+"
            r"|extract \w+ from \w+ (into|to) \w+)\b",
            re.IGNORECASE,
        ),
    ),
)


_SKILL_SIGNAL_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # "Use BEFORE every X" — strongest skill signal (output-shape rule)
    (
        "methodology_use_before",
        re.compile(r"\buse before every\b", re.IGNORECASE),
    ),
    # Template-following / fixed structure
    (
        "methodology_template",
        re.compile(
            r"\b(fixed section layout|template|house style)\b",
            re.IGNORECASE,
        ),
    ),
    # Architectural pattern / methodology framing
    (
        "methodology_pattern_for",
        re.compile(
            r"\b(architectural pattern for|meta-skill for designing|methodology for|pattern doc)\b",
            re.IGNORECASE,
        ),
    ),
)


@dataclass
class Verdict:
    suggested_kind: Kind
    confidence: float
    matched_rules: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def should_emit(self) -> bool:
        """Whether this verdict crosses the emit threshold."""
        return self.confidence >= EMIT_THRESHOLD


def _score_text(text: str) -> tuple[float, float, float, list[str]]:
    """Return (agent_score, tool_score, skill_score, matched_rule_names).

    Score is the sum of weights for matching rules in each category.
    Used by classify() to pick the highest-scoring kind.
    """
    matched: list[str] = []
    agent_score = 0.0
    tool_score = 0.0
    skill_score = 0.0

    for name, pattern in _AGENT_SIGNAL_RULES:
        if pattern.search(text):
            matched.append(name)
            agent_score += SIGNAL_WEIGHTS.get(name, 0.0)

    for name, pattern in _TOOL_SIGNAL_RULES:
        if pattern.search(text):
            matched.append(name)
            tool_score += SIGNAL_WEIGHTS.get(name, 0.0)

    for name, pattern in _SKILL_SIGNAL_RULES:
        if pattern.search(text):
            matched.append(name)
            # Skill rules have negative weights (subtract from agent/tool, add to skill confidence)
            skill_weight = abs(SIGNAL_WEIGHTS.get(name, 0.0))
            skill_score += skill_weight

    return agent_score, tool_score, skill_score, matched


def classify(
    description: str,
    current_location_kind: Kind,
    invocations_30d: int | None = None,
) -> Verdict:
    """Classify a single entry.

    Args:
        description: the frontmatter `description:` value (plus first ~100 lines of body)
        current_location_kind: where the file currently lives (`skill` if in skills/, `agent` if in agents/, etc.)
        invocations_30d: telemetry count over last 30 days. If 0, may emit a `process`
            candidate suggesting archive. None means telemetry unavailable for this entry.

    Returns:
        Verdict with suggested_kind. Caller decides whether to emit based on `should_emit`.
    """
    agent_score, tool_score, skill_score, matched = _score_text(description)
    reasons: list[str] = []

    # Orphan check: zero invocations over 30d AND location is "skill" or "agent"
    if invocations_30d == 0 and current_location_kind in ("skill", "agent"):
        reasons.append(f"Zero invocations over 30 days at current location ({current_location_kind})")
        return Verdict(
            suggested_kind="process",
            confidence=0.7,  # high confidence that something orphan-shaped is happening
            matched_rules=matched + ["orphan_zero_invocations"],
            reasons=reasons,
        )

    # No-match default: if no rules matched at all, the entry stays at its current
    # location with zero confidence. Without this, dict-ordering picks "agent" as
    # the default when all scores are zero, which floods the operator with false
    # positives for any plainly-described skill (e.g., "documentation" skill).
    if not matched:
        return Verdict(
            suggested_kind=current_location_kind,
            confidence=0.0,
            matched_rules=[],
            reasons=["No signals matched — entry stays at current location"],
        )

    # Pick the highest scoring kind. Skill is the "demotion" path when current is agent/tool.
    scores: dict[Kind, float] = {
        "agent": agent_score - skill_score,  # skill signals reduce agent likelihood
        "inline_tool": tool_score - skill_score,
        "skill": skill_score,
    }

    suggested = max(scores, key=lambda k: scores[k])
    raw_score = scores[suggested]

    # Skill case: if highest score is skill AND current location is already skill, no candidate.
    if suggested == "skill" and current_location_kind == "skill":
        return Verdict(
            suggested_kind="skill",
            confidence=0.0,  # no change needed
            matched_rules=matched,
            reasons=["Already a skill; methodology signals confirm classification"],
        )

    # Otherwise: confidence is the raw score clipped to [0, 1]
    confidence = max(0.0, min(1.0, raw_score))

    # If current location matches the suggestion, no candidate needed
    if suggested == current_location_kind:
        return Verdict(
            suggested_kind=suggested,
            confidence=0.0,
            matched_rules=matched,
            reasons=[f"Already classified as {suggested}; signals confirm"],
        )

    reasons.append(
        f"Currently in {current_location_kind}/, signals suggest {suggested}/ "
        f"(score={raw_score:.2f}, matched={matched})"
    )

    return Verdict(
        suggested_kind=suggested,
        confidence=confidence,
        matched_rules=matched,
        reasons=reasons,
    )
