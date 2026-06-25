#!/usr/bin/env python3
"""
SessionStart hook for tapestry-discipline (preserved runtime label: [loom-discipline]).

Triggers the architecture-snapshot pipeline:

  1. Runs scripts/architecture_snapshot.py in the project repo
  2. Runs scripts/architecture_diff.py
  3. Emits a short additionalContext block pointing the agent at the new
     diff.md AND requesting it invoke the architecture-analyst subagent to
     produce the narrative report.

Scope-guarded: only fires when LOOM_PROJECT_ID is set, the cwd matches the
optional TAPESTRY_SCOPE_DIRS allowlist, or the repo has the snapshot pipeline.

The script does NOT write the narrative itself — that's the analyst agent's
job. This script ensures the deterministic snapshot + diff data exists, so
the agent has a real input to interpret.

Errors here MUST be non-fatal (exit 0 with no output) — a broken hook should
never block session start.
"""
from __future__ import annotations

import json
import os
import subprocess
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


# Env-override precedence (PR-prep-2b 2026-06-19):
#   1. TAPESTRY_AGENT_CONTEXT_URL — Tapestry-aware deployments.
#   2. LOOM_AGENT_CONTEXT_URL — bare base host.
#   3. Placeholder default — set one of the above to your own deployment host.
# Same precedence pattern lives at the per-call overrides at _try_recall
# (search) and the MCP-status probe below.
_AGENT_CONTEXT_DEFAULT_URL = os.environ.get(
    "TAPESTRY_AGENT_CONTEXT_URL",
    os.environ.get(
        "LOOM_AGENT_CONTEXT_URL",
        "https://your-memory-host.example.com",
    ),
)
_MCP_PATH = "/mcp/memory/"


def _agent_context_base_url() -> str:
    """Resolve the agent-context base host (used for /health + /v1/recall) from
    the env precedence. The *_MEMORY_MCP_URL / *_MEMORY_URL vars point at the
    full /mcp/memory/ endpoint, so strip that suffix to recover the base host —
    this way all six configuration vars resolve to the same place. Falls back to
    the example.com placeholder when nothing is configured."""
    for var in ("TAPESTRY_AGENT_CONTEXT_URL", "LOOM_AGENT_CONTEXT_URL"):
        v = os.environ.get(var, "").strip()
        if v:
            return v.rstrip("/")
    for var in ("TAPESTRY_MEMORY_MCP_URL", "LOOM_MEMORY_MCP_URL",
                "TAPESTRY_MEMORY_URL", "LOOM_MEMORY_URL"):
        v = os.environ.get(var, "").strip()
        if v:
            return v.rstrip("/").removesuffix("/mcp/memory").rstrip("/")
    return _AGENT_CONTEXT_DEFAULT_URL.rstrip("/")


def _backend_configured() -> bool:
    """True iff a real memory backend is configured via env (the resolved base
    URL is not the example.com placeholder). When unconfigured the plugin runs
    in pure-discipline mode: no memory probe/recall, no timeout against the
    placeholder host. The discipline hooks need no backend."""
    return "example.com" not in _agent_context_base_url()


def _check_mcp_reachable(base_url: str, timeout: float = 3.0) -> tuple[bool, str]:
    """v0.1.8 (concrete-rule Layer 6): probe the MCP endpoint host and report
    whether memory tools will be usable in this session.

    Returns (reachable, status_string). reachable=False means agents in this
    session MAY find memory_* tool calls failing — surface loudly via
    additionalContext so operator and agent both SEE the failure rather
    than silently proceeding without memory access.

    The MCP transport speaks streamable HTTP and has no simple GET /
    health. Hitting /health on the parent service confirms the host is
    up; if /v1/recall (same DB + tenant resolution) is responsive, MCP
    almost certainly works.
    """
    import urllib.error
    import urllib.request

    health_url = base_url.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url=health_url, method="GET"),
            timeout=timeout,
        ) as resp:
            if resp.status == 200:
                return True, "OK"
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        return False, f"unreachable ({type(e).__name__})"


def _mcp_status_block(base_url: str) -> list[str]:
    """Concrete-rule Layer 6 visibility block. Always returns something;
    silence is the failure mode we're guarding against."""
    reachable, status = _check_mcp_reachable(base_url)
    mcp_url = base_url.rstrip("/") + _MCP_PATH
    if reachable:
        return [
            "[loom-memory · MCP transport]",
            f"MCP reachable at {mcp_url} ({status}). memory_read / memory_write / "
            f"memory_recall / memory_search / memory_list / memory_delete should be "
            f"available as tools.",
        ]
    return [
        "",
        "*** CONCRETE-RULE VIOLATION DETECTED ***",
        f"[loom-memory · MCP UNREACHABLE: {status}]",
        f"The loom-memory MCP server at {mcp_url} did not respond.",
        "",
        "Consequences:",
        "  - memory_read / memory_write / memory_recall MCP tool calls WILL FAIL",
        "  - cross-project memory persistence is offline for this session",
        "  - the platform's primary value proposition is degraded",
        "",
        "Recovery (in order):",
        "  1. Wait 30-60s for Render cold-start, then restart Claude Code",
        "  2. Check your hosting provider dashboard for the memory service",
        "  3. If service is down, check recent deploys / logs / Postgres health",
        "  4. Fallback: typed-file memory at ~/.claude/projects/<key>/memory/ still works "
        "for this session but does NOT persist to the cross-project store",
        "",
        "Why this warning exists:",
        "  loom-memory access is a concrete rule of this platform (see "
        "skills_private/concrete-rule/SKILL.md). Silent absence of memory access "
        "was the failure mode that prompted v0.1.8's defense-in-depth wiring.",
        "*****",
    ]


def _try_recall(cwd_lower: str, n: int = 5, timeout: float = 6.0) -> list[str]:
    """v0.1.7: call agent-context POST /v1/recall and format top-N memories
    as additionalContext lines. Stdlib-only (urllib). Never raises.

    Builds the recall context string from CLAUDE_PROJECT_DIR + LOOM_PROJECT_ID
    (already loaded into os.environ via _observability._load_dotenv at import
    time). project_tags scopes to the current project if LOOM_PROJECT_ID is
    set; otherwise omitted (cross-project recall).

    Timeout 6s: covers MCP host warm cold-starts (memory-service on
    starter tier = no spin-down; should respond in <1s typically). If we hit
    the timeout, silently skip — the architecture-snapshot context still
    emits. Auto-recall is best-effort.

    Returns a list of additionalContext lines, or empty list on any error.
    """
    import json as _json
    import urllib.error
    import urllib.request

    try:
        project_id = os.environ.get("LOOM_PROJECT_ID", "").strip()
        if project_id:
            context = (
                f"SessionStart in project '{project_id}'. Surface memories "
                f"relevant to this project + any user preferences/feedback that "
                f"apply broadly."
            )
            project_tags = [project_id]
        else:
            context = (
                f"SessionStart in cwd '{cwd_lower}'. Surface memories relevant "
                f"to general user preferences/feedback (no project tag set)."
            )
            project_tags = []

        body = _json.dumps({
            "context": context,
            "n": n,
            "project_tags": project_tags,
        }).encode("utf-8")

        url = _agent_context_base_url().rstrip("/") + "/v1/recall"

        req = urllib.request.Request(
            url=url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return []
            data = _json.loads(resp.read().decode("utf-8"))

        memories = data.get("memories", [])
        if not memories:
            return []

        out = ["[loom-memory · auto-recall]"]
        out.append(f"Surfaced {len(memories)} relevant memories at session start:")
        for m in memories:
            name = m.get("name", "<unnamed>")
            mtype = m.get("type", "?")
            # Trim content to a one-line preview; full body is queryable
            # via memory_read if the agent wants to load it.
            content = (m.get("content") or "").strip().splitlines()
            preview = content[0] if content else ""
            if len(preview) > 140:
                preview = preview[:137] + "..."
            out.append(f"  - [{mtype}] {name}: {preview}")
        out.append(
            "Full bodies available via the loom-memory MCP's memory_read "
            "tool (pass the name field). Use these to ground the work — "
            "especially feedback / lesson / preference records."
        )
        return out
    except (urllib.error.URLError, urllib.error.HTTPError,
            ConnectionError, TimeoutError, _json.JSONDecodeError,
            OSError, Exception):  # noqa: BLE001 - never raise from a hook
        return []


def _in_scope(cwd) -> bool:
    """True if tapestry-discipline hooks should run for this repo.

    In scope if LOOM_PROJECT_ID is set (the explicit per-project opt-in a
    consuming project declares via its `.env`, loaded into os.environ by
    _observability._load_dotenv at import time), OR the working-directory
    path matches a substring in the optional TAPESTRY_SCOPE_DIRS env
    allowlist (comma-separated). No project names are hardcoded — the plugin
    ships universal; each operator configures their own scope.

    Note: session_start keeps an additional ARCHITECTURE.md + snapshot-
    script fallback at its call site for repos that have the snapshot
    pipeline but no LOOM_PROJECT_ID set.
    """
    if os.environ.get("LOOM_PROJECT_ID", "").strip():
        return True
    # Optional path allowlist — no project names hardcoded; operators set
    # TAPESTRY_SCOPE_DIRS (comma-separated substrings) for path-based scoping.
    cwd_l = str(cwd or "").lower()
    allow = os.environ.get("TAPESTRY_SCOPE_DIRS", "")
    for sub in (s.strip().lower() for s in allow.split(",") if s.strip()):
        if sub and sub in cwd_l:
            return True
    return False


def main() -> int:
    start = now_ms()
    log_event("SessionStart", "start")
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        log_event("SessionStart", "end", exit_code=0, elapsed_ms=now_ms() - start, action="noop", note="malformed_input")
        return 0

    # Propagate session_id into the env so subsequent log_event calls
    # in this process pick it up (via the CLAUDE_SESSION_ID default in
    # _observability.log_event). Empty string = absent; log_event skips it.
    os.environ["CLAUDE_SESSION_ID"] = data.get("session_id") or ""

    cwd = Path(data.get("cwd") or os.getcwd())
    cwd_lower = str(cwd).lower()

    # Scope-guard. v0.1.12: scope also honors LOOM_PROJECT_ID (per-project
    # opt-in) via _in_scope, not just cwd substrings. The ARCHITECTURE.md +
    # snapshot-script fallback is preserved for repos that have the snapshot
    # pipeline but no LOOM_PROJECT_ID set.
    in_scope = (
        _in_scope(cwd)
        or ((cwd / "ARCHITECTURE.md").exists()
            and (cwd / "scripts" / "architecture_snapshot.py").exists())
    )
    if not in_scope:
        log_event("SessionStart", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=False, action="noop", note="out_of_scope")
        return 0

    snapshot_script = cwd / "scripts" / "architecture_snapshot.py"
    diff_script = cwd / "scripts" / "architecture_diff.py"
    if not snapshot_script.exists():
        # No scripts installed yet in this repo — silently skip.
        log_event("SessionStart", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="noop", note="snapshot_script_absent")
        return 0

    # Resolve python — prefer system python, fall back to specific paths
    # that work on this machine. Mirrors the strategy used by other hook
    # scripts (the hooks.json invokes us via the same python).
    python_exe = sys.executable

    snapshot_dir = cwd / "docs" / "architecture-snapshots"
    snapshots_before = (
        sorted(snapshot_dir.glob("*-snapshot.json")) if snapshot_dir.exists() else []
    )

    # Run snapshot
    try:
        subprocess.run(
            [python_exe, str(snapshot_script)],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            timeout=20,
        )
    except (subprocess.SubprocessError, OSError):
        log_event("SessionStart", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="noop", note="snapshot_script_error")
        return 0

    # Run diff (only meaningful if we have at least 1 prior, but the diff
    # script handles the no-prior case gracefully).
    try:
        subprocess.run(
            [python_exe, str(diff_script)],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            timeout=20,
        )
    except (subprocess.SubprocessError, OSError):
        # Snapshot worked but diff failed — still proceed; we have the snapshot.
        pass

    # Find what was just written.
    if not snapshot_dir.exists():
        log_event("SessionStart", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="noop", note="snapshot_dir_missing_post_run")
        return 0
    snapshots_after = sorted(snapshot_dir.glob("*-snapshot.json"))
    if not snapshots_after:
        log_event("SessionStart", "end", exit_code=0, elapsed_ms=now_ms() - start, scope_in=True, action="noop", note="no_snapshots_post_run")
        return 0
    new_snapshot = snapshots_after[-1]
    new_diff_md = new_snapshot.with_name(new_snapshot.stem.replace("-snapshot", "-diff") + ".md")
    new_diff_json = new_snapshot.with_name(new_snapshot.stem.replace("-snapshot", "-diff") + ".json")

    rel_snapshot = new_snapshot.relative_to(cwd)
    rel_diff_md = new_diff_md.relative_to(cwd) if new_diff_md.exists() else None
    rel_diff_json = new_diff_json.relative_to(cwd) if new_diff_json.exists() else None

    first_run = len(snapshots_before) == 0

    msg_lines = ["[loom-discipline · architecture-snapshot]"]
    if first_run:
        msg_lines.append(f"First snapshot written: {rel_snapshot}.")
        msg_lines.append("No prior to diff against. Future sessions will compare to this baseline.")
    else:
        msg_lines.append(f"Snapshot: {rel_snapshot}")
        if rel_diff_md:
            msg_lines.append(f"Diff:     {rel_diff_md}")
        msg_lines.append("")
        msg_lines.append(
            "Invoke the architecture-analyst subagent (in the tapestry-discipline plugin) "
            "to read the snapshot + diff and produce the narrative report at "
            "docs/architecture-snapshots/<timestamp>-narrative.md. Pass the file paths above as input. "
            "If the diff shows no changes, write the minimal narrative form."
        )

    # --- v0.1.7: auto-recall from loom-memory MCP store ---
    # Surface top-N relevant memories at session start. Calls the REST
    # counterpart at agent-context's POST /v1/recall (not the MCP transport
    # — that requires an MCP HTTP handshake we'd rather not do from a
    # one-shot Python process). Self-host mode = no auth header; agent-
    # context falls back to SELF_HOST_TENANT_ID.
    #
    # Never raises. If the recall fails (network blip, service cold-start
    # timeout, schema drift), the hook still emits the architecture-snapshot
    # context — auto-recall is best-effort, not load-bearing.
    # The memory backend is OPTIONAL. When the operator has pointed the plugin
    # at a real host (env), do best-effort recall + the MCP reachability probe
    # (whose "unreachable" warning is load-bearing — CORE DIRECTIVE 1). When NOT
    # configured, run in pure-discipline mode: skip the network calls and emit a
    # soft note instead of a violation, so the plugin never times out against
    # the placeholder host.
    if _backend_configured():
        recall_lines = _try_recall(cwd_lower)
        if recall_lines:
            msg_lines.append("")
            msg_lines.extend(recall_lines)
        msg_lines.append("")
        msg_lines.extend(_mcp_status_block(_agent_context_base_url()))
    else:
        msg_lines.append("")
        msg_lines.append("[memory: not configured — optional]")
        msg_lines.append(
            "Set TAPESTRY_MEMORY_MCP_URL to your own memory MCP endpoint to enable "
            "cross-session recall. The discipline hooks work without it."
        )

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(msg_lines),
        }
    }
    print(json.dumps(payload))
    log_event(
        "SessionStart", "end",
        exit_code=0, elapsed_ms=now_ms() - start,
        scope_in=True,
        action="snapshot_emitted",
        note=f"first_run={first_run};snapshot={rel_snapshot.name}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
