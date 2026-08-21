"""tapestry-cli — command-line interface for Tapestry.

Stdlib-only. Cross-platform. Subcommands:
  tapestry init    — onboard the current directory as a Tapestry consuming project
  tapestry version — print version + diagnostic info

(`loom` remains a deprecated command alias; see [project.scripts] in pyproject.)
"""
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    # Authoritative source: the installed package's own metadata, so this can
    # never drift from pyproject again (the 0.1.0-vs-0.1.3 bug it replaces).
    __version__ = _pkg_version("tapestry-cli")
except PackageNotFoundError:  # running from a source checkout, not pip-installed
    __version__ = "0.1.4"
