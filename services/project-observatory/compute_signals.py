"""Materialization entrypoint for the runtime-observer — the cron command.

Phase 1 **task 4** of the observer-capacity build (docs/plans/2026-08-23-
observer-capacity-build-sequence.md). This is the operator/cron command that
runs ONE observation pass: it reads the 005 telemetry substrate over a window,
computes the observation signals (signals.compute_signals — pure), and writes
one `run_id` snapshot into observation_signals
(infra/migrations/006_init_observation_signals.sql).

It MIRRORS the-loom/services/self-observer/main.py's shape — `--once` /
`--dry-run` argparse, one async pass, a counter summary — MINUS any candidate
emission. The self-observer emits candidates to architecture-registry; this
writes SIGNALS only (ADR-0001:27-29,42 — signals are evidence, not candidates).
Nothing here touches architecture-registry, the candidate path, or the-loom.

Run modes:
    python compute_signals.py            # one pass: compute + write a snapshot
    python compute_signals.py --once     # explicit one-pass (same as default)
    python compute_signals.py --dry-run  # compute + count + print; INSERT nothing
    python compute_signals.py --window-days 14   # override config.WINDOW_DAYS

It is an operator/cron command, so it may BLOCK and it FAILS LOUD: an
unresolved tenant or any DB error aborts with a nonzero exit and a message,
rather than silently writing nothing or a phantom-tenant snapshot.

## The single-transaction snapshot

The read of 005 and the write of 006 run inside ONE
`db.tenant_transaction(tenant_id)`, so the snapshot is atomic — a failed INSERT
rolls back the whole pass and nothing is half-written. One `run_id` and one
`computed_at` are generated for the whole pass (not left to 006's per-row
DEFAULT, which would vary across rows) so every row shares them.

## Fail-closed tenant

The tenant is resolved with `tenant.require_self_host_tenant()`, which raises
`TenantUnresolved` on the all-zeros nil tenant. This command REFUSES that case
(prints to stderr, exits nonzero) rather than reading/writing the nil tenant —
which would read "nothing" for every artifact and write signals into a phantom
tenant. This is the cron-side counterpart to the read route's 503 guard.

## Two-mode

Phase 1 resolves the self-host tenant only; hosted-multitenant is deferred
(tenant.py's docstring). db.py stays mode-agnostic — it only stamps
app.tenant_id — so when hosted read auth arrives this entrypoint is unaffected;
a hosted materialization pass would resolve its tenant differently and flow
through the same tenant_transaction + insert_signals unchanged.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
import uuid
from typing import Any, Mapping, Sequence

import config
import db
import signals
import tenant
import writes


# Exit codes (POSIX): 0 success, 1 unexpected failure (DB/etc.), 2 the
# fail-closed unresolved-tenant refusal (a distinct, expected operator error).
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_TENANT_UNRESOLVED = 2


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute observation signals over the 005 telemetry substrate and "
            "write one snapshot to observation_signals (one cron pass)."
        )
    )
    # --once is the default behavior (one pass); accepted for explicitness /
    # parity with self-observer and future cron wiring. There is no long-running
    # mode here — the command always does exactly one pass and exits.
    parser.add_argument(
        "--once",
        action="store_true",
        help="run exactly one pass and exit (the default behavior)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="compute + count + print what WOULD be written; INSERT nothing",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=config.WINDOW_DAYS,
        help=(
            "observation window in days to compute over "
            f"(default {config.WINDOW_DAYS} = config.WINDOW_DAYS)"
        ),
    )
    return parser.parse_args(argv)


def _kind_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Per-signal_kind counts for the summary, seeded with every kind so a
    kind that produced zero signals still prints as 0 (stable log shape)."""
    counts = {kind: 0 for kind in config.SIGNAL_KINDS}
    for r in records:
        counts[r["signal_kind"]] = counts.get(r["signal_kind"], 0) + 1
    return counts


async def run_once(
    *,
    window_days: int,
    subwindow_split: int,
    dry_run: bool,
) -> int:
    """One observation pass. Resolves the tenant fail-closed, then does the
    whole read + compute + write inside a SINGLE tenant_transaction. Returns a
    POSIX exit code. Closes the pool in a finally.
    """
    # Fail closed BEFORE opening the pool — refuse the nil tenant outright.
    try:
        tenant_id = tenant.require_self_host_tenant()
    except tenant.TenantUnresolved as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return EXIT_TENANT_UNRESOLVED

    # One run_id + one computed_at for the WHOLE snapshot — every row shares
    # them, rather than relying on 006's per-row computed_at DEFAULT (which
    # would vary across the rows of a single pass).
    run_id = str(uuid.uuid4())
    computed_at = time.time()

    try:
        # ONE transaction: the read of 005 and the write of 006 commit
        # atomically. A failed insert rolls back the whole pass — no
        # half-written snapshot. app.tenant_id == tenant_id, so 006's INSERT
        # WITH CHECK passes for every row.
        async with db.tenant_transaction(tenant_id) as conn:
            aggregates = await signals.load_aggregates(
                conn,
                window_days=window_days,
                subwindow_split=subwindow_split,
            )
            records = signals.compute_signals(aggregates, window_days=window_days)

            if dry_run:
                inserted = 0
            else:
                inserted = await writes.insert_signals(
                    conn,
                    records,
                    tenant_id=tenant_id,
                    run_id=run_id,
                    computed_at=computed_at,
                )
    finally:
        # Always drain the pool — this is a one-shot command, not a server.
        await db.close_pool()

    counts = _kind_counts(records)
    per_kind = " ".join(f"{kind}={counts[kind]}" for kind in config.SIGNAL_KINDS)
    print(
        "compute complete: "
        f"run_id={run_id} "
        f"dry_run={dry_run} "
        f"window_days={window_days} "
        f"aggregates={len(aggregates)} "
        f"signals={len(records)} "
        f"inserted={inserted} "
        f"[{per_kind}]"
    )
    if dry_run:
        print(f"(dry-run: {len(records)} signals computed, 0 written)")

    return EXIT_OK


async def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    # --window-days overrides config.WINDOW_DAYS; the sub-window split stays
    # config.SUBWINDOW_SPLIT (the degrading recent/earlier boundary).
    return await run_once(
        window_days=args.window_days,
        subwindow_split=config.SUBWINDOW_SPLIT,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
