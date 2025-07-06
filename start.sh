#!/bin/bash

echo "🏰 Starting Avalon Board Game..."
if [ ! -f .env ]; then
  echo "⚠️  .env file not found. Copy .env.example to .env and adjust settings."
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install Docker Compose."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "📦 Building and starting services..."
docker-compose up --build

echo "🎉 Avalon game is now running!"
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend API: ${REACT_APP_BACKEND_URL:-http://localhost:8001}"
echo "📚 API Docs: ${REACT_APP_BACKEND_URL:-http://localhost:8001}/docs"
echo ""
echo "To stop the game, press Ctrl+C or run: docker-compose down"
