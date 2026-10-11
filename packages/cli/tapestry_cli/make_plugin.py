"""`tapestry make-plugin <name>` — scaffold a personalized Claude Code plugin.

Emits a self-contained plugin + single-plugin marketplace that the operator
publishes to THEIR OWN GitHub repo and points at THEIR OWN backend. Nothing
personal to anyone else is baked in: the memory endpoint is env-driven with a
placeholder fallback, and the author is the operator.

The universal `tapestry-discipline` plugin is the always-on baseline (PROBE
reminders, citation, audit — no backend). This scaffold is the project-specific
layer: a behavior-only PreToolUse guard to customize for the project's shape,
plus an optional env-gated memory wiring. See the `plugin-authoring` skill in
tapestry-patterns for the full author-and-publish workflow.

Stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

# The node launcher is generic (finds Python, runs scripts/<name>.py, passes
# stdin, propagates exit code). Reused verbatim from the universal plugin.
_RUN_PYTHON_MJS = r'''#!/usr/bin/env node
/**
 * run-python.mjs — Node launcher for the Python hook scripts.
 * Claude Code guarantees Node on PATH but not Python; this finds Python and
 * invokes scripts/<name>.py, piping stdin through and propagating exit codes.
 *   node "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.mjs" <script_basename>
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT || dirname(__dirname);
const scriptName = process.argv[2];
if (!scriptName) { console.error("run-python.mjs: missing script name"); process.exit(0); }
const pythonScript = join(pluginRoot, "scripts", `${scriptName}.py`);
if (!existsSync(pythonScript)) { console.error(`run-python.mjs: not found: ${pythonScript}`); process.exit(0); }

const isWindows = process.platform === "win32";
const candidates = isWindows
  ? [["py", ["-3", pythonScript]], ["python", [pythonScript]], ["python3", [pythonScript]]]
  : [["python3", [pythonScript]], ["python", [pythonScript]]];

let stdinBuf = Buffer.alloc(0);
try { const fs = await import("node:fs"); stdinBuf = fs.readFileSync(0); } catch {}

let lastExitCode = 0, invoked = false;
for (const [cmd, args] of candidates) {
  try {
    const result = spawnSync(cmd, args, { input: stdinBuf, stdio: ["pipe", "inherit", "inherit"] });
    if (result.error && result.error.code === "ENOENT") continue;
    invoked = true; lastExitCode = result.status ?? 0; break;
  } catch { continue; }
}
if (!invoked) { console.error("run-python.mjs: no Python on PATH; hook skipped, not blocking."); process.exit(0); }
process.exit(lastExitCode);
'''

_HOOKS_JSON = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Edit|Write|MultiEdit",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'node "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.mjs" pre_tool_use',
                        "timeout": 10,
                    }
                ],
            }
        ]
    }
}


def _pre_tool_use_py(name: str) -> str:
    return f'''"""{name} — PreToolUse guard (behavior-only, no backend calls).

Customize the checks below for THIS project's shape. Emits a soft reminder via
additionalContext; never blocks by default (exit 0). Exit 2 to block a tool
call (Claude Code hook protocol). Keep it behavior-only so it works for any
operator with no backend configured.
"""
import json
import sys


def main() -> int:
    try:
        # Read bytes + decode UTF-8 explicitly; sys.stdin decodes cp1252 on Windows,
        # which garbles non-ASCII hook input (e.g. em dashes).
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    except Exception:  # never raise from a hook
        return 0

    # TODO: add project-specific guards here. Example checks you might add:
    #   - warn when editing a load-bearing file
    #   - require a test alongside a source change
    #   - block edits to a generated/vendored directory (return exit 2)
    _tool = data.get("tool_name", "")

    reminder = (
        "[{name}] PROBE before editing: confirm the change matches this "
        "project's conventions; cite file:line for any pattern you copy."
    ).format(name="{name}")

    print(json.dumps({{
        "hookSpecificOutput": {{
            "hookEventName": "PreToolUse",
            "additionalContext": reminder,
        }}
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''.replace("{name}", name)


def _plugin_json(name: str, author: str, with_memory: bool = False) -> dict:
    manifest = {
        "name": name,
        "description": (
            f"Personalized Tapestry discipline plugin for {name}. Project-specific "
            "guards. The universal tapestry-discipline plugin is the always-on "
            "baseline; this is the project layer. Generated by `tapestry make-plugin`."
        ),
        "version": "0.1.0",
        "author": {"name": author},
        "license": "Apache-2.0",
        "keywords": ["tapestry", "discipline", "personalized"],
    }
    if with_memory:
        # Opt-in only (--with-memory): tapestry-discipline already registers
        # loom-memory, so adding it here too double-registers it. Env-driven,
        # placeholder fallback — point at YOUR own memory backend.
        manifest["mcpServers"] = {
            "loom-memory": {
                "type": "http",
                "url": "${LOOM_MEMORY_MCP_URL:-https://your-memory-host.example.com/mcp/memory/}",
            }
        }
    return manifest


def _marketplace_json(name: str, author: str) -> dict:
    return {
        "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
        "name": name,
        "description": f"{author}'s plugin marketplace.",
        "owner": {"name": author},
        "plugins": [
            {
                "name": name,
                "source": "./",
                "description": "Personalized Tapestry discipline plugin.",
            }
        ],
    }


def _readme(name: str, login: str, with_memory: bool = False, standalone: bool = True) -> str:
    repo = f"{login}/{name}" if login else f"<your-github>/{name}"
    memory_note = (
        "\nThis plugin registers the loom-memory MCP (built with `--with-memory`). "
        "Point it at YOUR own backend via the `LOOM_MEMORY_MCP_URL` env var "
        "(defaults to a placeholder):\n```bash\n"
        "export LOOM_MEMORY_MCP_URL=https://<your-memory-host>/mcp/memory/\n```\n"
        if with_memory else
        "\nThis plugin is behavior-only (no backend). `tapestry-discipline` already "
        "registers loom-memory; re-run with `tapestry make-plugin --with-memory` only "
        "if you need a separate memory backend wired into this plugin.\n"
    )
    if standalone:
        publish = (
            "## Publish to your own marketplace\n"
            "```bash\n"
            f"gh repo create {repo} --public --source . --push\n"
            "```\n"
            "Then in Claude Code:\n"
            "```text\n"
            f"/plugin marketplace add {repo}\n"
            f"/plugin install {name}@{name}\n"
            "```\n"
        )
    else:
        publish = (
            "## Add to your existing marketplace\n"
            "This plugin has no marketplace.json of its own (built with "
            "`--no-marketplace`). Move it into your marketplace repo (e.g. under a "
            "`plugins/` dir) and add an entry to that repo's "
            "`.claude-plugin/marketplace.json`:\n"
            "```json\n"
            f'{{ "name": "{name}", "source": "./{name}", "description": "..." }}\n'
            "```\n"
            f"Then `/plugin install {name}@<your-marketplace-name>` in Claude Code.\n"
        )
    return f'''# {name}

A personalized Claude Code discipline plugin, generated by `tapestry make-plugin`.

The universal `tapestry-discipline` plugin is the always-on baseline. This plugin
is the project-specific layer: customize `scripts/pre_tool_use.py` with guards for
this project's shape.
{memory_note}
## Test locally
Enable it in `.claude/settings.json` (or `/plugin marketplace add` from this dir),
then trigger an edit and confirm the PreToolUse reminder fires.

{publish}'''


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", s.strip()).strip("-").lower()
    return s or "my-plugin"


def _git_author() -> str:
    try:
        out = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return "Your Name"


def _gh_login() -> str:
    try:
        out = subprocess.run(
            ["gh", "api", "user", "-q", ".login"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return ""


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name", help="Plugin name (kebab-case, e.g. my-project-guard).")
    parser.add_argument(
        "--dir", default=".",
        help="Parent directory to create the plugin in (default: current dir).",
    )
    parser.add_argument(
        "--author", default=None,
        help="Author name (default: git config user.name).",
    )
    parser.add_argument(
        "--with-memory", dest="with_memory", action="store_true",
        help="Register the loom-memory MCP in this plugin. Off by default — "
             "tapestry-discipline already registers it, so this avoids double-registration.",
    )
    parser.add_argument(
        "--no-marketplace", dest="no_marketplace", action="store_true",
        help="Don't emit a per-plugin marketplace.json — for adding this plugin to an "
             "existing multi-plugin marketplace repo instead of its own.",
    )
    parser.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="Print the files that would be created without writing them.",
    )


def run(args: argparse.Namespace) -> int:
    name = _slug(args.name)
    author = args.author or _git_author()
    login = _gh_login()
    root = Path(args.dir).resolve() / name

    standalone = not args.no_marketplace
    files = {
        ".claude-plugin/plugin.json": json.dumps(_plugin_json(name, author, args.with_memory), indent=2) + "\n",
        "hooks/hooks.json": json.dumps(_HOOKS_JSON, indent=2) + "\n",
        "hooks/run-python.mjs": _RUN_PYTHON_MJS,
        "scripts/pre_tool_use.py": _pre_tool_use_py(name),
        "README.md": _readme(name, login, args.with_memory, standalone),
    }
    if standalone:
        files[".claude-plugin/marketplace.json"] = json.dumps(_marketplace_json(name, author), indent=2) + "\n"

    if args.dry_run:
        print(f"Would create plugin '{name}' (author: {author}) at {root}:")
        for rel in files:
            print(f"  {root / rel}")
        return 0

    if root.exists():
        print(f"Refusing to overwrite existing directory: {root}")
        return 1

    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    print(f"Created plugin '{name}' (author: {author}) at {root}:")
    for rel in files:
        print(f"  {rel}")
    print()
    if standalone:
        repo = f"{login}/{name}" if login else "<your-github>/" + name
        print("Next: customize scripts/pre_tool_use.py, then publish to your own marketplace:")
        print(f"  gh repo create {repo} --public --source {root} --push")
        print(f"  /plugin marketplace add {repo}")
    else:
        print("Next: customize scripts/pre_tool_use.py, then move this plugin into your")
        print("marketplace repo and add an entry to its .claude-plugin/marketplace.json (see README).")
    return 0
