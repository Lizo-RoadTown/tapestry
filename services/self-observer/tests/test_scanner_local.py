"""Tests for github_scanner.scan_local target-threading + main-side self-skip
and project_id resolution.

scan_local is the discovery-free code path (used by --local smoke + these
tests). It proves the scanner now consumes an INJECTED target list (no static
REGISTRIES import) and carries project_id from the target onto every Entry.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SVC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SVC))

import main  # noqa: E402
import signal_rules  # noqa: E402
from config import RegistryTarget  # noqa: E402
from github_scanner import Entry, scan_local  # noqa: E402


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _make_repo(root: Path) -> RegistryTarget:
    """Lay out <root>/hub/skills/<name>/SKILL.md + agents/<name>.md."""
    _write(
        root / "hub" / "skills" / "documentation" / "SKILL.md",
        "---\nname: documentation\ndescription: Plan and write docs.\n---\nBody.\n",
    )
    _write(
        root / "hub" / "agents" / "planner.md",
        "---\nname: planner\ndescription: A helper.\n---\nBody.\n",
    )
    # excluded dir — must be skipped
    _write(
        root / "hub" / "skills" / "_upstream" / "vendored" / "SKILL.md",
        "---\nname: vendored\ndescription: vendored.\n---\nBody.\n",
    )
    return RegistryTarget(
        repo="Lizo-RoadTown/hub",
        paths=("skills", "agents"),
        project_id="proj-hub",
    )


def test_scan_local_threads_project_id_and_repo(tmp_path):
    target = _make_repo(tmp_path)
    entries = list(scan_local(tmp_path, [target]))
    assert entries, "expected entries from the fixture"
    for e in entries:
        assert e.repo == "Lizo-RoadTown/hub"
        assert e.project_id == "proj-hub"


def test_scan_local_honors_excludes(tmp_path):
    target = _make_repo(tmp_path)
    paths = {e.file_path for e in scan_local(tmp_path, [target])}
    assert not any("_upstream/" in p for p in paths), "vendored dir must be excluded"
    assert "skills/documentation/SKILL.md" in paths
    assert "agents/planner.md" in paths


def test_scan_local_empty_when_no_targets(tmp_path):
    _make_repo(tmp_path)
    assert list(scan_local(tmp_path, [])) == []


# ---------------------------------------------------------------------------
# main-side helpers
# ---------------------------------------------------------------------------


def _entry(**kw) -> Entry:
    base = dict(
        repo="Lizo-RoadTown/hub",
        file_path="skills/x/SKILL.md",
        current_kind="skill",
        frontmatter={"description": "d"},
        body_excerpt="b",
        description="d",
        migration_destination=None,
        project_id=None,
    )
    base.update(kw)
    return Entry(**base)  # type: ignore[arg-type]


def test_is_self_by_name_pattern():
    assert main._is_self(_entry(file_path="agents/agentic-upskilling.md"))
    assert main._is_self(_entry(file_path="services/self-observer/main.py"))
    assert not main._is_self(_entry(file_path="skills/documentation/SKILL.md"))


def test_is_self_by_migration_destination():
    assert main._is_self(
        _entry(migration_destination="tapestry/services/self-observer/config.py")
    )


def test_entry_to_candidate_uses_entry_project_id():
    verdict = signal_rules.Verdict(suggested_kind="agent", confidence=0.5, matched_rules=["r"])
    payload = main._entry_to_candidate(_entry(project_id="proj-hub"), verdict)
    assert payload.project_id == "proj-hub"


def test_entry_to_candidate_falls_back_to_default_project_id():
    verdict = signal_rules.Verdict(suggested_kind="agent", confidence=0.5, matched_rules=["r"])
    payload = main._entry_to_candidate(_entry(project_id=None), verdict)
    # default_project_id() returns a non-empty UUID string
    assert payload.project_id
    assert payload.project_id != ""
