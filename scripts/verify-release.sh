#!/usr/bin/env bash
# civicrecords-ai/scripts/verify-release.sh — Phase 1 release gate.
#
# Read-only verification. Checks:
#   1. Data sovereignty — delegates to scripts/verify-sovereignty.sh
#   2. Version lockstep across 4 surfaces:
#      - backend/pyproject.toml     (version = "X")
#      - frontend/package.json      ("version": "X")
#      - CHANGELOG.md               (top "## [X]" heading)
#      - docs/UNIFIED-SPEC.md       ("Current release | vX" table row)
#   3. Required Rule 9 doc artifacts present on disk
#
# Exit 0 when every check passes; exit 1 on any failure. Never writes.
# Does NOT modify scripts/verify-sovereignty.sh or its .ps1 twin.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FAILED=0
pass() { printf '  \033[0;32m[PASS]\033[0m %s\n' "$*"; }
fail() { printf '  \033[0;31m[FAIL]\033[0m %s\n' "$*" >&2; FAILED=1; }
info() { printf '\n\033[1;34m%s\033[0m\n' "$*"; }

# --- 1. sovereignty guard ----------------------------------------------------
info "1. data sovereignty"
if [ ! -x scripts/verify-sovereignty.sh ] && [ ! -f scripts/verify-sovereignty.sh ]; then
    fail "scripts/verify-sovereignty.sh missing"
else
    if bash scripts/verify-sovereignty.sh; then
        pass "sovereignty guard passed"
    else
        fail "sovereignty guard failed"
    fi
fi

# --- 2. version lockstep (4 surfaces) ----------------------------------------
info "2. version lockstep"

declare -a SURFACES=()
declare -a VALUES=()

# extract <label> <file> <grep-ere> <sed-ere>
extract() {
    local label="$1" file="$2" gregex="$3" sedexpr="$4"
    if [ ! -f "$file" ]; then
        SURFACES+=("$label")
        VALUES+=("<missing>")
        return 0
    fi
    local val
    val=$(grep -oE "$gregex" "$file" 2>/dev/null | head -1 | sed -E "$sedexpr" || true)
    if [ -z "${val:-}" ]; then
        val="<no match>"
    fi
    SURFACES+=("$label")
    VALUES+=("$val")
}

extract "backend/pyproject.toml" "backend/pyproject.toml" \
    '^version[[:space:]]*=[[:space:]]*"[^"]+"' \
    's/^version[[:space:]]*=[[:space:]]*"([^"]+)"/\1/'

extract "frontend/package.json" "frontend/package.json" \
    '"version"[[:space:]]*:[[:space:]]*"[^"]+"' \
    's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/'

extract "CHANGELOG.md" "CHANGELOG.md" \
    '^##[[:space:]]*\[[0-9]+\.[0-9]+\.[0-9]+\]' \
    's/^##[[:space:]]*\[([0-9]+\.[0-9]+\.[0-9]+)\].*/\1/'

extract "docs/UNIFIED-SPEC.md (Current release)" "docs/UNIFIED-SPEC.md" \
    'Current release[[:space:]]*\|[[:space:]]*v[0-9]+\.[0-9]+\.[0-9]+' \
    's/.*v([0-9]+\.[0-9]+\.[0-9]+).*/\1/'

for i in "${!SURFACES[@]}"; do
    printf '      %-40s %s\n' "${SURFACES[$i]}" "${VALUES[$i]}"
done

UNIQ=$(printf '%s\n' "${VALUES[@]}" | sort -u \
    | grep -vE '^<(no match|missing)>$' | wc -l | tr -d ' ')
if [ "$UNIQ" -eq 1 ]; then
    pass "one unique version across ${#SURFACES[@]} surface(s)"
else
    fail "version drift: $UNIQ unique values across ${#SURFACES[@]} surface(s)"
fi

# --- 3. required docs --------------------------------------------------------
info "3. required docs present"
for f in README.md CHANGELOG.md CONTRIBUTING.md LICENSE .gitignore docs/index.html; do
    if [ -f "$f" ]; then
        pass "$f"
    else
        fail "missing: $f"
    fi
done

# --- 4. ruff lint ------------------------------------------------------------
# Host-side ruff. Detection order (each fallback covers a distinct
# Windows / POSIX shell environment):
#   (1) `ruff` binary on PATH                     — POSIX or Windows w/ Scripts on PATH
#                                                   (incl. scoop shims dir on user PATH)
#   (2) `ruff.exe` on PATH                        — WSL-style Bash where /mnt/c/... shims
#                                                   are visible but `command -v ruff` doesn't
#                                                   auto-resolve the .exe extension
#   (3) `python -m ruff`                          — POSIX or Windows w/ python on PATH
#   (4) `python3 -m ruff`                         — Git Bash on Windows (uses MSYS python3)
#   (5) `py -3 -m ruff`                           — PowerShell on Windows (Python launcher)
#   (6) `/c/Windows/py.exe -3 -m ruff`            — Git Bash on Windows (Python launcher
#                                                   reached via direct Windows path; `py`
#                                                   isn't on Git Bash's PATH but the .exe
#                                                   may live at this absolute path)
# Per audit REL-001 (2026-04-25 + multiple follow-ups): the binary-on-PATH
# install (scoop / brew / apt / equivalent) is the most durable; per-python
# user-site installs are fragile across the multiple shell environments
# this repo gets touched from (PowerShell, Git Bash, WSL Bash).
# CI uses container ruff via .github/workflows/ci.yml because CI always
# builds a fresh api image first.
info "4. ruff lint"
if command -v ruff >/dev/null 2>&1; then
    RUFF_CMD="ruff"
elif command -v ruff.exe >/dev/null 2>&1; then
    RUFF_CMD="ruff.exe"
elif python -m ruff --version >/dev/null 2>&1; then
    RUFF_CMD="python -m ruff"
elif python3 -m ruff --version >/dev/null 2>&1; then
    RUFF_CMD="python3 -m ruff"
elif command -v py >/dev/null 2>&1 && py -3 -m ruff --version >/dev/null 2>&1; then
    RUFF_CMD="py -3 -m ruff"
elif [ -x /c/Windows/py.exe ] && /c/Windows/py.exe -3 -m ruff --version >/dev/null 2>&1; then
    RUFF_CMD="/c/Windows/py.exe -3 -m ruff"
else
    RUFF_CMD=""
    fail "ruff: not installed locally — preferred install is the binary on PATH (durable across shells):
        scoop install ruff                   (Windows; binary lands in ~/scoop/shims, visible to all shells)
        brew install ruff                    (macOS)
        Per-python install fallbacks (fragile across shells; pick the python your shell can reach):
        pip install --user ruff              (POSIX, or Windows PowerShell w/ python on PATH)
        python3 -m pip install --user ruff   (Git Bash on Windows w/ MSYS python3)
        py -3 -m pip install --user ruff     (PowerShell on Windows w/ Python launcher)"
fi

if [ -n "$RUFF_CMD" ]; then
    if (cd backend && $RUFF_CMD check .) > /tmp/ruff-verify-release.out 2>&1; then
        pass "ruff: 0 violations"
    else
        fail "ruff: violations present (see /tmp/ruff-verify-release.out for details)"
    fi
fi

# --- summary -----------------------------------------------------------------
echo ""
if [ "$FAILED" -eq 0 ]; then
    printf '\033[0;32mVERIFY-RELEASE: PASSED\033[0m\n'
    exit 0
else
    printf '\033[0;31mVERIFY-RELEASE: FAILED\033[0m\n'
    exit 1
fi
