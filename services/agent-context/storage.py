"""
Postgres + pgvector-backed memory store for the Agent Context Service.

Port of `Make_Skills/platform/api/memory/lance.py` with three changes:

1. **Storage:** LanceDB on disk → Render Postgres with the `vector(384)`
   column type from pgvector. Same schema, indexed for HNSW + btree.
2. **Tenant scoping:** explicit `_tenant_clause()` SQL fragment →
   row-level security (RLS) policies on the `records` table. Each
   transaction sets `app.tenant_id` via `SET LOCAL`; the policies in
   `001_init_memory.sql` enforce isolation.
3. **Concurrency:** sync `lancedb` calls in async handlers → async
   `psycopg` (psycopg3) with a connection pool. FastAPI awaits directly,
   no thread-pool hop.

What stays unchanged:

- The fastembed embedder (BAAI/bge-small-en-v1.5, 384-dim ONNX local).
- The public API surface (`insert_records`, `search`, `list_records`,
  `count`, `embed`). Callers in `memory.py` migrate by renaming the
  import — no signature changes.
- The `_strip()` helper that drops `vector` from API responses.

Reference: docs/plans/2026-05-25-the-loom-roadmap-v2.md Phase 2, and the
schema map in memory `reference_phase2_port_specifics.md`.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any

import psycopg
from fastembed import TextEmbedding
from pgvector.psycopg import register_vector_async
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


# ---------------------------------------------------------------------------
# Embedding model (unchanged from lance.py)
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_NDIMS = 384

_embedder_lock = threading.Lock()
_embedder: TextEmbedding | None = None


def _get_embedder() -> TextEmbedding:
    """Lazy-init the local ONNX embedder. Singleton across the process.

    First call downloads the model (~80MB) to `~/.cache/fastembed/`.
    Subsequent calls are instant. The model is small + fast + high
    quality for general English text; switching it changes the vector
    dimension and requires a migration to rebuild the column type.
    """
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            _embedder = TextEmbedding(model_name=DEFAULT_MODEL)
        return _embedder


def embed(text: str) -> list[float]:
    """Embed one string. fastembed returns a numpy array; convert to list."""
    embedder = _get_embedder()
    vec = next(embedder.embed([text]))
    return vec.tolist()


# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

_pool: AsyncConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def _configure_connection(conn: psycopg.AsyncConnection) -> None:
    """Register pgvector + use dict_row for every connection in the pool."""
    await register_vector_async(conn)
    conn.row_factory = dict_row


async def get_pool() -> AsyncConnectionPool:
    """Lazy-init the connection pool. Reads `LOOM_DB_URL` from the env.

    Pool size: min=2, max=10 for personal-use scale. Tune at Phase 4+
    if observability shows pool saturation.
    """
    global _pool
    async with _pool_lock:
        if _pool is None:
            dsn = os.environ.get("LOOM_DB_URL")
            if not dsn:
                raise RuntimeError(
                    "LOOM_DB_URL unset. Required for loom-agent-context's "
                    "storage layer. In Render this is auto-injected via "
                    "fromDatabase reference; for local dev set in .env."
                )
            _pool = AsyncConnectionPool(
                conninfo=dsn,
                min_size=2,
                max_size=10,
                open=False,
                configure=_configure_connection,
            )
            await _pool.open()
        return _pool


async def close_pool() -> None:
    """Close the pool. Call on FastAPI shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Tenant scoping (RLS — replaces lance._tenant_clause)
# ---------------------------------------------------------------------------


async def _set_tenant(conn: psycopg.AsyncConnection, tenant_id: str) -> None:
    """Set `app.tenant_id` for the current transaction. RLS policies in
    001_init_memory.sql read this via `current_setting('app.tenant_id', true)`.

    MUST be called inside an open transaction. Use within
    `async with conn.transaction(): ...`.

    Note: `SET LOCAL app.tenant_id = $1` is a Postgres syntax error —
    SET is a utility statement and doesn't accept bind parameters. Use
    `set_config(name, value, is_local)` instead; the `true` arg gives
    LOCAL (transaction-scoped) semantics.
    """
    await conn.execute(
        "SELECT set_config('app.tenant_id', %s, true)", (tenant_id,)
    )


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------


async def insert_records(
    records: list[dict[str, Any]],
    tenant_id: str,
    visibility: str = "private",
) -> int:
    """Insert records scoped to `tenant_id`. visibility defaults to 'private';
    pass 'public' to mark a record as part of the future Pillar 3c commons.
    Pass 'deleted' to soft-delete (the mcp_server delete handler uses this).

    Each dict must have id, type, content. Optional: project_tags,
    source_thread_id, ts, why, actor, extra. The vector field is computed
    here from `content` using the local fastembed embedder.

    Returns the number of rows inserted.

    Idempotency: on conflict (id), the row is REPLACED (upsert). This
    matches the Make_Skills behavior (delete-then-insert in mcp_server)
    but does it atomically in one INSERT ... ON CONFLICT.
    """
    if not records:
        return 0

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)

            rows: list[tuple[Any, ...]] = []
            for r in records:
                ts = float(r.get("ts", 0))
                # ts_last_accessed defaults to ts on insert; storage reads
                # update it later (recall, search, list paths) to reflect
                # actual access. Phase 2 MVP doesn't update-on-read; the
                # column being here lets Phase 4+ add that behavior without
                # a migration.
                ts_last_accessed = float(
                    r.get("ts_last_accessed", ts)
                )
                rows.append(
                    (
                        r["id"],
                        r["type"],
                        r["content"],
                        embed(r["content"]),
                        r.get("project_tags", []),
                        r.get("source_thread_id", ""),
                        ts,
                        r.get("why", ""),
                        tenant_id,
                        visibility,
                        r.get("actor", "unknown"),
                        ts_last_accessed,
                        json.dumps(r.get("extra", {})),
                    )
                )

            # INSERT ... ON CONFLICT (id) DO UPDATE — atomic upsert.
            # All non-key columns get overwritten; the embedding is
            # re-computed if content changed (caller passes new content).
            await conn.cursor().executemany(
                """
                INSERT INTO records (
                    id, type, content, vector, project_tags,
                    source_thread_id, ts, why, tenant_id, visibility,
                    actor, ts_last_accessed, extra
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    type = EXCLUDED.type,
                    content = EXCLUDED.content,
                    vector = EXCLUDED.vector,
                    project_tags = EXCLUDED.project_tags,
                    source_thread_id = EXCLUDED.source_thread_id,
                    ts = EXCLUDED.ts,
                    why = EXCLUDED.why,
                    tenant_id = EXCLUDED.tenant_id,
                    visibility = EXCLUDED.visibility,
                    actor = EXCLUDED.actor,
                    ts_last_accessed = EXCLUDED.ts_last_accessed,
                    extra = EXCLUDED.extra
                """,
                rows,
            )
            return len(rows)


# ---------------------------------------------------------------------------
# Search (semantic)
# ---------------------------------------------------------------------------


async def search(
    query: str,
    tenant_id: str,
    limit: int = 5,
    record_type: str | None = None,
    project_tags: list[str] | None = None,
    include_public: bool = True,
) -> list[dict[str, Any]]:
    """Semantic search scoped to `tenant_id`. Returns top-N by vector
    similarity (cosine distance via the `<=>` operator on the HNSW index).

    Optional filters:
      - record_type: exact type match
      - project_tags: array overlap (any tag matches)
      - include_public: if True (default), also include public-visibility
        rows from other tenants (Pillar 3c commons path). If False,
        restrict to this tenant only.
    """
    qvec = embed(query)

    where_parts: list[str] = []
    params: list[Any] = [qvec]  # $1 — used in ORDER BY

    if not include_public:
        # Exclude public commons; only this tenant. RLS already allows
        # cross-tenant reads of public rows, so we add an explicit clause
        # to restrict.
        where_parts.append("visibility != 'public'")

    if record_type:
        params.append(record_type)
        where_parts.append("type = %s")

    if project_tags:
        params.append(project_tags)
        where_parts.append("project_tags && %s::text[]")  # array overlap

    where_sql = ""
    if where_parts:
        where_sql = "WHERE " + " AND ".join(where_parts)

    sql = f"""
        SELECT id, type, content, project_tags, source_thread_id,
               ts, why, tenant_id, visibility,
               (vector <=> %s::vector) AS _distance
        FROM records
        {where_sql}
        ORDER BY vector <=> %s::vector
        LIMIT %s
    """
    # Re-bind the query vector for ORDER BY (psycopg requires separate
    # binding even for repeated params).
    params_full = [qvec] + params[1:] + [qvec, limit]

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(sql, params_full)
                rows = await cur.fetchall()
                return [_strip(dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# List (non-semantic)
# ---------------------------------------------------------------------------


async def list_records(
    tenant_id: str,
    limit: int = 50,
    offset: int = 0,
    record_type: str | None = None,
    project_tag: str | None = None,
    include_public: bool = True,
) -> list[dict[str, Any]]:
    """Non-semantic listing scoped to `tenant_id`. Newest first by `ts`."""
    where_parts: list[str] = []
    params: list[Any] = []

    if not include_public:
        where_parts.append("visibility != 'public'")

    if record_type:
        params.append(record_type)
        where_parts.append("type = %s")

    if project_tag:
        params.append([project_tag])
        where_parts.append("project_tags && %s::text[]")

    where_sql = ""
    if where_parts:
        where_sql = "WHERE " + " AND ".join(where_parts)

    sql = f"""
        SELECT id, type, content, project_tags, source_thread_id,
               ts, why, tenant_id, visibility
        FROM records
        {where_sql}
        ORDER BY ts DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()
                return [_strip(dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Count
# ---------------------------------------------------------------------------


async def count(tenant_id: str, include_public: bool = False) -> int:
    """Row count scoped to `tenant_id`. include_public=False by default so
    KPI cards show 'your records', not 'your records + the commons'."""
    where_sql = ""
    if not include_public:
        where_sql = "WHERE visibility != 'public'"

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT COUNT(*) AS n FROM records {where_sql}"
                )
                row = await cur.fetchone()
                return int((row or {}).get("n", 0))


# ---------------------------------------------------------------------------
# Delete (hard — used only for the upsert path; soft-delete uses insert
# with visibility='deleted')
# ---------------------------------------------------------------------------


async def get_by_id(
    record_id: str,
    tenant_id: str,
    include_deleted: bool = False,
) -> dict[str, Any] | None:
    """Primary-key lookup. Returns None if absent or (when
    include_deleted=False) if the row's visibility is 'deleted'.

    Used by mcp_server's memory_read tool and the upsert path in
    memory_write (to know if an existing row is being replaced).
    """
    where_parts = ["id = %s"]
    params: list[Any] = [record_id]
    if not include_deleted:
        where_parts.append("visibility != 'deleted'")
    where_sql = " AND ".join(where_parts)

    sql = f"""
        SELECT id, type, content, project_tags, source_thread_id,
               ts, why, tenant_id, visibility, actor, ts_last_accessed, extra
        FROM records
        WHERE {where_sql}
        LIMIT 1
    """

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                row = await cur.fetchone()
                if row is None:
                    return None
                return _strip(dict(row))


async def delete_by_id(record_id: str, tenant_id: str) -> int:
    """Hard-delete one record by id. Returns rowcount (0 or 1).

    Note: mcp_server's `memory_delete` is a SOFT delete (re-insert with
    visibility='deleted'), not a hard delete. This function exists for
    the upsert path where the old row is being replaced. Most callers
    should NOT use this directly.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            await _set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM records WHERE id = %s", (record_id,)
                )
                return cur.rowcount


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip(row: dict[str, Any]) -> dict[str, Any]:
    """Drop internal fields from API responses — vector + _distance are
    noise to clients."""
    return {k: v for k, v in row.items() if k not in {"vector", "_distance"}}
