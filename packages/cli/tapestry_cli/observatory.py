"""`tapestry observatory` — open the Observatory console.

The Observatory is the platform's coordination console (one deployed
instance). This opens it in a browser. Override the URL with
`--url` or the `TAPESTRY_OBSERVATORY_URL` environment variable.
"""
from __future__ import annotations

import argparse
import os
import webbrowser

DEFAULT_URL = "https://tapestry-khaki.vercel.app/observatory"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--url",
        default=os.environ.get("TAPESTRY_OBSERVATORY_URL", DEFAULT_URL),
        help="Console URL (default: the deployed console; override with TAPESTRY_OBSERVATORY_URL).",
    )
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="Print the URL instead of opening a browser.",
    )


def run(args: argparse.Namespace) -> int:
    url = args.url
    print(f"Observatory console: {url}")
    if args.print_only:
        return 0
    try:
        webbrowser.open(url)
        print("Opened in your default browser.")
    except Exception:
        print("(Couldn't open a browser automatically — open the URL above.)")
    return 0
