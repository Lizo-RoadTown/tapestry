"""self-observer entrypoint.

Run modes:
    python main.py                 # production: discover targets, scan via GitHub, emit
    python main.py --once          # same but exit after one scan (cron default)
    python main.py --dry-run       # scan + log candidates without POSTing
    python main.py --no-discovery  # skip project-registry discovery; static core only
    python main.py --local <root>  # scan local filesystem instead of GitHub
                                   # (used by smoke + unit testing the scanner)

Scan targets are STATIC CORE (config.static_core_targets) + every repo
registered in the project-registry (registry_client.build_scan_targets). The
repo list is dynamic; everything else (weights, threshold, excludes, skip-self,
scanned paths) stays config-driven.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator, Iterator

import config
import registry_client
import signal_rules
import synthesis
from candidate_client import CandidateClient, CandidatePayload
from config import AuthConfig, Endpoints, RegistryTarget, static_core_targets
from github_scanner import Entry, scan_github, scan_local
from memory_client import MemoryClient
from telemetry_client import TelemetryClient


# Self-exclusion: don't emit candidates for the observer's own files.
_SELF_MIGRATION_DESTINATIONS = {
    "tapestry/services/self-observer/",
    "tapestry/engine/agents/agentic-upskilling.md",
    "integrations/claude-code/tapestry-patterns/agents/agentic-upskilling",
}

# Belt-and-suspenders: name patterns identifying observer-owned files. Survives
# the case where source files don't have migration_destination frontmatter yet.
_SELF_NAME_PATTERNS = (
    "agentic-upskilling",
    "self-observer",
)


def _is_self(entry: Entry) -> bool:
    """Skip the observer's own files (canonical migration_destination OR name)."""
    dest = entry.migration_destination or ""
    if any(dest.startswith(p.rstrip("/")) for p in _SELF_MIGRATION_DESTINATIONS):
        return True
    file_path_lower = entry.file_path.lower()
    return any(pat in file_path_lower for pat in _SELF_NAME_PATTERNS)


def _entry_to_candidate(entry: Entry, verdict: signal_rules.Verdict) -> CandidatePayload:
    """Translate an Entry + Verdict into the CandidatePayload schema."""
    instance_id = f"{entry.repo}/{entry.file_path}"
    if len(instance_id) > 128:  # instance_id caps at 128 chars
        instance_id = instance_id[:128]
    return CandidatePayload(
        project_id=config.project_id_for(entry.project_id),
        source_path="path_b",
        candidate_type=verdict.suggested_kind,
        instance_id=instance_id,
        evidence_refs=[
            {
                "kind": "self_observation",
                "source_repo": entry.repo,
                "file_path": entry.file_path,
                "description_text": entry.frontmatter.get("description", ""),
                "signal_match": ",".join(verdict.matched_rules),
                "current_kind": entry.current_kind,
            }
        ],
        signals={
            "confidence": verdict.confidence,
            "matched_rules": verdict.matched_rules,
            "reasons": verdict.reasons,
        },
    )


async def _run_once_async(
    entries_source: AsyncIterator[Entry] | Iterator[Entry],
    client: CandidateClient,
    telemetry: TelemetryClient,
    dry_run: bool,
) -> dict[str, int]:
    """One scan pass. Returns counters for the log."""
    counters = {"scanned": 0, "skipped_self": 0, "skipped_dedup": 0, "emitted": 0}

    # Preload open-candidate dedup set (skipped in dry-run; one less GET)
    if not dry_run:
        open_hashes = await client.fetch_open_candidates()
        client.preload_dedup(open_hashes)

    async def _iterate():
        if hasattr(entries_source, "__anext__"):
            async for e in entries_source:  # type: ignore[union-attr]
                yield e
        else:
            for e in entries_source:  # type: ignore[union-attr]
                yield e

    async for entry in _iterate():
        counters["scanned"] += 1

        if _is_self(entry):
            counters["skipped_self"] += 1
            continue

        invocations = await telemetry.invocations_30d(entry.repo, entry.file_path)
        verdict = signal_rules.classify(
            description=entry.description,
            current_location_kind=entry.current_kind,
            invocations_30d=invocations,
        )

        if not verdict.should_emit:
            continue

        payload = _entry_to_candidate(entry, verdict)
        was_emitted = await client.emit(payload, dry_run=dry_run)
        if was_emitted:
            counters["emitted"] += 1
        else:
            counters["skipped_dedup"] += 1

    return counters


async def _resolve_targets(
    endpoints: Endpoints, auth: AuthConfig, *, discover: bool
) -> list[RegistryTarget]:
    """Static core, optionally merged with project-registry discovery."""
    if not discover:
        return list(static_core_targets())
    return await registry_client.build_scan_targets(endpoints, auth)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="self-observer scan")
    parser.add_argument("--once", action="store_true", help="exit after one scan")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="log candidates without POSTing to architecture-registry",
    )
    parser.add_argument(
        "--no-discovery",
        action="store_true",
        help="skip project-registry discovery; scan the static core only",
    )
    parser.add_argument(
        "--local",
        type=str,
        default=None,
        help="scan local filesystem root instead of GitHub (for testing)",
    )
    args = parser.parse_args(argv)

    endpoints = Endpoints.from_env()
    auth = AuthConfig.from_env()
    client = CandidateClient(endpoints, auth)
    telemetry = TelemetryClient(endpoints)

    if args.local:
        # Local scans read the filesystem; discovery targets remote repos, so
        # local mode uses the static core layout only.
        targets = list(static_core_targets())
        print(f"scanning {len(targets)} static-core target repo(s) from local root")
        entries_source: Iterator[Entry] | AsyncIterator[Entry] = scan_local(
            Path(args.local), targets
        )
    else:
        targets = asyncio.run(
            _resolve_targets(endpoints, auth, discover=not args.no_discovery)
        )
        print(
            f"scanning {len(targets)} target repo(s): "
            f"{', '.join(t.repo for t in targets)}"
        )
        entries_source = scan_github(auth, targets)

    counters = asyncio.run(
        _run_once_async(entries_source, client, telemetry, dry_run=args.dry_run)
    )

    print(
        f"scan complete: scanned={counters['scanned']} "
        f"emitted={counters['emitted']} "
        f"skipped_self={counters['skipped_self']} "
        f"skipped_dedup={counters['skipped_dedup']}"
    )

    # Synthesis-memo write. Skipped in dry-run (no candidates posted). Failure
    # is logged + absorbed; the scan run already succeeded.
    if not args.dry_run:
        memory_client = MemoryClient(endpoints, auth)
        try:
            asyncio.run(
                synthesis.build_and_write_synthesis(
                    memory_client=memory_client,
                    endpoints=endpoints,
                    auth=auth,
                    run_counters=counters,
                )
            )
        except Exception as exc:  # noqa: BLE001 — best-effort; scan already succeeded
            print(f"WARN: synthesis-memo write failed: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
