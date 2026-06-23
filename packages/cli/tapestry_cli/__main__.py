"""Allow `python -m tapestry_cli` invocation."""
import sys

from tapestry_cli.cli import main

if __name__ == "__main__":
    sys.exit(main())
