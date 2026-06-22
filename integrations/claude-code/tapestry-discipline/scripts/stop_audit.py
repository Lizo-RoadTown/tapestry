#!/usr/bin/env python3
"""
Stop hook for loom-discipline.

Fires at the end of the agent's turn. Runs two audits + one observer:

1. **PROBE-citation audit** (original). Scans the LAST assistant turn for
   phrases like "we use X" / "stack is Y" / "runs on Z" without an
   accompanying file:line citation. Surfaces "Stop-audit detected an
   unsubstantiated stack claim" via additionalContext.

2. **Agentic-upskilling audit** (v0.1.9, CORE DIRECTIVE 2). Walks the
   FULL session transcript. If the session crossed a "substantive
   boundary" heuristic (≥ 1 git commit/push action, OR ≥ 10 tool calls
   AND ≥ 3 assistant turns, OR ≥ 30 assistant turns) AND NO upskilling
   report has been emitted this session, surfaces
   "*** UPSKILLING PASS NOT RUN ***" with recovery steps.

3. **Phase 2 observer** (v0.1.10). If the upskilling report HAS been
   emitted (the agent did its job), invoke observer.scan_and_emit to
   parse the report + count Skill tool calls and POST/PATCH candidates
   to the Architecture Registry. See observer.py docstring for the
   full Phase 2 mechanism.

Does NOT block (Stop hook blocking is dangerous; would loop). Emits a
soft reminder via additionalContext so the next user message sees it.

Both findings combine into ONE additionalContext if both fire. The
observer never adds to additionalContext — it operates silently and
its side effects are visible only via GET /candidates and the local
.project-intelligence/workflow-candidates/ files.

The upskilling check uses a per-session marker file at
~/.claude/cache/session-<id>-upskilling-warned to avoid repeated warnings.

Reference: docs/plans/2026-05-22-discipline-plugin-and-starter-capture.md
in Lizo-RoadTown/Make_Skills.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

# v0.1.4: absolute-path importlib. See pre_tool_use.py header comment.
import importlib.util as _importlib_util

_obs_path = Path(__file__).resolve().parent / "_observability.py"
_obs_spec = _importlib_util.spec_from_file_location("_observability", _obs_path)
if _obs_spec is not None and _obs_spec.loader is not None:
    _obs_mod = _importlib_util.module_from_spec(_obs_spec)
    try:
        _obs_spec.loader.exec_module(_obs_mod)
        log_event = _obs_mod.log_event
        now_ms = _obs_mod.now_ms
    except Exception as _obs_err:  # noqa: BLE001
        _fallback_log = Path.home() / ".claude" / "logs" / "hook-import-errors.log"
        try:
            _fallback_log.parent.mkdir(parents=True, exist_ok=True)
            with _fallback_log.open("a", encoding="utf-8") as _flog:
                _flog.write(
                    f"{Path(__file__).name}: _observability exec_module failed: {_obs_err!r}\n"
                )
        except Exception:  # noqa: BLE001
            pass

        def log_event(*_args, **_kwargs):
            pass

        def now_ms() -> int:
            return int(time.time() * 1000)
else:
    _fallback_log = Path.home() / ".claude" / "logs" / "hook-import-errors.log"
    try:
        _fallback_log.parent.mkdir(parents=True, exist_ok=True)
        with _fallback_log.open("a", encoding="utf-8") as _flog:
            _flog.write(
                f"{Path(__file__).name}: _observability spec_from_file_location "
                f"returned None for path={_obs_path}\n"
            )
    except Exception:  # noqa: BLE001
        pass

    def log_event(*_args, **_kwargs):
        pass

    def now_ms() -> int:
        return int(time.time() * 1000)

# Heuristic: phrases that smell like factual claims about the stack/codebase.
SUSPICIOUS_CLAIM = re.compile(
    r"\b(?:we use|uses|stack is|backed by|runs on|stored in|implemented in|built on|written in|deployed on)\s+"
    r"([A-Z][A-Za-z][A-Za-z0-9._-]+)",
    re.IGNORECASE,
)

CITATION_REGEX = re.compile(
    r"[a-zA-Z_/\\.\-]+\.(py|ts|tsx|jsx|js|md|json|yaml|yml|toml|sh|ps1|sql):\d+"
)

REMINDER = (
    "Stop-audit detected an unsubstantiated stack claim in your last response: "
    "claims about what the project uses or runs on, but no file:line citation. "
    "In your next response, either verify with Grep/Read and amend the claim with "
    "a citation, or retract it. The PROBE rule applies retroactively."
)

# ---------------------------------------------------------------------------
# Upskilling-pass check (v0.1.9 / CORE DIRECTIVE 2)
# ---------------------------------------------------------------------------

# Substantive-boundary thresholds. A session crosses the boundary if ANY hold.
# Tuned conservative: avoids warning on short conversational sessions.
SUBSTANTIVE_MIN_ASSISTANT_TURNS_ALONE = 30   # solo signal: long session
SUBSTANTIVE_MIN_ASSISTANT_TURNS_PAIR = 3     # paired with tool count
SUBSTANTIVE_MIN_TOOL_CALLS_PAIR = 10         # paired with assistant turns
SUBSTANTIVE_GIT_ACTION_REGEX = re.compile(
    r"\bgit\s+(?:commit|push|merge|tag)\b", re.IGNORECASE
)

# Phrases an agent must emit when running the upskilling pass per
# skills_private/agentic-upskilling/SKILL.md:92-113. ALL must appear in
# the same session transcript for the report to be considered "run".
UPSKILLING_REPORT_MARKERS = (
    re.compile(r"skills?\s+invoked\s+this\s+session", re.IGNORECASE),
    re.compile(r"promotion\s+candidates", re.IGNORECASE),
)

# Or: a memory_write tool call whose `name` arg starts with "upskilling_report_".
UPSKILLING_MEMORY_WRITE_REGEX = re.compile(
    r'memory_write[^"]*"name"\s*:\s*"upskilling_report_', re.IGNORECASE
)

UPSKILLING_WARNING = (
    "*** UPSKILLING PASS NOT RUN ***\n"
    "This session has crossed a substantive boundary (multiple tool calls + "
    "assistant turns and/or git actions) but no agentic-upskilling end-of-"
    "session report was emitted.\n"
    "\n"
    "CORE DIRECTIVE 2 (docs/CORE_DIRECTIVES.md): every substantive session ends "
    "with the structured report per skills_private/agentic-upskilling/"
    "SKILL.md:92-113 — Skills invoked, Tools called, Promotion candidates, "
    "Demotion candidates, Recommendations.\n"
    "\n"
    "Recovery:\n"
    "  1. Emit the report in your next response, then\n"
    "  2. Write it to loom-memory as a `lesson`-type record named "
    "`upskilling_report_session_<YYYY_MM_DD>` with relevant project_tags.\n"
    "\n"
    "Why this warning exists:\n"
    "  Without the pass, no promotion candidates accumulate; the upskilling-"
    "dashboard / Agency Optimizer loop has no input. This warning makes the omission loud."
)


def _scan_session_metrics(raw: str) -> dict:
    """Walk the FULL JSONL transcript once and return both:
      - last_assistant_text (for the PROBE-citation audit)
      - session metrics for the upskilling-boundary heuristic

    Single forward pass; the original code did a reverse walk only for the
    last assistant turn. This generalization keeps the original behavior +
    adds counts cheaply.

    Returns a dict with: last_assistant_text, assistant_turns, tool_calls,
    git_action_seen, upskilling_report_seen.
    """
    last_assistant_text = ""
    assistant_turns = 0
    tool_calls = 0
    git_action_seen = False
    text_concat_for_marker_scan = []

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
        assistant_turns += 1
        content = entry.get("content") or (entry.get("message") or {}).get("content") or []
        text_parts = []
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    txt = block.get("text") or ""
                    text_parts.append(txt)
                    if SUBSTANTIVE_GIT_ACTION_REGEX.search(txt):
                        git_action_seen = True
                elif btype == "tool_use":
                    tool_calls += 1
                    # Also detect git via bash tool calls + memory_write upskilling reports.
                    tool_input = block.get("input") or {}
                    if isinstance(tool_input, dict):
                        cmd = tool_input.get("command") or ""
                        if isinstance(cmd, str) and SUBSTANTIVE_GIT_ACTION_REGEX.search(cmd):
                            git_action_seen = True
                        name_arg = tool_input.get("name") or ""
                        if isinstance(name_arg, str) and name_arg.startswith("upskilling_report_"):
                            # Detected via tool-input inspection (most reliable).
                            text_concat_for_marker_scan.append(
                                f'memory_write "name": "{name_arg}"'
                            )
        elif isinstance(content, str):
            text_parts.append(content)
            if SUBSTANTIVE_GIT_ACTION_REGEX.search(content):
                git_action_seen = True

        joined = "\n".join(text_parts)
        last_assistant_text = joined  # overwritten each iteration -> last one wins
        text_concat_for_marker_scan.append(joined)

    full_text = "\n".join(text_concat_for_marker_scan)
    upskilling_report_seen = (
        all(p.search(full_text) for p in UPSKILLING_REPORT_MARKERS)
        or bool(UPSKILLING_MEMORY_WRITE_REGEX.search(full_text))
    )

    return {
        "last_assistant_text": last_assistant_text,
        "assistant_turns": assistant_turns,
        "tool_calls": tool_calls,
        "git_action_seen": git_action_seen,
        "upskilling_report_seen": upskilling_report_seen,
    }


def _is_substantive_boundary(metrics: dict) -> bool:
    """The session has crossed the substantive-boundary threshold iff ANY
    of these hold (per docs/CORE_DIRECTIVES.md Directive 2):

      1. At least one git commit/push/merge/tag action
      2. ≥ 10 tool calls AND ≥ 3 assistant turns
      3. ≥ 30 assistant turns
    """
    if metrics["git_action_seen"]:
        return True
    if (metrics["tool_calls"] >= SUBSTANTIVE_MIN_TOOL_CALLS_PAIR
            and metrics["assistant_turns"] >= SUBSTANTIVE_MIN_ASSISTANT_TURNS_PAIR):
        return True
    if metrics["assistant_turns"] >= SUBSTANTIVE_MIN_ASSISTANT_TURNS_ALONE:
        return True
    return False


def _warned_marker_path(session_id: str) -> Path:
    """Per-session marker file. Presence = warning already fired this
    session; skip to avoid noisy repeated warnings."""
    cache_dir = Path.home() / ".claude" / "cache"
    safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", session_id or "unknown")[:64]
    return cache_dir / f"session-{safe_id}-upskilling-warned"


def _in_scope(cwd) -> bool:
    """True if loom-discipline hooks should run for this repo.

    In scope if EITHER the working-directory path contains a known loom
    substring (Make_Skills / the-loom / project-starter / _common), OR
    LOOM_PROJECT_ID is set — the explicit per-project opt-in a consuming
    project declares via its `.env` (loaded into os.environ by
    _observability._load_dotenv at import time).

    v0.1.12: added the LOOM_PROJECT_ID clause. Before this the gate was
    substring-only, so a fully-wired consuming project (LOOM_PROJECT_ID
    set, CLAUDE.md referencing the discipline) silently no-op'd every hook
    — e.g. SDE_Extraction. Honoring LOOM_PROJECT_ID closes that class of
    bug for every future consumer, not just one repo.
    """
    cwd_s = str(cwd or "")
    cwd_l = cwd_s.lower()
    if (
        "make_skills" in cwd_l
        or "make-skills" in cwd_l
        or "the-loom" in cwd_l
        or "tapestry" in cwd_l
        or "project-starter" in cwd_l
        or "_common" in cwd_s
    ):
        return True
    if os.environ.get("LOOM_PROJECT_ID", "").strip():
        return True
    return False


def main() -> int:
    start = now_ms()
    log_event("Stop", "start")
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        log_event("Stop", "end", exit_code=0, elapsed_ms=now_ms() - start, action="noop", note="malformed_input")
        return 0

    # Propagate session_id; subsequent log_event calls pick it up via
    # CLAUDE_SESSION_ID default in _observability.log_event.
    os.environ["CLAUDE_SESSION_ID"] = data.get("session_id") or ""

    cwd = data.get("cwd") or ""
    transcript_path = data.get("transcript_path") or ""

    # v0.1.12: scope also honors LOOM_PROJECT_ID (per-project opt-in),
    # not just cwd substrings.
    if not _in_scope(cwd):
        log_event("Stop", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=False, action="noop", note="out_of_scope")
        return 0

    if not transcript_path:
        log_event("Stop", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="noop", note="no_transcript_path")
        return 0

    try:
        raw = Path(transcript_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        log_event("Stop", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="noop", note="transcript_unreadable")
        return 0

    # Single forward pass through the transcript: produces both the
    # last_assistant_text (for the PROBE-citation audit) and the session
    # metrics (for the upskilling-boundary audit).
    metrics = _scan_session_metrics(raw)
    last_assistant_text = metrics["last_assistant_text"]

    if not last_assistant_text:
        log_event("Stop", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="noop", note="no_assistant_turn_found")
        return 0

    # Check 1: PROBE-citation audit (original behavior — operates on last turn only).
    claims = SUSPICIOUS_CLAIM.findall(last_assistant_text)
    cited = bool(CITATION_REGEX.search(last_assistant_text))
    claim_violation = bool(claims and not cited)

    # Check 2: agentic-upskilling audit (v0.1.9 / CORE DIRECTIVE 2). Operates
    # on FULL session, gated by substantive-boundary heuristic + already-warned
    # marker (to avoid noisy repeated warnings on every turn after threshold).
    session_id = data.get("session_id") or ""
    marker_path = _warned_marker_path(session_id)
    upskilling_violation = (
        _is_substantive_boundary(metrics)
        and not metrics["upskilling_report_seen"]
        and not marker_path.exists()
    )

    # Compose findings into one additionalContext if either fires.
    context_blocks: list[str] = []
    notes: list[str] = []
    action = "noop"

    if claim_violation:
        context_blocks.append(
            f"[loom-discipline] {REMINDER}\n"
            f"Detected claims: {', '.join(set(claims))[:200]}"
        )
        notes.append(f"claims={len(claims)};cited=False")
        action = "reminder_injected"

    if upskilling_violation:
        context_blocks.append(f"[loom-discipline] {UPSKILLING_WARNING}")
        notes.append(
            f"upskilling_boundary=True;assistant_turns={metrics['assistant_turns']};"
            f"tool_calls={metrics['tool_calls']};git={metrics['git_action_seen']}"
        )
        action = "upskilling_warned" if not claim_violation else "combined_warned"
        # Write the marker so we don't repeat on every subsequent Stop in this session.
        try:
            marker_path.parent.mkdir(parents=True, exist_ok=True)
            marker_path.write_text(
                f"upskilling-warned at session_id={session_id} ts={int(time.time())}\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    if context_blocks:
        payload = {
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": "\n\n".join(context_blocks),
            }
        }
        print(json.dumps(payload))

    # v0.1.10 Phase 2 observer. Only invoke when the agent emitted the
    # upskilling report (so the bookkeeping operates on real data). The
    # observer NEVER raises; failures are silent. It posts/patches
    # candidate rows to the Architecture Registry and persists local
    # state in .project-intelligence/workflow-candidates/.
    observer_summary = {"ran": False, "skipped_reason": "not_invoked"}
    if metrics["upskilling_report_seen"]:
        try:
            # Lazy-import: observer.py uses urllib only, no extra deps,
            # but importing on every Stop adds ~3ms even for the
            # short-circuit no-skills-detected case. Keep the import inside
            # the guard so non-substantive sessions don't pay for it.
            import importlib.util as _il
            _obs_path = Path(__file__).resolve().parent / "observer.py"
            _obs_spec = _il.spec_from_file_location("loom_observer", _obs_path)
            if _obs_spec is not None and _obs_spec.loader is not None:
                _obs_mod = _il.module_from_spec(_obs_spec)
                _obs_spec.loader.exec_module(_obs_mod)
                observer_summary = _obs_mod.scan_and_emit(
                    transcript_raw=raw,
                    cwd=Path(cwd),
                    session_id=session_id,
                    log_fn=log_event,
                )
        except Exception as obs_err:  # noqa: BLE001
            # Defensive — observer must NEVER block Stop. Log + move on.
            observer_summary = {
                "ran": False,
                "skipped_reason": f"observer_exception:{type(obs_err).__name__}",
                "errors": [str(obs_err)[:200]],
            }

    obs_note = (
        f"obs_ran={observer_summary.get('ran', False)};"
        f"obs_detected={observer_summary.get('skills_detected', 0)};"
        f"obs_created={observer_summary.get('candidates_created', 0)};"
        f"obs_updated={observer_summary.get('candidates_updated', 0)};"
        f"obs_skip={observer_summary.get('skipped_reason') or 'none'}"
    )

    log_event(
        "Stop", "end",
        exit_code=0,
        elapsed_ms=now_ms() - start,
        scope_in=True,
        action=action,
        note=";".join(notes + [obs_note])
             or f"claims={len(claims)};cited={cited};"
                f"upskilling_seen={metrics['upskilling_report_seen']};{obs_note}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
