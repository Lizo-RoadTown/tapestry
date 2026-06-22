"""
Read-only Postgres query tool for the deepagents agent.

The agent uses this to inspect its own state — conversation counts,
thread activity, checkpoint volume — and any custom analytics tables
that get added over time. Same data Grafana visualizes; SQL form for
the agent to summarize in natural language.

Read-only by enforcement:
- Connection uses an autocommit, read-only transaction
- The query is statically validated to start with SELECT or WITH (CTE)
- Multiple statements rejected (no semicolons inside the query)
- Hard timeout to prevent runaway queries
"""
from __future__ import annotations

import os
import re
from typing import Any

from langchain_core.tools import tool
import psycopg

QUERY_TIMEOUT_SECONDS = 10
ROW_LIMIT = 200

_SAFE_QUERY_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE | re.DOTALL)


@tool
def query_db(sql: str) -> str:
    """Run a read-only SQL query against the Make_Skills Postgres database
    (the same database that holds LangGraph conversation checkpoints and
    that Grafana queries for dashboards).

    Use this to answer questions about agent activity, conversation history,
    thread counts, message volume, etc. Examples of useful queries:
    - SELECT COUNT(DISTINCT thread_id) FROM checkpoints
    - SELECT thread_id, MAX(checkpoint_id) FROM checkpoints GROUP BY thread_id ORDER BY 2 DESC LIMIT 10
    - SELECT table_name FROM information_schema.tables WHERE table_schema='public'

    Restrictions:
    - SELECT and WITH (CTE) statements only — no INSERT / UPDATE / DELETE / DDL
    - One statement per call (no semicolons mid-query)
    - Hard 10-second timeout
    - Up to 200 rows returned

    Args:
        sql: A read-only SQL query.

    Returns:
        Pipe-delimited text table of results, or an error message.
    """
    if not _SAFE_QUERY_RE.match(sql):
        return "ERROR: only SELECT or WITH queries are permitted."
    if ";" in sql.rstrip().rstrip(";"):
        return "ERROR: only one statement per call (no inline semicolons)."

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return "ERROR: DATABASE_URL not set in the agent's environment."

    try:
        with psycopg.connect(
            db_url,
            autocommit=True,
            connect_timeout=5,
            options=f"-c statement_timeout={QUERY_TIMEOUT_SECONDS * 1000} -c default_transaction_read_only=on",
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                if cur.description is None:
                    return "(query returned no result set)"
                cols = [d.name for d in cur.description]
                rows = cur.fetchmany(ROW_LIMIT + 1)
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"

    if not rows:
        return "(0 rows)"

    truncated = len(rows) > ROW_LIMIT
    if truncated:
        rows = rows[:ROW_LIMIT]

    out = [" | ".join(cols), "-" * (sum(len(c) for c in cols) + 3 * (len(cols) - 1))]
    for row in rows:
        out.append(" | ".join(_render_cell(c) for c in row))
    if truncated:
        out.append(f"... ({ROW_LIMIT}+ rows; refine with LIMIT)")
    return "\n".join(out)


def _render_cell(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    if len(s) > 80:
        return s[:77] + "..."
    return s
