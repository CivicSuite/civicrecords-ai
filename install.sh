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
    if [ "$OS" = "Darwin" ]; then
        sed -i '' "s/CHANGE-ME-generate-with-openssl-rand-hex-32/$JWT_SECRET/" .env
    else
        sed -i "s/CHANGE-ME-generate-with-openssl-rand-hex-32/$JWT_SECRET/" .env
    fi
    echo ""
    echo "IMPORTANT: Edit .env to set your admin email and password:"
    echo "  nano .env"
    echo ""
    read -p "Press Enter after editing .env, or Ctrl+C to edit later..."
fi

# Pull and build
echo ">>> Pulling Docker images..."
docker compose pull

echo ">>> Building application images..."
docker compose build

# Run migrations before starting app
echo ">>> Running database migrations..."
docker compose up -d postgres redis
echo "Waiting for database..."
for i in $(seq 1 30); do
    if docker compose exec postgres pg_isready -U civicrecords &>/dev/null; then
        echo "[OK] Database is ready"
        break
    fi
    echo "  Waiting for database... ($i/30)"
    sleep 2
done
docker compose run --rm api alembic upgrade head

# Start all services
echo ">>> Starting all services..."
docker compose up -d

# Wait for health
echo ">>> Waiting for API to be healthy..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health &>/dev/null; then
        echo "[OK] API is healthy!"
        break
    fi
    echo "  Waiting... ($i/30)"
    sleep 5
done

# Pull embedding model
echo ">>> Pulling embedding model (required for search)..."
docker compose exec ollama ollama pull nomic-embed-text || echo "[WARN] Embedding model pull failed — retry: docker compose exec ollama ollama pull nomic-embed-text"

echo ""
echo ">>> To enable AI-powered search, pull a language model:"
echo "    docker compose exec ollama ollama pull gemma4:26b    (recommended, ~15GB)"
echo "    docker compose exec ollama ollama pull gemma3:4b     (lighter alternative, ~2.5GB)"

# Get IP
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
echo "  Run sovereignty check: bash scripts/verify-sovereignty.sh"
echo "============================================"
