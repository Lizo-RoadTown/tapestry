#!/usr/bin/env python3
"""
memory_snapshot.py — capture the-loom's memory store shape at a point in time.

Writes a single JSON file to docs/memory-snapshots/<UTC-timestamp>.json
containing row counts, type/actor/visibility breakdowns, table sizes, and
DB size. Snapshots are append-only — never edit a past file.

See docs/architecture/assessment-protocol.md for full context on what to
capture, when, and how to compare snapshots over time.

Usage:

    # Capture a fresh snapshot (default behavior)
    python scripts/memory_snapshot.py

    # Diff two snapshots
    python scripts/memory_snapshot.py --diff <ts1> <ts2>

    # Trend a single metric across all snapshots (ASCII line + CSV)
    python scripts/memory_snapshot.py --trend records.total_rows

Reads LOOM_DB_URL from the environment (or .env in the repo root).

Stdlib + psycopg only — no additional deps. Run with the same Python
that runs services/agent-context (which has psycopg installed).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "docs" / "memory-snapshots"

# Liz's stable self-host tenant_id — must match SELF_HOST_TENANT_ID in:
#   services/agent-context/mcp_server.py:70
#   services/agent-context/main.py
#   services/project-registry/auth_bridge.py:30
# Generated via uuid5('liz.loom.humancensys.com').
SELF_HOST_TENANT_ID = "1d8ec1b3-d62a-5fab-9a52-eb6a3e09f1c8"


# ---------------------------------------------------------------------------
# .env loader (stdlib; matches the pattern used by loom_init.py)
# ---------------------------------------------------------------------------


def _load_dotenv(env_path: Path) -> None:
    """Read KEY=VALUE lines from env_path into os.environ if absent.
    Silent if file doesn't exist. Does not overwrite existing env vars."""
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Snapshot capture
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    """ISO 8601 UTC timestamp safe for filenames: 2026-06-01T19-23-08Z"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H-%M-%SZ")


def capture(tenant_id: str = SELF_HOST_TENANT_ID) -> dict[str, Any]:
    """Query the DB and return the snapshot dict.

    Each query is a separate transaction; this is a read-only operation.
    psycopg is imported lazily so --diff and --trend modes don't require it.

    tenant_id: set as app.tenant_id so RLS policies surface this tenant's
    rows. Defaults to SELF_HOST_TENANT_ID (Liz's stable UUID). For hosted-
    multitenant: pass the tenant whose snapshot you want, or run multiple
    captures (one per tenant) and aggregate downstream. A true cross-tenant
    admin view would require a Postgres role with BYPASSRLS, which Render's
    managed-DB user does not have.
    """
    try:
        import psycopg
    except ImportError:
        print("psycopg not installed. Install with: pip install 'psycopg[binary]'", file=sys.stderr)
        sys.exit(1)

    dsn = os.environ.get("LOOM_DB_URL")
    if not dsn:
        print(
            "LOOM_DB_URL unset. Set it in .env or the environment.\n"
            "  Render-internal: postgresql://loom:...@dpg-...-internal/loom\n"
            "  Render-external: postgresql://loom:...@dpg-....render.com/loom?sslmode=require",
            file=sys.stderr,
        )
        sys.exit(2)

    snap: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "captured_at_iso": datetime.now(timezone.utc).isoformat(),
        "captured_at_epoch": time.time(),
        "tenant_id": tenant_id,
        "db_name": None,
        "tables": {},
        "project_tag_distribution": {},
        "db_size_bytes": 0,
        "notes": "",
    }

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # RLS: every tenant-scoped table policies on app.tenant_id.
            # Set once on the connection; queries inside this block all see
            # the scoped view. Use set_config (not SET LOCAL) because SET
            # LOCAL rejects bind parameters — see lesson_postgres_set_local_no_bind_params.
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))

            cur.execute("SELECT current_database()")
            row = cur.fetchone()
            snap["db_name"] = row[0] if row else None

            # ---- records table ----
            cur.execute("SELECT count(*) FROM records")
            total_records = cur.fetchone()[0]

            cur.execute("SELECT type, count(*) FROM records GROUP BY type ORDER BY count(*) DESC")
            by_type = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute("SELECT actor, count(*) FROM records GROUP BY actor ORDER BY count(*) DESC")
            by_actor = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute("SELECT visibility, count(*) FROM records GROUP BY visibility")
            by_visibility = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute("""
                SELECT to_char(to_timestamp(ts), 'YYYY-MM') AS month, count(*)
                FROM records
                WHERE ts > 0
                GROUP BY month
                ORDER BY month
            """)
            by_month = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute("SELECT pg_relation_size('records')")
            records_size = cur.fetchone()[0]

            # Index sizes — list each per-index for the records table
            cur.execute("""
                SELECT indexname, pg_relation_size(indexname::regclass)
                FROM pg_indexes
                WHERE tablename = 'records'
                ORDER BY indexname
            """)
            index_sizes = {r[0]: r[1] for r in cur.fetchall()}

            snap["tables"]["records"] = {
                "total_rows": total_records,
                "by_type": by_type,
                "by_actor": by_actor,
                "by_visibility": by_visibility,
                "by_month": by_month,
                "table_size_bytes": records_size,
                "index_sizes_bytes": index_sizes,
            }

            # ---- projects / repos / machines (no-op gracefully if not yet migrated) ----
            for table_name, group_cols in [
                ("projects", ["kind"]),
                ("repos", []),
                ("machines", []),
            ]:
                try:
                    cur.execute(f"SELECT count(*) FROM {table_name}")
                    total = cur.fetchone()[0]
                    entry: dict[str, Any] = {"total_rows": total}
                    for col in group_cols:
                        cur.execute(f"SELECT {col}, count(*) FROM {table_name} GROUP BY {col}")
                        entry[f"by_{col}"] = {r[0]: r[1] for r in cur.fetchall()}
                    snap["tables"][table_name] = entry
                except psycopg.errors.UndefinedTable:
                    conn.rollback()
                    snap["tables"][table_name] = {"total_rows": None, "note": "table does not exist (migration not yet applied)"}

            # ---- project_tags distribution across records ----
            cur.execute("""
                SELECT unnest(project_tags) AS tag, count(*)
                FROM records
                WHERE array_length(project_tags, 1) > 0
                GROUP BY tag
                ORDER BY count(*) DESC
            """)
            snap["project_tag_distribution"] = {r[0]: r[1] for r in cur.fetchall()}

            # ---- whole-DB size ----
            cur.execute("SELECT pg_database_size(current_database())")
            snap["db_size_bytes"] = cur.fetchone()[0]

    return snap


def write_snapshot(snap: dict[str, Any], notes: str = "") -> Path:
    """Write snap to docs/memory-snapshots/<timestamp>.json and return the path."""
    if notes:
        snap["notes"] = notes
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = _utc_timestamp()
    out = SNAPSHOT_DIR / f"{ts}.json"
    out.write_text(json.dumps(snap, indent=2, sort_keys=False), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def _load_snapshot(ts_or_path: str) -> dict[str, Any]:
    """Load a snapshot by timestamp prefix OR by full path."""
    p = Path(ts_or_path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    matches = sorted(SNAPSHOT_DIR.glob(f"{ts_or_path}*.json"))
    if not matches:
        print(f"No snapshot matching '{ts_or_path}' in {SNAPSHOT_DIR}", file=sys.stderr)
        sys.exit(3)
    if len(matches) > 1:
        print(f"Ambiguous prefix '{ts_or_path}' — matched {len(matches)} files. Be more specific.", file=sys.stderr)
        sys.exit(3)
    return json.loads(matches[0].read_text(encoding="utf-8"))


def _flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested dict to dotted-key form for diff output."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


def diff(ts_a: str, ts_b: str) -> None:
    """Print a flat diff of two snapshots: A → B."""
    a = _flatten(_load_snapshot(ts_a))
    b = _flatten(_load_snapshot(ts_b))

    keys = sorted(set(a) | set(b))
    print(f"Diff: {ts_a}  ->  {ts_b}")
    print("=" * 76)
    for k in keys:
        va = a.get(k, "-")
        vb = b.get(k, "-")
        if va == vb:
            continue
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            delta = vb - va
            sign = "+" if delta > 0 else ""
            print(f"{k:<55} {va!r:>10}  ->{vb!r:>10}  ({sign}{delta})")
        else:
            print(f"{k:<55} {va!r:>10}  ->{vb!r:>10}")


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------


def _resolve_metric(snap: dict[str, Any], path: str) -> Any:
    """records.total_rows → snap['tables']['records']['total_rows']"""
    parts = path.split(".")
    # Special-case: top-level "tables" prefix is implicit
    if parts[0] in {"records", "projects", "repos", "machines"}:
        parts = ["tables"] + parts
    cursor: Any = snap
    for p in parts:
        if isinstance(cursor, dict) and p in cursor:
            cursor = cursor[p]
        else:
            return None
    return cursor


def trend(metric_path: str) -> None:
    """Print the metric over time across all snapshots."""
    snapshots = sorted(SNAPSHOT_DIR.glob("*.json"))
    if not snapshots:
        print(f"No snapshots in {SNAPSHOT_DIR}", file=sys.stderr)
        return

    points: list[tuple[str, float]] = []
    for p in snapshots:
        snap = json.loads(p.read_text(encoding="utf-8"))
        ts_label = p.stem
        val = _resolve_metric(snap, metric_path)
        if isinstance(val, (int, float)):
            points.append((ts_label, float(val)))

    if not points:
        print(f"Metric '{metric_path}' not found or non-numeric across snapshots", file=sys.stderr)
        return

    max_val = max(p[1] for p in points)
    width = 40
    print(f"Trend: {metric_path}")
    print(f"Snapshots: {len(snapshots)}, with numeric values: {len(points)}")
    print()
    for ts_label, val in points:
        bar = "█" * (int((val / max_val) * width) if max_val > 0 else 0)
        print(f"{ts_label:<28} {val:>10.0f}  {bar}")
    print()
    print("# CSV (timestamp,value):")
    for ts_label, val in points:
        print(f"{ts_label},{val}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    _load_dotenv(REPO_ROOT / ".env")
    _load_dotenv(REPO_ROOT / "services" / "agent-context" / ".env")

    parser = argparse.ArgumentParser(description="the-loom memory store snapshot tool")
    parser.add_argument("--diff", nargs=2, metavar=("TS_A", "TS_B"),
                        help="Diff two snapshots by timestamp prefix or path")
    parser.add_argument("--trend", metavar="METRIC",
                        help="Trend a metric across all snapshots (e.g. records.total_rows)")
    parser.add_argument("--notes", default="",
                        help="Free-form notes to embed in the snapshot file")
    parser.add_argument("--tenant-id", default=SELF_HOST_TENANT_ID,
                        help=f"Tenant UUID for RLS scope. Default: SELF_HOST_TENANT_ID ({SELF_HOST_TENANT_ID}). "
                             "Hosted-multi-tenant: pass per-tenant; one capture per tenant.")
    args = parser.parse_args()

    if args.diff:
        diff(args.diff[0], args.diff[1])
        return 0

    if args.trend:
        trend(args.trend)
        return 0

    # Default: capture a fresh snapshot
    snap = capture(tenant_id=args.tenant_id)
    out = write_snapshot(snap, notes=args.notes)
    total = snap["tables"]["records"]["total_rows"]
    db_mb = snap["db_size_bytes"] / (1024 * 1024)
    print(f"Snapshot written: {out.relative_to(REPO_ROOT)}")
    print(f"  records: {total} rows, total DB size: {db_mb:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
