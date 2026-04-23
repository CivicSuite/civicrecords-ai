#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo "  CivicRecords AI — Installation Script"
echo "  Supports: Linux (Ubuntu/Debian), macOS"
echo "============================================"
echo ""

OS="$(uname -s)"

# Check/install Docker
if ! command -v docker &>/dev/null; then
    echo ">>> Docker not found. Installing..."
    if [ "$OS" = "Linux" ]; then
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker "$USER"
        echo "Docker installed. You may need to log out and back in for group changes."
    elif [ "$OS" = "Darwin" ]; then
        echo "Please install Docker Desktop for Mac from:"
        echo "  https://www.docker.com/products/docker-desktop/"
        echo "Then re-run this script."
        exit 1
    fi
fi

# Check Docker Compose
if ! docker compose version &>/dev/null; then
    echo ">>> Docker Compose not found."
    if [ "$OS" = "Linux" ]; then
        sudo apt-get update && sudo apt-get install -y docker-compose-plugin
    else
        echo "Docker Compose is included with Docker Desktop. Make sure Docker Desktop is running."
        exit 1
    fi
fi

# Check Docker is running
if ! docker info &>/dev/null; then
    echo "ERROR: Docker daemon is not running. Start Docker first."
    exit 1
fi

echo "[OK] Docker $(docker --version | cut -d' ' -f3)"
echo "[OK] $(docker compose version)"

# Create .env from template if not exists
if [ ! -f .env ]; then
    echo ">>> Creating .env from template..."
    cp .env.example .env
    JWT_SECRET=$(openssl rand -hex 32)
    # T2C: generate a strong admin password instead of leaving the placeholder.
    # Settings.check_first_admin_password rejects the .env.example value at startup.
    # Use hex so the value contains no shell or .env-parser metacharacters.
    ADMIN_PASSWORD=$(openssl rand -hex 16)
    if [ "$OS" = "Darwin" ]; then
        sed -i '' "s|CHANGE-ME-generate-with-openssl-rand-hex-32|$JWT_SECRET|" .env
        sed -i '' "s|CHANGE-ME-on-first-login|$ADMIN_PASSWORD|" .env
    else
        sed -i "s|CHANGE-ME-generate-with-openssl-rand-hex-32|$JWT_SECRET|" .env
        sed -i "s|CHANGE-ME-on-first-login|$ADMIN_PASSWORD|" .env
    fi
    echo ""
    echo "============================================"
    echo "  ADMIN PASSWORD GENERATED — copy this now"
    echo "============================================"
    echo "  Email:    admin@example.gov  (edit .env to change)"
    echo "  Password: $ADMIN_PASSWORD"
    echo "============================================"
    echo "  This password is stored in .env. Store it in your password manager."
    echo "  Press Enter when you have copied it."
    echo ""
    read -p "Press Enter to continue, or Ctrl+C to edit .env first..."

    # T5D — install-time PORTAL_MODE selection. Default is "private" (the
    # safer posture — staff-only, no public surface). Operators choose
    # "public" to expose the resident landing page + submission form +
    # resident-registration path (locked B4=(b) minimal surface).
    # Non-interactive installs can set CIVICRECORDS_PORTAL_MODE before
    # invoking install.sh to skip the prompt.
    if [ -n "$CIVICRECORDS_PORTAL_MODE" ]; then
        PORTAL_MODE_CHOICE=$(echo "$CIVICRECORDS_PORTAL_MODE" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
        if [ "$PORTAL_MODE_CHOICE" != "public" ] && [ "$PORTAL_MODE_CHOICE" != "private" ]; then
            echo ""
            echo "[WARN] CIVICRECORDS_PORTAL_MODE='$CIVICRECORDS_PORTAL_MODE' is not 'public' or 'private' — falling back to 'private'."
            PORTAL_MODE_CHOICE="private"
        else
            echo ""
            echo "PORTAL_MODE=$PORTAL_MODE_CHOICE (from env, non-interactive install)"
        fi
    elif [ -t 0 ]; then
        echo ""
        echo "============================================"
        echo "  Portal mode (T5D)"
        echo "============================================"
        echo "  private (default): staff-only deployment. No public routes. Residents"
        echo "                     cannot self-register. Login screen is the only"
        echo "                     externally reachable page."
        echo "  public:            exposes a minimal public surface — landing page,"
        echo "                     resident registration, and an authenticated"
        echo "                     records-request submission form for residents."
        echo ""
        read -p "Install in public mode? [y/N] " PORTAL_ANSWER
        PORTAL_ANSWER=$(echo "$PORTAL_ANSWER" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
        case "$PORTAL_ANSWER" in
            y|yes|public) PORTAL_MODE_CHOICE="public" ;;
            *)            PORTAL_MODE_CHOICE="private" ;;
        esac
        echo "PORTAL_MODE=$PORTAL_MODE_CHOICE"
    else
        PORTAL_MODE_CHOICE="private"
        echo "PORTAL_MODE=private (non-interactive install, default)"
    fi

    # Persist the chosen mode into .env, replacing the default "private"
    # value shipped by .env.example.
    if [ "$OS" = "Darwin" ]; then
        sed -i '' "s|^PORTAL_MODE=private$|PORTAL_MODE=$PORTAL_MODE_CHOICE|" .env
    else
        sed -i "s|^PORTAL_MODE=private$|PORTAL_MODE=$PORTAL_MODE_CHOICE|" .env
    fi
fi

# ─── Hardware Detection ───────────────────────────────────────────────────────
# T5C correction pass (2026-04-21): the detect_hardware.sh gate now exits 1
# when RAM < 32 GB (Tier 5 target-profile baseline), matching the Windows
# install.ps1 behavior (detect_hardware.ps1 L64: `exit 1` below 32 GB). We
# therefore propagate that failure instead of warning-and-continuing — an
# under-spec machine is not a "defaulting to CPU mode" scenario; it's a
# below-support-floor scenario and the installer must stop.
echo ""
echo "Detecting hardware capabilities..."
if ! bash scripts/detect_hardware.sh; then
    echo ""
    echo "[ERROR] Hardware gate failed. The machine does not meet the CivicRecords AI"
    echo "        target-profile baseline (32 GB RAM minimum). Installation aborted."
    echo "        Review the hardware-detection output above for the specific failure,"
    echo "        or rerun scripts/detect_hardware.sh on its own to see the full probe."
    exit 1
fi
echo ""

# Source the hardware config
if [ -f ".env.hardware" ]; then
    # shellcheck disable=SC1091
    source .env.hardware
fi

# ─── Select Compose Configuration ────────────────────────────────────────────
COMPOSE_FILES="-f docker-compose.yml"

if [ "${CIVICRECORDS_GPU_ENABLED:-false}" = "true" ]; then
    echo "GPU acceleration enabled — using ROCm device passthrough"
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.gpu.yml"
else
    echo "GPU not detected or not available — using CPU inference"
fi

# ─── Build Application Images ────────────────────────────────────────────────
echo ""
echo ">>> Pulling Docker images..."
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES pull

echo ">>> Building application images..."
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES build

# ─── Start Infrastructure and Wait for Database ──────────────────────────────
echo ">>> Starting database and cache..."
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES --env-file .env up -d postgres redis

echo ">>> Waiting for database..."
for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U civicrecords -q 2>/dev/null; then
        echo "[OK] Database is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: PostgreSQL did not become ready after 30 attempts."
        echo "Check: docker compose logs postgres"
        exit 1
    fi
    echo "  Waiting for database... ($i/30)"
    sleep 2
done

# ─── Run Migrations ──────────────────────────────────────────────────────────
echo ">>> Running database migrations..."
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES run --rm api alembic upgrade head

# ─── Start All Services ──────────────────────────────────────────────────────
echo ">>> Starting all services..."
# shellcheck disable=SC2086
if [ -f ".env.hardware" ]; then
    docker compose $COMPOSE_FILES --env-file .env --env-file .env.hardware up -d
else
    docker compose $COMPOSE_FILES --env-file .env up -d
fi

# Wait for API health
echo ">>> Waiting for API to be healthy..."
API_HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health &>/dev/null; then
        echo "[OK] API is healthy!"
        API_HEALTHY=true
        break
    fi
    echo "  Waiting... ($i/30)"
    sleep 5
done

if [ "$API_HEALTHY" = "false" ]; then
    echo "[WARN] API health check timed out. Check logs with: docker compose logs api"
fi

# ─── Gemma 4 Model Picker + Auto-Pull ────────────────────────────────────────
# Tier 5 Blocker 1 (locked 2026-04-21). All four supported Gemma 4 tags are
# presented. Default is gemma4:e4b. Target profile baseline is Windows 11 Pro
# 23H2+ / 32 GB min (64 GB rec) / GPU optional / CPU-only supportable.
# Only gemma4:e2b and gemma4:e4b are supportable at baseline. gemma4:26b and
# gemma4:31b require stronger hardware and are gated behind an explicit
# "yes" confirmation.
# Non-interactive install (CI, piped stdin): default is used unless env var
# CIVICRECORDS_SELECTED_MODEL=<tag> is set.

echo ""
echo ">>> Waiting for Ollama to be ready..."
for i in $(seq 1 30); do
    # shellcheck disable=SC2086
    if docker compose $COMPOSE_FILES exec -T ollama ollama list &>/dev/null; then
        echo "[OK] Ollama is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "[WARN] Ollama did not become ready. Model pull may fail."
    fi
    echo "  Waiting for Ollama... ($i/30)"
    sleep 3
done

echo ">>> Pulling embedding model (required for search)..."
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES exec ollama ollama pull nomic-embed-text || echo "[WARN] Embedding model pull failed — retry: docker compose exec ollama ollama pull nomic-embed-text"

DEFAULT_MODEL="gemma4:e4b"
SUPPORTED_MODELS="gemma4:e2b gemma4:e4b gemma4:26b gemma4:31b"

# Detect whether any supported Gemma 4 model is already present in Ollama
# shellcheck disable=SC2086
OLLAMA_LIST_OUTPUT=$(docker compose $COMPOSE_FILES exec -T ollama ollama list 2>/dev/null || true)
EXISTING_MODEL=""
for M in $SUPPORTED_MODELS; do
    if printf '%s\n' "$OLLAMA_LIST_OUTPUT" | grep -q "^${M} "; then
        EXISTING_MODEL="$M"
        break
    fi
done

SELECTED_MODEL="${CIVICRECORDS_SELECTED_MODEL:-}"

if [ -n "$EXISTING_MODEL" ] && [ -z "$SELECTED_MODEL" ]; then
    echo ""
    echo "[OK] Supported Gemma 4 model already present in Ollama: $EXISTING_MODEL"
    echo "     Skipping language-model pull."
    SELECTED_MODEL="$EXISTING_MODEL"
else
    echo ""
    echo "===== Gemma 4 model picker ====="
    echo ""
    echo "CivicRecords AI supports four Gemma 4 models. The target profile is"
    echo "Windows 11 Pro 23H2+ / 32 GB RAM minimum (64 GB recommended) /"
    echo "GPU optional / CPU-only supported. Models 26b and 31b require stronger"
    echo "hardware than the baseline and must be selected explicitly."
    echo ""
    echo "  1) gemma4:e2b  Edge / 2.3B effective params / 7.2 GB disk / ~16 GB RAM  [supportable]"
    echo "  2) gemma4:e4b  Edge / 4.5B effective params / 9.6 GB disk / ~20 GB RAM  [supportable]  (DEFAULT)"
    echo "  3) gemma4:26b  Workstation MoE / 25.2B total, 3.8B active /  18 GB disk / 48+ GB RAM recommended  [not supportable at 32 GB baseline]"
    echo "  4) gemma4:31b  Workstation dense / 30.7B params            /  20 GB disk / 64+ GB RAM recommended  [not supportable at 32 GB baseline; GPU recommended]"
    echo ""

    if [ -n "$SELECTED_MODEL" ]; then
        echo "Using CIVICRECORDS_SELECTED_MODEL=$SELECTED_MODEL (non-interactive override)."
    elif [ -t 0 ]; then
        printf "Enter 1-4 (or press Enter for default gemma4:e4b): "
        read -r CHOICE
        case "$CHOICE" in
            1) SELECTED_MODEL="gemma4:e2b" ;;
            ""|2) SELECTED_MODEL="gemma4:e4b" ;;
            3) SELECTED_MODEL="gemma4:26b" ;;
            4) SELECTED_MODEL="gemma4:31b" ;;
            *) echo "Unknown choice '$CHOICE' — falling back to default gemma4:e4b."
               SELECTED_MODEL="gemma4:e4b" ;;
        esac

        case "$SELECTED_MODEL" in
            gemma4:26b)
                echo ""
                echo "WARNING: gemma4:26b is NOT supportable at the 32 GB baseline target profile."
                echo "         Your machine should have at least 48 GB RAM for acceptable performance."
                printf "Type 'yes' to confirm and proceed with gemma4:26b anyway: "
                read -r CONFIRM
                if [ "$CONFIRM" != "yes" ]; then
                    echo "Aborted gemma4:26b selection. Falling back to default gemma4:e4b."
                    SELECTED_MODEL="gemma4:e4b"
                fi
                ;;
            gemma4:31b)
                echo ""
                echo "WARNING: gemma4:31b is NOT supportable at the 32 GB baseline target profile."
                echo "         Your machine should have at least 64 GB RAM, and a GPU is recommended."
                printf "Type 'yes' to confirm and proceed with gemma4:31b anyway: "
                read -r CONFIRM
                if [ "$CONFIRM" != "yes" ]; then
                    echo "Aborted gemma4:31b selection. Falling back to default gemma4:e4b."
                    SELECTED_MODEL="gemma4:e4b"
                fi
                ;;
        esac
    else
        SELECTED_MODEL="$DEFAULT_MODEL"
        echo "Non-interactive install — selecting default: $SELECTED_MODEL"
        echo "Override by setting CIVICRECORDS_SELECTED_MODEL=<tag> before running."
    fi

    echo ""
    echo ">>> Pulling $SELECTED_MODEL (this may take several minutes)..."
    # shellcheck disable=SC2086
    if docker compose $COMPOSE_FILES exec ollama ollama pull "$SELECTED_MODEL"; then
        echo "[OK] Model pulled: $SELECTED_MODEL"
    else
        echo "[WARN] Model pull for $SELECTED_MODEL failed. Retry manually:"
        echo "    docker compose exec ollama ollama pull $SELECTED_MODEL"
    fi
fi

echo ""
echo "Selected LLM model: $SELECTED_MODEL"

# Get IP
OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
    IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")
else
    IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
fi

echo ""
echo "============================================"
echo "  Installation complete!"
echo ""
echo "  Admin panel:  http://${IP}:8080"
echo "  API:          http://${IP}:8000"
echo "  API docs:     http://${IP}:8000/docs"
echo ""
if [ "${CIVICRECORDS_GPU_ENABLED:-false}" = "true" ]; then
    echo "  GPU inference: ENABLED (${CIVICRECORDS_PLATFORM} / GFX ${CIVICRECORDS_GFX_VERSION})"
else
    echo "  GPU inference: DISABLED (CPU only)"
    echo "  See docs for GPU enablement on AMD Ryzen"
fi
echo ""
echo "  Run sovereignty check: bash scripts/verify-sovereignty.sh"
echo "============================================"
