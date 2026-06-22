"""One-off migration runner for loom-postgres.

Usage:
    # 1. Export the EXTERNAL database URL (don't paste it inline; keeps it
    #    out of shell history).
    export LOOM_DB_URL_EXTERNAL='postgresql://...'

    # 2. Run the migration:
    python scripts/apply_migration.py infra/migrations/001_init_memory.sql

Requires psycopg3 (already installed in Liz's Python env per probe).

This is a one-off bootstrap script. Once Phase 4+ adds a proper
migration framework (Alembic or a startup-hook script), this gets
deleted. For now it exists because Render MCP only supports read-only
SQL queries — DDL like CREATE EXTENSION / CREATE TABLE can't go through
the MCP, and the dashboard's PSQL console isn't available on Render's
free tier database.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: python scripts/apply_migration.py <path-to-sql-file>",
            file=sys.stderr,
        )
        return 2

    sql_path = Path(sys.argv[1])
    if not sql_path.exists():
        print(f"error: file not found: {sql_path}", file=sys.stderr)
        return 1

    dsn = os.environ.get("LOOM_DB_URL_EXTERNAL")
    if not dsn:
        print(
            "error: LOOM_DB_URL_EXTERNAL not set. Export the EXTERNAL\n"
            "       postgres URL from Render dashboard (loom-postgres ->\n"
            "       Connect -> External -> External Database URL).\n",
            file=sys.stderr,
        )
        return 1

    sql = sql_path.read_text(encoding="utf-8")
    print(f"Applying {sql_path}...")
    print(f"  bytes: {len(sql)}")
    print()

    # psycopg3 supports multi-statement scripts when autocommit=True or
    # when the whole script is wrapped in a transaction. The migration
    # file already wraps in BEGIN/COMMIT, so use autocommit=True and let
    # the file's BEGIN/COMMIT control the transaction.
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

            # Drain any NOTICEs/messages
            for msg in conn.info.notices[-20:] if hasattr(conn.info, "notices") else []:
                print(f"  notice: {msg}")

    print()
    print(f"OK. Verifying:")

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT extname FROM pg_extension WHERE extname = 'vector') AS vector_ext,
                  (SELECT to_regclass('public.records')::text)                AS records_table,
                  (SELECT COUNT(*) FROM pg_indexes
                    WHERE tablename = 'records')                               AS records_indexes,
                  (SELECT COUNT(*) FROM pg_policies
                    WHERE tablename = 'records')                               AS records_policies
                """
            )
            row = cur.fetchone()
            if row is None:
                print("  WARN: verification query returned no rows")
                return 1
            vector_ext, records_table, indexes, policies = row
            print(f"  vector extension : {vector_ext or 'MISSING'}")
            print(f"  records table    : {records_table or 'MISSING'}")
            print(f"  indexes on records: {indexes}")
            print(f"  RLS policies     : {policies}")

            ok = (
                vector_ext == "vector"
                and records_table == "records"
                and indexes >= 5
                and policies == 4
            )
            print()
            print("RESULT:", "OK" if ok else "INCOMPLETE - check schema")
            return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
