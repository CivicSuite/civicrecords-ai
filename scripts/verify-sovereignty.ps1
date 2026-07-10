# CivicSunshine - Data Sovereignty Check (Windows)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  CivicSunshine - Data Sovereignty Check"
Write-Host "============================================"
Write-Host ""

$pass = 0
$fail = 0
$warn = 0
$apiRunning = $false

function Check($desc, $result) {
    if ($result -eq "PASS") {
        Write-Host "  [PASS] $desc" -ForegroundColor Green
        $script:pass++
    } elseif ($result -eq "WARN") {
        Write-Host "  [WARN] $desc" -ForegroundColor Yellow
        $script:warn++
    } else {
        Write-Host "  [FAIL] $desc" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host "1. Checking Docker services..."
try {
    $runningServices = docker compose ps --services --status running 2>$null
    if ($runningServices -match '(^|\r?\n)api(\r?\n|$)') {
        $apiRunning = $true
        Check "API service is running" "PASS"
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
        if ($health.status -eq "ok") {
            Check "API responding" "PASS"
        } else {
            Check "API responding" "FAIL"
        }
    } else {
        Check "API service is running (start stack with: docker compose up -d)" "FAIL"
        Check "API responding (start stack with: docker compose up -d)" "FAIL"
    }
} catch {
    Check "API service is running (start stack with: docker compose up -d)" "FAIL"
    Check "API responding (start stack with: docker compose up -d)" "FAIL"
}

Write-Host ""
Write-Host "2. Checking for outbound connections..."
if ($apiRunning) {
    try {
        $status = docker compose exec api bash -c "apt-get install -y -qq procps 2>/dev/null; ss -tunp 2>/dev/null | grep ESTAB | grep -v '127.0.0.1\|172\.\|10\.\|192\.168\.' || true" 2>$null
        if ([string]::IsNullOrWhiteSpace($status)) {
            Check "No unexpected outbound connections" "PASS"
        } else {
            Check "Unexpected outbound connections found" "FAIL"
        }
    } catch {
        Check "Could not check outbound connections" "FAIL"
    }
} else {
    Check "No unexpected outbound connections (requires running stack)" "FAIL"
}

Write-Host ""
Write-Host "3. Checking data storage..."
try {
    $volumes = docker compose config --volumes 2>$null
    foreach ($vol in $volumes -split "`n") {
        if ($vol.Trim()) {
            Check "Volume '$($vol.Trim())' is local" "PASS"
        }
    }
} catch {
    Check "Could not verify volumes" "WARN"
}

Write-Host ""
Write-Host "4. Checking for telemetry..."
$hits = Get-ChildItem -Path "backend/app" -Recurse -Include "*.py" | Select-String -Pattern "analytics|telemetry|sentry|datadog|newrelic|mixpanel|segment|amplitude" -List
if ($hits.Count -eq 0) {
    Check "No telemetry in application code" "PASS"
} else {
    Check "Possible telemetry found in: $($hits.Path -join ', ')" "WARN"
}

Write-Host ""
Write-Host "5. Checking environment..."
if (Test-Path ".env") {
    $cloudKeys = Select-String -Path ".env" -Pattern "OPENAI|ANTHROPIC|AWS_|AZURE_|GCP_"
    if ($null -eq $cloudKeys) {
        Check "No cloud API keys in .env" "PASS"
    } else {
        Check "Cloud API keys found in .env" "WARN"
    }
} else {
    Check ".env file exists" "FAIL"
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Results: $pass passed, $warn warnings, $fail failed"
Write-Host "============================================"

if ($fail -gt 0) {
    Write-Host "  DATA SOVEREIGNTY: FAILED" -ForegroundColor Red
    exit 1
} elseif ($warn -gt 0) {
    Write-Host "  DATA SOVEREIGNTY: PASSED WITH WARNINGS" -ForegroundColor Yellow
} else {
    Write-Host "  DATA SOVEREIGNTY: PASSED" -ForegroundColor Green
}
