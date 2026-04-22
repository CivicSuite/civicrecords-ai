# CivicRecords AI — T5E Windows Prereq Check
#
# Runs after the Inno Setup wizard copies files and BEFORE `launch.ps1`
# invokes `install.ps1`. Reports on the 4 prerequisites CivicRecords
# needs on a fresh Windows 11 Pro 23H2+ machine:
#
#   1. Docker Desktop (or Docker Engine on WSL) — required.
#   2. WSL 2 + Virtual Machine Platform — required by Docker Desktop on
#      Windows. If missing, gives concrete `wsl --install` guidance and
#      flags that a reboot is typically required.
#   3. System RAM ≥ 32 GB (Tier 5 Blocker 2 target-profile floor).
#   4. Host Ollama — optional. If present, host-Ollama path is preferred
#      (matches CIVICRECORDS_USE_HOST_OLLAMA branching in install.ps1).
#
# Exit codes:
#   0  — all required prereqs are satisfied; install.ps1 may proceed.
#   1  — one or more required prereqs are missing; remediation printed.
#
# Scott's T5E directive: report concretely and actionably. No vague
# reassurance. Do NOT attempt to install Docker Desktop from here — too
# much scope + elevation risk. Detect and guide.

$ErrorActionPreference = "Continue"
$allOk = $true

function Line([string]$msg) { Write-Host $msg }
function Ok([string]$label) { Write-Host "  [OK]    $label" -ForegroundColor Green }
function Fail([string]$label, [string[]]$remediation) {
    $script:allOk = $false
    Write-Host "  [MISS]  $label" -ForegroundColor Red
    foreach ($r in $remediation) { Write-Host "          $r" -ForegroundColor Yellow }
}
function Warn([string]$label, [string]$note) {
    Write-Host "  [OPT]   $label — $note" -ForegroundColor Cyan
}

Line ""
Line "======================================================"
Line "  CivicRecords AI — prereq check (Windows target)"
Line "======================================================"
Line ""

# ─── 1. Docker ────────────────────────────────────────────────────────────
Line "1) Docker"
$dockerFound = $false
try {
    $ver = (docker --version 2>$null)
    if ($LASTEXITCODE -eq 0 -and $ver) {
        $dockerFound = $true
        Ok "Docker CLI: $ver"
    }
} catch { }

if (-not $dockerFound) {
    Fail "Docker not found on PATH" @(
        "Install Docker Desktop for Windows from:",
        "  https://www.docker.com/products/docker-desktop/",
        "After installation, start Docker Desktop and re-run this installer."
    )
} else {
    try {
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Ok "Docker daemon is running"
        } else {
            Fail "Docker CLI is installed but the daemon is not running" @(
                "Start Docker Desktop from the Start Menu and wait for the",
                "whale icon in the system tray to indicate 'Docker Desktop is",
                "running'. Then re-run this installer."
            )
        }
    } catch {
        Fail "Could not query Docker daemon state" @(
            "Start Docker Desktop and re-run."
        )
    }

    try {
        $null = docker compose version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Ok "Docker Compose v2 available"
        } else {
            Fail "Docker Compose v2 not available" @(
                "Upgrade Docker Desktop (Compose ships with it on Windows).",
                "Standalone 'docker-compose' (v1) is NOT supported."
            )
        }
    } catch {
        Fail "Docker Compose v2 check failed" @(
            "Upgrade Docker Desktop."
        )
    }
}

Line ""

# ─── 2. WSL 2 + Virtual Machine Platform ──────────────────────────────────
Line "2) WSL 2 + Virtual Machine Platform"
$wslOk = $false
try {
    $wslStatus = (wsl --status 2>$null) -join "`n"
    if ($LASTEXITCODE -eq 0 -and $wslStatus -match "Default Version:\s*2") {
        Ok "WSL default version = 2"
        $wslOk = $true
    } elseif ($LASTEXITCODE -eq 0) {
        Fail "WSL is installed but default version is not 2" @(
            "Run (elevated):   wsl --set-default-version 2",
            "Then restart the machine and re-run this installer."
        )
    } else {
        Fail "WSL is not installed or not enabled" @(
            "Run (elevated PowerShell):   wsl --install --no-distribution",
            "This enables WSL 2 and the Virtual Machine Platform feature.",
            "A REBOOT is required after that command. Re-run the installer",
            "once the machine is back up."
        )
    }
} catch {
    Fail "WSL status check failed" @(
        "Run (elevated):   wsl --install --no-distribution   (reboot required)"
    )
}

# Virtual Machine Platform Windows feature — best-effort check; Docker
# Desktop usually enables this as part of its own install.
try {
    $vmp = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -ErrorAction Stop
    if ($vmp.State -eq "Enabled") {
        Ok "Virtual Machine Platform feature enabled"
    } else {
        Fail "Virtual Machine Platform feature not enabled" @(
            "Run (elevated PowerShell):",
            "  Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform",
            "REBOOT required afterwards."
        )
    }
} catch {
    Warn "Virtual Machine Platform state" "could not query (likely fine if Docker Desktop is already running)"
}

Line ""

# ─── 3. RAM floor (Tier 5 Blocker 2 target profile = 32 GB min) ───────────
Line "3) System RAM (Tier 5 target-profile floor: 32 GB)"
try {
    $ramBytes = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
    $ramGB = [math]::Round($ramBytes / 1GB)
    if ($ramGB -ge 32) {
        Ok "RAM: $ramGB GB (meets 32 GB baseline)"
    } else {
        Fail "RAM: $ramGB GB — below 32 GB target-profile floor" @(
            "CivicRecords AI's 4-model Gemma 4 picker requires a machine",
            "with at least 32 GB RAM for the edge models (gemma4:e2b /",
            "gemma4:e4b) to run comfortably. Below this floor, no supported",
            "Gemma 4 model runs reliably."
        )
    }
} catch {
    Warn "RAM probe failed" "continuing — install.ps1 / detect_hardware.ps1 will re-check at run time"
}

Line ""

# ─── 4. Host Ollama (optional; preferred when present) ────────────────────
Line "4) Host Ollama (optional; preferred when present per target profile)"
$hostOllama = Get-Command ollama -ErrorAction SilentlyContinue
if ($hostOllama) {
    Ok "Host Ollama found at: $($hostOllama.Source)"
    try {
        $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
        Ok "Host Ollama service is responding on :11434"
        Write-Host "          install.ps1 will prefer host Ollama over the in-container service." -ForegroundColor Cyan
    } catch {
        Warn "Host Ollama is installed but not currently running" "start it with 'ollama serve' before launching CivicRecords AI"
    }
} else {
    Warn "Host Ollama not installed" "CivicRecords AI will fall back to the in-container Ollama service (CPU inference)"
    Line "          To enable host-Ollama (GPU-friendlier) path, install from:"
    Line "            https://ollama.ai/download/windows"
    Line "          Then re-run the installer."
}

Line ""
Line "======================================================"
if ($allOk) {
    Line "  Prereq check: PASSED"
    Line "  launch.ps1 will proceed to install.ps1 (4-model"
    Line "  picker + first-boot seeding)."
    Line "======================================================"
    exit 0
} else {
    Line "  Prereq check: BLOCKED"
    Line "  Address the items flagged [MISS] above, then re-run"
    Line "  the CivicRecords AI installer from the Start Menu."
    Line "======================================================"
    exit 1
}
