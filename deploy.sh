#!/bin/bash
# Quick deployment script for GVM
# Usage: ./deploy.sh

set -e  # Exit on error

echo "🚀 Capacity Chatbot Service - Deployment Script"
echo "================================================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "📝 Please create a .env file with your configuration."
    echo "   See DEPLOYMENT_GUIDE.md for required variables."
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed!"
    echo "📦 Install Docker: sudo apt-get install -y docker.io docker-compose"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed!"
    echo "📦 Install Docker Compose: sudo apt-get install -y docker-compose"
    exit 1
fi

# Check if user is in docker group
if ! groups | grep -q docker; then
    echo "⚠️  Warning: User not in docker group. You may need to use sudo."
    echo "   To fix: sudo usermod -aG docker \$USER && newgrp docker"
fi

echo ""
echo "📦 Building and starting containers..."
docker-compose up -d --build

echo ""
echo "⏳ Waiting for service to start..."
sleep 5

echo ""
echo "🔍 Checking service status..."
docker-compose ps

echo ""
echo "📋 Recent logs:"
docker-compose logs --tail=20 backend

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Useful commands:"
echo "   View logs:    docker-compose logs -f backend"
echo "   Stop service: docker-compose down"
echo "   Restart:      docker-compose restart backend"
echo "   Status:       docker-compose ps"
echo ""
echo "🌐 Service should be available at: http://localhost:8000"
echo "   (Or your GVM's external IP:8000 if firewall is configured)"

