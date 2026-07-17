"""
Read-only inspector for the subagents in subagents/. Surfaces metadata
(name, description, model, skills, persona) to the dashboard's /agents
page. Distinct from agent.py's load_subagents which builds runtime
SubAgent dicts; this returns a JSON-serializable shape for the UI.

Self-host edits the underlying AGENTS.md / deepagents.toml files in
the IDE; hosted-multitenant will eventually persist per-tenant
overrides in a tenant_subagents table (Phase 2b ships filesystem-only).
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(os.environ.get("AGENT_REPO_ROOT", "/repo")).resolve()


def list_subagents() -> list[dict[str, Any]]:
    """One entry per subagent directory under subagents/."""
    base = REPO_ROOT / "subagents"
    if not base.is_dir():
        return []

    out: list[dict[str, Any]] = []
    for sub_dir in sorted(base.iterdir()):
        if not sub_dir.is_dir() or sub_dir.name.startswith("_") or sub_dir.name.startswith("."):
            continue
        agents_md = sub_dir / "AGENTS.md"
        toml_path = sub_dir / "deepagents.toml"
        if not (agents_md.exists() and toml_path.exists()):
            continue

        try:
            with open(toml_path, "rb") as f:
                cfg = tomllib.load(f)
        except Exception:
            continue

        agent_block = cfg.get("agent", {})
        model_block = cfg.get("model", {})

        out.append(
            {
                "slug": sub_dir.name,
                "name": agent_block.get("name", sub_dir.name),
                "description": agent_block.get("description", ""),
                "skills": agent_block.get("skills", []),
                "model": {
                    "provider": model_block.get("provider"),
                    "name": model_block.get("name"),
                },
                "persona_excerpt": _first_paragraph(
                    agents_md.read_text(encoding="utf-8", errors="replace")
                ),
            }
        )
    return out


def get_subagent(slug: str) -> dict[str, Any]:
    """Full detail for one subagent (slug = directory name)."""
    base = REPO_ROOT / "subagents"
    sub_dir = (base / slug).resolve()
    try:
        sub_dir.relative_to(base)
    except ValueError:
        raise PermissionError(f"path escapes base: {slug}")
    if not sub_dir.is_dir():
        raise FileNotFoundError(f"no subagent: {slug}")

    agents_md = sub_dir / "AGENTS.md"
    toml_path = sub_dir / "deepagents.toml"
    if not (agents_md.exists() and toml_path.exists()):
        raise FileNotFoundError(f"subagent {slug} missing required files")

    with open(toml_path, "rb") as f:
        cfg = tomllib.load(f)

    return {
        "slug": slug,
        "name": cfg.get("agent", {}).get("name", slug),
        "description": cfg.get("agent", {}).get("description", ""),
        "skills": cfg.get("agent", {}).get("skills", []),
        "model": {
            "provider": cfg.get("model", {}).get("provider"),
            "name": cfg.get("model", {}).get("name"),
        },
        "persona": agents_md.read_text(encoding="utf-8", errors="replace"),
        "raw_toml": toml_path.read_text(encoding="utf-8", errors="replace"),
    }


def _first_paragraph(text: str) -> str:
    """First non-empty paragraph after the title — used for the list-card excerpt."""
    lines = text.splitlines()
    in_para = False
    para: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if not stripped:
            if in_para:
                break
            continue
        in_para = True
        para.append(stripped)
        if len(" ".join(para)) > 280:
            break
    text = " ".join(para)
    return text[:280] + ("…" if len(text) > 280 else "")
