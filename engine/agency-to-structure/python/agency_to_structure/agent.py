"""
Build the deepagents agent from the repo's deepagents.toml.

This module is the single integration point with the deepagents library —
keeping it isolated means we can adapt to API changes in deepagents without
touching the FastAPI service code.

EXPECT TO ITERATE: deepagents is moving fast and the exact signature of
create_deep_agent + the PostgresSaver wiring may need adjustment when this
first runs. Verify against the version pinned in platform/requirements.txt.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Read deepagents.toml into a dict."""
    with open(config_path, "rb") as f:
        return tomllib.load(f)


async def build_agent(config_path: str | Path | None = None, repo_root: str | Path | None = None):
    """
    Build the deepagents agent with an async Postgres-backed checkpointer.

    Returns (agent, checkpointer). The checkpointer is shared with
    AgentRuntime for per-student agents — thread_ids are UUIDs so
    collisions across default-agent and per-agent threads are impossible.

    Call .ainvoke() / .astream() on the agent. Each call must pass a
    thread_id in the config so the AsyncPostgresSaver persists state
    per conversation.
    """
    from contextlib import asynccontextmanager

    from deepagents import create_deep_agent
    from langgraph.checkpoint.postgres import _ainternal
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    from loom_auth import langgraph_tenant_ctx as current_tenant

    class TenantScopedSaver(AsyncPostgresSaver):
        """Wrap _cursor() to inject `SET LOCAL app.tenant_id` on every
        connection acquire. Defense-in-depth: even if a forged thread_id
        bypasses the gateway check on /chat, RLS on the checkpoint tables
        (when added — currently the conversations sidecar carries the policy)
        sees `app.tenant_id` set to the calling tenant only."""

        @asynccontextmanager
        async def _cursor(self, *, pipeline: bool = False):
            tid = current_tenant.get()
            async with self.lock, _ainternal.get_connection(self.conn) as conn:
                await conn.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    (str(tid),),
                )
                async with conn.cursor(binary=True, row_factory=dict_row) as cur:
                    yield cur

    config_path = Path(config_path or os.environ["AGENT_CONFIG_PATH"])
    repo_root = Path(repo_root or os.environ.get("AGENT_REPO_ROOT", config_path.parent))
    cfg = load_config(config_path)

    agent_cfg = cfg.get("agent", {})
    model_cfg = cfg.get("model", {})

    # Resolve relative paths in config against the repo root.
    def abspath(p: str) -> str:
        return str((repo_root / p).resolve())

    skills = [abspath(p) for p in agent_cfg.get("skills", [])]
    memory = [abspath(p) for p in agent_cfg.get("memory", [])]
    subagents_dir_raw = agent_cfg.get("subagents_dir")
    subagents_dir = Path(abspath(subagents_dir_raw)) if subagents_dir_raw else None

    # Postgres checkpointer — per-thread conversation persistence.
    # Use a ConnectionPool so the saver has a real connection for the app's lifetime
    # (PostgresSaver.from_conn_string returns a context manager, which doesn't fit a
    # long-lived FastAPI lifespan).
    db_url = os.environ["DATABASE_URL"]
    pool = AsyncConnectionPool(
        conninfo=db_url,
        max_size=20,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,
    )
    await pool.open()

    # Pillar 0 — tenant abstraction. Run before checkpointer.setup() so
    # the conversations sidecar table (which gates checkpoint access via
    # RLS) is in place before any chat traffic.
    # TODO(audit §2.2 integration): core.db.migrations was NOT lifted in
    # PR-3 (§1.2) — schema-bearing migrations live in tapestry/infra/migrations/
    # and are applied via tapestry/scripts/apply_migration.py (PR-6). When
    # this agent.py is wired into a running service, replace this call with
    # the apply_migration.py flow or import from a yet-to-be-created
    # `loom_sdk.migrations` module.
    from core.db import migrations  # noqa: F401 — placeholder; see TODO above
    await migrations.run_all(pool)

    checkpointer = TenantScopedSaver(pool)
    await checkpointer.setup()  # idempotent — creates the checkpoint tables on first run

    subagents = load_subagents(subagents_dir, repo_root) if subagents_dir else []

    # Built-in tools — what the agent gets without uncommenting any MCPs.
    # Memory recall now comes from the-loom MCP at
    # https://loom-agent-context.onrender.com/mcp/memory/ (configured per-session
    # in the consumer's MCP client), not from a Make_Skills-internal LanceDB tool.
    from loom_sdk.tools.db import query_db
    # TODO(audit §2.2 integration): services.admin.roadmap.tools belongs
    # with audit §2.1 (subagents + roadmap-maintenance MCP wrapping)
    # which is DEFERRED to Step 8 territory. When §2.1 lands, rewire to
    # the lifted destination (likely tapestry/engine/agency-to-structure/
    # or tapestry/services/admin/).
    from services.admin.roadmap.tools import (  # noqa: F401 — placeholder
        add_roadmap_item,
        roadmap_overview,
        update_roadmap_status,
    )
    builtin_tools = [
        query_db,
        roadmap_overview,
        update_roadmap_status,
        add_roadmap_item,
    ]

    from loom_sdk.providers.model_registry import resolve_model

    agent = create_deep_agent(
        model=resolve_model(model_cfg),
        tools=builtin_tools,
        memory=memory,
        skills=skills,
        subagents=subagents,
        checkpointer=checkpointer,
    )
    return agent, checkpointer


def load_subagents(subagents_dir: Path, repo_root: Path) -> list[dict[str, Any]]:
    """Walk subagents_dir, build a SubAgent TypedDict for each subdirectory that has
    both AGENTS.md and deepagents.toml. AGENTS.md becomes the system_prompt; the
    [agent] block in deepagents.toml provides name/description/skills; the [model]
    block (optional) provides a per-subagent model override.
    """
    subagents: list[dict[str, Any]] = []
    if not subagents_dir.is_dir():
        return subagents
    for sub_dir in sorted(subagents_dir.iterdir()):
        if not sub_dir.is_dir() or sub_dir.name.startswith("_") or sub_dir.name.startswith("."):
            continue
        agents_md = sub_dir / "AGENTS.md"
        toml_path = sub_dir / "deepagents.toml"
        if not (agents_md.exists() and toml_path.exists()):
            continue
        sub_cfg = load_config(toml_path)
        agent_block = sub_cfg.get("agent", {})
        model_block = sub_cfg.get("model", {})

        sub: dict[str, Any] = {
            "name": agent_block.get("name", sub_dir.name),
            "description": agent_block.get("description", ""),
            "system_prompt": agents_md.read_text(encoding="utf-8"),
        }
        skill_paths = agent_block.get("skills", [])
        if skill_paths:
            sub["skills"] = [str((repo_root / p).resolve()) for p in skill_paths]
        if model_block and model_block.get("name"):
            from loom_sdk.providers.model_registry import resolve_model

            try:
                sub["model"] = resolve_model(model_block)
            except Exception as e:
                # Don't crash the agent build if one subagent has a misconfigured
                # model — log and let the subagent inherit the orchestrator's model.
                import logging

                logging.getLogger("agent").warning(
                    "subagent %s: model resolve failed (%s); inheriting orchestrator model",
                    sub.get("name"),
                    e,
                )
        subagents.append(sub)
    return subagents
