"""
Pillar 1B step 6 — per-(tenant, agent_id) deepagents instantiation.

Replaces the singleton built in api/agent.py for the case where the
student is chatting with one of THEIR built agents (rather than the
platform-default guide-shaped agent). The default agent stays the
singleton; per-agent instances are built on demand from a saved
`user_agents` row + its skills + the tenant's decrypted API key.

Cache layers:
  _agent_configs   : (tenant_id, agent_id) -> AgentConfig
  _built_agents    : (tenant_id, agent_id) -> compiled deepagents instance
  _provider_clients: (tenant_id, provider, model) -> ChatModel (future TTL eviction)
  _compiled_skills : (skill_id, version) -> Tool (immutable per version)

See docs/proposals/pillar-1b-agent-runtime.md.

Step 7 (skill compilation) is bundled with step 6 since per-agent
runtime is pointless without working skills. Step 8 (MCP integration
loading) is deferred — agents without integrations work fine.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from uuid import UUID

from loom_auth import TenantContext
from loom_sdk.db import tenant_conn

log = logging.getLogger("runtime")


@dataclass(frozen=True)
class StudentSkill:
    """One row of student_skills materialized into the runtime."""

    id: UUID
    name: str
    description: str
    body_md: str
    version: int


@dataclass(frozen=True)
class StudentIntegration:
    """One row of student_integrations materialized into the runtime."""

    id: UUID
    mcp_server_slug: str
    config: dict


@dataclass(frozen=True)
class AgentConfig:
    """Everything the runtime needs to instantiate a student-built agent.

    `api_key` is the decrypted secret for `provider`. Populated by
    _get_config from student_secrets via pgp_sym_decrypt. None means
    no key stored — caller must handle (likely fall back to provider's
    env-var key or error out with a clear message).
    """

    id: UUID
    tenant_id: UUID
    name: str
    starter: str
    provider: str
    model: str | None
    persona: str | None
    api_key: str | None
    skills: list[StudentSkill] = field(default_factory=list)
    integrations: list[StudentIntegration] = field(default_factory=list)


class AgentRuntime:
    """Per-(tenant, agent_id) deepagents instantiation.

    Built once at FastAPI startup, replaces the singleton's role for
    student-built agents. The platform-default agent (the guide's
    speech model) continues to be built by api/agent.build_agent.

    Cache layers (all gated by TTL/size eviction in later steps):

      _agent_configs   : (tenant_id, agent_id) -> AgentConfig
                         Invalidated when user_agents / student_skills /
                         student_integrations rows change for that key.

      _provider_clients: (tenant_id, provider, model) -> ChatModel
                         Filled in step 5 when chat() actually
                         instantiates models.

      _compiled_skills : (skill_id, version) -> Tool
                         Filled in step 7. Skills are immutable per
                         version, so eviction is rarely needed.

      _mcp_clients     : (tenant_id, integration_id) -> MCPClient
                         Filled in step 8 with idle keepalive + per-
                         tenant hard caps.
    """

    def __init__(
        self,
        default_agent: object | None = None,
        checkpointer: object | None = None,
    ) -> None:
        # The singleton deepagents instance built by api/agent.build_agent
        # at FastAPI startup. Used for agent_id=None (the platform-default
        # guide-shaped agent).
        self._default_agent = default_agent

        # Shared checkpointer (TenantScopedSaver) used when building per-
        # agent instances. Same pool as the default agent — thread_ids
        # are UUIDs so collisions are impossible.
        self._checkpointer = checkpointer

        # Simple dicts for the skeleton. Step 9 swaps in TTL/LRU caches
        # (cachetools or equivalent) once we have observation data for
        # sizing.
        self._agent_configs: dict[tuple[str, str], AgentConfig] = {}
        self._built_agents: dict[tuple[str, str], object] = {}
        self._provider_clients: dict[tuple[str, str, str], object] = {}
        self._compiled_skills: dict[tuple[str, int], object] = {}
        self._mcp_clients: dict[tuple[str, str], object] = {}

    # ---- Config loading ----

    async def _get_config(
        self, ctx: TenantContext, agent_id: UUID
    ) -> AgentConfig | None:
        """Load an AgentConfig from the DB. Returns None if no row matches
        (deleted, wrong tenant, or unknown UUID).

        All queries run through tenant_conn so RLS enforces tenant
        scoping at the SQL layer — passing a stale tenant_id can't
        produce another tenant's data.

        api_key is the decrypted secret for the agent's chosen provider.
        Pulled via pgp_sym_decrypt(encrypted_value, current_setting('app.secrets_key')).
        When MAKE_SKILLS_SECRETS_KEY isn't set on the deployment, the
        GUC is unset and the SELECT returns NULL — caller must handle.
        """
        cache_key = (ctx.tenant_id, str(agent_id))
        cached = self._agent_configs.get(cache_key)
        if cached is not None:
            return cached

        async with tenant_conn(ctx) as conn:
            # ---- user_agents row ----
            cur = await conn.execute(
                """
                SELECT id, name, starter, provider, model, persona
                FROM user_agents
                WHERE id = %s::uuid AND deleted_at IS NULL
                """,
                (str(agent_id),),
            )
            row = await cur.fetchone()
            if not row:
                return None
            agent_id_uuid, name, starter, provider, model, persona = row

            # ---- student_skills rows ----
            cur = await conn.execute(
                """
                SELECT id, name, description, body_md, version
                FROM student_skills
                WHERE agent_id = %s::uuid
                ORDER BY created_at
                """,
                (str(agent_id),),
            )
            skill_rows = await cur.fetchall()
            skills = [
                StudentSkill(
                    id=r[0],
                    name=r[1],
                    description=r[2],
                    body_md=r[3],
                    version=r[4],
                )
                for r in skill_rows
            ]

            # ---- student_integrations rows ----
            cur = await conn.execute(
                """
                SELECT id, mcp_server_slug, config_json
                FROM student_integrations
                WHERE agent_id = %s::uuid
                ORDER BY created_at
                """,
                (str(agent_id),),
            )
            integ_rows = await cur.fetchall()
            integrations = [
                StudentIntegration(
                    id=r[0],
                    mcp_server_slug=r[1],
                    config=r[2] or {},
                )
                for r in integ_rows
            ]

            # ---- decrypted API key for the agent's provider ----
            # pgp_sym_decrypt returns NULL if app.secrets_key isn't set
            # OR if no matching row exists. Both cases produce api_key=None
            # which the runtime handles by falling back to env vars or
            # erroring out with a clear message at chat time.
            cur = await conn.execute(
                """
                SELECT pgp_sym_decrypt(
                    encrypted_value,
                    current_setting('app.secrets_key', true)
                )
                FROM student_secrets
                WHERE provider_slug = %s
                """,
                (provider,),
            )
            secret_row = await cur.fetchone()
            api_key = secret_row[0] if secret_row else None

        config = AgentConfig(
            id=agent_id_uuid,
            tenant_id=UUID(ctx.tenant_id),
            name=name,
            starter=starter,
            provider=provider,
            model=model,
            persona=persona,
            api_key=api_key,
            skills=skills,
            integrations=integrations,
        )
        self._agent_configs[cache_key] = config
        return config

    def invalidate_agent(self, tenant_id: str, agent_id: UUID) -> None:
        """Drop cached config + built instance for a (tenant, agent) pair.
        Called by agent/skill/integration write endpoints after a save
        so the next chat call rebuilds from fresh DB state."""
        key = (tenant_id, str(agent_id))
        self._agent_configs.pop(key, None)
        self._built_agents.pop(key, None)

    # ---- Internal: build a deepagents instance from saved config ----

    def _build_agent_from_config(
        self,
        config: "AgentConfig",
        *,
        source_tenant_id: str | None = None,
    ) -> object:
        """Materialize a per-student agent from its AgentConfig.

        Resolves the LLM provider with the student's decrypted key (or
        falls back to platform env vars if the student hasn't set one
        for this provider). Compiles each saved skill into a callable
        tool. Wires the persona as the agent's instructions/system
        prompt. Uses the shared checkpointer so threads persist.

        Telemetry (PR-prep-1): when `source_tenant_id` is provided (the
        loom-side UUID, resolved upstream by `_resolve_agent` via
        `tenant_mapping.lookup_source_tenant`), each compiled skill
        emits a TelemetryEvent to the in-process collector on invocation.
        Passed as a kwarg to keep this method sync — the async lookup
        happens in `_resolve_agent` before calling here.
        """
        from deepagents import create_deep_agent

        from loom_sdk.providers.model_registry import RECOMMENDED_STARTERS, resolve_model
        from skill_compiler.compiler import compile_skill_to_tool

        # Resolve model. Use the agent's saved model, falling back to
        # the platform's recommended starter for that provider if the
        # agent has no model set (older rows or "use default").
        model_name = config.model or RECOMMENDED_STARTERS.get(config.provider)
        if not model_name:
            raise RuntimeError(
                f"No model configured for provider {config.provider!r} "
                f"and no recommended starter — set agent.model on save."
            )

        model_cfg: dict[str, Any] = {"provider": config.provider, "name": model_name}
        if config.api_key:
            # model_registry's resolvers accept api_key via **kwargs; most
            # providers map it to their SDK's `api_key` parameter.
            model_cfg["api_key"] = config.api_key

        model = resolve_model(model_cfg)

        # Compile skills to tools. Each skill becomes a callable named
        # by skill.name; the LLM picks among them by their `description`.
        # `source_tenant_id` + `model_name` are baked into each tool's
        # closure so telemetry events carry the correct identifiers at
        # invocation time without reading ambient context.
        tools = [
            compile_skill_to_tool(
                skill,
                model,
                source_tenant_id=source_tenant_id,
                model_name=model_name,
            )
            for skill in config.skills
        ]

        # Build the deepagents instance. Persona becomes the agent's
        # instructions. No subagents — those are platform-level (the
        # default agent uses them); per-student agents are flat.
        kwargs: dict[str, Any] = {
            "model": model,
            "tools": tools,
        }
        if config.persona:
            kwargs["instructions"] = config.persona
        if self._checkpointer is not None:
            kwargs["checkpointer"] = self._checkpointer

        return create_deep_agent(**kwargs)

    # ---- Internal: resolve which deepagents instance to use ----

    async def _resolve_agent(
        self, ctx: TenantContext, agent_id: UUID | None
    ) -> object:
        """Returns the deepagents instance to invoke for this call.

        agent_id=None  → the platform-default singleton (the guide-shaped
                         agent built by api/agent.build_agent at startup).
        agent_id=<UUID> → load the student's saved config and either return
                          a cached compiled instance or build a fresh one.
        """
        if agent_id is None:
            if self._default_agent is None:
                raise RuntimeError(
                    "AgentRuntime has no default_agent — pass it in "
                    "during FastAPI lifespan setup."
                )
            return self._default_agent

        # Check cache first
        key = (ctx.tenant_id, str(agent_id))
        cached = self._built_agents.get(key)
        if cached is not None:
            return cached

        # Load config + build
        config = await self._get_config(ctx, agent_id)
        if config is None:
            raise ValueError(
                f"Agent {agent_id} not found in tenant {ctx.tenant_id} "
                f"(deleted, wrong tenant, or never created)."
            )

        # Reverse-look-up the source-side tenant UUID for telemetry.
        # The TelemetryEvent's tenant_id field carries the loom-side UUID
        # (the consumer scopes by it), NOT the engine_tenant_id. Done
        # here (async, once per cache miss) rather than per-invocation.
        # If the tenant has no mapping row, source_tenant_id stays None
        # and telemetry is silently skipped — see lookup_source_tenant's
        # docstring for the rationale.
        source_tenant_id: str | None = None
        try:
            from loom_sdk.db import get_pool
            from skill_making.tenant_mapping import lookup_source_tenant

            source_tenant_id = await lookup_source_tenant(
                get_pool(), ctx.tenant_id, source_system="loom"
            )
        except Exception:
            # Resolution failures (DB blip, pool not initialised in tests)
            # MUST NOT block agent invocation. Telemetry silently degrades.
            log.debug(
                "lookup_source_tenant failed for tenant=%s; telemetry "
                "will be skipped for this agent build",
                ctx.tenant_id,
                exc_info=True,
            )

        agent = self._build_agent_from_config(
            config, source_tenant_id=source_tenant_id
        )
        self._built_agents[key] = agent
        log.info(
            "built per-agent runtime: tenant=%s agent=%s provider=%s "
            "skills=%d telemetry=%s",
            ctx.tenant_id, agent_id, config.provider, len(config.skills),
            "on" if source_tenant_id else "off",
        )
        return agent

    # ---- Chat surface ----

    async def chat(
        self,
        ctx: TenantContext,
        agent_id: UUID | None,
        thread_id: str,
        message: str,
    ) -> dict:
        """Single-shot chat. Returns {'response': str}.

        Caller (the FastAPI endpoint) handles thread-belongs-to-tenant
        gating, current_tenant ContextVar setting, and the fire-and-
        forget memory recorder. This method only owns agent invocation.
        """
        agent = await self._resolve_agent(ctx, agent_id)
        config = {
            "configurable": {"thread_id": thread_id, "tenant_id": ctx.tenant_id}
        }
        result = await agent.ainvoke(  # type: ignore[attr-defined]
            {"messages": [{"role": "user", "content": message}]},
            config=config,
        )
        final = (
            result["messages"][-1]
            if isinstance(result, dict) and "messages" in result
            else result
        )
        response_text = getattr(final, "content", None) or str(final)
        return {"response": response_text}

    async def stream(
        self,
        ctx: TenantContext,
        agent_id: UUID | None,
        thread_id: str,
        message: str,
    ) -> AsyncIterator[object]:
        """Streamed chat. Yields raw chunks from deepagents.astream;
        caller is responsible for serializing them into SSE."""
        agent = await self._resolve_agent(ctx, agent_id)
        config = {
            "configurable": {"thread_id": thread_id, "tenant_id": ctx.tenant_id}
        }
        async for chunk in agent.astream(  # type: ignore[attr-defined]
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            stream_mode="messages",
        ):
            yield chunk
