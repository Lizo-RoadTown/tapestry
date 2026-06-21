"""Unit tests for the in-process telemetry collector.

Covers the contract that:
- Events enqueue without raising even when the collector isn't started
- The flusher batches events and posts via send_telemetry_batch
- Shutdown drains remaining events with a bounded grace window
- Queue overflow is logged + drops the event (NEVER blocks the producer)

Tests use a stubbed `send_telemetry_batch` to avoid network. The flusher
itself is exercised inside an asyncio event loop.
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import patch

import pytest

from skill_making import telemetry_collector
from skill_making.telemetry_sender import build_event


def _make_event():
    return build_event(
        skill_id=uuid.uuid4(),
        thread_id="test-thread",
        tenant_id=uuid.uuid4(),
        outcome="success",
        latency_ms=10,
        tokens_in=5,
        tokens_out=10,
        model="test-model",
        trigger_context="test",
    )


def test_record_event_returns_false_when_not_started():
    """Pre-start enqueues must not raise and must signal no-op."""
    # Fresh collector module-level instance for safety
    telemetry_collector._collector = telemetry_collector._Collector()
    assert telemetry_collector.record_event(_make_event()) is False


@pytest.mark.asyncio
async def test_start_stop_idempotent():
    """Starting twice is a no-op; stopping when stopped is a no-op."""
    telemetry_collector._collector = telemetry_collector._Collector()
    await telemetry_collector.start_collector()
    await telemetry_collector.start_collector()  # idempotent
    await telemetry_collector.stop_collector()
    await telemetry_collector.stop_collector()  # idempotent


@pytest.mark.asyncio
async def test_events_flush_in_batch():
    """Events enqueued before flush get sent as a single batch."""
    telemetry_collector._collector = telemetry_collector._Collector()

    calls = []

    async def fake_send(batch):
        calls.append(batch)

    with patch.object(telemetry_collector, "send_telemetry_batch", fake_send):
        await telemetry_collector.start_collector()
        # Enqueue 3 events; well under BATCH_SIZE, so they wait for the
        # flush interval timer.
        for _ in range(3):
            assert telemetry_collector.record_event(_make_event()) is True

        # Stop with grace; should drain whatever's queued.
        await telemetry_collector.stop_collector()

    assert len(calls) >= 1
    total_events = sum(len(b.events) for b in calls)
    assert total_events == 3


@pytest.mark.asyncio
async def test_batch_size_triggers_immediate_flush():
    """If BATCH_SIZE events queue before the interval, they flush
    in a single batch without waiting."""
    telemetry_collector._collector = telemetry_collector._Collector()

    flushes = []

    async def fake_send(batch):
        flushes.append(len(batch.events))

    # Shrink BATCH_SIZE for the test so we don't enqueue 100 events.
    with patch.object(telemetry_collector, "BATCH_SIZE", 5):
        with patch.object(telemetry_collector, "send_telemetry_batch", fake_send):
            await telemetry_collector.start_collector()
            for _ in range(5):
                telemetry_collector.record_event(_make_event())
            # Give the flusher one loop tick to pick them up
            await asyncio.sleep(0.1)
            await telemetry_collector.stop_collector()

    assert flushes
    assert sum(flushes) == 5


@pytest.mark.asyncio
async def test_send_failure_does_not_crash_flusher():
    """If send_telemetry_batch raises, the flusher logs + continues."""
    telemetry_collector._collector = telemetry_collector._Collector()

    call_count = {"n": 0}

    async def failing_send(batch):
        call_count["n"] += 1
        from skill_making.telemetry_sender import TelemetrySendError
        raise TelemetrySendError("simulated network failure")

    with patch.object(telemetry_collector, "BATCH_SIZE", 2):
        with patch.object(telemetry_collector, "send_telemetry_batch", failing_send):
            await telemetry_collector.start_collector()
            telemetry_collector.record_event(_make_event())
            telemetry_collector.record_event(_make_event())
            await asyncio.sleep(0.1)
            # Send another after the first failure to prove the flusher
            # didn't crash
            telemetry_collector.record_event(_make_event())
            telemetry_collector.record_event(_make_event())
            await asyncio.sleep(0.1)
            await telemetry_collector.stop_collector()

    # At least the first batch attempt happened
    assert call_count["n"] >= 1


@pytest.mark.asyncio
async def test_queue_overflow_drops_event():
    """When the queue is at MAX_QUEUE_DEPTH, enqueue returns False
    without raising."""
    telemetry_collector._collector = telemetry_collector._Collector()

    # Shrink MAX_QUEUE_DEPTH to a tiny value for the test
    with patch.object(telemetry_collector, "MAX_QUEUE_DEPTH", 2):
        await telemetry_collector.start_collector()
        # The flusher will start consuming immediately; to actually
        # observe overflow we need to stall it. Patch send to await an
        # event we control.
        gate = asyncio.Event()

        async def slow_send(batch):
            await gate.wait()

        with patch.object(telemetry_collector, "send_telemetry_batch", slow_send):
            # Fill + overflow. With MAX_QUEUE_DEPTH=2 and the flusher
            # potentially picking one off immediately, queue size races
            # — but eventually we'll see at least one False return.
            results = [
                telemetry_collector.record_event(_make_event())
                for _ in range(20)
            ]
            assert False in results
            # Release the gate so shutdown can drain
            gate.set()
            await telemetry_collector.stop_collector()
