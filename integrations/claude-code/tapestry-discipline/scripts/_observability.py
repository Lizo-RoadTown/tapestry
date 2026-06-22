"""
Shared observability helper for loom-discipline hook scripts.

Each hook calls log_event() to produce TWO outputs:

1. LOCAL — append a single JSON line to
   ${CLAUDE_PROJECT_DIR}/.claude/logs/hooks.jsonl (or
   ~/.claude/logs/hooks.jsonl if CLAUDE_PROJECT_DIR is unset). Same shape
   the plugin has emitted since v0.1.0. The local file is the source of
   truth and the fallback when the network is unavailable.

2. REMOTE — push the same event as an OTLP/HTTP log to Grafana Cloud
   (or any OTLP receiver) iff `OTEL_EXPORTER_OTLP_ENDPOINT` and
   `OTEL_EXPORTER_OTLP_HEADERS` are set in the environment. Standard
   OTel SDK env vars; the plugin reads them at runtime — no config
   changes required if you switch from Grafana Cloud to another OTLP
   receiver.

Record shape:
  {
    "ts": "<iso8601>",
    "hook": "<event_name>",        # e.g. "PreToolUse", "Stop"
    "phase": "start" | "end",
    "exit_code": int (end only),
    "elapsed_ms": int (end only),
    "scope_in": bool,              # did the hook decide it was in-scope
    "action": str | None,          # e.g. "reminder_injected", "block"
    "note": str | None
  }

Discipline (MS-agent's two rules, v0.1.6):

- Local write FIRST, OTel push SECOND. A Grafana/network blip CANNOT
  kill the local log. The local file always reflects ground truth.
- OTel push is wrapped in try/except; failures append to
  ~/.claude/logs/hook-otel-errors.log (mirrors the v0.1.4 import-error
  fallback). Never crash the harness.

Never raises. If everything fails, the hook continues silently.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# .env loader (v0.1.7)
# ---------------------------------------------------------------------------
#
# Hook scripts run as short-lived Python processes spawned by run-python.mjs.
# They inherit env from the Claude Code process tree — which on Windows comes
# from System/User-scope env vars set via SetEnvironmentVariable. That works,
# but it's friction: every credential rotation requires re-running PowerShell
# commands, and there are several ways for the user to mis-set values
# (literal placeholder pasted, quoting issues, missing User scope, etc).
#
# A project-local `.env` file is the universal pattern for this. Adding it
# here means credential changes are a one-line edit in an editor instead of
# a copy-paste PowerShell workflow.
#
# Stdlib-only loader (no python-dotenv dep — matches the rest of this
# module's no-install philosophy). Discipline:
#   - Existing os.environ entries WIN (a shell-set value overrides .env)
#   - Last duplicate KEY in the file wins (matches python-dotenv behavior)
#   - Quoted values have outer quotes stripped
#   - Lines starting with # or missing = are skipped
#   - File-read errors never raise (observability must not break hooks)
#
# `.env` is gitignored (see .gitignore line 38). Never commit one with real
# secrets; commit a `.env.example` showing the expected keys instead.


def _load_dotenv() -> None:
    """Load ${CLAUDE_PROJECT_DIR}/.env into os.environ. Never raises.

    Existing env vars WIN — `.env` only fills gaps, never overwrites. This
    matches python-dotenv's default and lets a user shadow a `.env` value
    by setting the shell var, which is useful for one-off overrides.
    """
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if not project_dir:
        return
    env_path = Path(project_dir) / ".env"
    if not env_path.is_file():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes if both ends match.
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:  # noqa: BLE001
        # Observability MUST NOT break hooks.
        pass


# Run at module import — every hook script that imports _observability
# picks up .env values before any os.environ.get() call downstream.
_load_dotenv()


# ---------------------------------------------------------------------------
# LOCAL JSONL (v0.1.0 — v0.1.5; unchanged)
# ---------------------------------------------------------------------------


def _log_dir() -> Path:
    base = os.environ.get("CLAUDE_PROJECT_DIR")
    if base:
        d = Path(base) / ".claude" / "logs"
    else:
        d = Path.home() / ".claude" / "logs"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Can't create — fall back to /tmp-ish location; if even that fails,
        # the caller will see no log file but the hook keeps running.
        d = Path(os.environ.get("TEMP") or "/tmp") / "claude-hooks"
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return d


def _write_local_jsonl(entry: dict[str, Any]) -> None:
    """Append one JSON line. Never raises."""
    try:
        path = _log_dir() / "hooks.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:  # noqa: BLE001
        # Observability MUST NOT break hooks. Swallow everything.
        pass


# ---------------------------------------------------------------------------
# OTLP/HTTP push (v0.1.6)
# ---------------------------------------------------------------------------
#
# Why raw urllib.request instead of the OpenTelemetry SDK:
#
# Hook scripts run as one-shot Python processes spawned by the Node bridge
# (run-python.mjs) on every Claude Code hook fire. Cold-start cost matters.
# The OTel SDK pulls in protobuf + a ~200KB dependency tree; importing it
# adds 100–300ms per hook fire on Windows. For our payload (a single log
# record per call) the SDK's batching + retry features are wasted overhead.
#
# Direct urllib.request POST to the OTLP/HTTP endpoint:
#   - stdlib only (no install steps; works wherever Python 3.10+ runs)
#   - ~5–20ms per call
#   - JSON wire format (OTLP supports both JSON and protobuf over HTTP;
#     Grafana Cloud accepts JSON; protobuf would need an extra dep)
#   - explicit error handling (we control the fallback)
#
# Trade-off accepted: no batching, no retry, no automatic flush. For an
# interactive Claude Code session at 10–100 events/min, this is fine.
# Phase 4's loom-telemetry-ingestion service handles batching server-side.


def _parse_otel_headers(raw: str) -> dict[str, str]:
    """Parse OTEL_EXPORTER_OTLP_HEADERS into HTTP header dict.

    Spec: comma-separated `key=value` pairs; values are URL-encoded so
    spaces/commas/equals in values survive transport. We URL-decode each
    value before setting as an HTTP header.

    Example input:  `Authorization=Basic%20MTU2NzM4Nw%3D%3D,X-Scope-OrgID=42`
    Example output: {"Authorization": "Basic MTU2NzM4Nw==", "X-Scope-OrgID": "42"}
    """
    headers: dict[str, str] = {}
    for pair in raw.split(","):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        key = key.strip()
        value = urllib.parse.unquote(value.strip())
        if key:
            headers[key] = value
    return headers


def _parse_resource_attributes(raw: str) -> list[dict[str, Any]]:
    """Parse OTEL_RESOURCE_ATTRIBUTES (`key=value,key=value`) into the
    OTLP resource.attributes list shape.
    """
    attrs: list[dict[str, Any]] = []
    for pair in raw.split(","):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        attrs.append(
            {
                "key": key.strip(),
                "value": {"stringValue": value.strip()},
            }
        )
    return attrs


def _entry_to_otlp_log(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a hooks.jsonl entry into an OTLP/HTTP JSON log payload.

    OTLP/HTTP JSON log shape (simplified):
      {
        "resourceLogs": [{
          "resource": { "attributes": [{"key": "service.name", "value": {"stringValue": "loom-discipline"}}] },
          "scopeLogs": [{
            "logRecords": [{
              "timeUnixNano": "<int as string>",
              "severityText": "INFO",
              "body": { "stringValue": "<hook event summary>" },
              "attributes": [...one attribute per entry field...]
            }]
          }]
        }]
      }
    """
    # Resource attributes — service.name from OTEL_SERVICE_NAME, plus any
    # OTEL_RESOURCE_ATTRIBUTES (namespace, deployment.environment, etc.).
    service_name = os.environ.get("OTEL_SERVICE_NAME", "loom-discipline")
    resource_attrs: list[dict[str, Any]] = [
        {"key": "service.name", "value": {"stringValue": service_name}}
    ]
    extra_resource = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
    if extra_resource:
        resource_attrs.extend(_parse_resource_attributes(extra_resource))

    # Log record attributes — one per entry field, typed by Python type.
    record_attrs: list[dict[str, Any]] = []
    for key, value in entry.items():
        if key in ("ts", "hook"):
            # ts is in timeUnixNano; hook becomes the body.
            continue
        if value is None:
            continue
        if isinstance(value, bool):
            record_attrs.append({"key": key, "value": {"boolValue": value}})
        elif isinstance(value, int):
            # OTLP intValue is a string (per spec — JSON int range issues).
            record_attrs.append({"key": key, "value": {"intValue": str(value)}})
        elif isinstance(value, float):
            record_attrs.append({"key": key, "value": {"doubleValue": value}})
        else:
            record_attrs.append({"key": key, "value": {"stringValue": str(value)}})

    # Also surface the hook name as a label-friendly attribute so LogQL
    # filters like {hook_name="PreToolUse"} work.
    hook_name = entry.get("hook")
    if hook_name:
        record_attrs.append(
            {"key": "hook_name", "value": {"stringValue": str(hook_name)}}
        )

    # Time as nanoseconds since epoch.
    try:
        ts_str = entry.get("ts", "")
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        time_unix_nano = int(dt.timestamp() * 1_000_000_000)
    except (KeyError, ValueError, AttributeError):
        time_unix_nano = int(time.time() * 1_000_000_000)

    # Body is the full entry as JSON. Two reasons:
    # 1. Dashboard panels typically pipe `| json` to extract fields. A
    #    plain-string body fails with JSONParserErr, breaking every panel
    #    that uses that pattern.
    # 2. The full entry as JSON makes the live-tail panel self-describing
    #    (you can read everything about a hook event from the body alone)
    #    without losing the per-field metadata queryability that the
    #    `attributes` field provides.
    # The metadata (record_attrs) is still sent separately, so queries can
    # use either `| json | field=...` (body parse) or `| field=...` (metadata
    # filter) — both work after this change.
    return {
        "resourceLogs": [
            {
                "resource": {"attributes": resource_attrs},
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "timeUnixNano": str(time_unix_nano),
                                "severityText": "INFO",
                                "severityNumber": 9,
                                "body": {"stringValue": json.dumps(entry)},
                                "attributes": record_attrs,
                            }
                        ]
                    }
                ],
            }
        ]
    }


def _push_otlp(entry: dict[str, Any]) -> None:
    """Push entry as OTLP log to Grafana Cloud. Never raises.

    Silently skips if OTEL_EXPORTER_OTLP_ENDPOINT is unset (e.g., user
    hasn't configured Grafana Cloud yet — local jsonl write still ran).
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return
    headers_raw = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")

    try:
        payload = _entry_to_otlp_log(entry)
        url = f"{endpoint.rstrip('/')}/v1/logs"
        http_headers = {"Content-Type": "application/json"}
        http_headers.update(_parse_otel_headers(headers_raw))

        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=http_headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            if status >= 400:
                raise RuntimeError(f"OTLP receiver returned {status}")
    except Exception as e:  # noqa: BLE001
        _log_otel_error(e)


def _log_otel_error(err: Exception) -> None:
    """Append OTel push error to hook-otel-errors.log. Never raises.

    Mirrors v0.1.4's hook-import-errors.log pattern — failures are
    observable instead of silent, but don't crash the harness.
    """
    try:
        path = Path.home() / ".claude" / "logs" / "hook-otel-errors.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now(timezone.utc).isoformat()} "
                f"{type(err).__name__}: {err}\n"
            )
    except Exception:  # noqa: BLE001
        # Even the error log failed. Nothing we can do without crashing
        # the harness. Drop silently.
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def log_event(
    hook: str,
    phase: str,
    *,
    scope_in: bool | None = None,
    action: str | None = None,
    note: str | None = None,
    exit_code: int | None = None,
    elapsed_ms: int | None = None,
    session_id: str | None = None,
    tool_name: str | None = None,
    project_id: str | None = None,
) -> None:
    """Record a hook event.

    Local jsonl write happens first (always). OTel push happens second
    (only if env configured). Never raises. Never blocks the hook.

    Optional dimensions:
      session_id  — Claude Code session ID. Read from stdin JSON by each
                    hook script and passed through. Enables per-session
                    grouping in Grafana panels.
      tool_name   — Tool name (PreToolUse only). Enables per-tool breakdown.
      project_id  — Project identifier. Defaults to LOOM_PROJECT_ID env var
                    if not provided. Enables per-project filtering before
                    Phase 3's full Project Registry lands.
    """
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "hook": hook,
        "phase": phase,
    }
    if scope_in is not None:
        entry["scope_in"] = scope_in
    if action is not None:
        entry["action"] = action
    if note is not None:
        entry["note"] = note
    if exit_code is not None:
        entry["exit_code"] = exit_code
    if elapsed_ms is not None:
        entry["elapsed_ms"] = elapsed_ms
    # session_id defaults to CLAUDE_SESSION_ID env var so each hook script
    # only needs to set it once (after parsing stdin) — every log_event call
    # in that same process inherits it without explicit threading.
    sid = session_id or os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        entry["session_id"] = sid
    # tool_name defaults to LOOM_HOOK_TOOL_NAME env var (only set by
    # pre_tool_use.py after parsing stdin). Same env-var pattern as
    # CLAUDE_SESSION_ID — avoids threading tool_name through every
    # log_event call site.
    tn = tool_name or os.environ.get("LOOM_HOOK_TOOL_NAME")
    if tn:
        entry["tool_name"] = tn
    # project_id defaults to LOOM_PROJECT_ID env var so callers don't have
    # to thread it through every log_event call. Explicit param overrides.
    pid = project_id or os.environ.get("LOOM_PROJECT_ID")
    if pid:
        entry["project_id"] = pid

    # 1. Local (must run; never raises).
    _write_local_jsonl(entry)

    # 2. Remote OTel push (best-effort; never raises).
    _push_otlp(entry)


# Wall-clock helper for elapsed_ms.
def now_ms() -> int:
    return int(time.time() * 1000)
