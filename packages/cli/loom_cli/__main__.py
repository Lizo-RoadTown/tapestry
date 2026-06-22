"""Allow `python -m loom_cli` invocation."""
import sys

from loom_cli.cli import main

if __name__ == "__main__":
    sys.exit(main())
