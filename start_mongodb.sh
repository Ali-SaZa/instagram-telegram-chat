#!/bin/bash

# MongoDB Docker Startup Script for Instagram-Telegram Chat Project

echo "🚀 Starting MongoDB with Docker for Instagram-Telegram Chat Project..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml not found. Please run this script from the project root directory."
    exit 1
fi

echo "📦 Starting MongoDB and Mongo Express..."
docker-compose up -d

# Wait a moment for services to start
echo "⏳ Waiting for services to start..."
sleep 5

# Check service status
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "✅ MongoDB is now running!"
echo ""
echo "🌐 MongoDB: localhost:27017"
echo "🔧 Mongo Express (Admin): http://localhost:8081"
echo "   Username: admin"
echo "   Password: password123"
echo ""
echo "📝 To view logs: docker-compose logs -f"
echo "🛑 To stop: docker-compose down"
echo ""
echo "🎯 Next steps:"
echo "   1. Copy env.docker to .env: cp env.docker .env"
echo "   2. Edit .env with your Telegram bot token"
echo "   3. Test connection: python3 test_db_connection.py"
echo "   4. Start your application: python3 src/main.py"
echo "" 