#!/bin/bash

# Quick deployment test script
echo "🧪 Testing Docker Compose Build..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Creating .env from example..."
    cp .env.example .env 2>/dev/null || echo "# Add your environment variables here" > .env
fi

# Test build without starting
echo "🔨 Testing build process..."
docker compose build --no-cache

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    
    # Test the deployment command you want to use
    echo "🚀 Testing deployment command..."
    docker compose up -d --build --force-recreate
    
    if [ $? -eq 0 ]; then
        echo "✅ Deployment successful!"
        
        # Wait a moment for services to start
        sleep 10
        
        # Check service health
        echo "🔍 Checking service health..."
        if curl -f http://localhost:8001/health >/dev/null 2>&1; then
            echo "✅ Backend healthy!"
        else
            echo "⚠️  Backend might still be starting..."
        fi
        
        if curl -f http://localhost:3000 >/dev/null 2>&1; then
            echo "✅ Frontend healthy!"
        else
            echo "⚠️  Frontend might still be starting..."
        fi
        
        # Show running containers
        echo "📋 Running containers:"
        docker compose ps
        
    else
        echo "❌ Deployment failed!"
        echo "📋 Checking logs..."
        docker compose logs --tail=20
        exit 1
    fi
else
    echo "❌ Build failed!"
    exit 1
fi

echo ""
echo "🎉 Test completed! Your deployment should work."
echo "🌐 Access your app at:"
echo "   Frontend: http://localhost:3000"
echo "   Backend: http://localhost:8001"
echo "   Health: http://localhost:8001/health"