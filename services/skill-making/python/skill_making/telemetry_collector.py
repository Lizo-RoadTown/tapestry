"""In-process telemetry collector for skill invocations.

Sits between the agent loop and `telemetry_sender.send_telemetry_batch`:

- `record_event(event)`  — sync, non-blocking. Enqueues a TelemetryEvent
  from inside the agent runtime's `compile_skill_to_tool._run` wrapper.
- Background flusher drains the queue, batches events, and POSTs each
  batch to the-loom's telemetry-ingestion via the configured sender.
- Flush triggers: BATCH_SIZE events queued, OR FLUSH_INTERVAL_SECONDS
  elapsed since last flush. Whichever fires first.
- Shutdown drains remaining events with a bounded grace window so the
  FastAPI worker can stop without dropping in-flight telemetry.

Per the canonical wire contract (`services/skill_making/models.py`):
  - TelemetryEvent carries SOURCE-side `tenant_id` (the loom's UUID),
    NOT the engine-side UUID. Reverse-lookup happens at agent build
    time via `tenant_mapping.lookup_source_tenant`.
  - Privacy: structural metadata only — `skill_id`, `tenant_id` (opaque),
    `outcome`, `latency_ms`, token counts. Enforced by pydantic
    `extra='forbid'` on TelemetryEvent itself.

This module is intentionally simple (in-process queue + background
task). If the FastAPI worker crashes mid-batch, events buffered in
memory are lost — acceptable for v0 since the engine state of record
is `student_skills` + `promoted_skills` rows; telemetry is observation
metadata, not durable business data. A future PR could swap the
in-process queue for a Postgres-backed durable queue if loss matters.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from skill_making.telemetry_sender import (
    TelemetryBatch,
    TelemetrySendError,
    send_telemetry_batch,
)

log = logging.getLogger("skill_making.telemetry_collector")

# Tuning. The wire spec allows up to 1000 events per request flushed
# every 10s; we use smaller numbers here so the first batches land
# quickly during real-use validation (PR-prep-1's purpose is data flow,
# not throughput).
BATCH_SIZE = 100
FLUSH_INTERVAL_SECONDS = 10.0

# Hard cap on queue depth. If the producer (agent loop) outpaces the
# consumer (this flusher), oldest events are dropped to bound memory
# rather than block the agent's response. A bounded queue is the
# defensive default; raising this is cheap if telemetry volume warrants.
MAX_QUEUE_DEPTH = 10_000

# Shutdown grace: how long to wait for the in-flight queue to drain
# during FastAPI lifespan shutdown before giving up.
SHUTDOWN_GRACE_SECONDS = 5.0


class _Collector:
    """Singleton-style collector. Module-level helpers below wrap it."""

    def __init__(self):
        # Lazy-create the queue inside the running loop; constructing
        # asyncio primitives at import time binds them to whichever loop
        # is "current" then, which may not be FastAPI's.
        self._queue: Optional[asyncio.Queue] = None
        self._flusher_task: Optional[asyncio.Task] = None
        self._stopped = False

    async def start(self) -> None:
        """Start the background flusher. Idempotent — calling twice is
        a no-op so re-entry from lifespan or tests is safe."""
        if self._flusher_task is not None and not self._flusher_task.done():
            return
        self._queue = asyncio.Queue(maxsize=MAX_QUEUE_DEPTH)
        self._stopped = False
        self._flusher_task = asyncio.create_task(self._flush_loop())
        log.info(
            "telemetry collector started (batch_size=%d, flush_interval=%.1fs, "
            "max_queue_depth=%d)",
            BATCH_SIZE, FLUSH_INTERVAL_SECONDS, MAX_QUEUE_DEPTH,
        )

    async def stop(self) -> None:
        """Signal the flusher to drain and exit. Waits up to
        SHUTDOWN_GRACE_SECONDS for the queue to empty."""
        if self._flusher_task is None:
            return
        self._stopped = True
        # The flusher checks _stopped at each iteration; the get() call
        # uses a short timeout so the loop exits even if no events arrive.
        try:
            await asyncio.wait_for(
                self._flusher_task, timeout=SHUTDOWN_GRACE_SECONDS,
            )
        except asyncio.TimeoutError:
            log.warning(
                "telemetry collector did not finish draining in %.1fs; "
                "%d events may be lost",
                SHUTDOWN_GRACE_SECONDS,
                self._queue.qsize() if self._queue is not None else -1,
            )
            self._flusher_task.cancel()
        self._flusher_task = None
        self._queue = None

    def enqueue(self, event) -> bool:
        """Add a TelemetryEvent to the queue.

        Returns True on success, False if the queue is full or the
        collector hasn't started. Non-blocking — callers (the agent
        loop) must not be stalled by telemetry overflow.
        """
        if self._queue is None:
            return False
        try:
            self._queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            log.warning(
                "telemetry queue full at depth=%d; dropping event for "
                "skill_id=%s", MAX_QUEUE_DEPTH, getattr(event, "skill_id", "?"),
            )
            return False

    async def _flush_loop(self) -> None:
        """Drain the queue into batches, send via send_telemetry_batch.

        Inner wait_for is capped at WAKE_INTERVAL so the loop re-checks
        `_stopped` frequently — this is what makes the SHUTDOWN_GRACE
        window honored (without it, an in-flight `wait_for` could block
        for up to FLUSH_INTERVAL_SECONDS past the stop signal).
        """
        assert self._queue is not None
        # Slice for the wait_for so _stopped gets re-checked at this
        # cadence. Small enough that SHUTDOWN_GRACE bounds the worst-case
        # tail; large enough not to busy-poll in the steady state.
        WAKE_INTERVAL = 0.25

        while True:
            buffer = []
            deadline = asyncio.get_running_loop().time() + FLUSH_INTERVAL_SECONDS

            # Fill the buffer up to BATCH_SIZE or until FLUSH_INTERVAL elapses.
            while len(buffer) < BATCH_SIZE:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                slice_timeout = min(WAKE_INTERVAL, remaining)
                try:
                    event = await asyncio.wait_for(
                        self._queue.get(), timeout=slice_timeout,
                    )
                    buffer.append(event)
                except asyncio.TimeoutError:
                    # No event arrived in this slice. If stopped, flush
                    # whatever we have + exit. Otherwise loop and try
                    # again until the outer deadline.
                    if self._stopped:
                        break

            if buffer:
                await self._send_batch_with_error_swallow(buffer)
            elif self._stopped:
                # Empty queue + stop signal → done.
                return

            if self._stopped and self._queue.empty():
                return

    async def _send_batch_with_error_swallow(self, events) -> None:
        """Send a batch. Log on failure; do NOT re-queue (avoids tight
        retry loops if loom-side is down). The retry inside
        send_telemetry_batch already handles transient blips."""
        try:
            batch = TelemetryBatch(events=events)
            await send_telemetry_batch(batch)
        except TelemetrySendError as e:
            log.error(
                "telemetry batch send failed (events=%d); dropping batch: %s",
                len(events), e,
            )
        except Exception:
            log.exception(
                "telemetry batch send raised unexpectedly (events=%d); "
                "dropping batch", len(events),
            )


# Module-level singleton. Imported once by main.py lifespan + the
# compiler's _run wrapper.
_collector = _Collector()


async def start_collector() -> None:
    """Lifespan startup hook. Idempotent."""
    await _collector.start()


async def stop_collector() -> None:
    """Lifespan shutdown hook. Drains queue (bounded by
    SHUTDOWN_GRACE_SECONDS) then exits."""
    await _collector.stop()


def record_event(event) -> bool:
    """Non-blocking enqueue. Returns False if the collector isn't
    running OR the queue is full; True on success.

    Called from compile_skill_to_tool's _run wrapper after every skill
    invocation. MUST NOT raise — telemetry failures can never block the
    agent's response.
    """
    return _collector.enqueue(event)
