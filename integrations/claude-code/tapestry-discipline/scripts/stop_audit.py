#!/usr/bin/env python3
"""
Stop hook for tapestry-discipline (preserved runtime label: [loom-discipline]).

Fires at the end of the agent's turn. Runs two audits + one observer:

1. **PROBE-citation audit** (original). Scans the LAST assistant turn for
   phrases like "we use X" / "stack is Y" / "runs on Z" without an
   accompanying file:line citation. Surfaces "Stop-audit detected an
   unsubstantiated stack claim" via additionalContext.

2. **Agentic-upskilling audit** (v0.1.9, CORE DIRECTIVE 2; recurring since
   v0.1.20). Walks the FULL session transcript. If a "substantive boundary"
   (≥ 1 git commit/push action, OR ≥ 10 tool calls AND ≥ 3 assistant turns,
   OR ≥ 30 assistant turns) has been crossed by work done SINCE the most
   recent upskilling report — and we have not already warned for this window —
   surfaces "*** UPSKILLING PASS NOT RUN ***" with recovery steps. Measuring
   work SINCE the last report (not once per session) makes the prompt RECUR in
   long-lived sessions: each emitted report resets the window, a fresh boundary
   of new work re-arms it. Fixes weeks-long sessions where the end-of-session
   trigger never arrives.

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
~/.claude/cache/session-<id>-upskilling-warned storing a JSON watermark
(reports_at_warn + turns_at_warn) so it re-warns once per window of new work
rather than once per session.

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

# The report counts as emitted IFF the session contains a memory_write tool
# call that persists the report record. Gate on the actual tool block, never on
# prose phrases: the old markers ("skills invoked this session", "promotion
# candidates") are the report's own section headers, so merely reading or
# discussing the report/observer/spec tripped them — a false positive in 163 of
# 166 in-scope sessions. Canonical record name per docs/CORE_DIRECTIVES.md
# "Report format (Directive 3)".
UPSKILLING_REPORT_NAME_REGEX = re.compile(
    r"^upskilling_report_session_\d{4}_\d{2}_\d{2}$"
)

UPSKILLING_WARNING = (
    "*** UPSKILLING PASS NOT RUN ***\n"
    "This session has crossed a substantive boundary (multiple tool calls + "
    "assistant turns and/or git actions) but no agentic-upskilling end-of-"
    "session report was emitted.\n"
    "\n"
    "CORE DIRECTIVE 3 (docs/CORE_DIRECTIVES.md, 'Report format'): every "
    "substantive session ends with the structured report — Skills invoked, "
    "Tools called, Promotion candidates, Demotion candidates, Recommendations.\n"
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
    upskilling_report_seen = False
    report_content = ""
    report_name = ""
    # v0.1.20 (recurring trigger): watermarks for "work since the last report".
    # report_count = how many upskilling reports the transcript holds;
    # turns/tools_at_last_report = the metric snapshot at the MOST RECENT report;
    # git_since_last_report = a git action occurred AFTER the last report.
    report_count = 0
    turns_at_last_report = 0
    tools_at_last_report = 0
    git_since_last_report = False

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
                        git_since_last_report = True
                elif btype == "tool_use":
                    tool_calls += 1
                    # Detect git via bash tool calls, and the upskilling report
                    # via the memory_write tool block that persists it. Gate on
                    # the TOOL name (must be a memory_write, not a read/delete of
                    # a prior report) AND the anchored record name — never on
                    # prose, which false-positives on discussion of the report.
                    tool_name = block.get("name") or ""
                    tool_input = block.get("input") or {}
                    if isinstance(tool_input, dict):
                        cmd = tool_input.get("command") or ""
                        if isinstance(cmd, str) and SUBSTANTIVE_GIT_ACTION_REGEX.search(cmd):
                            git_action_seen = True
                            git_since_last_report = True
                        record_name = tool_input.get("name") or ""
                        if (
                            isinstance(tool_name, str)
                            and "memory_write" in tool_name
                            and isinstance(record_name, str)
                            and UPSKILLING_REPORT_NAME_REGEX.match(record_name)
                        ):
                            upskilling_report_seen = True
                            # v0.1.20: snapshot watermarks at THIS report so the
                            # recurring trigger measures work done AFTER it.
                            report_count += 1
                            turns_at_last_report = assistant_turns
                            tools_at_last_report = tool_calls
                            git_since_last_report = False
                            # v0.1.19: capture the report body (the memory_write
                            # `content`) so the Stop hook can persist it on disk.
                            _rc = tool_input.get("content")
                            if isinstance(_rc, str) and _rc.strip():
                                report_content = _rc
                                report_name = record_name
        elif isinstance(content, str):
            text_parts.append(content)
            if SUBSTANTIVE_GIT_ACTION_REGEX.search(content):
                git_action_seen = True
                git_since_last_report = True

        joined = "\n".join(text_parts)
        last_assistant_text = joined  # overwritten each iteration -> last one wins

    return {
        "last_assistant_text": last_assistant_text,
        "assistant_turns": assistant_turns,
        "tool_calls": tool_calls,
        "git_action_seen": git_action_seen,
        "upskilling_report_seen": upskilling_report_seen,
        "report_content": report_content,
        "report_name": report_name,
        "report_count": report_count,
        "turns_at_last_report": turns_at_last_report,
        "tools_at_last_report": tools_at_last_report,
        "git_since_last_report": git_since_last_report,
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
    """Per-session marker file storing the upskilling-warn watermark (JSON:
    reports_at_warn + turns_at_warn). v0.1.20: content is a watermark, not a
    boolean flag — so the trigger can recur per window of new work."""
    cache_dir = Path.home() / ".claude" / "cache"
    safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", session_id or "unknown")[:64]
    return cache_dir / f"session-{safe_id}-upskilling-warned"


# Re-prompt after this many NEW assistant turns even if no report was emitted, so
# a session that ignores the warning still gets nudged again (not once-per-session).
RE_WARN_TURN_INTERVAL = 30


def _since_report_metrics(metrics: dict) -> dict:
    """Metrics for work done SINCE the most recent upskilling report (or since
    session start if none). Feeding _is_substantive_boundary this delta — rather
    than whole-session totals — is what makes the trigger RECUR: each report
    resets the window, and a fresh boundary of new work re-arms the warning.
    Fixes weeks-long sessions where the end-of-session trigger never fires."""
    return {
        "assistant_turns": metrics["assistant_turns"] - metrics.get("turns_at_last_report", 0),
        "tool_calls": metrics["tool_calls"] - metrics.get("tools_at_last_report", 0),
        "git_action_seen": bool(metrics.get("git_since_last_report", False)),
    }


def _read_marker(session_id: str) -> dict | None:
    """Read the JSON watermark, or None if absent/unreadable/legacy-plaintext.
    A pre-v0.1.20 plaintext marker fails json.loads -> None -> treated as
    'not yet warned this window' (warns once, then rewrites as JSON)."""
    try:
        data = json.loads(_warned_marker_path(session_id).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_marker(session_id: str, reports_at_warn: int, turns_at_warn: int) -> None:
    """Persist the watermark at the moment of a warning. Best-effort."""
    path = _warned_marker_path(session_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "reports_at_warn": reports_at_warn,
                "turns_at_warn": turns_at_warn,
                "ts": int(time.time()),
            }),
            encoding="utf-8",
        )
    except OSError:
        pass


def _in_scope(cwd) -> bool:
    """True if tapestry-discipline hooks should run for this repo.

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


# ---------------------------------------------------------------------------
# Permanent report persistence (v0.1.19)
# ---------------------------------------------------------------------------
#
# The upskilling report is written to loom-memory by the agent. That record is
# remote and ephemeral for documentation purposes. This persists the SAME report
# body to a committed on-disk Markdown file so it can be sifted for docs and
# post-mortems from the repo itself. Best-effort; NEVER raises (Stop-hook contract).

_REPORT_DATE_RE = re.compile(r"(\d{4})_(\d{2})_(\d{2})")


def _autocommit_report(cwd, path, msg):
    """Pathspec-commit ONLY the report file, leaving any staged agent work
    untouched. Best-effort; never raises."""
    import subprocess
    try:
        inside = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=10,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return
        subprocess.run(
            ["git", "-C", str(cwd), "add", "--", str(path)],
            capture_output=True, timeout=10,
        )
        # `git commit -- <path>` is a pathspec commit: only this path is committed,
        # regardless of what else is staged in the index.
        subprocess.run(
            ["git", "-C", str(cwd), "commit", "-m", msg, "--", str(path)],
            capture_output=True, timeout=15,
        )
    except Exception:  # noqa: BLE001
        pass


def _persist_report_to_disk(cwd_str, session_id, content, record_name):
    """Write the emitted upskilling report to
    <cwd>/docs/session-reports/<YYYY-MM-DD>-<session8>.md and best-effort commit
    it. Idempotent (identical content = no-op). Returns the path str or None.
    NEVER raises."""
    try:
        if not content or not content.strip():
            return None
        cwd = Path(cwd_str) if cwd_str else Path.cwd()
        m = _REPORT_DATE_RE.search(record_name or "")
        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else time.strftime("%Y-%m-%d")
        sid8 = re.sub(r"[^a-zA-Z0-9]+", "", session_id or "")[:8] or "session"
        reports_dir = cwd / "docs" / "session-reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"{date}-{sid8}.md"
        header = (
            "---\n"
            f"session: {session_id}\n"
            f"project: {os.environ.get('LOOM_PROJECT_ID', '')}\n"
            f"memory_record: {record_name}\n"
            "generated_by: tapestry-discipline Stop hook\n"
            "---\n\n"
        )
        body = header + content.rstrip() + "\n"
        if path.exists():
            try:
                if path.read_text(encoding="utf-8") == body:
                    return None  # identical — nothing to do
            except OSError:
                pass
        path.write_text(body, encoding="utf-8")
        _autocommit_report(cwd, path, f"chore(session-report): {path.name} [tapestry-discipline]")
        return str(path)
    except Exception:  # noqa: BLE001
        return None


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
    # v0.1.20 recurring trigger: warn when a fresh substantive boundary of work
    # has accumulated SINCE the last emitted report, unless we've already warned
    # for this window (same report count) within RE_WARN_TURN_INTERVAL turns.
    # Replaces the once-per-session gate so weeks-long sessions self-prompt.
    _report_count = metrics.get("report_count", 0)
    _marker = _read_marker(session_id)
    if _marker is None:
        _already_warned_window = False
    else:
        _same_window = _marker.get("reports_at_warn") == _report_count
        _turns_since_warn = metrics["assistant_turns"] - int(_marker.get("turns_at_warn", 0) or 0)
        _already_warned_window = _same_window and _turns_since_warn < RE_WARN_TURN_INTERVAL
    upskilling_violation = (
        _is_substantive_boundary(_since_report_metrics(metrics))
        and not _already_warned_window
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
            f"upskilling_boundary=True;report_count={_report_count};"
            f"assistant_turns={metrics['assistant_turns']};"
            f"tool_calls={metrics['tool_calls']};git={metrics['git_action_seen']}"
        )
        action = "upskilling_warned" if not claim_violation else "combined_warned"
        # Record the watermark (report count + turn count at this warning) so we
        # don't repeat within the same window until RE_WARN_TURN_INTERVAL more
        # turns pass or a new report is emitted.
        _write_marker(session_id, _report_count, metrics["assistant_turns"])

    if context_blocks:
        payload = {
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": "\n\n".join(context_blocks),
            }
        }
        print(json.dumps(payload))

    # v0.1.19: persist the emitted upskilling report to a committed on-disk file
    # (docs/session-reports/), in addition to the memory write. Best-effort.
    if metrics["upskilling_report_seen"]:
        _rp = _persist_report_to_disk(
            cwd, session_id,
            metrics.get("report_content", ""), metrics.get("report_name", ""),
        )
        if _rp:
            notes.append("report_persisted=1")

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
