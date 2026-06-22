#!/usr/bin/env bash
# seed-memory.sh
#
# Seeds Claude Code's auto-memory directory for THIS project. Run once
# after scaffolding. Idempotent and self-healing — safe to re-run; never
# overwrites existing memory files; restores any individual placeholder
# files that have been deleted.
#
# What it does:
#   1. Computes the Claude Code project key from the current working
#      directory.
#   2. Creates ~/.claude/projects/<project-key>/memory/ if missing.
#   3. Writes MEMORY.md (the index) if missing.
#   4. Writes placeholder typed-memory files showing the format, if missing.
#      Each file is independent — re-running fills only what's absent.
#
# The typed-memory protocol:
#   - One file per memory entry, named <type>_<short-slug>.md
#   - Types: user, feedback, project, reference
#   - YAML frontmatter on each file (name, description, metadata.type)
#   - MEMORY.md is a one-line-per-file index — pointers, not content
#   - Cross-link related memories with [[name]] syntax
#
# Usage:
#   cd /path/to/your/scaffolded-project
#   ./scripts/seed-memory.sh

set -euo pipefail

# Compute project key from cwd. Claude Code uses the absolute path with
# drive-colon replaced by '--' and path separators replaced by '-'.
CWD="$(pwd)"
case "${OSTYPE:-}" in
  msys*|cygwin*|mingw*)
    # Git-Bash on Windows: cwd is /c/Users/... -> c--Users-...
    PROJECT_KEY="${CWD#/}"           # strip leading slash
    PROJECT_KEY="${PROJECT_KEY/\//--}"  # first / becomes --
    PROJECT_KEY="${PROJECT_KEY//\//-}"  # remaining / become -
    ;;
  *)
    # Unix-likes: /home/user/... -> -home-user-...
    PROJECT_KEY="${CWD//\//-}"
    ;;
esac

MEMORY_DIR="${HOME}/.claude/projects/${PROJECT_KEY}/memory"
mkdir -p "$MEMORY_DIR"

# Per-file write-if-missing helper (self-healing on re-run)
write_if_missing() {
  local target="$1"
  local content="$2"
  if [[ -f "$target" ]]; then
    echo "SKIP $(basename "$target") (already exists)"
  else
    printf '%s' "$content" > "$target"
    echo "OK   $(basename "$target")"
  fi
}

# Starter MEMORY.md (the index)
read -r -d '' MEMORY_MD <<'EOF' || true
<!-- MEMORY.md — index of typed-memory files for this project.

This file is loaded into every Claude Code session in this project. Keep
each line under ~150 characters. Lines after 200 are truncated by the
harness, so the index stays concise.

Format per line:
  - [Title](file.md) — one-line hook

Memory file types (the file's prefix indicates type):
  - user_*       Facts about the user (role, preferences, knowledge, goals)
  - feedback_*   Guidance the user has given about how to work
  - project_*    Project-specific facts (who's doing what, why, deadlines)
  - reference_*  Pointers to external systems (issue tracker, dashboard, etc.)

Each memory file has YAML frontmatter (name, description, metadata.type).
Cross-link related memories with [[name]] syntax in the body.

The entries below are example placeholders. Edit them with real
information or delete them. -->

# Memory

## User
- [User role and context](user_role.md) — example placeholder; edit or delete

## Project
- [What this project is](project_purpose.md) — example placeholder; edit or delete
EOF

# Example user memory (generic placeholder)
read -r -d '' USER_ROLE_MD <<'EOF' || true
---
name: user-role
description: The user's role, primary work, and how they want to be collaborated with
metadata:
  type: user
---

<!-- Example placeholder. Replace with real information about yourself
or delete this file. If you delete it, also remove the corresponding
line in MEMORY.md.

Save user memories when you learn about:
  - The user's role, background, technical depth
  - Their stated preferences and goals
  - Domain knowledge they bring that should shape explanations -->

Example: "<your-name> is a <role> working primarily on <project>.
<Notes on technical depth, communication preferences, etc.>"
EOF

# Example project memory (generic placeholder)
read -r -d '' PROJECT_PURPOSE_MD <<'EOF' || true
---
name: project-purpose
description: What this project is, why it exists, and how it relates to other work
metadata:
  type: project
---

<!-- Example placeholder. Replace with real information about this
project or delete this file. Project memories decay relatively quickly
— keep them up to date.

Save project memories when you learn:
  - What the project is for, who it's for
  - Key constraints (deadlines, budget, regulatory, technical)
  - How it fits into a broader portfolio
  - Decisions that have been made and the WHY behind them -->

Example: "<project-name> is a <type> at <url>. Primary audience is
<audience>. Current priority is <thing>. See [[user-role]] for the
maintainer's context."
EOF

# Write each independently; any that exist are left alone
write_if_missing "$MEMORY_DIR/MEMORY.md"          "$MEMORY_MD"
write_if_missing "$MEMORY_DIR/user_role.md"       "$USER_ROLE_MD"
write_if_missing "$MEMORY_DIR/project_purpose.md" "$PROJECT_PURPOSE_MD"

echo ""
echo "Memory seeded at $MEMORY_DIR"
echo "The example files are starter content. Edit them with real facts or delete them;"
echo "future Claude Code sessions in this project will load MEMORY.md automatically and"
echo "start writing real typed-memory files as you work."
