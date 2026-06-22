# seed-memory.ps1
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
#   cd C:\path\to\your\scaffolded-project
#   ./scripts/seed-memory.ps1

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# Compute project key from cwd. Claude Code uses the absolute path with
# drive-colon replaced by '--' and path separators replaced by '-'.
$cwd = (Get-Location).Path
$projectKey = $cwd -replace ':', '-' -replace '[\\/]', '-'

$memoryDir = Join-Path $env:USERPROFILE ".claude\projects\$projectKey\memory"
New-Item -ItemType Directory -Force -Path $memoryDir | Out-Null

# Per-file write-if-missing helper (self-healing on re-run)
function Write-IfMissing {
    param([string]$Target, [string]$Content)
    if (Test-Path $Target) {
        Write-Host "SKIP $(Split-Path $Target -Leaf) (already exists)"
    } else {
        $Content | Set-Content -Path $Target -Encoding UTF8 -NoNewline
        Write-Host "OK   $(Split-Path $Target -Leaf)"
    }
}

$MEMORY_MD = @'
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
'@

$USER_ROLE_MD = @'
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
'@

$PROJECT_PURPOSE_MD = @'
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
'@

Write-IfMissing -Target (Join-Path $memoryDir "MEMORY.md")          -Content $MEMORY_MD
Write-IfMissing -Target (Join-Path $memoryDir "user_role.md")       -Content $USER_ROLE_MD
Write-IfMissing -Target (Join-Path $memoryDir "project_purpose.md") -Content $PROJECT_PURPOSE_MD

Write-Host ""
Write-Host "Memory seeded at $memoryDir"
Write-Host "The example files are starter content. Edit them with real facts or delete them;"
Write-Host "future Claude Code sessions in this project will load MEMORY.md automatically and"
Write-Host "start writing real typed-memory files as you work."
