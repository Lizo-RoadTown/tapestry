#!/usr/bin/env python3
"""
PreToolUse hook for loom-discipline.

Fires before Edit / Write / MultiEdit. Checks two conditions:

1. **Citation requirement.** If the agent is about to write to platform/api/
   or web/ (runtime code) AND the recent transcript shows no file:line
   citation, inject a corrective reminder (without blocking).

2. **Dev-tooling-vs-runtime classification.** If the edit target is a
   shared-interface boundary (e.g., the dual-mode discipline), inject a
   reminder to classify in the response.

Does NOT block by default — emits additionalContext as a soft reminder.
Set DISCIPLINE_STRICT=1 in the environment to make these checks blocking.

Reads the transcript path from the input JSON; if absent or unreadable,
exits 0 with no output. Never crash the harness over a missing transcript.

Reference: docs/plans/2026-05-22-discipline-plugin-and-starter-capture.md
in Lizo-RoadTown/Make_Skills.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

# Shared observability helper (v0.1.4: absolute-path importlib).
#
# v0.1.2/v0.1.3 used `sys.path.insert + from _observability import ...`,
# which silently fell back to no-op stubs when invoked via the Node
# launcher (run-python.mjs). __file__ resolves correctly under direct
# python invocation but Path(__file__).resolve().parent didn't surface
# the script's own directory on sys.path under the launcher's subprocess
# pattern. Result: hooks.jsonl was never written; PR #38's Loki
# dashboard panels stayed empty.
#
# v0.1.4 uses importlib.util.spec_from_file_location with an absolute
# path computed from __file__ — bypasses sys.path entirely. If the
# import still fails (e.g., _observability.py is missing from the
# install), the failure is logged to a fallback file
# (~/.claude/logs/hook-import-errors.log) so the error is observable
# instead of silent.
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

# v0.1.3: three citation forms accepted.
# 1. file.ext:line — the original strict form.
# 2. bare file.ext path with at least one slash — citing a file as a whole
#    (e.g., `render.yaml` config, a whole script).
# 3. https://... URL — citing external docs (Context7, GitHub, vendor docs).
_FILE_EXTS = r"(?:py|ts|tsx|jsx|js|md|json|yaml|yml|toml|sh|ps1|sql)"
CITATION_PATTERNS = (
    re.compile(rf"[a-zA-Z_/\\.\-]+\.{_FILE_EXTS}:\d+"),
    re.compile(rf"[a-zA-Z_][a-zA-Z0-9_./\\\-]*[/\\][a-zA-Z0-9_.\-]+\.{_FILE_EXTS}\b"),
    re.compile(r"https?://[^\s)\]]+"),
)

RUNTIME_PATHS = ("platform/", "platform\\", "web/", "web\\")

# v0.1.3: dual-mode trigger should fire only on actual runtime-code edits.
# Docs and config files that merely mention the trigger keywords (e.g., a
# planning doc listing `AUTH_SECRET` as a discussion item) are not boundary
# changes. Skip them.
DUAL_MODE_SKIP_EXTS = (".md", ".rst", ".txt", ".mdx")
DUAL_MODE_SKIP_PREFIXES = (
    "docs/",
    "docs\\",
    "README",
    "CHANGELOG",
    "CONTRIBUTING",
    "ARCHITECTURE",
    "AGENTS.md",
    "CLAUDE.md",
    ".github/",
    ".github\\",
)

CITATION_REMINDER = (
    "PreToolUse check: about to edit runtime code without recent file:line citation. "
    "Either cite the source you're following (file:line) in this turn's earlier output, "
    "or pause and PROBE before writing. The discipline says cite-then-edit."
)

DUAL_MODE_REMINDER = (
    "PreToolUse check: this edit touches a tenant-scoped or dual-mode boundary. "
    "Confirm in your response that the change is correct for BOTH self-host and "
    "hosted-multitenant modes (per ARCHITECTURE.md and CONTRIBUTING.md)."
)

DUAL_MODE_TRIGGERS = (
    # Tightened in v0.1.2: removed "memory" and "tenant" (caused frequent
    # false positives on session memory writes and any docs mentioning tenants).
    # Keep only patterns specific to actual runtime tenant-scoping code.
    "tenant_id",
    "RLS",
    "current_setting('app.tenant",
    "AUTH_SECRET",
    "JWTTenantResolver",
    "set_config('app.tenant",
)


def looks_like_runtime(path: str) -> bool:
    return any(marker in path for marker in RUNTIME_PATHS)


def has_recent_citation(transcript_path: str) -> bool:
    if not transcript_path:
        return True  # Can't verify; don't false-alarm.
    try:
        text = Path(transcript_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return True
    # Look at the tail — last ~5k chars covers a few turns.
    tail = text[-5000:]
    return any(pat.search(tail) for pat in CITATION_PATTERNS)


def _target_is_docs(target: str) -> bool:
    """True when the edit target is a docs/markdown file or convention doc.

    Dual-mode triggers should not fire on these — they mention boundary
    keywords as discussion items, not as runtime boundary changes.
    """
    if not target:
        return False
    lowered = target.lower()
    if lowered.endswith(DUAL_MODE_SKIP_EXTS):
        return True
    normalized = target.replace("\\", "/")
    # Strip leading paths so "anything/docs/x" and "docs/x" both match.
    for prefix in DUAL_MODE_SKIP_PREFIXES:
        prefix_norm = prefix.replace("\\", "/")
        if normalized.startswith(prefix_norm) or f"/{prefix_norm}" in normalized:
            return True
    return False


def touches_dual_mode(tool_input: dict) -> bool:
    target = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("filePath")
        or ""
    )
    if _target_is_docs(target):
        return False
    blob = json.dumps(tool_input, default=str)
    return any(trigger in blob for trigger in DUAL_MODE_TRIGGERS)


def emit_reminder(text: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": f"[loom-discipline] {text}",
        }
    }
    print(json.dumps(payload))


def emit_block(reason: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"[loom-discipline] {reason}",
        }
    }
    print(json.dumps(payload))


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
    log_event("PreToolUse", "start")
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        log_event("PreToolUse", "end", exit_code=0, elapsed_ms=now_ms() - start, action="noop", note="malformed_input")
        return 0

    # Propagate session_id + tool_name via env vars so subsequent
    # log_event calls in this process pick them up automatically (via
    # CLAUDE_SESSION_ID / LOOM_HOOK_TOOL_NAME defaults in
    # _observability.log_event). Avoids threading kwargs through every
    # call site.
    os.environ["CLAUDE_SESSION_ID"] = data.get("session_id") or ""

    tool_name = data.get("tool_name") or ""
    tool_input = data.get("tool_input") or {}
    transcript_path = data.get("transcript_path") or ""
    cwd = data.get("cwd") or ""

    os.environ["LOOM_HOOK_TOOL_NAME"] = tool_name

    # Only police loom-scoped repos. v0.1.12: scope also honors
    # LOOM_PROJECT_ID (per-project opt-in), not just cwd substrings.
    if not _in_scope(cwd):
        log_event("PreToolUse", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=False, action="noop", note=f"out_of_scope;tool={tool_name}")
        return 0

    if tool_name not in ("Edit", "Write", "MultiEdit"):
        log_event("PreToolUse", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="noop", note=f"tool_not_matched;tool={tool_name}")
        return 0

    target = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("filePath")
        or ""
    )

    strict = os.environ.get("DISCIPLINE_STRICT", "") == "1"

    # Check 1: runtime edit without citation
    if looks_like_runtime(target) and not has_recent_citation(transcript_path):
        if strict:
            emit_block(
                f"Editing runtime file {target} without a recent file:line citation. "
                "Run Grep/Read to ground the change, cite it, then retry."
            )
            log_event("PreToolUse", "end", exit_code=2, elapsed_ms=now_ms() - start, scope_in=True, action="block", note=f"strict_mode;runtime_edit_no_citation;target={target}")
            return 2
        emit_reminder(CITATION_REMINDER)
        log_event("PreToolUse", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="reminder_injected", note=f"citation_reminder;target={target}")
        return 0

    # Check 2: dual-mode boundary touch
    if touches_dual_mode(tool_input):
        emit_reminder(DUAL_MODE_REMINDER)
        log_event("PreToolUse", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="reminder_injected", note=f"dual_mode_trigger;target={target}")
        return 0

    # No issue.
    log_event("PreToolUse", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="noop", note=f"clean;target={target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
