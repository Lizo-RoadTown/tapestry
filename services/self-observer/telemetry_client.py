"""Read invocation counts from project-observatory / telemetry-ingestion.

v1 STUB: the observatory read-side query API this would call is not wired yet.

This module returns None for every query in v1. Once project-observatory's read
API exists (services/project-observatory/), swap the stub for the real call.
Signal-rules already handle None gracefully (treats as "telemetry unavailable,
don't emit orphan candidates").
"""
from __future__ import annotations

from config import Endpoints


class TelemetryClient:
    """Reads invocation counts. v1 = stub returning None."""

    def __init__(self, endpoints: Endpoints):
        self.endpoints = endpoints

    async def invocations_30d(self, repo: str, file_path: str) -> int | None:
        """Return invocation count over last 30 days for an entry.

        Returns:
            None if telemetry unavailable (v1 default).
            int if observatory's read API is wired (future).

        When this returns 0, signal_rules emits a `process` candidate
        suggesting archive. So returning None (not 0) is the safe default
        — won't trigger false orphan detection until telemetry is real.
        """
        # TODO(post-v1): swap for real query against telemetry_query_url
        # once project-observatory exposes /metrics or /query endpoints.
        return None
