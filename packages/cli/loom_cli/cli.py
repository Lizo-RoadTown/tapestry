"""Top-level CLI dispatcher for `loom`.

Subcommands:
  loom init      — onboard the current directory as a loom consuming project
  loom version   — print version + diagnostic info

Add a new subcommand by:
  1. Creating loom_cli/<name>.py with add_arguments(parser) + run(args) -> int
  2. Importing + registering it in SUBCOMMANDS below
"""
from __future__ import annotations

import argparse
import sys

from loom_cli import __version__, init as init_cmd


SUBCOMMANDS: dict[str, dict] = {
    "init": {
        "help": "Onboard the current directory as a loom consuming project.",
        "add_arguments": init_cmd.add_arguments,
        "run": init_cmd.run,
    },
}


def _print_version() -> int:
    import platform
    print(f"loom-cli {__version__}")
    print(f"  python: {platform.python_version()} ({platform.system()} {platform.release()})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="loom",
        description="the-loom command-line interface",
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
