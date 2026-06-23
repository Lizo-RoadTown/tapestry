#!/usr/bin/env python3
"""
UserPromptSubmit hook for tapestry-discipline (preserved runtime label: [loom-discipline]).

Two responsibilities:

  1. **Adaptive reminder injection.** Reads the user's prompt, pattern-matches
     intent, and emits an additionalContext reminder Claude sees BEFORE
     processing. The reminder is short and tailored — generic prompts get a
     base reminder; intent-laden prompts get the targeted rule.

  2. **Repetition-detector (v0.1.2).** If the prompt contains phrases like
     "I already told you" / "remember that" / "always X", append a memory
     stub to ~/.claude/projects/<project_key>/memory/ so the friction is
     written down at the moment of correction (not deferred to session end).
     The stub is a draft — the agent fills in the body in the response.

Triggers (the reminder patterns):

  - "does X use" / "where is" / "what's the stack"  →  PROBE-first
  - "build" / "implement" / "wire up" / "add"       →  dev-tooling-vs-runtime
  - "fix" / "debug" / "why doesn't"                 →  PROBE + cite-skills
  - "I already told you" / "remember that" / "always" → memory-write stub
  - Anything else                                   →  base reminder

Exit 0 always. The hook should never block UserPromptSubmit.

Reference: docs/proposals/lancedb-memory-mcp.md and the plan at
docs/plans/2026-05-22-discipline-plugin-and-starter-capture.md in
Lizo-RoadTown/Make_Skills.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Make the shared observability helper importable when this script runs
# under the Node launcher (which sets cwd to wherever Claude Code is).
# v0.1.4: absolute-path importlib. See pre_tool_use.py header comment for
# why sys.path.insert + `from _observability import` failed silently under
# the Node launcher.
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

        def log_event(*_args, **_kwargs):  # type: ignore[misc]
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

    def log_event(*_args, **_kwargs):  # type: ignore[misc]
        pass

    def now_ms() -> int:
        return int(time.time() * 1000)


BASE_REMINDER = (
    "Discipline check: PROBE files before asserting (cite file:line). "
    "Distinguish dev-tooling (scripts/, docs/) from runtime (platform/, web/). "
    "Save corrections as feedback memory immediately. "
    "CORE DIRECTIVE 1 (docs/CORE_DIRECTIVES.md): if memory_recall / memory_write "
    "MCP tools are unavailable, HALT and report — do not work without loom-memory."
)

PROBE_REMINDER = (
    "PROBE FIRST. The user is asking about the codebase or stack — "
    "run Grep/Read on the relevant file BEFORE answering. "
    "Cite file:line in the response. The 'obvious' answers are the ones that go wrong."
)

BUILD_REMINDER = (
    "Before building: classify the change. Dev-tooling (scripts/, docs/, session memory) "
    "or runtime (platform/api/, web/)? Name which in your response. "
    "Then PROBE the surrounding code BEFORE writing — cite file:line for any pattern you copy."
)

DEBUG_REMINDER = (
    "Debug discipline: PROBE the actual file state first (Grep/Read). "
    "If a skill applies (e.g., systematic-debugging, lessons-learned), invoke it by name. "
    "Don't guess from training-data defaults — the specific project may differ."
)

REMEMBER_REMINDER = (
    "REPETITION DETECTED. The user is asking you to remember or correcting "
    "something they've already said. A memory stub has been queued at "
    "~/.claude/projects/<project>/memory/feedback_remember_<ts>.md — your "
    "response MUST (1) honor the correction in this turn, and (2) fill in "
    "the stub with the rule + 'Why' + 'How to apply' lines before ending."
)

# Reminder pattern → message. First match wins; order matters.
PATTERNS = [
    # Repetition detector (highest priority — capture before generic build/probe rules eat it)
    (
        re.compile(
            r"\b(i\s+already\s+told\s+you|remember\s+that|always\s+do|always\s+use|i'?ve\s+said|stop\s+forgetting|don'?t\s+forget)\b",
            re.IGNORECASE,
        ),
        REMEMBER_REMINDER,
    ),
    (
        re.compile(
            r"\b(does|do)\b.*\buse\b|where (is|does)|what'?s the stack|which library",
            re.IGNORECASE,
        ),
        PROBE_REMINDER,
    ),
    (
        re.compile(r"\bfix\b|\bdebug\b|why doesn'?t|broken|failing", re.IGNORECASE),
        DEBUG_REMINDER,
    ),
    (
        re.compile(
            r"\b(build|implement|wire(?:\s+up)?|add|create|scaffold)\b", re.IGNORECASE
        ),
        BUILD_REMINDER,
    ),
]


def _project_key_from_cwd(cwd: str) -> str:
    """Convert a path into Claude Code's project-memory key format
    (e.g. 'c:\\Users\\Liz\\Make_Skills' → 'c--Users-Liz-Make-Skills')."""
    p = Path(cwd).resolve() if cwd else Path.cwd()
    s = str(p)
    s = re.sub(r"[\\/:]", "-", s).strip("-")
    return s


def _write_memory_stub(cwd: str, prompt: str) -> Path | None:
    """Queue a feedback memory stub with the offending prompt as context.
    Returns the stub path on success, None on failure. Never raises."""
    try:
        project_key = _project_key_from_cwd(cwd)
        mem_dir = Path.home() / ".claude" / "projects" / project_key / "memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        stub_path = mem_dir / f"feedback_remember_{ts}.md"
        if stub_path.exists():
            return stub_path
        excerpt = prompt.strip().replace("\n", " ")[:200]
        body = (
            "---\n"
            f"name: remember-{ts}\n"
            "description: STUB — created automatically by tapestry-discipline UserPromptSubmit hook on detection of repetition phrasing. Fill in the rule + Why + How to apply lines as the response is composed; this stub is meant to be edited before the turn ends.\n"
            "metadata:\n"
            "  type: feedback\n"
            "  auto_created: true\n"
            "---\n\n"
            "**Rule:** _(fill in the durable rule this correction encodes)_\n\n"
            "**Why:** _(the specific moment Liz had to repeat herself — quote her phrasing)_\n\n"
            f"Triggering prompt excerpt:\n\n> {excerpt}\n\n"
            "**How to apply:** _(when this rule kicks in; what surface to apply it on; what the agent should do differently)_\n"
        )
        stub_path.write_text(body, encoding="utf-8")
        return stub_path
    except Exception:  # noqa: BLE001
        return None


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


def main() -> int:
    start = now_ms()
    log_event("UserPromptSubmit", "start")
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        log_event(
            "UserPromptSubmit", "end", exit_code=0, elapsed_ms=now_ms() - start,
            action="noop", note="malformed_input",
        )
        return 0

    # Propagate session_id; subsequent log_event calls pick it up via
    # CLAUDE_SESSION_ID default in _observability.log_event.
    os.environ["CLAUDE_SESSION_ID"] = data.get("session_id") or ""

    prompt = data.get("prompt") or ""
    cwd = data.get("cwd") or ""

    # v0.1.12: scope also honors LOOM_PROJECT_ID (per-project opt-in),
    # not just cwd substrings.
    if not _in_scope(cwd):
        log_event(
            "UserPromptSubmit", "end", exit_code=0, elapsed_ms=now_ms() - start,
            scope_in=False, action="noop", note="out_of_scope",
        )
        return 0

    # Pick the most-specific reminder that matches; fall back to base.
    reminder = BASE_REMINDER
    matched_label = "base"
    for i, (pattern, msg) in enumerate(PATTERNS):
        if pattern.search(prompt):
            reminder = msg
            matched_label = ["remember", "probe", "debug", "build"][i] if i < 4 else "base"
            break

    # Side effect for the REMEMBER pattern: queue a memory stub.
    note = matched_label
    if matched_label == "remember":
        stub_path = _write_memory_stub(cwd, prompt)
        if stub_path:
            note = f"remember;stub={stub_path.name}"

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": f"[loom-discipline] {reminder}",
        }
    }
    print(json.dumps(payload))
    log_event(
        "UserPromptSubmit", "end", exit_code=0, elapsed_ms=now_ms() - start,
        scope_in=True, action="reminder_injected", note=note,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
