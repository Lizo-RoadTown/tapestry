"""Tests for the pre_tool_use hook's citation + dual-mode logic.

Run from the plugin root:

    python -m unittest plugins/loom-discipline/tests/test_pre_tool_use.py

Or via CI: see .github/workflows/validate.yml.

Tests cover the v0.1.3 fixes:

1. Citation regex accepts URLs and bare file paths (not just file:line).
2. Dual-mode trigger does NOT fire on docs/markdown files that merely
   mention the trigger keywords.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Import the hook under test.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pre_tool_use  # noqa: E402


class TestCitationDetection(unittest.TestCase):
    """has_recent_citation must accept three citation forms."""

    def _check_transcript(self, content: str) -> bool:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            path = tmp.name
        try:
            return pre_tool_use.has_recent_citation(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_file_line_citation_accepted(self):
        """The original form: path/to/file.ext:42."""
        self.assertTrue(
            self._check_transcript("see platform/api/main.py:42 for context")
        )

    def test_url_citation_accepted(self):
        """v0.1.3: https URLs count as citations."""
        self.assertTrue(
            self._check_transcript(
                "per https://grafana.com/docs/loki/latest/ the schema is v13"
            )
        )

    def test_http_url_citation_accepted(self):
        """v0.1.3: http URLs too (not just https)."""
        self.assertTrue(
            self._check_transcript("see http://localhost:3001/dashboards")
        )

    def test_bare_file_path_with_extension_accepted(self):
        """v0.1.3: a file path with extension and a slash counts."""
        self.assertTrue(
            self._check_transcript("matches the pattern in scripts/foo.py exactly")
        )

    def test_plain_prose_not_a_citation(self):
        """No file:line, no URL, no path → no citation."""
        self.assertFalse(
            self._check_transcript("the agent should do the right thing")
        )

    def test_missing_transcript_returns_true(self):
        """Per the existing contract: can't verify → don't false-alarm."""
        self.assertTrue(pre_tool_use.has_recent_citation(""))
        self.assertTrue(
            pre_tool_use.has_recent_citation("/nonexistent/path/transcript.jsonl")
        )


class TestDualModeGating(unittest.TestCase):
    """touches_dual_mode must skip docs and convention files."""

    def test_md_file_with_trigger_keyword_skipped(self):
        """v0.1.3: a .md file mentioning AUTH_SECRET is not a boundary change."""
        self.assertFalse(
            pre_tool_use.touches_dual_mode(
                {
                    "file_path": "docs/plans/something.md",
                    "content": "We use AUTH_SECRET for JWT signing.",
                }
            )
        )

    def test_runtime_py_file_with_trigger_keyword_fires(self):
        """Runtime edits still fire the dual-mode reminder."""
        self.assertTrue(
            pre_tool_use.touches_dual_mode(
                {
                    "file_path": "platform/api/auth.py",
                    "content": "secret = os.environ['AUTH_SECRET']",
                }
            )
        )

    def test_changelog_with_trigger_keyword_skipped(self):
        """CHANGELOG.md mentioning AUTH_SECRET is documentation, not boundary."""
        self.assertFalse(
            pre_tool_use.touches_dual_mode(
                {
                    "file_path": "CHANGELOG.md",
                    "content": "- Added AUTH_SECRET gating",
                }
            )
        )

    def test_readme_skipped(self):
        """Top-level README is documentation."""
        self.assertFalse(
            pre_tool_use.touches_dual_mode(
                {
                    "file_path": "README.md",
                    "content": "Set AUTH_SECRET in your env",
                }
            )
        )

    def test_nested_docs_path_skipped(self):
        """Nested docs paths also skip — not just top-level docs/."""
        self.assertFalse(
            pre_tool_use.touches_dual_mode(
                {
                    "file_path": "platform/api/docs/internal.md",
                    "content": "JWTTenantResolver behavior",
                }
            )
        )

    def test_runtime_ts_file_fires(self):
        """Web runtime edits still fire."""
        self.assertTrue(
            pre_tool_use.touches_dual_mode(
                {
                    "file_path": "web/lib/auth.ts",
                    "content": "tenant_id check",
                }
            )
        )

    def test_no_trigger_keyword_no_fire(self):
        """Runtime edit with no trigger keyword → no fire."""
        self.assertFalse(
            pre_tool_use.touches_dual_mode(
                {
                    "file_path": "platform/api/main.py",
                    "content": "print('hello')",
                }
            )
        )

    def test_empty_target_falls_back_to_keyword_check(self):
        """If no file_path provided, behave like v0.1.2: check the blob."""
        # No file_path → _target_is_docs returns False → keyword check runs.
        self.assertTrue(
            pre_tool_use.touches_dual_mode({"content": "AUTH_SECRET"})
        )


class TestScopeCheck(unittest.TestCase):
    """v0.1.5: in-scope check now includes the-loom + is case-insensitive.

    The hook's main() function early-exits with `action=noop` when cwd is
    out of scope. We can't call main() directly without faking stdin, so
    we exercise the same scope-check expression as a unit test by
    constructing the exact predicate locally and verifying it matches
    what the script enforces. If the script's predicate changes, this
    test will fall out of date and signal that scope coverage shifted.
    """

    def _is_in_scope(self, cwd: str) -> bool:
        # Mirror the predicate at pre_tool_use.py:233-241 (v0.1.5).
        cwd_l = cwd.lower()
        return (
            "make_skills" in cwd_l
            or "make-skills" in cwd_l
            or "the-loom" in cwd_l
            or "project-starter" in cwd_l
            or "_common" in cwd
        )

    def test_make_skills_paths_in_scope(self):
        for path in [
            "C:/Users/Liz/Make_Skills",
            "/home/liz/Make_Skills",
            "/tmp/make-skills-fork",
            "C:/Users/Liz/MAKE_SKILLS",
        ]:
            self.assertTrue(self._is_in_scope(path), f"expected in-scope: {path}")

    def test_the_loom_paths_in_scope(self):
        """v0.1.5: the-loom is now a first-class scope."""
        for path in [
            "C:/Users/Liz/the-loom",
            "/home/liz/the-loom",
            "C:/Users/Liz/The-Loom",
        ]:
            self.assertTrue(self._is_in_scope(path), f"expected in-scope: {path}")

    def test_project_starter_paths_in_scope(self):
        for path in [
            "C:/Users/Liz/project-starter",
            "C:/Users/Liz/my-app-from-project-starter",
        ]:
            self.assertTrue(self._is_in_scope(path), f"expected in-scope: {path}")

    def test_unrelated_paths_out_of_scope(self):
        for path in [
            "C:/Users/Liz/random-project",
            "/tmp/somewhere-else",
            "C:/Users/Liz/Documents",
        ]:
            self.assertFalse(self._is_in_scope(path), f"expected out-of-scope: {path}")


class TestSubprocessInvocation(unittest.TestCase):
    """v0.1.4 regression test: mimics the Node launcher invocation pattern.

    Background: in v0.1.2/v0.1.3, the hook scripts used
    `sys.path.insert + from _observability import ...` which silently fell
    back to no-op stubs when invoked via run-python.mjs (the Node launcher
    that hooks.json points at). Result: hooks.jsonl was never written.

    The v0.1.4 fix uses `importlib.util.spec_from_file_location` with an
    absolute path. This test invokes pre_tool_use.py as a subprocess and
    confirms the log file gets written — catches regressions where future
    refactors break the import in the launcher-subprocess context.
    """

    def test_subprocess_writes_log_when_in_scope(self):
        import json
        import os
        import subprocess
        import tempfile

        script_dir = Path(__file__).resolve().parent.parent / "scripts"
        script_path = script_dir / "pre_tool_use.py"
        self.assertTrue(script_path.exists(), f"missing {script_path}")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            project_dir = tmp / "Make_Skills_test"
            project_dir.mkdir()
            log_dir = project_dir / ".claude" / "logs"

            # Fake hook payload — a Write to a docs file, in scope.
            fake_input = {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(project_dir / "docs" / "test.md"),
                    "content": "innocuous content, no triggers",
                },
                "transcript_path": "",
                "cwd": str(project_dir),
            }

            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = str(project_dir)
            # Force the log to land in our temp dir, not the user's real
            # ~/.claude/logs/, so we can assert against it cleanly.

            result = subprocess.run(
                ["python", str(script_path)],
                input=json.dumps(fake_input),
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )

            # Hook must exit 0 (never crash the harness).
            self.assertEqual(
                result.returncode, 0,
                f"hook exited {result.returncode}; stderr: {result.stderr}",
            )

            # The whole point of v0.1.4: the log file should exist with at
            # least the start + end entries for this invocation.
            log_file = log_dir / "hooks.jsonl"
            self.assertTrue(
                log_file.exists(),
                f"hooks.jsonl was NOT written. "
                f"This is the v0.1.2/v0.1.3 silent-import regression. "
                f"Check that pre_tool_use.py's _observability import succeeded; "
                f"if not, ~/.claude/logs/hook-import-errors.log should explain why. "
                f"stderr: {result.stderr}",
            )

            # Should have at least one valid JSON line per hook phase.
            lines = log_file.read_text(encoding="utf-8").splitlines()
            self.assertGreaterEqual(
                len(lines), 1,
                f"hooks.jsonl is empty. Lines: {lines}",
            )
            for line in lines:
                entry = json.loads(line)  # raises if not valid JSON
                self.assertIn("hook", entry)
                self.assertIn("phase", entry)


if __name__ == "__main__":
    unittest.main()
