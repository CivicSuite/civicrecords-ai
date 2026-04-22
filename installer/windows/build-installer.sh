#!/bin/bash
# Build the CivicRecords AI Windows installer using Inno Setup.
#
# T5E (Tier 5 Blocker E) — UNSIGNED BY DESIGN. No code-signing step here.
# Scott locked B3 signing posture = α (unsigned) on 2026-04-22.
#
# Adapted from patentforgelocal/installer/windows/build-installer.sh.
# KEY DELTA: the PFL build driver had a typo in its output-name check
# ("PatentForgeLocalLocal-..." — double "Local") that has been
# deliberately NOT carried forward. Our expected output filename matches
# the `.iss` OutputBaseFilename exactly.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Building CivicRecords AI Windows Installer (UNSIGNED) ==="
echo "Repo root: $REPO_ROOT"

# ─── Locate Inno Setup compiler ───────────────────────────────────────────
ISCC=""
if command -v iscc &>/dev/null; then
    ISCC="$(command -v iscc)"
elif [ -f "C:/Program Files (x86)/Inno Setup 6/ISCC.exe" ]; then
    ISCC="C:/Program Files (x86)/Inno Setup 6/ISCC.exe"
elif [ -f "C:/Program Files/Inno Setup 6/ISCC.exe" ]; then
    ISCC="C:/Program Files/Inno Setup 6/ISCC.exe"
fi

if [ -z "$ISCC" ] || [ ! -f "$ISCC" ]; then
    echo "ERROR: Inno Setup 6 not found."
    echo "Install via:  choco install innosetup -y"
    echo "Or download:  https://jrsoftware.org/isdl.php"
    exit 1
fi
echo "Using ISCC: $ISCC"

# ─── Verify required bundle sources ───────────────────────────────────────
MISSING=0

check_file() {
    if [ ! -f "$REPO_ROOT/$1" ]; then
        echo "MISSING: $1"
        MISSING=1
    fi
}

check_dir() {
    if [ ! -d "$REPO_ROOT/$1" ]; then
        echo "MISSING: $1/"
        MISSING=1
    fi
}

echo ""
echo "Checking bundle sources…"
check_file "install.ps1"
check_file "install.sh"
check_file "docker-compose.yml"
check_file ".env.example"
check_file "Dockerfile.backend"
check_file "Dockerfile.frontend"
check_file "LICENSE"
check_file "README.md"
check_dir  "scripts"
check_dir  "backend/app"
check_dir  "frontend/src"
check_dir  "docs"
check_file "installer/windows/launch-install.ps1"
check_file "installer/windows/launch-start.ps1"
check_file "installer/windows/prereq-check.ps1"
check_file "installer/windows/README.md"

if [ "$MISSING" -eq 1 ]; then
    echo ""
    echo "ERROR: Required bundle sources are missing."
    echo "Verify the repo is intact and try again."
    exit 1
fi
echo "All bundle sources present."

# ─── Resolve the installer version (single authoritative source) ─────────
# Precedence:
#   1. CIVICRECORDS_VERSION env var (CI sets this from the git tag, with
#      any leading "v" stripped, on tagged release builds).
#   2. backend/pyproject.toml [project] version = "..." (authoritative for
#      untagged local dev builds).
#
# The resolved value is passed to ISCC via /DMyAppVersion=<semver> so the
# .iss never carries a hardcoded version string. build-installer.sh and
# .github/workflows/release.yml both route through this same function, so
# the artifact name produced here matches the artifact name the release
# workflow uploads.
resolve_version() {
    if [ -n "${CIVICRECORDS_VERSION:-}" ]; then
        echo "$CIVICRECORDS_VERSION"
        return 0
    fi
    local pyproject="$REPO_ROOT/backend/pyproject.toml"
    if [ ! -f "$pyproject" ]; then
        echo "ERROR: backend/pyproject.toml not found — cannot resolve version." >&2
        return 1
    fi
    # Match the FIRST `version = "X.Y.Z"` under the [project] table. We
    # anchor on the exact shape used by PEP 621 to avoid matching deps.
    local v
    v=$(grep -E '^version[[:space:]]*=[[:space:]]*"[^"]+"' "$pyproject" | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
    if [ -z "$v" ]; then
        echo "ERROR: could not parse [project] version from $pyproject." >&2
        return 1
    fi
    echo "$v"
}

APP_VERSION=$(resolve_version) || exit 1
echo "Resolved installer version: $APP_VERSION"
if [ -n "${CIVICRECORDS_VERSION:-}" ]; then
    echo "  source: \$CIVICRECORDS_VERSION (CI / tag override)"
else
    echo "  source: backend/pyproject.toml (authoritative for local dev)"
fi

# ─── Ensure output directory exists ───────────────────────────────────────
mkdir -p "$REPO_ROOT/build"

# ─── Compile the installer ────────────────────────────────────────────────
echo ""
echo "Compiling installer…"
"$ISCC" "/DMyAppVersion=$APP_VERSION" "$REPO_ROOT/installer/windows/civicrecords-ai.iss"

# OutputBaseFilename in the .iss is CivicRecordsAI-{#MyAppVersion}-Setup,
# so the expected artifact name below is derived from the same resolved
# version. Any drift here is a bug in this script or in the .iss.
OUTPUT="$REPO_ROOT/build/CivicRecordsAI-${APP_VERSION}-Setup.exe"
if [ -f "$OUTPUT" ]; then
    SIZE=$(du -h "$OUTPUT" | cut -f1)
    # SHA-256 for release-page verification (operators can compare
    # against the checksum published on the GitHub release).
    SHA256=""
    if command -v sha256sum &>/dev/null; then
        SHA256=$(sha256sum "$OUTPUT" | awk '{print $1}')
    elif command -v shasum &>/dev/null; then
        SHA256=$(shasum -a 256 "$OUTPUT" | awk '{print $1}')
    fi
    echo ""
    echo "=== Installer built successfully (UNSIGNED) ==="
    echo "Output:   $OUTPUT"
    echo "Size:     $SIZE"
    if [ -n "$SHA256" ]; then
        echo "SHA-256:  $SHA256"
    fi
    echo ""
    echo "Reminder: this binary is UNSIGNED. Operators who double-click it"
    echo "will see Windows SmartScreen ('Windows protected your PC') on first"
    echo "run. The installer/windows/README.md documents the remediation."
else
    echo ""
    echo "ERROR: Expected output not found at $OUTPUT"
    echo "Contents of build/:"
    ls -la "$REPO_ROOT/build/" 2>/dev/null || echo "  (build/ does not exist)"
    exit 1
fi
