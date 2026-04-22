# CivicRecords AI — Install / Repair flow (T5E).
#
# This script runs the full first-run bootstrap or an on-demand repair.
# Invoked from:
#   - Inno Setup's [Run] section immediately after Setup completes (first run)
#   - Start Menu shortcut "Install or Repair CivicRecords AI" (manual repair)
#
# It is NOT the daily-start flow. The daily-start flow is launch-start.ps1,
# wired to the Start Menu / Desktop shortcut "Start CivicRecords AI".
#
# Steps:
#   1. Run prereq-check.ps1. Exit if a required prereq is missing.
#   2. Invoke install.ps1 (ships the T5C 4-model Gemma 4 picker and the
#      T5B first-boot auto-seed).
#      install.ps1 will:
#        * run "docker compose pull" and "docker compose up -d"
#        * pull the "nomic-embed-text" embedding model via Ollama
#        * pull the Gemma 4 model the operator selects in the picker
#          (default: gemma4:e4b). Expect several minutes on first run.
#        * auto-seed the T5B baseline datasets on backend first boot
#   3. On successful install, open the admin panel in the default browser.
#
# Called with:
#   powershell -ExecutionPolicy Bypass -NoProfile -File launch-install.ps1
#
# The working directory at entry is {app} (set by the Inno Setup [Icons]
# entry's `WorkingDir` attribute). Everything below is relative to that.

$ErrorActionPreference = "Continue"

$appRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$prereq = Join-Path $PSScriptRoot "prereq-check.ps1"
$install = Join-Path $appRoot "install.ps1"

Set-Location $appRoot

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  CivicRecords AI -- Install / Repair (UNSIGNED)" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This flow runs the full bootstrap: prereq check, Docker" -ForegroundColor Yellow
Write-Host "Compose bring-up, Gemma 4 model picker + auto-pull, and" -ForegroundColor Yellow
Write-Host "first-boot baseline seeding. Use this after a fresh install," -ForegroundColor Yellow
Write-Host "after changing the selected LLM, or to repair a broken stack." -ForegroundColor Yellow
Write-Host ""
Write-Host "For normal day-to-day starts, use the 'Start CivicRecords AI'" -ForegroundColor Yellow
Write-Host "shortcut instead -- it brings the stack up without re-running" -ForegroundColor Yellow
Write-Host "the installer or pulling models." -ForegroundColor Yellow
Write-Host ""
Write-Host "This installer ships UNSIGNED by design (Scott-locked T5E" -ForegroundColor Yellow
Write-Host "posture alpha on 2026-04-22). If Windows SmartScreen blocked" -ForegroundColor Yellow
Write-Host "the initial setup, see installer\windows\README.md for the" -ForegroundColor Yellow
Write-Host "concrete 'More info -> Run anyway' remediation steps." -ForegroundColor Yellow
Write-Host ""

# --- Step 1: prereq check ---------------------------------------------------
& powershell.exe -ExecutionPolicy Bypass -NoProfile -File $prereq
$prereqExit = $LASTEXITCODE
if ($prereqExit -ne 0) {
    Write-Host ""
    Write-Host "Prereq check failed with exit code $prereqExit." -ForegroundColor Red
    Write-Host "Address the items listed above, then re-run 'Install or" -ForegroundColor Yellow
    Write-Host "Repair CivicRecords AI' from the Start Menu." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to close"
    exit $prereqExit
}

# --- Step 2: invoke the existing install.ps1 (T5C picker + T5B seeds) ------
Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Running install.ps1 (Compose bring-up + model pull)" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

if (-not (Test-Path $install)) {
    Write-Host "[ERROR] install.ps1 not found at $install" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

& powershell.exe -ExecutionPolicy Bypass -NoProfile -File $install
$installExit = $LASTEXITCODE
if ($installExit -ne 0) {
    Write-Host ""
    Write-Host "install.ps1 exited $installExit. Review the output above." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit $installExit
}

# --- Step 3: open the admin panel ------------------------------------------
$adminUrl = "http://localhost:8080/"
Write-Host ""
Write-Host "Opening admin panel: $adminUrl" -ForegroundColor Green
Start-Process $adminUrl

Write-Host ""
Write-Host "CivicRecords AI is running. For daily starts from now on, use" -ForegroundColor Green
Write-Host "the 'Start CivicRecords AI' shortcut -- it brings the stack" -ForegroundColor Green
Write-Host "up without re-running the installer or re-pulling models." -ForegroundColor Green
Write-Host ""
Write-Host "To stop the stack, use the 'Stop CivicRecords AI' shortcut or" -ForegroundColor Green
Write-Host "run 'docker compose down' in $appRoot" -ForegroundColor Green
Write-Host ""
