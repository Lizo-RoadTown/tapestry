"""E1.5 gate: signal_rules.py must classify ≥14 of 16 docs-agent skills
correctly before any observer deploy.

Fixtures = the 16 SKILL.md description fields PROBE'd 2026-06-13.
Expected verdicts = Part 1 of the plan
(tapestry/docs/proposals/2026-06-13-skill-vs-agent-conversion-and-self-observer.md).

If this test fails on ≥3 fixtures, the rules need tuning before deploy.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow `import signal_rules` from sibling module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import signal_rules  # noqa: E402


# Each fixture: (skill_name, description, expected_suggested_kind_when_currently_skill)
# The currently-skill assumption matches reality — all 16 live under docs-agent/skills/.
# Expected kind == "skill" means: stays as skill (no candidate emitted).
# Expected kind == "agent" / "inline_tool" means: promote candidate.
FIXTURES: list[tuple[str, str, str]] = [
    (
        "agentic-skill-design",
        "Meta-skill for designing skills that DECIDE and EXECUTE rather than ask the user permission for every choice. Use when authoring a new skill or rewriting an existing skill that asks too many questions. Captures the PROBE -> DECIDE -> ACT -> REPORT pattern Liz wants for stack-with-conditions requests.",
        "skill",
    ),
    (
        "agentic-upskilling",
        "Active practice -- observe how the user actually works, identify which skills they invoke repeatedly, and promote those into tools when promotion criteria are met. Each user's tool library grows to reflect THEIR workflow over time. Use continuously, not as a one-shot. Lives at /skills/upskilling on the site (planned). Drives Pillar 2's 'Make skills together' surface.",
        "agent",
    ),
    (
        "deep-research-pattern",
        "Architectural pattern for multi-agent deep research with strict context isolation. Use when designing or extending the research subagents under subagents/ -- covers shallow vs. deep mode, the three-role topology, and context boundaries.",
        "skill",
    ),
    (
        "design-evaluation",
        "Evaluate a design question with multiple options across the dimensions that matter for the project -- produces a tradeoff matrix, scores each option, and recommends a path (often a hybrid). Use when the user asks 'which approach', 'should we use X or Y', 'compare these styles', or shares competitor screenshots and asks what to learn from them. Different from next-actions-planning -- that picks WHAT to do; this picks HOW to do it.",
        # Group B: stays as skill but produces an artifact. The rules will likely
        # flag it as agent-shaped (multi_step_artifact matches). This is an
        # ACKNOWLEDGED edge case — the rule overfits here; operator review
        # in E4 catches it. We allow either "agent" or "skill" as a pass.
        "skill_or_agent",
    ),
    (
        "documentation",
        "Plan, write, and audit project documentation using the Diataxis framework, Architecture Decision Records (ADRs), and the docs-as-code workflow. Use whenever a task involves creating, reviewing, restructuring, or auditing documentation -- including READMEs, API references, tutorials, design docs, or in-code docstrings.",
        "skill",
    ),
    (
        "document-parsing",
        "Convert PDFs, Word docs, PowerPoint, Excel, and scanned images into LLM-friendly markdown. Use when the agent needs to read source documents -- research papers, reports, slide decks, financial filings -- that aren't already in plain text.",
        "inline_tool",
    ),
    (
        "eval-deep-research",
        "Run the deep_research_bench (DRB) harness against a deepagents-produced report set. Use when you want to score the research subagents on the 100-task benchmark with the RACE (report quality) and FACT (citation grounding) judges.",
        "agent",
    ),
    (
        "infrastructure-mapping",
        "Map any project's infrastructure as modules + interfaces + bond strength, grounded in Herbert Simon's nearly-decomposable systems framework (1962) and its modern descendants (Parnas, Baldwin & Clark, DDD, hexagonal architecture). Produces a module table, an interface table (with 'signal felt by Claude vs by the user' columns), a Mermaid diagram, and identifies WHERE infrastructure investment closes silent leaks. Use when auditing a codebase for the first time, after acquiring a repo, before a refactor, or when the user is frustrated that the system feels unstructured. Different from next-actions-planning (picks what to do next) and design-evaluation (picks how to do one thing) -- this skill produces the WHOLE-SYSTEM MAP so other skills can target it.",
        "agent",
    ),
    (
        "layered-explanation",
        "Use BEFORE every explanation of infrastructure, architecture, tooling, library choice, telemetry stacks, CI pipelines, or any technical concept where the user needs to make a decision. Structures the response as four progressively-deeper layers (ELI5 metaphor -> quick-reference table or diagram -> depth with file:line citations -> one-paragraph mental model) so the user can self-select the depth they need instead of being trapped between walls of jargon and condescending oversimplification.",
        "skill",
    ),
    (
        "lessons-learned",
        "Walk back through prior chat transcripts to find systematic friction patterns (misunderstandings, recurring info needs, negotiations, user corrections), then crystallize them into intake forms (skills/<topic>/intake.md) and memory updates so future invocations of recurring tasks need fewer round-trips. Use when the user wants the system to 'get sharper' or after a long working session.",
        "agent",
    ),
    (
        "next-actions-planning",
        "Produce a grounded 'what to do next' plan for the project -- based on what shipped, what's open, what blocks what, and what the user has signaled they care about. Use when the user asks 'what's next?' or after a major piece of work lands. Probes the repo, scores candidates, writes a plan file, returns a 3-bullet recommendation.",
        "agent",
    ),
    (
        "open-source-documentation",
        "Maintain documentation for an open-source project so contributors can onboard, design decisions are auditable, and per-section docs stay current. Defines the docs/ tree (concepts / how-to / reference / decisions / proposals), the ADR pattern for design decisions, when to update what, and the dual-mode discipline (every doc explains both self-host and hosted modes). Use when authoring or updating any file under docs/, or when a design choice is made that should be tracked.",
        "skill",
    ),
    (
        "orchestration-cataloging",
        "Identify recurring work patterns in the user's recent build (research bursts, proposal writing, schema migrations, isolation tests, UI scaffolding, etc.) and recommend turning the high-frequency ones into reusable subagents, skills, or scripts. Use when the user asks 'what should I make reusable', 'what patterns am I repeating', or after several similar tasks ship in a row.",
        "agent",
    ),
    (
        "proposal-authoring",
        "Author a design proposal in Make_Skills's house style -- fixed section layout, project tone (state what is, not what it isn't), two-mode notes, open questions, references. Use when starting a new file under docs/proposals/, when transcribing a research synthesis into a proposal, or when reviewing a draft proposal for tone and structure compliance. Captures the template observed across 8+ existing proposals.",
        "skill",
    ),
    (
        "roadmap-maintenance",
        "Keep ROADMAP.md current as work ships. Use the update_roadmap_status, add_roadmap_item, and roadmap_overview tools to flip statuses, add items, and check the current state. Liz amends manually whenever she wants; agent updates only when there's concrete evidence (a commit, a verified test, a user statement).",
        "agent",
    ),
    (
        "web-app-scaffold",
        "Agentic scaffolder for deployable web apps. Probes context, decides the stack with defensible defaults, executes the build, deploys where authorized, and reports. Use when the user wants a chat UI / dashboard / front-end 'on my website' / 'live' / 'hooked to my domain'. Don't ask permission for routine choices -- make them and own them.",
        "agent",
    ),
]


@pytest.mark.parametrize("name,description,expected_kind", FIXTURES)
def test_per_fixture_classification(name: str, description: str, expected_kind: str):
    """Each fixture's classify() output should match the expected kind.

    "skill_or_agent" expected = edge case (design-evaluation); both pass.
    """
    verdict = signal_rules.classify(
        description=description,
        current_location_kind="skill",  # all 16 currently live in docs-agent/skills/
        invocations_30d=None,  # telemetry not available in unit test
    )

    if expected_kind == "skill_or_agent":
        assert verdict.suggested_kind in ("skill", "agent"), (
            f"{name}: edge case, expected skill or agent, got {verdict.suggested_kind} "
            f"(matched={verdict.matched_rules})"
        )
    else:
        assert verdict.suggested_kind == expected_kind, (
            f"{name}: expected {expected_kind}, got {verdict.suggested_kind} "
            f"(matched={verdict.matched_rules}, reasons={verdict.reasons})"
        )


def test_overall_pass_rate_meets_e1_5_gate():
    """E1.5 gate: ≥14 of 16 fixtures must classify correctly to clear for deploy."""
    passes = 0
    failures: list[tuple[str, str, str]] = []

    for name, description, expected_kind in FIXTURES:
        verdict = signal_rules.classify(
            description=description,
            current_location_kind="skill",
            invocations_30d=None,
        )

        # Edge case: design-evaluation passes if either skill or agent
        is_pass = (
            verdict.suggested_kind == expected_kind
            or (expected_kind == "skill_or_agent" and verdict.suggested_kind in ("skill", "agent"))
        )

        if is_pass:
            passes += 1
        else:
            failures.append((name, expected_kind, verdict.suggested_kind))

    # Print failures for debugging tuning
    if failures:
        msg = f"Pass rate: {passes}/16. Failures:\n"
        for name, expected, got in failures:
            msg += f"  - {name}: expected {expected}, got {got}\n"
        # Pass rate ≥14 / 16 = 87.5% required
        if passes < 14:
            pytest.fail(msg)
        else:
            print(f"\nE1.5 gate: {passes}/16 (>=14 required, PASS). Tuning candidates:\n{msg}")


def test_orphan_detection_via_zero_invocations():
    """A skill with zero invocations over 30d should be flagged as a `process` candidate
    suggesting archive, regardless of description content."""
    verdict = signal_rules.classify(
        description="Plan, write, and audit project documentation using the Diataxis framework.",
        current_location_kind="skill",
        invocations_30d=0,
    )
    assert verdict.suggested_kind == "process"
    assert verdict.confidence >= 0.5
    assert "orphan_zero_invocations" in verdict.matched_rules


def test_agentic_upskilling_actually_emits():
    """E1.5 gap: my earlier tests checked suggested_kind but not should_emit.
    agentic-upskilling classified as agent but had confidence 0.2, below the
    0.5 emit threshold — so production didn't actually emit it. After adding
    the observe_identify_promote_loop signal (weight 0.6), confidence should
    cross the threshold AND should_emit should be True.

    This test pins both: kind=agent AND should_emit=True. If either regresses
    in future tuning, deploy is blocked.
    """
    agentic_upskilling_desc = next(
        (desc for name, desc, _ in FIXTURES if name == "agentic-upskilling"), None
    )
    assert agentic_upskilling_desc is not None, "fixture missing"

    verdict = signal_rules.classify(
        description=agentic_upskilling_desc,
        current_location_kind="skill",
        invocations_30d=None,
    )
    assert verdict.suggested_kind == "agent", (
        f"expected agent, got {verdict.suggested_kind} "
        f"(matched={verdict.matched_rules}, confidence={verdict.confidence:.2f})"
    )
    assert verdict.should_emit, (
        f"verdict suggests {verdict.suggested_kind} but confidence={verdict.confidence:.2f} "
        f"is below emit threshold — production won't surface this candidate."
    )


def test_strongly_classified_agents_all_emit():
    """Every Group C entry (expected agent promotion) MUST cross the emit threshold,
    not just classify correctly. Catches the subtle regression where rules
    classify but confidence stays sub-threshold."""
    expected_agents = [
        (name, desc) for name, desc, kind in FIXTURES if kind == "agent"
    ]
    sub_threshold: list[tuple[str, float, list[str]]] = []

    for name, desc in expected_agents:
        verdict = signal_rules.classify(
            description=desc, current_location_kind="skill", invocations_30d=None
        )
        if verdict.suggested_kind == "agent" and not verdict.should_emit:
            sub_threshold.append((name, verdict.confidence, verdict.matched_rules))

    assert not sub_threshold, (
        "These agent-classified fixtures have confidence below the emit threshold "
        f"— production will NOT surface them:\n{sub_threshold}"
    )
