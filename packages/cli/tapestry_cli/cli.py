"""Top-level CLI dispatcher for `tapestry`.

Subcommands:
  tapestry onboard     — `init` + writes .claude/settings.json with tapestry plugins
                   enabled (the 4-step quickstart path)
  tapestry observatory — open the Observatory console in a browser
  tapestry init      — register the project, write .env / .mcp.json / .project-intelligence/
                   (the granular path — does NOT touch .claude/settings.json)
  tapestry version   — print version + diagnostic info

Add a new subcommand by:
  1. Creating tapestry_cli/<name>.py with add_arguments(parser) + run(args) -> int
  2. Importing + registering it in SUBCOMMANDS below
"""
from __future__ import annotations

import argparse
import sys

from tapestry_cli import (
    __version__,
    init as init_cmd,
    observatory as observatory_cmd,
    onboard as onboard_cmd,
)


SUBCOMMANDS: dict[str, dict] = {
    "onboard": {
        "help": "Onboard the current directory + write .claude/settings.json (recommended).",
        "add_arguments": onboard_cmd.add_arguments,
        "run": onboard_cmd.run,
    },
    "observatory": {
        "help": "Open the Observatory console in a browser.",
        "add_arguments": observatory_cmd.add_arguments,
        "run": observatory_cmd.run,
    },
    "init": {
        "help": "Onboard the current directory as a Tapestry consuming project (no settings.json).",
        "add_arguments": init_cmd.add_arguments,
        "run": init_cmd.run,
    },
}


def _print_version() -> int:
    import platform
    print(f"tapestry-cli {__version__}")
    print(f"  python: {platform.python_version()} ({platform.system()} {platform.release()})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tapestry",
        description="Tapestry command-line interface — onboard projects, inspect state, open the Observatory.",
    )
    subs = parser.add_subparsers(dest="command", metavar="<command>")
    subs.add_parser("version", help="Print version and platform info.")
    for name, spec in SUBCOMMANDS.items():
        sub = subs.add_parser(name, help=spec["help"])
        spec["add_arguments"](sub)

    args = parser.parse_args(argv)

    if args.command == "version":
        return _print_version()
    if args.command in SUBCOMMANDS:
        return SUBCOMMANDS[args.command]["run"](args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
