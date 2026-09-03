"""Configuration for self-observer scans.

What it scans, where it writes, what counts as a signal.

Home: tapestry/services/self-observer/config.py (migrated from the-loom
legacy source — CORE DIRECTIVE 2 Lift/Refactor). This service stands alone:
it talks to GitHub (scan) and two Tapestry HTTP services (project-registry
for target discovery, architecture-registry for candidate emission). No
runtime dependency on the-loom or Make_Skills.

## Scan targets = static core + dynamic discovery

The set of repos scanned each pass is:

  1. STATIC CORE (`static_core_targets()`): the platform's own pattern homes —
     tapestry itself and the public marketplace. Always scanned.
  2. DYNAMIC (`registry_client.discover_targets()`): every repo registered
     under every project in the project-registry. This is what makes the
     observer registry-driven — registering a consuming project is enough to
     get its skills/agents observed; no code change here.

Everything EXCEPT the repo list stays config-driven: weights, EMIT_THRESHOLD,
excludes, skip-self, and the paths scanned inside a discovered consuming repo.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegistryTarget:
    """One GitHub repo (and the paths inside it) that self-observer scans.

    Each (repo, path) pair is treated independently for signal detection. The
    same file appearing under two targets is deduped at candidate emission
    time via content_hash, not at the target level.

    project_id: the architecture-registry project this repo's candidates
        belong to. Set from the project-registry for discovered repos; set
        from env/known-map for static core; None falls back to
        default_project_id() at emit time.
    """

    repo: str  # "Lizo-RoadTown/tapestry"
    paths: tuple[str, ...]  # ("engine", "integrations/...")
    branch: str = "main"
    project_id: str | None = None


# ---------------------------------------------------------------------------
# Static core — the platform's own pattern homes. Always scanned.
# ---------------------------------------------------------------------------

# Paths inside tapestry that hold the canonical patterns library + engine.
_TAPESTRY_PATHS: tuple[str, ...] = (
    "integrations/claude-code/tapestry-patterns/skills",
    "integrations/claude-code/tapestry-patterns/agents",
    "engine",
)

# Paths inside the public marketplace: each plugin exposes skills/ + agents/.
_MARKETPLACE_PATHS: tuple[str, ...] = (
    "plugins",  # walked recursively; plugins/*/skills and plugins/*/agents land underneath
)

# Known architecture-registry project_ids for the static-core repos.
# marketplace was verified in the legacy config (2026-06-13). tapestry's own
# project_id is not known here — it falls back to default_project_id() unless
# TAPESTRY_PROJECT_ID is set. FLAG FOR OPERATOR: register tapestry in the
# project-registry (or set TAPESTRY_PROJECT_ID) so its candidates land under
# the right project rather than the platform default.
_MARKETPLACE_PROJECT_ID = "17e3f41a-6c79-471b-a22d-b330d9dddfe8"


def static_core_targets() -> tuple[RegistryTarget, ...]:
    """The always-scanned platform-owned repos. Reads env for project_ids."""
    return (
        RegistryTarget(
            repo="Lizo-RoadTown/tapestry",
            paths=_TAPESTRY_PATHS,
            project_id=os.environ.get("TAPESTRY_PROJECT_ID"),
        ),
        RegistryTarget(
            repo="Lizo-RoadTown/claude-skills-marketplace",
            paths=_MARKETPLACE_PATHS,
            project_id=os.environ.get(
                "MARKETPLACE_PROJECT_ID", _MARKETPLACE_PROJECT_ID
            ),
        ),
    )


# Default paths scanned inside a dynamically-discovered consuming repo. The
# project-registry Repo model (services/project-registry/models.py:87-93)
# carries only url + default_branch — no path list — so the observer applies
# this convention-based set to every discovered repo. Covers both the
# plugin-style layout and the project-starter `.claude/` layout.
CONSUMING_REPO_DEFAULT_PATHS: tuple[str, ...] = (
    "skills",
    "agents",
    ".claude/skills",
    ".claude/agents",
    "plugins",
)


# Path patterns to exclude even if they fall under a scanned target.
# Vendored / archive / deprecated dirs that are not platform-authored source.
# Matched as substring against file_path.
EXCLUDE_PATH_PATTERNS: tuple[str, ...] = (
    "_upstream/",            # vendored from anthropics/skills, not authored here
    "anthropics-skills/",    # same
    "deprecated/",           # top-level archives
    "docs/_archive/",        # historical proposals
    "node_modules/",         # JS dep dir (defensive)
    "__pycache__/",          # Python bytecode (defensive)
)


@dataclass(frozen=True)
class Endpoints:
    """Where the observer reads from / writes to. All env-driven.

    candidate_registry_url: architecture-registry — candidate POST target.
        Env: TAPESTRY_ARCHITECTURE_REGISTRY_URL || LOOM_ARCHITECTURE_REGISTRY_URL.
    project_registry_url: project-registry — dynamic target discovery.
        Env: TAPESTRY_REGISTRY_URL || LOOM_PROJECT_REGISTRY_URL.

    Defaults point at the EXISTING deployed services so restored data appends
    to what is already there and the dashboard keeps working.
    """

    candidate_registry_url: str
    telemetry_query_url: str
    memory_url: str  # loom-agent-context REST surface (/v1/write + /v1/read)
    project_registry_url: str = "https://loom-project-registry.onrender.com"

    @classmethod
    def from_env(cls) -> "Endpoints":
        return cls(
            candidate_registry_url=(
                os.environ.get("TAPESTRY_ARCHITECTURE_REGISTRY_URL")
                or os.environ.get("LOOM_ARCHITECTURE_REGISTRY_URL")
                or "https://loom-architecture-registry.onrender.com"
            ),
            project_registry_url=(
                os.environ.get("TAPESTRY_REGISTRY_URL")
                or os.environ.get("LOOM_PROJECT_REGISTRY_URL")
                or "https://loom-project-registry.onrender.com"
            ),
            telemetry_query_url=os.environ.get(
                "TELEMETRY_QUERY_URL",
                "https://loom-telemetry-ingestion.onrender.com",
            ),
            memory_url=os.environ.get(
                "LOOM_MEMORY_URL",
                "https://loom-agent-context.onrender.com",
            ),
        )


@dataclass(frozen=True)
class AuthConfig:
    """Auth tokens. Self-host mode: no JWT, endpoint resolves to SELF_HOST_TENANT_ID.

    - github_token (GITHUB_TOKEN): sent as a Bearer to the GitHub API so the
      private consuming repos are readable. Absent → public-only scan at a low
      rate limit.
    - observer_jwt (OBSERVER_JWT): sent as a Bearer to BOTH Tapestry services
      (project-registry discovery + architecture-registry emission + memory).
      Absent → no Authorization header → the receiver resolves the request to
      its SELF_HOST_TENANT_ID (self-host mode). Not a new scheme — this is the
      existing auth_bridge.verify_bearer contract.
    """

    github_token: str | None = field(default=None)  # GITHUB_TOKEN env var
    observer_jwt: str | None = field(default=None)  # OBSERVER_JWT env var (optional)

    @classmethod
    def from_env(cls) -> "AuthConfig":
        return cls(
            github_token=os.environ.get("GITHUB_TOKEN"),
            observer_jwt=os.environ.get("OBSERVER_JWT"),
        )


# Signal-rule weights.
# Higher confidence → more likely to surface as a candidate without rejection.
# Tuned during the E1.5 unit tests (see tests/test_signal_rules.py).
SIGNAL_WEIGHTS: dict[str, float] = {
    "multi_step_artifact": 0.4,  # "produces a tradeoff matrix", "outputs a report"
    "explicit_probe_verb": 0.3,  # "probes the repo", "walks the directory"
    "tool_list_in_description": 0.3,  # description names tools (roadmap-maintenance signal)
    "executes_external": 0.3,  # "executes the build", "deploys", "runs the harness"
    "continuous_operation": 0.2,  # "Use continuously, not as a one-shot"
    "identify_and_recommend": 0.4,  # "Identify X and recommend Y" (orchestration-cataloging shape)
    "observe_identify_promote_loop": 0.6,  # "observe... identify... promote" — three-step autonomous loop (agentic-upskilling shape)
    "pure_io_transform": 0.5,  # tool signal: "convert X to Y", "render X as Y"
    "methodology_use_before": -0.4,  # skill signal: "Use BEFORE every X"
    "methodology_template": -0.3,  # skill signal: "fixed section layout"
    "methodology_pattern_for": -0.3,  # skill signal: "Pattern for...", "Methodology for..."
}

# Confidence threshold above which a candidate is emitted.
#
# 0.3 (lowered from 0.5 during E1.5) so single-signal agent matches — common
# for the Group C fixtures, each matching exactly ONE rule worth 0.2-0.4 —
# still emit. Trade-off: more false positives (each ~5s to reject) vs. false
# negatives (invisible, accumulate as silent drift). Tilts toward surfacing.
EMIT_THRESHOLD: float = 0.3


# Fallback architecture-registry project_id for a scanned repo whose project
# is not otherwise known (static-core repo without an env-set id, or a
# discovered repo missing its registry project id). Env-overridable via
# TAPESTRY_DEFAULT_PROJECT_ID. The baked default is the platform tenant the
# legacy observer emitted under, kept so restored candidates land in the same
# place the dashboard already reads. It is a bare UUID constant — NOT an
# import of or runtime call into the-loom.
_BAKED_DEFAULT_PROJECT_ID = "63846bc6-4519-4216-8d71-c7df71290eb9"


def default_project_id() -> str:
    """Fallback project_id for repos with no known project."""
    return os.environ.get("TAPESTRY_DEFAULT_PROJECT_ID", _BAKED_DEFAULT_PROJECT_ID)


def project_id_for(target_project_id: str | None) -> str:
    """Resolve a target's project_id, falling back to the platform default."""
    return target_project_id or default_project_id()
