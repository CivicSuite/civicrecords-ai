# CivicRecords AI — Windows Installation Script
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
    # Use String.Replace (literal) instead of -replace (regex) to avoid metachar issues.
    $envContent = (Get-Content ".env" -Raw)
    $envContent = $envContent.Replace("CHANGE-ME-generate-with-openssl-rand-hex-32", $jwtSecret)
    $envContent = $envContent.Replace("CHANGE-ME-on-first-login", $adminPassword)
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
    Read-Host "Press Enter to continue, or Ctrl+C to edit .env first"
}

# ─── Hardware Detection ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "Detecting hardware capabilities..." -ForegroundColor Cyan
& "$PSScriptRoot\scripts\detect_hardware.ps1"
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

# ─── Select Compose Configuration ────────────────────────────────────────────
$composeFiles = @("-f", "docker-compose.yml")
$useHostOllama = $hardwareEnv["CIVICRECORDS_USE_HOST_OLLAMA"] -eq "true"
$gpuEnabled = $hardwareEnv["CIVICRECORDS_GPU_ENABLED"] -eq "true"

if ($useHostOllama) {
    Write-Host "GPU acceleration enabled — using native Ollama on host (DirectML)" -ForegroundColor Green
    $composeFiles += @("-f", "docker-compose.host-ollama.yml")
} else {
    Write-Host "Using in-container Ollama — CPU inference" -ForegroundColor Yellow
}

# ─── Build Application Images ────────────────────────────────────────────────
Write-Host ""
Write-Host ">>> Pulling Docker images..."
& docker compose @composeFiles pull

Write-Host ">>> Building application images..."
& docker compose @composeFiles build

# ─── Start Infrastructure and Wait for Database ──────────────────────────────
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

# ─── Run Migrations ──────────────────────────────────────────────────────────
Write-Host ">>> Running database migrations..."
& docker compose @composeFiles run --rm api alembic upgrade head

# ─── Start All Services ──────────────────────────────────────────────────────
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

# ─── Pull Models ─────────────────────────────────────────────────────────────
$recommendedModel = if ($hardwareEnv["CIVICRECORDS_RECOMMENDED_MODEL"]) { $hardwareEnv["CIVICRECORDS_RECOMMENDED_MODEL"] } else { "gemma4:12b" }

Write-Host ""
if (-not $useHostOllama) {
    Write-Host ">>> Waiting for Ollama to be ready..."
    for ($i = 1; $i -le 30; $i++) {
        try {
            $ollamaCheck = docker compose @composeFiles exec -T ollama ollama list 2>$null
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
    # Use native Ollama for model pulls (GPU-accelerated)
    try {
        & ollama pull nomic-embed-text
    } catch {
        Write-Host "[WARN] Embedding model pull failed — retry: ollama pull nomic-embed-text" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host ">>> To enable AI-powered search, pull a language model:"
    Write-Host "    ollama pull $recommendedModel"
} else {
    # Use in-container Ollama
    try {
        & docker compose @composeFiles exec ollama ollama pull nomic-embed-text
    } catch {
        Write-Host "[WARN] Embedding model pull failed — retry: docker compose exec ollama ollama pull nomic-embed-text" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host ">>> To enable AI-powered search, pull a language model:"
    Write-Host "    docker compose exec ollama ollama pull $recommendedModel"
}

if ($recommendedModel -eq "gemma4:12b") {
    $ramGB = if ($hardwareEnv["CIVICRECORDS_TOTAL_RAM_GB"]) { $hardwareEnv["CIVICRECORDS_TOTAL_RAM_GB"] } else { "32" }
    Write-Host "    (recommended for your ${ramGB}GB RAM configuration)"
    Write-Host "    Alternative: gemma4:27b (needs 48GB+ RAM)"
} else {
    $ramGB = if ($hardwareEnv["CIVICRECORDS_TOTAL_RAM_GB"]) { $hardwareEnv["CIVICRECORDS_TOTAL_RAM_GB"] } else { "64" }
    Write-Host "    (recommended for your ${ramGB}GB RAM configuration)"
}

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
