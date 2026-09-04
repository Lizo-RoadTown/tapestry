"""Pytest setup for services/self-observer tests.

Puts the service dir on sys.path so `import config`, `import signal_rules`,
`import registry_client`, etc. resolve when pytest runs from the repo root.

Run from services/self-observer/:

    cd services/self-observer
    pip install -r requirements.txt -r requirements-test.txt
    pytest tests/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

_SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))
