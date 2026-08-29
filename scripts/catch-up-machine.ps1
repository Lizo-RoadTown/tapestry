#requires -Version 5
<#
catch-up-machine.ps1 — bring this machine's Claude Code plugins up to date.

WHY: Claude Code plugins install per-MACHINE (user scope), NOT per-repo. One run
here updates the plugins for EVERY repo on this machine. If a machine has been idle
while the tapestry marketplace moved forward, this catches it up in one command.

USAGE (Windows):
    cd <your tapestry clone>
    git pull
    powershell -ExecutionPolicy Bypass -File scripts\catch-up-machine.ps1

Then RESTART Claude Code — the CLI installs the new versions, but running sessions
keep the old ones until you restart.

The equivalent on macOS/Linux is the same three CLI calls in bash:
    claude plugin marketplace update
    claude plugin update tapestry-discipline@tapestry -y
    claude plugin update tapestry-patterns@tapestry -y
#>

$ErrorActionPreference = 'Continue'

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host 'ERROR: the `claude` CLI is not on PATH. Install Claude Code first.' -ForegroundColor Red
    exit 1
}

Write-Host '==> [1/4] Refreshing all marketplace catalogs from source...'
claude plugin marketplace update

Write-Host ''
Write-Host '==> [2/4] Updating the Tapestry plugins (discipline + patterns)...'
claude plugin update tapestry-discipline@tapestry -y
claude plugin update tapestry-patterns@tapestry -y

Write-Host ''
Write-Host '==> [3/4] Updating every other installed plugin to its latest...'
$ids = claude plugin list 2>$null |
    Select-String -Pattern '([A-Za-z0-9._-]+@[A-Za-z0-9._-]+)' -AllMatches |
    ForEach-Object { $_.Matches } | ForEach-Object { $_.Value } |
    Sort-Object -Unique
foreach ($id in $ids) {
    if ($id -like 'tapestry-discipline@*' -or $id -like 'tapestry-patterns@*') { continue }
    Write-Host "    updating $id"
    claude plugin update $id -y
}

Write-Host ''
Write-Host '==> [4/4] Final installed plugin versions:'
claude plugin list

Write-Host ''
Write-Host 'DONE. Now RESTART Claude Code to apply all updates.' -ForegroundColor Green
