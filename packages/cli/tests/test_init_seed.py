"""Tests for tapestry_cli.init seed helpers (0.1.5 full-skeleton redesign).

Run from packages/cli/:  python -m pytest tests/ -q
These test the pure file-writing helpers directly; they do NOT hit the network
(the registry calls are not exercised here).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tapestry_cli import init  # noqa: E402


# ---------------------------------------------------------------------------
# _write_env_file — LOOM_PROJECT_ID + OTel from env, no the-loom dependency
# ---------------------------------------------------------------------------


def test_env_file_writes_project_id_and_sources_otel_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp.example/v1")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_HEADERS", raising=False)
    init._write_env_file(tmp_path, "demo-proj")
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "LOOM_PROJECT_ID=demo-proj" in env
    # set var is written as a real line
    assert "OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.example/v1" in env
    # unset var is written as a commented placeholder, never a bare/blank secret
    assert "# OTEL_EXPORTER_OTLP_HEADERS=" in env


def test_env_file_all_placeholders_when_no_otel_in_env(tmp_path, monkeypatch):
    for k in init._OTEL_KEYS:
        monkeypatch.delenv(k, raising=False)
    init._write_env_file(tmp_path, "p")
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    for k in init._OTEL_KEYS:
        assert f"# {k}=" in env


def test_env_file_does_not_overwrite(tmp_path):
    (tmp_path / ".env").write_text("PRE=existing\n", encoding="utf-8")
    init._write_env_file(tmp_path, "p")
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "PRE=existing\n"


def test_no_the_loom_reader_remains():
    # the the-loom coupling was removed
    assert not hasattr(init, "_read_loom_env")


# ---------------------------------------------------------------------------
# _write_project_skeleton — full skeleton, idempotent, no secrets
# ---------------------------------------------------------------------------

_EXPECTED = [
    "CLAUDE.md",
    ".gitignore",
    "docs/architecture-snapshots/.gitkeep",
    "docs/architecture/README.md",
    "docs/adr/README.md",
    "skills/README.md",
]


def test_skeleton_creates_all_expected_files(tmp_path):
    init._write_project_skeleton(tmp_path, "demo-proj", "Demo Project", "A demo repo.")
    for rel in _EXPECTED:
        assert (tmp_path / rel).exists(), f"missing {rel}"


def test_claude_md_is_parameterized_and_inlines_directive_1(tmp_path):
    init._write_project_skeleton(tmp_path, "demo-proj", "Demo Project", "A demo repo.")
    claude = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "demo-proj" in claude
    assert "Demo Project" in claude
    assert "A demo repo." in claude
    assert "CORE DIRECTIVE 1" in claude  # inlined, not referenced


def test_gitignore_has_env_and_snapshot_block(tmp_path):
    init._write_project_skeleton(tmp_path, "p", "P", "")
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "\n.env\n" in "\n" + gi + "\n"
    assert "docs/architecture-snapshots/*" in gi
    assert "!docs/architecture-snapshots/.gitkeep" in gi


def test_gitignore_appends_missing_lines_without_clobber(tmp_path):
    (tmp_path / ".gitignore").write_text("customrule/\n", encoding="utf-8")
    init._write_project_skeleton(tmp_path, "p", "P", "")
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "customrule/" in gi  # preserved
    assert ".env" in gi  # appended


def test_skeleton_is_idempotent(tmp_path):
    init._write_project_skeleton(tmp_path, "p", "P", "desc")
    claude_before = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    # hand-edit CLAUDE.md, then re-run — must NOT overwrite
    (tmp_path / "CLAUDE.md").write_text("EDITED BY HAND\n", encoding="utf-8")
    init._write_project_skeleton(tmp_path, "p", "P", "desc")
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "EDITED BY HAND\n"
    # and gitignore doesn't duplicate lines on re-run
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert gi.count("docs/architecture-snapshots/*") == 1


def test_skills_readme_distinguishes_three_homes(tmp_path):
    init._write_project_skeleton(tmp_path, "p", "P", "")
    readme = (tmp_path / "skills" / "README.md").read_text(encoding="utf-8")
    assert ".project-intelligence/local-skills/" in readme
    assert "tapestry-patterns" in readme


def test_no_secret_literal_in_seeded_files(tmp_path):
    init._write_project_skeleton(tmp_path, "p", "P", "")
    # the .mcp.json header references the env var by NAME; the skeleton itself
    # must never embed a literal key. Sanity: no obvious secret prefixes.
    for rel in _EXPECTED:
        text = (tmp_path / rel).read_text(encoding="utf-8")
        assert "rnd_" not in text
        assert "Bearer eyJ" not in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
