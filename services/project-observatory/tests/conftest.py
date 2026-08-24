"""Pytest setup for services/project-observatory tests.

The signal classifiers (signals.py's compute_* functions) are PURE — no DB, no
clock, no I/O — so these tests need neither a Postgres nor pytest-asyncio; they
feed hand-built aggregate dicts and assert the returned signal records. The
only setup needed is putting the service dir on sys.path so `import signals`
and `import config` resolve when pytest runs from the repo root.

Run from services/project-observatory/:

    cd services/project-observatory
    pip install -r requirements.txt -r requirements-test.txt
    pytest tests/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

_SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICE_DIR))
