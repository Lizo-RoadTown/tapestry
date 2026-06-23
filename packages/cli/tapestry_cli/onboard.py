"""`loom onboard` — `init` + writes `.claude/settings.json` with the tapestry plugins enabled.

Wraps `loom init` so a single command does everything `loom init` does PLUS:

- writes `.claude/settings.json` with `tapestry-discipline@tapestry` and
  `tapestry-patterns@tapestry` enabled (idempotent merge if the file
  already exists)
- prints a 2-step epilogue covering the operator actions that have to
  happen inside Claude Code (plugin install + IDE reload)

Argument surface is identical to `loom init` — see `init.add_arguments`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tapestry_cli import init as init_cmd


# The two plugins the consolidated `tapestry` marketplace ships.
# These names are the install identifiers (per
# tapestry/.claude-plugin/marketplace.json), distinct from the runtime
# emission strings the hook scripts still produce ([loom-discipline]) —
# see feedback_plugin_install_name_vs_runtime_emission_string_2026_06_22.
TAPESTRY_PLUGINS = (
    "tapestry-discipline@tapestry",
    "tapestry-patterns@tapestry",
)


def _write_claude_settings(project_dir: Path) -> None:
    """Ensure `.claude/settings.json` has both tapestry plugins enabled.

    Idempotent: merges into existing `enabledPlugins` if the file is
    present; creates a minimal one if absent. Other settings (permissions,
    etc.) are preserved.
    """
    settings_dir = project_dir / ".claude"
    settings_dir.mkdir(exist_ok=True)
    settings_path = settings_dir / "settings.json"

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  WARN: {settings_path} exists but couldn't be parsed ({e}).")
            print(f"        Skipping merge. Add the plugins manually:")
            for plugin in TAPESTRY_PLUGINS:
                print(f'          "{plugin}": true')
            return

        enabled = existing.setdefault("enabledPlugins", {})
        changed = False
        for plugin in TAPESTRY_PLUGINS:
            if enabled.get(plugin) is not True:
                enabled[plugin] = True
                changed = True
                print(f"  enabled {plugin} in {settings_path}")
        if not changed:
            print(f"  both tapestry plugins already enabled in {settings_path}")
            return
        settings_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        return

    # Create fresh
    config = {"enabledPlugins": {plugin: True for plugin in TAPESTRY_PLUGINS}}
    settings_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {settings_path}")


def _print_operator_epilogue() -> None:
    """Print the 2 manual steps that can't be automated from CLI."""
    print()
    print("==> Two more steps (operator):")
    print()
    print("  1. In Claude Code chat, register the tapestry marketplace + install the plugins:")
    print()
    print("       /plugin marketplace add Lizo-RoadTown/tapestry")
    print("       /plugin install tapestry-discipline@tapestry")
    print("       /plugin install tapestry-patterns@tapestry")
    print()
    print("  2. Reload the IDE so the new hooks bind:")
    print()
    print("       VS Code:        Cmd+Shift+P → 'Developer: Reload Window'")
    print("       Claude Code CLI: exit + restart `claude` in this project")
    print()
    print("That's it. The SessionStart hook will auto-recall memories on next session start.")


def add_arguments(p: argparse.ArgumentParser) -> None:
    """Same argument surface as `loom init` — delegated to it."""
    init_cmd.add_arguments(p)


def run(args: argparse.Namespace) -> int:
    """Run `loom init`, then write `.claude/settings.json`, then print operator steps."""
    rc = init_cmd.run(args)
    if rc != 0:
        return rc

    print()
    print(f"--> [extra] Write .claude/settings.json with tapestry plugins enabled...")
    _write_claude_settings(Path.cwd())

    _print_operator_epilogue()
    return 0
