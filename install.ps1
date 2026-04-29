# CivicRecords AI Ã¢â‚¬â€ Windows Installation Script
# Requires: Windows 10/11 with Docker Desktop

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  CivicRecords AI - Installation Script"
Write-Host "  Target: Windows 10/11 with Docker Desktop"
Write-Host "============================================"
Write-Host ""

# Check Docker
try {
    $dockerVersion = docker --version 2>$null
    Write-Host "[OK] Docker found: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker is not installed or not running." -ForegroundColor Red
    Write-Host "Install Docker Desktop from: https://www.docker.com/products/docker-desktop/"
    Write-Host "After installing, make sure Docker Desktop is running before re-running this script."
    exit 1
}

# Check Docker Compose
try {
    $composeVersion = docker compose version 2>$null
    Write-Host "[OK] Docker Compose found: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker Compose not available." -ForegroundColor Red
    exit 1
}

# Check Docker is actually running
try {
    docker info 2>$null | Out-Null
    Write-Host "[OK] Docker daemon is running" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker daemon is not running. Start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Create .env from template if not exists
if (-not (Test-Path ".env")) {
    Write-Host ">>> Creating .env from template..."
    Copy-Item ".env.example" ".env"
    # Generate JWT secret
    $jwtSecret = -join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })
    # T2C: generate a strong admin password instead of leaving the placeholder.
    # Settings.check_first_admin_password rejects the .env.example value at startup.
    # Use hex so the value contains no shell or .env-parser metacharacters.
    $adminPassword = -join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })
    # T6 / ENG-001: generate an at-rest encryption key for the
    # data_sources.connection_config column. Fernet expects 44 chars of
    # URL-safe base64 encoding 32 random bytes. Use the .NET CSPRNG +
    # Convert.ToBase64String + URL-safe character substitution.
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $keyBytes = New-Object byte[] 32
    $rng.GetBytes($keyBytes)
    $rng.Dispose()
    $encryptionKey = ([Convert]::ToBase64String($keyBytes)) -replace '\+','-' -replace '/','_'
    # Use String.Replace (literal) instead of -replace (regex) to avoid metachar issues.
    $envContent = (Get-Content ".env" -Raw)
    $envContent = $envContent.Replace("CHANGE-ME-generate-with-openssl-rand-hex-32", $jwtSecret)
    $envContent = $envContent.Replace("CHANGE-ME-on-first-login", $adminPassword)
    $envContent = $envContent.Replace("CHANGE-ME-generate-with-fernet-generate-key", $encryptionKey)
    Set-Content ".env" -Value $envContent -NoNewline
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Yellow
    Write-Host "  ADMIN PASSWORD GENERATED - copy this now" -ForegroundColor Yellow
    Write-Host "============================================" -ForegroundColor Yellow
    Write-Host "  Email:    admin@example.gov  (edit .env to change)"
    Write-Host "  Password: $adminPassword" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Yellow
    Write-Host "  This password is stored in .env. Store it in your password manager."
    Write-Host "  Press Enter when you have copied it."
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Red
    Write-Host "  AT-REST ENCRYPTION KEY GENERATED (T6 / ENG-001)" -ForegroundColor Red
    Write-Host "============================================" -ForegroundColor Red
    Write-Host "  Key:      $encryptionKey" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Red
    Write-Host "  This key encrypts data_sources.connection_config at rest."
    Write-Host ""
    Write-Host "  *** BACK THIS UP SEPARATELY FROM YOUR DATABASE. ***" -ForegroundColor Yellow
    Write-Host "  Losing this key means every saved data-source"
    Write-Host "  connection configuration becomes unreadable. Store it"
    Write-Host "  alongside your JWT_SECRET in a password manager or"
    Write-Host "  secrets vault - NOT in the same location as DB backups."
    Write-Host ""
    Read-Host "Press Enter to continue, or Ctrl+C to edit .env first"

    $portalMode = $env:CIVICRECORDS_PORTAL_MODE
    if ($portalMode) {
        $portalMode = $portalMode.Trim().ToLower()
        if ($portalMode -ne "public" -and $portalMode -ne "private") {
            Write-Host ""
            Write-Host "[WARN] CIVICRECORDS_PORTAL_MODE='$portalMode' is not 'public' or 'private' -- falling back to 'private'." -ForegroundColor Yellow
            $portalMode = "private"
        } else {
            Write-Host ""
            Write-Host "PORTAL_MODE=$portalMode (from env, non-interactive install)" -ForegroundColor Cyan
        }
    } elseif ([Environment]::UserInteractive) {
        Write-Host ""
        Write-Host "============================================" -ForegroundColor Cyan
        Write-Host "  Portal mode (T5D)" -ForegroundColor Cyan
        Write-Host "============================================" -ForegroundColor Cyan
        Write-Host "  private (default): staff-only deployment. No public routes. Residents"
        Write-Host "                     cannot self-register. Login screen is the only"
        Write-Host "                     externally reachable page."
        Write-Host "  public:            exposes a minimal public surface -- landing page,"
        Write-Host "                     resident registration, and an authenticated"
        Write-Host "                     records-request submission form for residents."
        Write-Host ""
        $answer = (Read-Host "Install in public mode? [y/N]").Trim().ToLower()
        if ($answer -eq "y" -or $answer -eq "yes" -or $answer -eq "public") {
            $portalMode = "public"
        } else {
            $portalMode = "private"
        }
        Write-Host "PORTAL_MODE=$portalMode" -ForegroundColor Cyan
    } else {
        $portalMode = "private"
        Write-Host "PORTAL_MODE=private (non-interactive install, default)" -ForegroundColor Cyan
    }

    # Persist the chosen mode into .env, replacing the default "private"
    # value shipped by .env.example. Using literal String.Replace (not
    # -replace regex) to avoid metachar issues.
    $envContent = (Get-Content ".env" -Raw)
    $envContent = $envContent.Replace("PORTAL_MODE=private", "PORTAL_MODE=$portalMode")
    Set-Content ".env" -Value $envContent -NoNewline
}

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Hardware Detection Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
Write-Host ""
Write-Host "Detecting hardware capabilities..." -ForegroundColor Cyan
& "$PSScriptRoot\scripts\detect_hardware.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Hardware detection failed. Fix the prerequisite issue above, then re-run install.ps1." -ForegroundColor Red
    exit 1
}
Write-Host ""

# Load hardware config
$hardwareEnv = @{}
if (Test-Path ".env.hardware") {
    Get-Content ".env.hardware" | ForEach-Object {
        if ($_ -match "^([^#][^=]+)=(.*)$") {
            $hardwareEnv[$matches[1]] = $matches[2].Trim('"')
        }
    }
}

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Select Compose Configuration Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
$composeFiles = @("-f", "docker-compose.yml")
$useHostOllama = $hardwareEnv["CIVICRECORDS_USE_HOST_OLLAMA"] -eq "true"
$gpuEnabled = $hardwareEnv["CIVICRECORDS_GPU_ENABLED"] -eq "true"

if ($useHostOllama) {
    Write-Host "GPU acceleration enabled - using native Ollama on host (DirectML)" -ForegroundColor Green
    $composeFiles += @("-f", "docker-compose.host-ollama.yml")
} else {
    Write-Host "Using in-container Ollama - CPU inference" -ForegroundColor Yellow
}

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Build Application Images Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
Write-Host ""
Write-Host ">>> Pulling Docker images..."
& docker compose @composeFiles pull

Write-Host ">>> Building application images..."
& docker compose @composeFiles build

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Start Infrastructure and Wait for Database Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
Write-Host ">>> Starting database and cache..."
$envFileArgs = @("--env-file", ".env")
if (Test-Path ".env.hardware") {
    $envFileArgs += @("--env-file", ".env.hardware")
}
& docker compose @composeFiles @envFileArgs up -d postgres redis

Write-Host ">>> Waiting for database..."
$dbReady = $false
for ($i = 1; $i -le 30; $i++) {
    $result = docker compose exec -T postgres pg_isready -U civicrecords -q 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Database is ready" -ForegroundColor Green
        $dbReady = $true
        break
    }
    if ($i -eq 30) {
        Write-Host "ERROR: PostgreSQL did not become ready after 30 attempts." -ForegroundColor Red
        Write-Host "Check: docker compose logs postgres"
        exit 1
    }
    Write-Host "  Waiting for database... ($i/30)"
    Start-Sleep -Seconds 2
}

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Run Migrations Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
Write-Host ">>> Running database migrations..."
& docker compose @composeFiles run --rm api alembic upgrade head

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Start All Services Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
Write-Host ">>> Starting all services..."
& docker compose @composeFiles @envFileArgs up -d

# Wait for API health
Write-Host ">>> Waiting for API to be healthy..."
$healthy = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5 -ErrorAction Stop
        if ($response.status -eq "ok") {
            Write-Host "[OK] API is healthy!" -ForegroundColor Green
            $healthy = $true
            break
        }
    } catch {}
    Write-Host "  Waiting... ($i/30)"
    Start-Sleep -Seconds 5
}

if (-not $healthy) {
    Write-Host "[WARN] API health check timed out. Check logs with: docker compose logs api" -ForegroundColor Yellow
}

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Gemma 4 Model Picker + Auto-Pull Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# Tier 5 Blocker 1 (locked 2026-04-21). All four supported Gemma 4 tags are
# presented. Default is gemma4:e4b. Target profile baseline is Windows 11 Pro
# 23H2+ / 32 GB min (64 GB rec) / GPU optional / CPU-only supportable.
# Only gemma4:e2b and gemma4:e4b are supportable at baseline. gemma4:26b and
# gemma4:31b require stronger hardware and are gated behind an explicit
# "yes" confirmation.
# Non-interactive install: default is used unless env var
# CIVICRECORDS_SELECTED_MODEL=<tag> is set.

$defaultModel = "gemma4:e4b"
$supportedModels = @("gemma4:e2b", "gemma4:e4b", "gemma4:26b", "gemma4:31b")

Write-Host ""
if (-not $useHostOllama) {
    Write-Host ">>> Waiting for Ollama to be ready..."
    for ($i = 1; $i -le 30; $i++) {
        try {
            $null = docker compose @composeFiles exec -T ollama ollama list 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[OK] Ollama is ready" -ForegroundColor Green
                break
            }
        } catch {}
        if ($i -eq 30) {
            Write-Host "[WARN] Ollama did not become ready. Model pull may fail." -ForegroundColor Yellow
        }
        Write-Host "  Waiting for Ollama... ($i/30)"
        Start-Sleep -Seconds 3
    }
}

Write-Host ">>> Pulling embedding model (required for search)..."

if ($useHostOllama) {
    try {
        & ollama pull nomic-embed-text
    } catch {
        Write-Host "[WARN] Embedding model pull failed - retry: ollama pull nomic-embed-text" -ForegroundColor Yellow
    }
} else {
    try {
        & docker compose @composeFiles exec ollama ollama pull nomic-embed-text
    } catch {
        Write-Host "[WARN] Embedding model pull failed - retry: docker compose exec ollama ollama pull nomic-embed-text" -ForegroundColor Yellow
    }
}

# Detect whether any supported Gemma 4 model is already present in Ollama
if ($useHostOllama) {
    $ollamaListRaw = (& ollama list 2>$null) -join "`n"
} else {
    $ollamaListRaw = (& docker compose @composeFiles exec -T ollama ollama list 2>$null) -join "`n"
}
$existingModel = $null
foreach ($m in $supportedModels) {
    $escaped = [regex]::Escape($m)
    if ($ollamaListRaw -match "(?m)^$escaped\s") {
        $existingModel = $m
        break
    }
}

$selectedModel = $env:CIVICRECORDS_SELECTED_MODEL

if ($existingModel -and -not $selectedModel) {
    Write-Host ""
    Write-Host "[OK] Supported Gemma 4 model already present in Ollama: $existingModel" -ForegroundColor Green
    Write-Host "     Skipping language-model pull."
    $selectedModel = $existingModel
} else {
    Write-Host ""
    Write-Host "===== Gemma 4 model picker =====" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "CivicRecords AI supports four Gemma 4 models. The target profile is"
    Write-Host "Windows 11 Pro 23H2+ / 32 GB RAM minimum (64 GB recommended) /"
    Write-Host "GPU optional / CPU-only supported. Models 26b and 31b require stronger"
    Write-Host "hardware than the baseline and must be selected explicitly."
    Write-Host ""
    Write-Host "  1) gemma4:e2b  Edge / 2.3B effective params / 7.2 GB disk / ~16 GB RAM  [supportable]"
    Write-Host "  2) gemma4:e4b  Edge / 4.5B effective params / 9.6 GB disk / ~20 GB RAM  [supportable]  (DEFAULT)" -ForegroundColor Green
    Write-Host "  3) gemma4:26b  Workstation MoE / 25.2B total, 3.8B active /  18 GB disk / 48+ GB RAM recommended  [not supportable at 32 GB baseline]" -ForegroundColor Yellow
    Write-Host "  4) gemma4:31b  Workstation dense / 30.7B params            /  20 GB disk / 64+ GB RAM recommended  [not supportable at 32 GB baseline; GPU recommended]" -ForegroundColor Yellow
    Write-Host ""

    if ($selectedModel) {
        Write-Host "Using CIVICRECORDS_SELECTED_MODEL=$selectedModel (non-interactive override)."
    } elseif ([Console]::IsInputRedirected) {
        $selectedModel = $defaultModel
        Write-Host "Non-interactive install - selecting default: $selectedModel"
        Write-Host "Override by setting `$env:CIVICRECORDS_SELECTED_MODEL=<tag> before running."
    } else {
        $choice = Read-Host "Enter 1-4 (or press Enter for default gemma4:e4b)"
        switch ($choice) {
            "1" { $selectedModel = "gemma4:e2b" }
            ""  { $selectedModel = "gemma4:e4b" }
            "2" { $selectedModel = "gemma4:e4b" }
            "3" { $selectedModel = "gemma4:26b" }
            "4" { $selectedModel = "gemma4:31b" }
            default {
                Write-Host "Unknown choice '$choice' - falling back to default gemma4:e4b." -ForegroundColor Yellow
                $selectedModel = "gemma4:e4b"
            }
        }

        if ($selectedModel -eq "gemma4:26b") {
            Write-Host ""
            Write-Host "WARNING: gemma4:26b is NOT supportable at the 32 GB baseline target profile." -ForegroundColor Yellow
            Write-Host "         Your machine should have at least 48 GB RAM for acceptable performance."
            $confirm = Read-Host "Type 'yes' to confirm and proceed with gemma4:26b anyway"
            if ($confirm -ne "yes") {
                Write-Host "Aborted gemma4:26b selection. Falling back to default gemma4:e4b."
                $selectedModel = "gemma4:e4b"
            }
        } elseif ($selectedModel -eq "gemma4:31b") {
            Write-Host ""
            Write-Host "WARNING: gemma4:31b is NOT supportable at the 32 GB baseline target profile." -ForegroundColor Yellow
            Write-Host "         Your machine should have at least 64 GB RAM, and a GPU is recommended."
            $confirm = Read-Host "Type 'yes' to confirm and proceed with gemma4:31b anyway"
            if ($confirm -ne "yes") {
                Write-Host "Aborted gemma4:31b selection. Falling back to default gemma4:e4b."
                $selectedModel = "gemma4:e4b"
            }
        }
    }

    Write-Host ""
    Write-Host ">>> Pulling $selectedModel (this may take several minutes)..."
    $pullOk = $false
    try {
        if ($useHostOllama) {
            & ollama pull $selectedModel
        } else {
            & docker compose @composeFiles exec ollama ollama pull $selectedModel
        }
        if ($LASTEXITCODE -eq 0) { $pullOk = $true }
    } catch {}

    if ($pullOk) {
        Write-Host "[OK] Model pulled: $selectedModel" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Model pull for $selectedModel failed. Retry manually:" -ForegroundColor Yellow
        if ($useHostOllama) {
            Write-Host "    ollama pull $selectedModel"
        } else {
            Write-Host "    docker compose exec ollama ollama pull $selectedModel"
        }
    }
}

Write-Host ""
Write-Host "Selected LLM model: $selectedModel"

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" } | Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Installation complete!"
Write-Host ""
Write-Host "  Admin panel:  http://${ip}:8080"
Write-Host "  API:          http://${ip}:8000"
Write-Host "  API docs:     http://${ip}:8000/docs"
Write-Host ""
if ($gpuEnabled) {
    $plat = $hardwareEnv["CIVICRECORDS_PLATFORM"]
    if ($useHostOllama) {
        Write-Host "  GPU inference: ENABLED (Native Ollama / DirectML / $plat)" -ForegroundColor Green
    } else {
        Write-Host "  GPU inference: ENABLED ($plat)" -ForegroundColor Green
    }
} else {
    Write-Host "  GPU inference: DISABLED (CPU only)" -ForegroundColor Yellow
    Write-Host "  See docs for GPU enablement on AMD Ryzen"
}
Write-Host ""
Write-Host "  Run sovereignty check: .\scripts\verify-sovereignty.ps1"
Write-Host "============================================" -ForegroundColor Cyan
