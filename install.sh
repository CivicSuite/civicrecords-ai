#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo "  CivicRecords AI — Installation Script"
echo "  Target: Ubuntu 24.04 LTS"
echo "============================================"
echo ""

# Check OS
if ! grep -q "Ubuntu 24" /etc/os-release 2>/dev/null; then
    echo "WARNING: This script is designed for Ubuntu 24.04 LTS."
    echo "Your OS may work but is not officially supported."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi
fi

# Install Docker if not present
if ! command -v docker &>/dev/null; then
    echo ">>> Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "Docker installed. You may need to log out and back in for group changes."
fi

# Install Docker Compose plugin if not present
if ! docker compose version &>/dev/null; then
    echo ">>> Installing Docker Compose plugin..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
fi

# Create .env from template if not exists
if [ ! -f .env ]; then
    echo ">>> Creating .env from template..."
    cp .env.example .env
    # Generate a random JWT secret
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s/CHANGE-ME-generate-with-openssl-rand-hex-32/$JWT_SECRET/" .env
    echo ""
    echo "IMPORTANT: Edit .env to set your admin email and password:"
    echo "  nano .env"
    echo ""
    read -p "Press Enter after editing .env, or Ctrl+C to edit later..."
fi

# Pull and start services
echo ">>> Pulling Docker images..."
docker compose pull

echo ">>> Building application images..."
docker compose build

echo ">>> Starting services..."
docker compose up -d

# Wait for health
echo ">>> Waiting for services to be healthy..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health &>/dev/null; then
        echo "API is healthy!"
        break
    fi
    echo "  Waiting... ($i/30)"
    sleep 5
done

# Pull recommended Ollama model
echo ">>> Pulling recommended LLM model (this may take a while)..."
docker compose exec ollama ollama pull gemma3:4b-it-qf4_0 || echo "Model pull failed — you can retry later with: docker compose exec ollama ollama pull <model>"

echo ""
echo "============================================"
echo "  Installation complete!"
echo ""
echo "  Admin panel:  http://$(hostname -I | awk '{print $1}'):8080"
echo "  API:          http://$(hostname -I | awk '{print $1}'):8000"
echo "  API docs:     http://$(hostname -I | awk '{print $1}'):8000/docs"
echo ""
echo "  Run sovereignty check: bash scripts/verify-sovereignty.sh"
echo "============================================"
