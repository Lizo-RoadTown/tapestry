# Single Python image used by both the api and ui services.
# The compose file picks the entrypoint per service.

FROM python:3.12-slim

# System deps for psycopg (Postgres driver) and document parsing libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps. The platform/requirements.txt is the source of truth.
COPY platform/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the runtime code. Post-Phase-5 layout:
#   core/     — universal engine logic (runtime, auth, db, providers, etc.)
#   services/ — API + admin surfaces (services/api/main.py is the uvicorn target)
#   adapters/ — project-type adapters (Layer 2; stub-only today)
COPY core /app/core
COPY services /app/services
COPY adapters /app/adapters

# Bake in skills, subagents, and root config. In local docker-compose these
# are SHADOWED by the read-only volume mount at /repo (so edits hot-reload).
# In Render (no volume mount), the COPY here is what the agent reads —
# AGENT_REPO_ROOT is set to /app on Render and /repo locally.
COPY skills /app/skills
COPY subagents /app/subagents
COPY AGENTS.md /app/AGENTS.md
COPY deepagents.toml /app/deepagents.toml
COPY .mcp.json /app/.mcp.json

# Default command:
#   - Local docker-compose: overridden by `command:` in docker-compose.yml (port 8001)
#   - Render: respects $PORT (typically 10000); falls back to 8001 if unset
CMD ["sh", "-c", "exec uvicorn services.api.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
