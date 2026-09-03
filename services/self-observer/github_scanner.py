"""Walk platform-owned + registered repos via GitHub API. Yields one Entry per file.

Reads frontmatter + first ~100 lines of body. Computes description text used
by signal_rules.classify().

The list of repos to scan is passed IN (from registry_client.build_scan_targets
in production, or config.static_core_targets() for a discovery-free run) — this
module no longer owns the repo list. That is what makes the observer
registry-driven.

For a TRUE dry-run of the rules without GitHub access, see scan_local() which
reads from the local filesystem instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Iterator, Literal, Sequence

import httpx
import yaml

from config import EXCLUDE_PATH_PATTERNS, AuthConfig, RegistryTarget


def _is_excluded(file_path: str) -> bool:
    """Check whether a path matches any exclusion pattern."""
    normalized = file_path.replace("\\", "/")
    return any(pat in normalized for pat in EXCLUDE_PATH_PATTERNS)


Kind = Literal["skill", "agent", "inline_tool", "process"]


@dataclass
class Entry:
    """One scanned file (SKILL.md, agent .md, tool definition).

    Fields:
        repo: "Lizo-RoadTown/tapestry"
        file_path: relative path within the repo
        current_kind: where this file currently lives ("skill" if under skills/, etc.)
        frontmatter: parsed YAML frontmatter (name, description, etc.)
        body_excerpt: first ~100 lines of body text
        description: the field signal_rules consumes (frontmatter description + body excerpt)
        migration_destination: from frontmatter if present (used for skip-self check)
        project_id: architecture-registry project this entry's candidate belongs to
            (from the RegistryTarget; None → resolved to the platform default at emit).
    """

    repo: str
    file_path: str
    current_kind: Kind
    frontmatter: dict
    body_excerpt: str
    description: str
    migration_destination: str | None
    project_id: str | None = None


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_md(content: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Empty dict if no frontmatter."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    try:
        fm = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    if not isinstance(fm, dict):
        fm = {}
    return fm, match.group(2)


def _kind_from_path(file_path: str) -> Kind:
    """Infer current location kind from path.

    Convention: any file under skills/* is a skill; under agents/* is an agent;
    under tools/* is an inline_tool. Anything else defaults to skill.
    """
    parts = file_path.split("/")
    if "skills" in parts:
        return "skill"
    if "agents" in parts or "subagents" in parts:
        return "agent"
    if "tools" in parts:
        return "inline_tool"
    return "skill"


def _build_description(frontmatter: dict, body_excerpt: str) -> str:
    """Compose the text signal_rules consumes: frontmatter description + body."""
    fm_desc = frontmatter.get("description", "")
    return f"{fm_desc}\n\n{body_excerpt}"


def scan_local(
    local_root: Path, targets: Sequence[RegistryTarget]
) -> Iterator[Entry]:
    """Walk local filesystem instead of GitHub. Useful for tests + dry-run.

    Assumes layout: <local_root>/<repo_dir>/<paths_in_targets>/
    """
    for target in targets:
        repo_dir = target.repo.split("/")[-1]
        for sub_path in target.paths:
            full_dir = local_root / repo_dir / sub_path
            if not full_dir.is_dir():
                continue
            for md_path in full_dir.rglob("*.md"):
                rel = md_path.relative_to(local_root / repo_dir).as_posix()
                if _is_excluded(rel):
                    continue
                # Convention: <name>/SKILL.md is the entry for a skill dir.
                if md_path.name.lower() not in ("skill.md", "skill_idea.md"):
                    # For agent files (.md directly in agents/), accept any .md
                    if "agents" not in md_path.parts and "subagents" not in md_path.parts:
                        continue
                try:
                    content = md_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                fm, body = _parse_md(content)
                body_excerpt = "\n".join(body.splitlines()[:100])
                rel_path = md_path.relative_to(local_root / repo_dir).as_posix()
                yield Entry(
                    repo=target.repo,
                    file_path=rel_path,
                    current_kind=_kind_from_path(rel_path),
                    frontmatter=fm,
                    body_excerpt=body_excerpt,
                    description=_build_description(fm, body_excerpt),
                    migration_destination=fm.get("migration_destination"),
                    project_id=target.project_id,
                )


async def scan_github(
    auth: AuthConfig, targets: Sequence[RegistryTarget]
) -> AsyncIterator[Entry]:
    """Walk the given GitHub repos via the contents API.

    Sends `GITHUB_TOKEN` as a Bearer so PRIVATE consuming repos are readable.
    Absent → public-only scan at a lower rate limit. A repo/path that 403/404s
    (private repo the token can't see, or a path that doesn't exist) is logged
    and skipped — one bad repo never crashes the whole pass.
    """
    if not auth.github_token:
        print("INFO: GITHUB_TOKEN not set — scanning public repos only at low rate limit")

    headers = {"Accept": "application/vnd.github.v3+json"}
    if auth.github_token:
        headers["Authorization"] = f"Bearer {auth.github_token}"

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        for target in targets:
            for sub_path in target.paths:
                async for entry in _walk_path(client, target, sub_path):
                    yield entry


async def _walk_path(
    client: httpx.AsyncClient, target: RegistryTarget, sub_path: str
) -> AsyncIterator[Entry]:
    """Walk one path inside one repo, depth-first. Skips on any non-200."""
    url = (
        f"https://api.github.com/repos/{target.repo}/contents/{sub_path}"
        f"?ref={target.branch}"
    )
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        print(f"WARN: GitHub GET failed for {target.repo}/{sub_path}: {exc}")
        return
    if resp.status_code in (403, 404):
        # 404 = path/branch absent (common for the convention-based consuming
        # paths); 403 = private repo the token can't read or rate-limited.
        # Both are expected and non-fatal — skip this (repo, path).
        print(
            f"INFO: skip {target.repo}/{sub_path} @ {target.branch} "
            f"(GitHub {resp.status_code})"
        )
        return
    if resp.status_code != 200:
        print(
            f"WARN: GitHub {resp.status_code} for {target.repo}/{sub_path}: "
            f"{resp.text[:200]}"
        )
        return

    contents = resp.json()
    if not isinstance(contents, list):
        return

    for item in contents:
        if item["type"] == "dir":
            async for entry in _walk_path(client, target, item["path"]):
                yield entry
            continue
        if item["type"] != "file" or not item["name"].endswith(".md"):
            continue
        if _is_excluded(item["path"]):
            continue

        try:
            file_resp = await client.get(item["download_url"])
        except httpx.HTTPError:
            continue
        if file_resp.status_code != 200:
            continue

        fm, body = _parse_md(file_resp.text)
        body_excerpt = "\n".join(body.splitlines()[:100])
        yield Entry(
            repo=target.repo,
            file_path=item["path"],
            current_kind=_kind_from_path(item["path"]),
            frontmatter=fm,
            body_excerpt=body_excerpt,
            description=_build_description(fm, body_excerpt),
            migration_destination=fm.get("migration_destination"),
            project_id=target.project_id,
        )
