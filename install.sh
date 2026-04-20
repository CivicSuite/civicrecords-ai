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
fi

# ─── Hardware Detection ───────────────────────────────────────────────────────
echo ""
echo "Detecting hardware capabilities..."
bash scripts/detect_hardware.sh || echo "[WARN] Hardware detection failed — defaulting to CPU mode"
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

# ─── Pull Models ─────────────────────────────────────────────────────────────
RECOMMENDED_MODEL="${CIVICRECORDS_RECOMMENDED_MODEL:-gemma4:12b}"

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

echo ""
echo ">>> To enable AI-powered search, pull a language model:"
echo "    docker compose exec ollama ollama pull $RECOMMENDED_MODEL"
if [ "$RECOMMENDED_MODEL" = "gemma4:12b" ]; then
    echo "    (recommended for your ${CIVICRECORDS_TOTAL_RAM_GB:-32}GB RAM configuration)"
    echo "    Alternative: docker compose exec ollama ollama pull gemma4:27b  (needs 48GB+ RAM)"
else
    echo "    (recommended for your ${CIVICRECORDS_TOTAL_RAM_GB:-64}GB RAM configuration)"
fi

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
