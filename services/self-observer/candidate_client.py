"""Client for POSTing candidates to the architecture-registry.

Wire contract: architecture-registry models.CandidateCreate (POSTed over HTTP;
the observer depends on the deployed service by URL, not on its source).
Auth pattern: JWT Bearer / self-host per auth_bridge.verify_bearer.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import httpx

from config import AuthConfig, Endpoints


@dataclass
class CandidatePayload:
    """Payload matching models.CandidateCreate.

    Field semantics (architecture-registry models.CandidateCreate):
        project_id: REQUIRED UUID. The project this candidate belongs to.
        source_path: "path_b" for platform-observatory observations.
            The "this came from self-observer" detail rides in evidence_refs.
        candidate_type: one of 9 taxonomy values per models.py:32-42 ("what this may become").
            NOTE: candidate_type=process today encodes ORPHAN — semantic placeholder
            until Tapestry observation_kind lands (§3.2 of 2026-06-18 review).
        instance_id: str, max 128 (models.py:66). Convention: f"{repo}/{file_path}", truncated.
        evidence_refs: array of evidence dicts. Each has {kind, source_repo, file_path, ...}.
        signals: confidence + matched_rules from signal_rules.
    """

    project_id: str
    source_path: str
    candidate_type: str
    instance_id: str
    evidence_refs: list[dict[str, Any]]
    signals: dict[str, Any]

    def content_hash(self) -> str:
        """Identity key for dedup.

        Includes source_repo as a discriminator so cross-repo entries with
        the same description but divergent bodies (e.g., docs-agent
        `roadmap-maintenance` skill vs Make_Skills/skills_private/
        `roadmap-maintenance` methodology) stay separate. MS-agent flagged
        this case at `ms_agent_to_loom_agent_self_observer_responses_2026_06_13` §1.

        Within the same repo, identical description+kind dedups (which is
        the intended behavior for re-scans of the same file).
        """
        descriptive = {
            "candidate_type": self.candidate_type,
            "source_repo": next(
                (e.get("source_repo", "") for e in self.evidence_refs),
                "",
            ),
            "evidence_text": next(
                (e.get("description_text", "") for e in self.evidence_refs),
                "",
            ),
        }
        return hashlib.sha256(
            json.dumps(descriptive, sort_keys=True).encode()
        ).hexdigest()[:16]


class CandidateClient:
    """POSTs candidates to architecture-registry. Holds the open-candidates dedup set."""

    def __init__(self, endpoints: Endpoints, auth: AuthConfig):
        self.endpoints = endpoints
        self.auth = auth
        # In-memory dedup set per scan run. Rebuilds each fire.
        self._seen_hashes: set[str] = set()

    def _headers(self) -> dict[str, str]:
        """Auth header. Self-host mode (no JWT) returns empty -- endpoint
        resolves to SELF_HOST_TENANT_ID per auth_bridge.verify_bearer:81-100."""
        headers = {"Content-Type": "application/json"}
        if self.auth.observer_jwt:
            headers["Authorization"] = f"Bearer {self.auth.observer_jwt}"
        return headers

    async def fetch_open_candidates(self) -> set[str]:
        """Pre-load existing open candidates' content hashes for dedup.

        Reads via GET /candidates (no trailing slash — endpoint redirects 307
        from /candidates/ to /candidates; explicit form avoids the round-trip).
        """
        url = f"{self.endpoints.candidate_registry_url}/candidates"
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(
                url, headers=self._headers(), params={"status": "open"}
            )
            if resp.status_code != 200:
                # Soft-fail: if we can't fetch open candidates, proceed without dedup.
                # Better to emit dupes than to fail the entire run.
                return set()
            data = resp.json()
            hashes: set[str] = set()
            for cand in data.get("candidates", []):
                # Reconstruct hash from the same fields content_hash() uses
                # (candidate_type + source_repo + description_text). Must match
                # the live hash function or dedup breaks.
                evidence_refs = cand.get("evidence_refs", [])
                descriptive = {
                    "candidate_type": cand.get("candidate_type"),
                    "source_repo": next(
                        (e.get("source_repo", "") for e in evidence_refs),
                        "",
                    ),
                    "evidence_text": next(
                        (e.get("description_text", "") for e in evidence_refs),
                        "",
                    ),
                }
                h = hashlib.sha256(
                    json.dumps(descriptive, sort_keys=True).encode()
                ).hexdigest()[:16]
                hashes.add(h)
            return hashes

    async def emit(self, payload: CandidatePayload, dry_run: bool = False) -> bool:
        """Emit a candidate. Returns True if posted, False if deduped or dry-run.

        Skip rules:
            1. Content hash already in this run's seen set
            2. Content hash present in pre-loaded open candidates
            3. dry_run mode (print only)
        """
        h = payload.content_hash()
        if h in self._seen_hashes:
            return False
        self._seen_hashes.add(h)

        body = {
            "project_id": payload.project_id,
            "source_path": payload.source_path,
            "candidate_type": payload.candidate_type,
            "instance_id": payload.instance_id,
            "evidence_refs": payload.evidence_refs,
            "signals": payload.signals,
        }

        if dry_run:
            print(f"[dry-run] would POST candidate:\n{json.dumps(body, indent=2)}\n")
            return False

        url = f"{self.endpoints.candidate_registry_url}/candidates"
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.post(url, headers=self._headers(), json=body)
            if resp.status_code >= 400:
                # Log and continue. One bad payload shouldn't kill the entire run.
                print(
                    f"WARN: candidate POST failed {resp.status_code}: {resp.text[:300]}"
                )
                return False
            return True

    def preload_dedup(self, hashes: set[str]) -> None:
        """Seed dedup set with hashes from previously-open candidates."""
        self._seen_hashes.update(hashes)
