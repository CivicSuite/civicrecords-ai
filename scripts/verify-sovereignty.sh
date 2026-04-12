#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo "  CivicRecords AI — Data Sovereignty Check"
echo "============================================"
echo ""

PASS=0
FAIL=0
WARN=0

check() {
    local desc="$1"
    local result="$2"
    if [ "$result" = "PASS" ]; then
        echo "  [PASS] $desc"
        PASS=$((PASS + 1))
    elif [ "$result" = "WARN" ]; then
        echo "  [WARN] $desc"
        WARN=$((WARN + 1))
    else
        echo "  [FAIL] $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "1. Checking Docker network isolation..."
API_PORTS=$(docker compose port api 8000 2>/dev/null || echo "")
if [ -n "$API_PORTS" ]; then
    check "API bound to local port" "PASS"
else
    check "API bound to local port" "FAIL"
fi

echo ""
echo "2. Checking for outbound connections..."
OUTBOUND=$(docker compose exec api ss -tunp 2>/dev/null | grep -v "127.0.0.1\|172\.\|10\.\|192\.168\." | grep "ESTAB" || true)
if [ -z "$OUTBOUND" ]; then
    check "No unexpected outbound connections from API" "PASS"
else
    check "No unexpected outbound connections from API — found: $OUTBOUND" "FAIL"
fi

echo ""
echo "3. Checking data storage locations..."
VOLUMES=$(docker compose config --volumes 2>/dev/null)
for vol in $VOLUMES; do
    DRIVER=$(docker volume inspect "$(docker compose config --format json | python3 -c "import sys,json; c=json.load(sys.stdin); print(c.get('name','civicrecords-ai') + '_$vol')" 2>/dev/null)" --format '{{.Driver}}' 2>/dev/null || echo "local")
    if [ "$DRIVER" = "local" ]; then
        check "Volume '$vol' uses local storage driver" "PASS"
    else
        check "Volume '$vol' uses non-local driver: $DRIVER" "FAIL"
    fi
done

echo ""
echo "4. Checking for telemetry endpoints..."
TELEMETRY_HITS=$(grep -r "analytics\|telemetry\|sentry\|datadog\|newrelic\|mixpanel\|segment\|amplitude" backend/app/ --include="*.py" -l 2>/dev/null || true)
if [ -z "$TELEMETRY_HITS" ]; then
    check "No telemetry libraries found in application code" "PASS"
else
    check "Possible telemetry found in: $TELEMETRY_HITS" "WARN"
fi

echo ""
echo "5. Checking environment configuration..."
if [ -f .env ]; then
    CLOUD_KEYS=$(grep -iE "OPENAI|ANTHROPIC|AWS_|AZURE_|GCP_" .env || true)
    if [ -z "$CLOUD_KEYS" ]; then
        check "No cloud API keys in .env" "PASS"
    else
        check "Cloud API keys found in .env — data may leave the network" "WARN"
    fi
else
    check ".env file exists" "FAIL"
fi

echo ""
echo "============================================"
echo "  Results: $PASS passed, $WARN warnings, $FAIL failed"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    echo "  DATA SOVEREIGNTY: FAILED — review issues above"
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo "  DATA SOVEREIGNTY: PASSED WITH WARNINGS"
    exit 0
else
    echo "  DATA SOVEREIGNTY: PASSED"
    exit 0
fi
