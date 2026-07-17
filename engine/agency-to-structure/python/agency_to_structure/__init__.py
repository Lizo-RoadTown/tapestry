"""agency_to_structure: Tapestry's recursive-skill runtime engine.

Lifted from Make_Skills/core/{runtime,orchestration} per audit §2.2
(2026-06-22). Three modules:

- ``agent`` — ``build_agent()`` integration with deepagents + PostgresSaver
- ``runtime`` — per-(tenant, agent_id) instantiation; skill + provider cache
- ``subagents`` — in-process dispatch

INTEGRATION STATUS — NOT YET RUNTIME-WIRED.

These modules import cleanly but have TWO function-local imports that
need follow-up before a service can call them:

1. ``agent.build_agent`` imports ``from core.db import migrations`` at the
   point where it calls ``migrations.run_all(pool)``. tapestry/infra/migrations/
   + tapestry/scripts/apply_migration.py serve this role today; the call
   needs to be rewired or migrated to a ``loom_sdk.migrations`` module.

2. ``agent.build_agent`` imports ``from services.admin.roadmap.tools``
   for the built-in tool set. ``services/admin/`` was NOT lifted in audit
   §2.2; it belongs with audit §2.1 (subagents + roadmap-maintenance MCP
   wrapping) which is DEFERRED to Step 8 territory.

Both are marked with ``TODO(audit §2.2 integration)`` comments at the
relevant call sites.

Lift adaptations applied:
- ``core.auth.auth.TenantContext`` → ``loom_auth.TenantContext``
- ``core.db.db.tenant_conn`` / ``get_pool`` → ``loom_sdk.db.tenant_conn`` / ``get_pool``
- ``core.auth.tenant_context.current_tenant`` → ``loom_auth.langgraph_tenant_ctx``
  (the ContextVar was renamed in PR-3 to make the LangGraph chokepoint
  role explicit; aliased locally as ``current_tenant`` in agent.py to
  preserve call-site code)
- ``core.providers.model_registry`` → ``loom_sdk.providers.model_registry``
- ``core.skill_making.compiler`` → ``skill_compiler.compiler``
- ``services.skill_making.tenant_mapping`` → ``skill_making.tenant_mapping``
"""

__all__: list[str] = []
