# CivicRecords AI -- Daily start flow (T5E).
#
# This script brings up the existing Docker Compose stack and opens the
# admin panel. It does NOT run the prereq check, does NOT invoke
# install.ps1, does NOT re-pull any model, and does NOT re-seed data.
#
# Invoked from:
#   - Start Menu shortcut "Start CivicRecords AI"
#   - Desktop shortcut "Start CivicRecords AI" (if the desktopicon task
#     was selected at install time)
#
# For first-run install, LLM changes, or repair, use the separate
# "Install or Repair CivicRecords AI" shortcut (launch-install.ps1).
#
# Called with:
#   powershell -ExecutionPolicy Bypass -NoProfile -File launch-start.ps1
#
# The working directory at entry is {app}. Everything below is relative.

$ErrorActionPreference = "Continue"

$appRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $appRoot

Write-Host ""
Write-Host "CivicRecords AI -- starting the Docker Compose stack..." -ForegroundColor Cyan
Write-Host "  (no install, no model pull, no data seed)" -ForegroundColor DarkGray
Write-Host ""

# --- Quick Docker reachability check ---------------------------------------
$dockerOk = $false
try {
    & docker version --format "{{.Server.Version}}" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}

if (-not $dockerOk) {
    Write-Host "[ERROR] Docker is not reachable." -ForegroundColor Red
    Write-Host ""
    Write-Host "Fix:" -ForegroundColor Yellow
    Write-Host "  1. Start Docker Desktop and wait for the whale icon" -ForegroundColor Yellow
    Write-Host "     in the system tray to say 'Docker is running'." -ForegroundColor Yellow
    Write-Host "  2. Re-run 'Start CivicRecords AI' from the Start Menu." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If this is a first run (or you just reinstalled), use" -ForegroundColor Yellow
    Write-Host "'Install or Repair CivicRecords AI' instead -- it runs" -ForegroundColor Yellow
    Write-Host "the prereq check and configures the stack." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 1
}

# --- Bring up the stack (idempotent; no-ops if already running) ------------
Write-Host ">>> docker compose up -d" -ForegroundColor Cyan
& docker compose up -d
$upExit = $LASTEXITCODE
if ($upExit -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] 'docker compose up -d' failed (exit $upExit)." -ForegroundColor Red
    Write-Host ""
    Write-Host "Fix:" -ForegroundColor Yellow
    Write-Host "  1. Check 'docker compose logs' in the install dir" -ForegroundColor Yellow
    Write-Host "     ($appRoot) for the specific service that failed." -ForegroundColor Yellow
    Write-Host "  2. If images or volumes are missing (not just stopped)," -ForegroundColor Yellow
    Write-Host "     run 'Install or Repair CivicRecords AI' from the" -ForegroundColor Yellow
    Write-Host "     Start Menu to rebuild the stack." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to close"
    exit $upExit
}

# --- Open the admin panel ---------------------------------------------------
$adminUrl = "http://localhost:8080/"
Write-Host ""
Write-Host "Opening admin panel: $adminUrl" -ForegroundColor Green
Start-Process $adminUrl

Write-Host ""
Write-Host "CivicRecords AI is running. To stop the stack, use the" -ForegroundColor Green
Write-Host "'Stop CivicRecords AI' shortcut in the Start Menu or run" -ForegroundColor Green
Write-Host "'docker compose down' in $appRoot" -ForegroundColor Green
Write-Host ""
