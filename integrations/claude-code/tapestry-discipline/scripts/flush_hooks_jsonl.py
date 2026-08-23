#!/usr/bin/env python3
"""flush-hooks-jsonl — replay a discipline-hook `hooks.jsonl` into /hook-events.

Phase 0 **task 7** of the observer-capacity build
(docs/plans/2026-08-23-observer-capacity-build-sequence.md). This is the
BACKFILL counterpart to the live hook sink (task 5, `_observability._push_ingest`)
and the ingest endpoint (task 4, `services/telemetry-ingestion/main.py`).

## What it is for

The live sink is best-effort: it fires on every hook with a 2s timeout and
swallows every failure (`_observability._push_ingest` -> `_log_otel_error`). So
a machine that was OFFLINE — or ran before the `/hook-events` endpoint existed —
still has a complete LOCAL `hooks.jsonl` (the source of truth,
`_observability._write_local_jsonl`) but MISSING rows in Postgres. This CLI
replays that local log into `/hook-events` to reconcile.

## Why replay is safe (idempotent by construction)

We add NO dedup of our own. The task-4 mapper derives a STABLE `uuid5` id from
each entry's own fields — `session_id | hook_name | phase | tool_name | raw ts`
(`hook_event_handler._hook_event_id`, using the RAW `ts` value straight off the
jsonl line). `persist.persist_events` then INSERTs with `ON CONFLICT (id) DO
NOTHING`. So re-POSTing a line already ingested derives the identical id and is
dropped server-side. The one hard requirement on us: send the entry's fields
UNCHANGED so the mapper hashes the same id. We do — each line is parsed and
forwarded verbatim (this CLI is READ-ONLY on the log; it never rewrites it).

Consequence the operator should expect: a second run over the same file reports
`events_processed ~= 0` even though every line was sent. That is dedup working,
not a failure. The summary text says so explicitly.

## How it differs from the hook sink (deliberately opposite discipline)

This is an OPERATOR CLI (dev-tooling), NOT a hook. Where the hook sink must
NEVER raise, block, or surface config errors, this command:
  - BLOCKS (synchronous POST with a real timeout + a couple of retries)
  - ERRORS LOUDLY on misconfiguration (endpoint/secret unset) with a nonzero
    exit — an operator running a backfill wants to KNOW it did nothing, not
    have it silently no-op the way the offline-safe hook sink does.
  - Is READ-ONLY on `hooks.jsonl` — it opens the log for reading only and
    never truncates, rewrites, or moves it.

## Reused crypto (no re-implementation)

The batch HMAC is `_observability._hook_signature` — imported, not copied — so
the exact wire format (`t=<unix>,v1=<hex>` over `f"{ts}.{raw_body}"` with
`LOOM_HOOK_BRIDGE_SECRET`) stays single-sourced with the live sink and matches
`services/telemetry-ingestion/bridge_hmac.verify_signature`. Importing
`_observability` is side-effect-free for our purposes: its only import-time
action is `_load_dotenv()`, which reads `${CLAUDE_PROJECT_DIR}/.env` into GAPS
in `os.environ` (never overwriting a shell-set value, never touching the jsonl,
never hitting the network). For this CLI that load is a bonus — it picks up
`LOOM_INGEST_ENDPOINT` / `LOOM_HOOK_BRIDGE_SECRET` from `.env` just like the hooks.

stdlib + raw urllib only (matches the no-heavy-deps style of these scripts).
"""
from __future__ import annotations

import argparse
import importlib.util as _importlib_util
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# ---------------------------------------------------------------------------
# Reuse _observability by absolute path (same importlib pattern the hooks use,
# e.g. stop_audit.py:49). We pull in ONLY the signing helper + the env-var-name
# constants so the wire contract stays single-sourced. Import-time side effect
# is limited to _observability._load_dotenv() (reads ${CLAUDE_PROJECT_DIR}/.env
# into gaps in os.environ — no writes, no network). That is desirable here.
# ---------------------------------------------------------------------------
import os  # noqa: E402  (after the header; os is only needed for env reads)

_OBS_PATH = Path(__file__).resolve().parent / "_observability.py"


def _load_observability() -> Any:
    spec = _importlib_util.spec_from_file_location("_observability", _OBS_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot locate _observability at {_OBS_PATH}")
    mod = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # runs _load_dotenv() — the only side effect
    return mod


try:
    _obs = _load_observability()
    _hook_signature = _obs._hook_signature
    INGEST_ENDPOINT_ENV = _obs._INGEST_ENDPOINT_ENV  # "LOOM_INGEST_ENDPOINT"
    HOOK_BRIDGE_SECRET_ENV = _obs._HOOK_BRIDGE_SECRET_ENV  # "LOOM_HOOK_BRIDGE_SECRET"
    SIGNATURE_HEADER = _obs._INGEST_SIGNATURE_HEADER  # "X-Loom-Hook-Signature"
except Exception as exc:  # noqa: BLE001
    # Unlike a hook, we do NOT degrade to a no-op — a backfill that cannot sign
    # is useless. Fail loud, fail early.
    print(
        f"flush-hooks-jsonl: FATAL — could not import signing helper from "
        f"{_OBS_PATH}: {exc!r}",
        file=sys.stderr,
    )
    sys.exit(4)


# Server contract (services/telemetry-ingestion/main.py:42). One request may
# not exceed this many entries, so no batch we send may be larger.
_MAX_HOOK_EVENTS = 1000

_DEFAULT_BATCH_SIZE = 200
_DEFAULT_JSONL = Path.home() / ".claude" / "logs" / "hooks.jsonl"

# POST behavior (operator CLI: it MAY block + retry, opposite of the sink).
_HTTP_TIMEOUT_SECONDS = 30
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.5


# ---------------------------------------------------------------------------
# ts parsing (mirrors hook_event_handler._to_epoch for --since comparison ONLY;
# we NEVER mutate the entry's ts — the raw value is what the mapper hashes).
# ---------------------------------------------------------------------------


def _to_epoch(ts_value: Any) -> float:
    """Parse an epoch number, a numeric string, or an ISO-8601 string to epoch
    seconds. Raises ValueError on anything unparseable."""
    if isinstance(ts_value, bool):
        raise ValueError("ts must not be a boolean")
    if isinstance(ts_value, (int, float)):
        return float(ts_value)
    if ts_value is None:
        raise ValueError("ts is required")
    s = str(ts_value).strip()
    if not s:
        raise ValueError("ts is empty")
    try:
        return float(s)
    except ValueError:
        pass
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _parse_since(raw: str) -> float:
    """Parse a --since argument (epoch or ISO-8601) to epoch seconds."""
    try:
        return _to_epoch(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--since must be epoch seconds or ISO-8601 (got {raw!r}): {exc}"
        )


# ---------------------------------------------------------------------------
# Reading the log (READ-ONLY).
# ---------------------------------------------------------------------------


class _ReadStats:
    def __init__(self) -> None:
        self.lines_read = 0
        self.malformed = 0
        self.filtered_out = 0


def _iter_entries(
    path: Path, since: float | None, limit: int | None, stats: _ReadStats
) -> Iterator[dict[str, Any]]:
    """Yield parsed entry dicts from the jsonl file. Opens READ-ONLY.

    - Blank lines are skipped silently.
    - A malformed (non-JSON, or non-object) line is WARNED to stderr and
      skipped — one bad line never aborts the whole run.
    - `since` (epoch) filters entries whose ts < since; a since with an
      unparseable ts is treated as not-matching (filtered out, warned).
    - `limit` caps the number of YIELDED entries.
    """
    yielded = 0
    # newline="" + mode "r": pure read, no truncation, no rewrite of the log.
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            stats.lines_read += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                stats.malformed += 1
                print(
                    f"flush-hooks-jsonl: WARN line {lineno}: skipping malformed "
                    f"JSON ({exc})",
                    file=sys.stderr,
                )
                continue
            if not isinstance(entry, dict):
                stats.malformed += 1
                print(
                    f"flush-hooks-jsonl: WARN line {lineno}: skipping non-object "
                    f"entry (type {type(entry).__name__})",
                    file=sys.stderr,
                )
                continue
            if since is not None:
                try:
                    entry_epoch = _to_epoch(entry.get("ts"))
                except ValueError:
                    stats.filtered_out += 1
                    print(
                        f"flush-hooks-jsonl: WARN line {lineno}: unparseable ts "
                        f"{entry.get('ts')!r}; excluded by --since",
                        file=sys.stderr,
                    )
                    continue
                if entry_epoch < since:
                    stats.filtered_out += 1
                    continue
            yield entry
            yielded += 1
            if limit is not None and yielded >= limit:
                return


def _batched(items: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


# ---------------------------------------------------------------------------
# POST one batch (signs + sends the IDENTICAL bytes; retries on transient error).
# ---------------------------------------------------------------------------


def _post_batch(endpoint: str, secret: str, batch: list[dict[str, Any]]) -> int:
    """POST one {"events": [...]} batch to /hook-events. Returns the batch's
    events_processed from the ack. Raises RuntimeError on a hard failure
    (4xx, or exhausted retries) — the caller aborts loudly.

    The bytes signed are the EXACT bytes sent (serialize once), and the signing
    timestamp is fresh per attempt so it stays inside bridge_hmac's ±5min replay
    window even for a long backfill.
    """
    raw_body = json.dumps({"events": batch})
    body_bytes = raw_body.encode("utf-8")
    last_err: Exception | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        ts = int(time.time())  # fresh signing ts each attempt (replay window)
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: _hook_signature(raw_body, secret, ts),
        }
        req = urllib.request.Request(
            url=endpoint, data=body_bytes, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECONDS) as resp:
                ack_raw = resp.read().decode("utf-8")
            try:
                ack = json.loads(ack_raw)
            except json.JSONDecodeError:
                ack = {}
            return int(ack.get("events_processed", 0))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                pass
            # 4xx is a hard error (bad signature=401, malformed=400, too big=413):
            # retrying will not help. Fail loud immediately.
            if 400 <= exc.code < 500:
                raise RuntimeError(
                    f"endpoint rejected batch ({exc.code} {exc.reason}): {detail}"
                ) from exc
            last_err = RuntimeError(
                f"endpoint returned {exc.code} {exc.reason}: {detail}"
            )
        except urllib.error.URLError as exc:
            last_err = RuntimeError(f"network error: {exc.reason}")
        except Exception as exc:  # noqa: BLE001
            last_err = RuntimeError(f"unexpected error: {exc!r}")

        if attempt < _MAX_ATTEMPTS:
            print(
                f"flush-hooks-jsonl: WARN batch attempt {attempt}/{_MAX_ATTEMPTS} "
                f"failed ({last_err}); retrying...",
                file=sys.stderr,
            )
            time.sleep(_RETRY_BACKOFF_SECONDS * attempt)

    raise RuntimeError(
        f"batch failed after {_MAX_ATTEMPTS} attempts: {last_err}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="flush-hooks-jsonl",
        description=(
            "Replay a discipline-hook hooks.jsonl into the telemetry-ingestion "
            "/hook-events endpoint. Idempotent (server dedups by stable id), so a "
            "re-run reports events_processed~=0. Read-only on the log."
        ),
    )
    p.add_argument(
        "path",
        nargs="?",
        default=str(_DEFAULT_JSONL),
        help=f"Path to hooks.jsonl (default: {_DEFAULT_JSONL})",
    )
    p.add_argument(
        "--endpoint",
        default=os.environ.get(INGEST_ENDPOINT_ENV),
        help=(
            f"Full URL of the /hook-events route "
            f"(default: ${INGEST_ENDPOINT_ENV})"
        ),
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=_DEFAULT_BATCH_SIZE,
        help=f"Entries per POST (default {_DEFAULT_BATCH_SIZE}, max {_MAX_HOOK_EVENTS})",
    )
    p.add_argument(
        "--since",
        type=_parse_since,
        default=None,
        metavar="TS",
        help="Only replay entries with ts >= TS (epoch seconds or ISO-8601).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Replay at most this many entries (after --since filtering).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse, count, and validate; print what WOULD be sent; POST nothing.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # --- validate args ---
    if args.batch_size < 1:
        print("flush-hooks-jsonl: FATAL — --batch-size must be >= 1", file=sys.stderr)
        return 2
    batch_size = args.batch_size
    if batch_size > _MAX_HOOK_EVENTS:
        print(
            f"flush-hooks-jsonl: WARN — --batch-size {batch_size} exceeds the "
            f"server max {_MAX_HOOK_EVENTS}; clamping to {_MAX_HOOK_EVENTS}.",
            file=sys.stderr,
        )
        batch_size = _MAX_HOOK_EVENTS
    if args.limit is not None and args.limit < 0:
        print("flush-hooks-jsonl: FATAL — --limit must be >= 0", file=sys.stderr)
        return 2

    path = Path(args.path).expanduser()
    if not path.is_file():
        print(
            f"flush-hooks-jsonl: FATAL — jsonl file not found: {path}",
            file=sys.stderr,
        )
        return 1

    # --- read (READ-ONLY) ---
    stats = _ReadStats()
    try:
        entries = list(_iter_entries(path, args.since, args.limit, stats))
    except OSError as exc:
        print(
            f"flush-hooks-jsonl: FATAL — could not read {path}: {exc}",
            file=sys.stderr,
        )
        return 1

    batches = list(_batched(entries, batch_size))

    # --- DRY RUN: never touches the network, never needs endpoint/secret ---
    if args.dry_run:
        print("flush-hooks-jsonl: DRY RUN (nothing was POSTed)")
        print(f"  file            : {path}")
        print(f"  lines read      : {stats.lines_read}")
        print(f"  malformed/skip  : {stats.malformed}")
        if args.since is not None:
            print(f"  filtered (since): {stats.filtered_out}")
        print(f"  entries to send : {len(entries)}")
        print(f"  batch size      : {batch_size}")
        print(f"  batches to send : {len(batches)}")
        if entries:
            sample = json.dumps(entries[0])
            if len(sample) > 300:
                sample = sample[:300] + "...(truncated)"
            print(f"  first entry     : {sample}")
        print("  (idempotent: a real run is safe to repeat; re-runs dedup server-side)")
        return 0

    # --- REAL RUN: misconfiguration is a LOUD failure, not a silent no-op ---
    endpoint = args.endpoint
    if not endpoint:
        print(
            f"flush-hooks-jsonl: FATAL — no endpoint. Pass --endpoint or set "
            f"${INGEST_ENDPOINT_ENV} to the full /hook-events URL. (This is an "
            f"operator command; it errors rather than silently doing nothing.)",
            file=sys.stderr,
        )
        return 2
    secret = os.environ.get(HOOK_BRIDGE_SECRET_ENV)
    if not secret:
        print(
            f"flush-hooks-jsonl: FATAL — ${HOOK_BRIDGE_SECRET_ENV} is unset. Set "
            f"the shared HMAC secret (same value the endpoint verifies with).",
            file=sys.stderr,
        )
        return 2

    if not entries:
        print("flush-hooks-jsonl: nothing to send (0 entries after read/filter).")
        print(f"  lines read     : {stats.lines_read}")
        print(f"  malformed/skip : {stats.malformed}")
        return 0

    # --- POST batch by batch; abort loudly on a hard failure ---
    events_processed = 0
    batches_sent = 0
    for i, batch in enumerate(batches, start=1):
        try:
            processed = _post_batch(endpoint, secret, batch)
        except RuntimeError as exc:
            print(
                f"flush-hooks-jsonl: FATAL — batch {i}/{len(batches)} failed: {exc}",
                file=sys.stderr,
            )
            print(
                f"  (sent {batches_sent} batch(es), {events_processed} event(s) "
                f"processed before this failure; re-running is safe — the server "
                f"dedups already-ingested entries.)",
                file=sys.stderr,
            )
            return 3
        events_processed += processed
        batches_sent += 1

    # --- summary ---
    print("flush-hooks-jsonl: done")
    print(f"  file            : {path}")
    print(f"  lines read      : {stats.lines_read}")
    print(f"  malformed/skip  : {stats.malformed}")
    if args.since is not None:
        print(f"  filtered (since): {stats.filtered_out}")
    print(f"  entries sent    : {len(entries)}")
    print(f"  batches sent    : {batches_sent}")
    print(f"  events_processed: {events_processed}  (sum of endpoint acks)")
    if events_processed < len(entries):
        deduped = len(entries) - events_processed
        print(
            f"  note            : {deduped} entr(y/ies) were already in Postgres "
            f"and were DEDUPED server-side (stable-id ON CONFLICT DO NOTHING). "
            f"events_processed counts only NEW rows, so a re-run over the same "
            f"file correctly reports ~0."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
