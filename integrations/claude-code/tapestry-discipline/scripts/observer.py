"""
Phase 2 local observer for the recursive-skill engine.

Per the ratified build sequence (loom_agent_to_ms_agent_pillar_2_sequence_
ratified_2026_06_12), Phase 2 turns the agent's upskilling reports into
durable Architecture Registry candidate rows. This is the missing Path A
mechanism — without it, candidates only land via manual operator POSTs.

## Layer composition

  Stop hook (v0.1.9, CORE DIRECTIVE 3)
      ↓ surfaces "*** UPSKILLING PASS NOT RUN ***" if missed
  Agent runs the upskilling pass
      ↓ emits "Skills invoked this session: ... (N uses)" + memory_write
  This observer (v0.1.10, Phase 2)
      ↓ parses the report + counts explicit Skill tool calls
      ↓ POSTs new candidates to architecture-registry
      ↓ PATCHes status as sessions_seen crosses thresholds
  Architecture Registry candidate row
      ↓ available via GET /candidates for the future upskilling dashboard

## What this module does

Given a transcript JSONL + the project's .project-intelligence/ directory:

  1. Counts explicit `Skill` tool invocations across the session
     (objective signal, undercounts because skills are mostly applied
     behaviorally without an explicit tool call).
  2. Parses the most recent upskilling report in the transcript for
     "Skills invoked: ... (N uses)" pattern (the agent's introspective
     count — authoritative when present).
  3. Merges both signal sources, taking the higher count per skill.
  4. For each skill with count >= MIN_COUNT_TO_CONSIDER:
       - Loads local record from
         .project-intelligence/workflow-candidates/<slug>.json
       - Dedups by (session_id, skill_name) — same skill in same session
         doesn't re-emit.
       - If new: POSTs candidate to /candidates (status=draft)
       - If recurring: PATCHes status as sessions_seen crosses thresholds
         (draft -> observed at 2, observed -> recurring at 3)
       - Persists the local record.

## What this module does NOT do

  - Detect workflow / decision / pattern candidates (only skill type for v1)
  - Compute the deeper signals (has_clear_triggers, has_stable_steps,
    reduces_need_for_live_judgment) — those need LLM judgment, deferred to
    a Phase 2.x revision
  - Cross-project signals (Phase 3 Pattern Detection)
  - Promotion governance (Phase 5 Policy Service)

## Two-mode commitment

The observer hits the Architecture Registry via HTTP with no Authorization
header. The Registry's auth_bridge.verify_bearer treats this as self-host
mode (returns SELF_HOST_TENANT_ID). For hosted-multitenant use, the
observer would need to mint or read a JWT — deferred until any project
actually needs that mode.

## Failure semantics

The observer NEVER blocks Stop hook flow. All HTTP failures, parse
failures, IO errors are caught and logged silently. The Stop hook proceeds
regardless. Worst case: a candidate isn't emitted this session; the next
session will try again.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Registry endpoint. Env-override precedence (PR-prep-2b 2026-06-19):
#   1. TAPESTRY_ARCHITECTURE_REGISTRY_URL — Tapestry-migration-aware deployments
#      set this to their own deployment host.
#   2. LOOM_ARCHITECTURE_REGISTRY_URL — bare base host.
#   3. Placeholder default — set one of the above to your own deployment host.
# Same precedence pattern lives at the per-call override below (search for
# TAPESTRY_ARCHITECTURE_REGISTRY_URL).
_REGISTRY_DEFAULT_URL = os.environ.get(
    "TAPESTRY_ARCHITECTURE_REGISTRY_URL",
    os.environ.get(
        "LOOM_ARCHITECTURE_REGISTRY_URL",
        "https://your-architecture-registry.example.com",
    ),
)
_CANDIDATES_PATH = "/candidates"

# Memory MCP REST endpoint — for writing candidates back into loom-memory
# so they surface via auto-recall in any agent's session (CORE DIRECTIVE 1
# cross-agent channel). Same env precedence as the architecture-registry.
_MEMORY_URL = os.environ.get(
    "TAPESTRY_MEMORY_MCP_URL",
    os.environ.get(
        "LOOM_MEMORY_MCP_URL",
        f"{os.environ.get('TAPESTRY_MEMORY_URL', os.environ.get('LOOM_MEMORY_URL', 'https://your-memory-host.example.com')).rstrip('/')}",
    ),
).rstrip("/").removesuffix("/mcp/memory")
_MEMORY_WRITE_PATH = "/v1/write"

# A skill must be invoked at least this many times in a session to be
# considered for candidate emission. Tuned conservative — the SKILL.md
# 5-criteria gate says "3+ uses" so we match.
MIN_COUNT_TO_CONSIDER = 3

# Status transition thresholds based on sessions_seen (the longitudinal
# count). Per docs/proposals/2026-05-25-agency-optimizer-pattern.md:188.
#   sessions_seen == 1  -> draft
#   sessions_seen == 2  -> observed
#   sessions_seen >= 3  -> recurring
# Higher transitions (stable, promotion_requested) are NOT made by the
# observer — those require LLM judgment or Policy Service decisions in
# later phases.
_STATUS_BY_SESSIONS_SEEN = {1: "draft", 2: "observed"}
_RECURRING_AT = 3

# Local record schema version — bump when the JSON shape changes
# meaningfully so future-self can detect old records.
LOCAL_RECORD_SCHEMA_VERSION = 1

# Slug regex for filenames (workflow-candidates/<slug>.json).
_SLUG_INVALID = re.compile(r"[^a-zA-Z0-9_-]+")


# Upskilling-report parser. Each line looks like one of these (per
# docs/CORE_DIRECTIVES.md Directive 3):
#
#     - layered-explanation       (15+ uses)
#     - layered-explanation (15 uses)
#     - layered-explanation: 15
#
# The regex captures the skill name and the integer (ignoring `+`).
# Skill names typically use lowercase + hyphens; some include `:` prefixes
# (`superpowers:systematic-debugging`) — we keep the full path-style name.
_REPORT_LINE_RE = re.compile(
    r"-\s+`?(?P<skill>[a-zA-Z][a-zA-Z0-9:_-]+)`?\s*[(:]"
    r"\s*(?P<count>\d+)\+?\s*(?:uses?|use\b|\))?",
    re.IGNORECASE,
)

# v2 (Phase 2 refinement, after ms_agent_to_loom_agent_loom_platform_seeded_
# 2026_06_12): also catch the "Promotion candidates" section of the
# upskilling report. Each line is an agent-surfaced proposal — a new
# skill the agent thinks is worth codifying. Unlike skill-invocation
# counts these don't need a >= 3 threshold; each entry is one observation
# of an agent's judgment that this is worth promoting.
_PROMOTION_CANDIDATE_BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<body>\S.*)$")

# Bullet bodies that indicate "no candidates this session". Skip these.
_NEGATIVE_SIGNAL_PREFIXES = (
    "none",
    "n/a",
    "no new",
    "nothing",
)

# Section markers that bound the "Promotion candidates" subsection.
_PROMOTION_SECTION_END = (
    "demotion candidates",
    "recommendations",
    "outcome",
    "key facts",
    "what's next",
    "next steps",
)

# Delimiters used between a candidate's NAME and its DESCRIPTION in
# bullet text. Em-dash with surrounding spaces is MS-agent's convention
# in their upskilling reports; ": " is the fallback.
_NAME_DESC_DELIMS = (" — ", " – ", " -- ", ": ")


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------


def count_skill_tool_calls(raw: str) -> dict[str, int]:
    """Walk the JSONL transcript and count explicit `Skill` tool
    invocations by skill name. Returns dict[skill_name -> count].

    Skills invoked via the Skill tool look like:
      {"role":"assistant", "content":[
        {"type":"tool_use", "name":"Skill", "input":{"skill":"<name>", ...}}
      ]}

    This is the OBJECTIVE signal — concrete tool invocations. Undercounts
    because most skill application is behavioral (auto-loaded SKILL.md
    content without an explicit tool call); the upskilling-report parser
    captures the rest.
    """
    counts: dict[str, int] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = entry.get("role") or (entry.get("message") or {}).get("role") or ""
        if role != "assistant":
            continue
        content = entry.get("content") or (entry.get("message") or {}).get("content") or []
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            if block.get("name") != "Skill":
                continue
            tool_input = block.get("input") or {}
            skill_name = ""
            if isinstance(tool_input, dict):
                skill_name = tool_input.get("skill") or ""
            if not skill_name:
                continue
            counts[skill_name] = counts.get(skill_name, 0) + 1
    return counts


def parse_upskilling_report(raw: str) -> dict[str, int]:
    """Find the most recent upskilling-report block in the transcript
    and parse out "Skills invoked: ... (N uses)" lines.

    The report block per docs/CORE_DIRECTIVES.md Directive 3 has the marker
    "Skills invoked this session" followed by indented lines.
    This function:
      1. Locates the LATEST assistant text containing the marker.
      2. Extracts the section starting from the marker until the next
         section marker (Tools called, Promotion, Demotion, Recommendations)
         or end of text.
      3. Parses each "- skill-name (N uses)" line.

    Returns dict[skill_name -> count]. Empty dict if no report found or
    no parseable lines.
    """
    # Walk forward; keep overwriting so we capture the LATEST.
    latest_report_text = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = entry.get("role") or (entry.get("message") or {}).get("role") or ""
        if role != "assistant":
            continue
        content = entry.get("content") or (entry.get("message") or {}).get("content") or []
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            text = block.get("text") or ""
            if "skills invoked this session" in text.lower():
                latest_report_text = text

    if not latest_report_text:
        return {}

    # Extract just the "Skills invoked" subsection. Look for the marker,
    # then capture until the next section marker or end-of-text.
    lower = latest_report_text.lower()
    start = lower.find("skills invoked this session")
    if start < 0:
        return {}
    # Find next section marker after start.
    end_markers = ("tools called", "promotion candidates", "demotion candidates",
                   "recommendations")
    end = len(latest_report_text)
    for m in end_markers:
        idx = lower.find(m, start + len("skills invoked this session"))
        if idx > 0 and idx < end:
            end = idx
    section = latest_report_text[start:end]

    # Parse each bullet line.
    counts: dict[str, int] = {}
    for line in section.splitlines():
        m = _REPORT_LINE_RE.search(line)
        if not m:
            continue
        skill = m.group("skill").strip()
        try:
            count = int(m.group("count"))
        except (TypeError, ValueError):
            continue
        # Don't shadow the `agentic-upskilling` skill itself — it's the
        # one running the report, not a candidate.
        if skill.lower() in ("agentic-upskilling", "agentic_upskilling"):
            continue
        # Merge — take max if duplicated within the section.
        prior = counts.get(skill, 0)
        counts[skill] = max(prior, count)

    return counts


def _split_promotion_entry(body: str) -> tuple[str, str]:
    """Split a promotion-candidate bullet body into (name, description).

    Example inputs and their splits:

      '"Diagnose plugin version state" procedure — reconstructed from...'
         -> name='"Diagnose plugin version state" procedure',
            description='reconstructed from...'

      'probe_then_cite: STRONG candidate. 5/5 criteria met...'
         -> name='probe_then_cite',
            description='STRONG candidate. 5/5 criteria met...'

      'some-skill'
         -> name='some-skill', description=''

    The name is stripped of surrounding quotes/backticks since slugify
    will re-normalize anyway.
    """
    for delim in _NAME_DESC_DELIMS:
        idx = body.find(delim)
        if idx > 0:
            name = body[:idx].strip().strip('"').strip("`").strip()
            desc = body[idx + len(delim):].strip()
            return name, desc
    return body.strip().strip('"').strip("`").strip(), ""


def parse_promotion_candidates(raw: str) -> list[dict[str, str]]:
    """v2 (Phase 2 refinement): find the most recent upskilling-report
    block in the transcript and parse out the "Promotion candidates"
    section.

    Returns a list of {"name": <str>, "description": <str>} dicts.
    Negative-signal entries (None / N/A / "no new this session") are
    skipped.

    Unlike skill-invocation counts (which require >= 3 to be candidate-
    eligible), each entry in this section represents an AGENT-SURFACED
    proposal — the agent's judgment that this is worth codifying. The
    threshold is 1. scan_and_emit posts these immediately with
    signals.is_new_skill_idea = True so the platform can distinguish
    "skill used N times" from "skill that should exist."
    """
    latest_report_text = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = entry.get("role") or (entry.get("message") or {}).get("role") or ""
        if role != "assistant":
            continue
        content = entry.get("content") or (entry.get("message") or {}).get("content") or []
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            text = block.get("text") or ""
            if "promotion candidates" in text.lower():
                latest_report_text = text

    if not latest_report_text:
        return []

    lower = latest_report_text.lower()
    start = lower.find("promotion candidates")
    if start < 0:
        return []
    end = len(latest_report_text)
    for marker in _PROMOTION_SECTION_END:
        idx = lower.find(marker, start + len("promotion candidates"))
        if idx > 0 and idx < end:
            end = idx
    section = latest_report_text[start:end]

    results: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for line in section.splitlines():
        m = _PROMOTION_CANDIDATE_BULLET_RE.match(line)
        if not m:
            continue
        body = m.group("body").strip()
        if not body:
            continue
        lower_body = body.lower()
        if any(lower_body.startswith(s) for s in _NEGATIVE_SIGNAL_PREFIXES):
            continue
        name, description = _split_promotion_entry(body)
        # Skip degenerate names (too short, all punctuation, etc.).
        if not name or len(name) < 2:
            continue
        # Skip names that duplicate within this section (could happen if
        # an entry mentions multiple slugs).
        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        results.append({"name": name, "description": description[:512]})

    return results


def merge_counts(*sources: dict[str, int]) -> dict[str, int]:
    """For each skill name across all sources, return the MAX count.
    The agent's report and the explicit Skill tool count are both
    floors of "how many times was this skill applied" — take the larger."""
    merged: dict[str, int] = {}
    for source in sources:
        for skill, count in source.items():
            if count > merged.get(skill, 0):
                merged[skill] = count
    return merged


# ---------------------------------------------------------------------------
# Local record management
# ---------------------------------------------------------------------------


def _slugify_skill(skill_name: str) -> str:
    """Skill name -> safe-for-filesystem slug. `superpowers:systematic-debugging`
    becomes `superpowers-systematic-debugging`. Same convention as the
    upskilling SKILL.md's report format."""
    s = skill_name.strip().replace(":", "-").replace("/", "-").replace("\\", "-")
    s = _SLUG_INVALID.sub("-", s)
    s = s.strip("-")[:128]
    return s.lower() or "unknown"


def _local_record_path(project_intelligence_dir: Path, skill_name: str) -> Path:
    return (
        project_intelligence_dir / "workflow-candidates"
        / f"{_slugify_skill(skill_name)}.json"
    )


def _load_local_record(path: Path) -> dict[str, Any]:
    """Load the JSON record at path; return defaults if missing/unreadable."""
    if not path.exists():
        return {
            "schema_version": LOCAL_RECORD_SCHEMA_VERSION,
            "candidate_id": None,
            "skill_name": "",
            "sessions_seen": 0,
            "session_ids": [],
            "total_count": 0,
            "last_count": 0,
            "first_seen_at": 0.0,
            "last_seen_at": 0.0,
            "current_status": "draft",
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema_version": LOCAL_RECORD_SCHEMA_VERSION,
            "candidate_id": None,
            "skill_name": "",
            "sessions_seen": 0,
            "session_ids": [],
            "total_count": 0,
            "last_count": 0,
            "first_seen_at": 0.0,
            "last_seen_at": 0.0,
            "current_status": "draft",
        }


def _save_local_record(path: Path, record: dict[str, Any]) -> None:
    """Atomic-ish write. Best-effort; on failure, the next session retries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _read_project_uuid(project_intelligence_dir: Path) -> Optional[str]:
    """Read the UUID from .project-intelligence/project-context.json (per
    tapestry_cli/init.py:_write_project_intelligence). Returns None if
    absent — observer skips when it can't resolve the project_id."""
    path = project_intelligence_dir / "project-context.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pid = data.get("project_id")
        # Sanity check: UUID shape. Don't pass through arbitrary strings.
        if isinstance(pid, str) and len(pid) == 36 and pid.count("-") == 4:
            return pid
    except (OSError, json.JSONDecodeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------


def derive_status(sessions_seen: int) -> str:
    """Map sessions_seen to candidate status. Phase 2 only manages the
    early states; higher transitions (stable, promotion_requested) come
    from Phase 5 Policy Service."""
    if sessions_seen >= _RECURRING_AT:
        return "recurring"
    return _STATUS_BY_SESSIONS_SEEN.get(sessions_seen, "draft")


# ---------------------------------------------------------------------------
# HTTP — POST / PATCH to Architecture Registry
# ---------------------------------------------------------------------------


def _registry_url() -> str:
    """The registry base URL. Allows override via TAPESTRY_ARCHITECTURE_REGISTRY_URL
    (Tapestry-aware) or LOOM_ARCHITECTURE_REGISTRY_URL (pre-Tapestry) for
    testing or future hosted-multitenant deploys."""
    url = (
        os.environ.get("TAPESTRY_ARCHITECTURE_REGISTRY_URL")
        or os.environ.get("LOOM_ARCHITECTURE_REGISTRY_URL")
        or _REGISTRY_DEFAULT_URL
    )
    # Don't follow localhost overrides in production hook fires.
    if url.startswith("http://localhost") or url.startswith("http://127."):
        return _REGISTRY_DEFAULT_URL
    return url


def _memory_auth_headers() -> dict[str, str]:
    """Bearer header for the shared memory secret when configured, else {}.
    Mode-agnostic: sends the credential only when TAPESTRY_MEMORY_API_KEY (or
    the LOOM_MEMORY_API_KEY alias) is set, so the same code works before and
    after the memory endpoint requires auth. Applied ONLY to memory-endpoint
    calls, never to the architecture-registry."""
    key = (
        os.environ.get("TAPESTRY_MEMORY_API_KEY")
        or os.environ.get("LOOM_MEMORY_API_KEY")
        or ""
    ).strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _http_json(
    method: str, url: str, body: dict[str, Any], timeout: float = 6.0,
    extra_headers: Optional[dict[str, str]] = None,
) -> Optional[dict[str, Any]]:
    """POST/PATCH a JSON body. Returns the parsed response dict or None
    on any failure. Never raises — observer is best-effort."""
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status < 200 or resp.status >= 300:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, ConnectionError, OSError,
            json.JSONDecodeError):
        return None


def _slugify_memory_name(text: str, max_len: int = 80) -> str:
    """Slugify text into a memory name. lowercase, kebab-case, length-bounded."""
    s = _SLUG_INVALID.sub("-", (text or "candidate").lower()).strip("-")
    return s[:max_len] if s else "candidate"


def write_candidate_memory(
    *,
    candidate: dict[str, Any],
    skill_name: str,
    short_description: str,
    project_tag: Optional[str],
    sessions_seen: int,
    status: str,
    is_status_change: bool = False,
) -> None:
    """Mirror a candidate into loom-memory so it surfaces via auto-recall
    in every project session (and via cross-agent recall). Silent on
    failure — never blocks the observer flow.

    Naming: `observer_candidate_<slug>` so repeated emissions for the same
    skill upsert (memory_write semantics on conflicting name = replace).
    Each call refreshes the content to reflect the latest status +
    session count.
    """
    candidate_id = candidate.get("id") or candidate.get("candidate_id") or ""
    if not candidate_id:
        return

    name = f"observer_candidate_{_slugify_memory_name(skill_name)}"
    status_phrase = "Status change: " if is_status_change else "Observer-emitted: "
    content_lines = [
        f"{status_phrase}{skill_name}",
        "",
        f"Status: {status} (sessions_seen={sessions_seen})",
        f"Candidate ID: {candidate_id}",
    ]
    if short_description:
        content_lines.append("")
        content_lines.append(short_description)
    content = "\n".join(content_lines)

    body: dict[str, Any] = {
        "name": name,
        "record_type": "skill_idea",
        "content": content,
        "why": (
            f"Observer surfaced this {'pattern transition' if is_status_change else 'pattern'} "
            f"so it reaches agents via auto-recall, not just via the architecture-registry."
        ),
        "actor": "loom-discipline-observer",
        "extra": {
            "candidate_id": candidate_id,
            "status": status,
            "sessions_seen": sessions_seen,
        },
    }
    if project_tag:
        body["project_tags"] = [project_tag]

    _http_json(
        "POST", _MEMORY_URL + _MEMORY_WRITE_PATH, body, timeout=4.0,
        extra_headers=_memory_auth_headers(),
    )


def post_candidate(
    *,
    project_uuid: str,
    skill_name: str,
    session_id: str,
    count_this_session: int,
    instance_id: str = "",
    is_new_skill_idea: bool = False,
    short_description: str = "",
) -> Optional[dict[str, Any]]:
    """POST a fresh candidate. Returns the Registry's response (incl.
    server-generated `id`) or None on failure.

    Two paths share this function:
      1. skill-invocation-count path (Phase 2 v1): skill was actually
         invoked N times this session. signals.is_new_skill_idea = False.
         Evidence kind: skill_invocation_count.
      2. agent-surfaced-idea path (Phase 2 v2): agent wrote a
         "Promotion candidates" entry proposing a NEW skill. count = 1
         (one observation). signals.is_new_skill_idea = True.
         signals.short_description holds the agent's free-text rationale.
         Evidence kind: agent_surfaced_skill_idea.

    Phase 3 (Pattern Detection) overwrites repeated_across_projects.
    """
    evidence_kind = (
        "agent_surfaced_skill_idea" if is_new_skill_idea
        else "skill_invocation_count"
    )
    evidence_entry: dict[str, Any] = {
        "kind": evidence_kind,
        "skill_name": skill_name,
        "count": count_this_session,
        "session_id": session_id,
        "observed_at": time.time(),
        "observer_version": "phase_2_v2",
    }
    if short_description:
        evidence_entry["short_description"] = short_description[:512]

    signals: dict[str, Any] = {
        "skill_name": skill_name,
        "count_this_session": count_this_session,
        "sessions_seen": 1,
        "repeated_across_sessions": False,
        "repeated_across_projects": False,
        "is_new_skill_idea": is_new_skill_idea,
    }
    if short_description:
        signals["short_description"] = short_description[:512]

    body = {
        "project_id": project_uuid,
        "instance_id": instance_id,
        "source_path": "path_a",
        "candidate_type": "skill",
        "status": "draft",
        "evidence_refs": [evidence_entry],
        "signals": signals,
    }
    response = _http_json("POST", _registry_url() + _CANDIDATES_PATH, body)

    # Mirror to loom-memory so the candidate surfaces via auto-recall in
    # every agent's session (the cross-agent channel). LOOM_PROJECT_ID is
    # the project tag — same value the discipline plugin's other hooks use.
    if response:
        write_candidate_memory(
            candidate=response,
            skill_name=skill_name,
            short_description=short_description,
            project_tag=os.environ.get("LOOM_PROJECT_ID"),
            sessions_seen=1,
            status="draft",
            is_status_change=False,
        )

    return response


def patch_candidate_status(
    candidate_id: str, new_status: str, reason: str,
    *,
    skill_name: str = "",
    short_description: str = "",
    sessions_seen: int = 0,
) -> Optional[dict[str, Any]]:
    """PATCH a candidate's status. The Registry appends a status_change
    entry to evidence_refs with the reason.

    Also mirrors the status change into loom-memory so the agent sees the
    advancement (draft -> observed -> recurring) at next session start.
    """
    body = {"status": new_status, "reason": reason}
    url = f"{_registry_url()}{_CANDIDATES_PATH}/{candidate_id}/status"
    response = _http_json("PATCH", url, body)

    if response and skill_name:
        write_candidate_memory(
            candidate={"id": candidate_id},
            skill_name=skill_name,
            short_description=short_description,
            project_tag=os.environ.get("LOOM_PROJECT_ID"),
            sessions_seen=sessions_seen,
            status=new_status,
            is_status_change=True,
        )

    return response


# ---------------------------------------------------------------------------
# Main entry — called from stop_audit.py
# ---------------------------------------------------------------------------


def scan_and_emit(
    *,
    transcript_raw: str,
    cwd: Path,
    session_id: str,
    log_fn: Optional[Any] = None,
) -> dict[str, Any]:
    """Phase 2 observer's main entry point.

    Reads the transcript, detects skill candidates, posts/patches them to
    the Architecture Registry, and persists local longitudinal state in
    .project-intelligence/workflow-candidates/.

    Returns a summary dict (for logging):
      {
        "ran": bool,
        "skipped_reason": str | None,
        "skills_detected": int,
        "candidates_created": int,
        "candidates_updated": int,
        "errors": list[str],
      }

    NEVER raises — observer is best-effort; Stop hook always proceeds.
    """
    summary = {
        "ran": False,
        "skipped_reason": None,
        "skills_detected": 0,
        "ideas_detected": 0,
        "candidates_created": 0,
        "candidates_updated": 0,
        "errors": [],
    }

    def _log(*args, **kwargs):
        if log_fn:
            try:
                log_fn(*args, **kwargs)
            except Exception:  # noqa: BLE001
                pass

    # Walk up from cwd to find the nearest .project-intelligence/ ancestor.
    # cwd may not be the project root when the agent cd's into a subdir
    # mid-session — silently skipping for that reason would lose
    # observations across the rest of the session. v0.1.14 bugfix: this
    # used to be `cwd / ".project-intelligence"` literally, which failed
    # the moment a subdirectory got open.
    project_intelligence_dir: Optional[Path] = None
    for candidate in [cwd, *cwd.parents]:
        candidate_dir = candidate / ".project-intelligence"
        if candidate_dir.exists():
            project_intelligence_dir = candidate_dir
            break
    if project_intelligence_dir is None:
        summary["skipped_reason"] = "no_project_intelligence_dir"
        return summary

    project_uuid = _read_project_uuid(project_intelligence_dir)
    if not project_uuid:
        summary["skipped_reason"] = "no_project_uuid_in_context_json"
        return summary

    # Three signal sources now (v2): explicit Skill tool calls + skill-
    # counts from the upskilling report's "Skills invoked" section +
    # promotion-candidate bullets from the report's "Promotion candidates"
    # section. The first two merge into a single count dict; the third
    # produces a parallel list of agent-surfaced ideas.
    tool_counts = count_skill_tool_calls(transcript_raw)
    report_counts = parse_upskilling_report(transcript_raw)
    merged = merge_counts(tool_counts, report_counts)
    promotion_ideas = parse_promotion_candidates(transcript_raw)

    summary["skills_detected"] = sum(
        1 for c in merged.values() if c >= MIN_COUNT_TO_CONSIDER
    )
    summary["ideas_detected"] = len(promotion_ideas)

    # Skip only if BOTH sources are empty.
    if not merged and not promotion_ideas:
        summary["skipped_reason"] = "no_skills_detected"
        return summary

    summary["ran"] = True

    for skill_name, count_this_session in merged.items():
        if count_this_session < MIN_COUNT_TO_CONSIDER:
            continue

        record_path = _local_record_path(project_intelligence_dir, skill_name)
        record = _load_local_record(record_path)

        # Dedup: same session_id already processed for this skill?
        if session_id and session_id in record.get("session_ids", []):
            continue

        # Update longitudinal state.
        record["schema_version"] = LOCAL_RECORD_SCHEMA_VERSION
        record["skill_name"] = skill_name
        now = time.time()
        if not record.get("first_seen_at"):
            record["first_seen_at"] = now
        record["last_seen_at"] = now
        record["last_count"] = count_this_session
        record["total_count"] = (record.get("total_count") or 0) + count_this_session
        sessions_list = list(record.get("session_ids") or [])
        if session_id and session_id not in sessions_list:
            sessions_list.append(session_id)
        record["session_ids"] = sessions_list
        record["sessions_seen"] = len(sessions_list)

        if record.get("candidate_id") is None:
            # New candidate — POST to registry.
            response = post_candidate(
                project_uuid=project_uuid,
                skill_name=skill_name,
                session_id=session_id,
                count_this_session=count_this_session,
            )
            if response is None:
                summary["errors"].append(f"POST_failed:{skill_name}")
                # Don't persist the local record — retry next session.
                continue
            record["candidate_id"] = response.get("id")
            record["current_status"] = response.get("status") or "draft"
            summary["candidates_created"] += 1
            _log("observer", "candidate_created", skill=skill_name,
                 candidate_id=record["candidate_id"])
        else:
            # Existing candidate — maybe PATCH status.
            new_status = derive_status(record["sessions_seen"])
            if new_status != record.get("current_status"):
                response = patch_candidate_status(
                    record["candidate_id"], new_status,
                    f"observer: sessions_seen={record['sessions_seen']}",
                    skill_name=skill_name,
                    sessions_seen=record["sessions_seen"],
                )
                if response is None:
                    summary["errors"].append(f"PATCH_failed:{skill_name}")
                    # Save the longitudinal state anyway — sessions_seen
                    # is local-only truth; the PATCH retries next session.
                else:
                    record["current_status"] = new_status
                    summary["candidates_updated"] += 1
                    _log("observer", "candidate_status_updated",
                         skill=skill_name,
                         candidate_id=record["candidate_id"],
                         status=new_status)

        _save_local_record(record_path, record)

    # v2: second pass for promotion candidates. Same lifecycle (draft ->
    # observed at 2 sessions -> recurring at 3+) but no count threshold —
    # each entry is one agent-surfaced observation, count=1 always.
    # signals.is_new_skill_idea distinguishes these in the Registry.
    for entry in promotion_ideas:
        idea_name = entry["name"]
        idea_desc = entry["description"]

        record_path = _local_record_path(project_intelligence_dir, idea_name)
        record = _load_local_record(record_path)

        # Dedup: same session_id already processed for this idea?
        if session_id and session_id in record.get("session_ids", []):
            continue

        record["schema_version"] = LOCAL_RECORD_SCHEMA_VERSION
        record["skill_name"] = idea_name
        record["is_new_skill_idea"] = True
        if idea_desc:
            record["short_description"] = idea_desc[:512]
        now = time.time()
        if not record.get("first_seen_at"):
            record["first_seen_at"] = now
        record["last_seen_at"] = now
        record["last_count"] = 1
        record["total_count"] = (record.get("total_count") or 0) + 1
        sessions_list = list(record.get("session_ids") or [])
        if session_id and session_id not in sessions_list:
            sessions_list.append(session_id)
        record["session_ids"] = sessions_list
        record["sessions_seen"] = len(sessions_list)

        if record.get("candidate_id") is None:
            response = post_candidate(
                project_uuid=project_uuid,
                skill_name=idea_name,
                session_id=session_id,
                count_this_session=1,
                is_new_skill_idea=True,
                short_description=idea_desc,
            )
            if response is None:
                summary["errors"].append(f"POST_failed:idea:{idea_name}")
                continue
            record["candidate_id"] = response.get("id")
            record["current_status"] = response.get("status") or "draft"
            summary["candidates_created"] += 1
            _log("observer", "idea_candidate_created", idea=idea_name,
                 candidate_id=record["candidate_id"])
        else:
            new_status = derive_status(record["sessions_seen"])
            if new_status != record.get("current_status"):
                response = patch_candidate_status(
                    record["candidate_id"], new_status,
                    f"observer: idea sessions_seen={record['sessions_seen']}",
                    skill_name=idea_name,
                    short_description=idea_desc,
                    sessions_seen=record["sessions_seen"],
                )
                if response is None:
                    summary["errors"].append(f"PATCH_failed:idea:{idea_name}")
                else:
                    record["current_status"] = new_status
                    summary["candidates_updated"] += 1
                    _log("observer", "idea_candidate_status_updated",
                         idea=idea_name,
                         candidate_id=record["candidate_id"],
                         status=new_status)

        _save_local_record(record_path, record)

    return summary
