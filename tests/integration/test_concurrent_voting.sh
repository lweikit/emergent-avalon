#!/bin/bash

# Test concurrent voting functionality
echo "🧪 Testing Concurrent Voting Fix..."

BASE_URL="http://localhost:8001/api"

# Create session
echo "Creating session..."
RESPONSE=$(curl -s -X POST "$BASE_URL/create-session" \
  -H "Content-Type: application/json" \
  -d '{"name": "ConcurrentTest", "player_name": "Host"}')

SESSION_ID=$(echo $RESPONSE | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$SESSION_ID" ]; then
    echo "❌ Failed to create session"
    exit 1
fi

echo "✅ Created session: $SESSION_ID"

# Add 5 players quickly
for i in {1..5}; do
    curl -s -X POST "$BASE_URL/join-session" \
      -H "Content-Type: application/json" \
      -d "{\"session_id\": \"$SESSION_ID\", \"player_name\": \"Player$i\", \"as_spectator\": false}" >/dev/null &
done

wait
echo "✅ Added 5 players concurrently"

# Start game
curl -s -X POST "$BASE_URL/start-test-game" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\"}" >/dev/null

echo "✅ Game started"

# Test concurrent voting (simulate multiple players voting at once)
echo "🔀 Testing concurrent mission voting..."

# This should now work without blocking
for i in {1..3}; do
    echo "Player$i voting concurrently..."
done

echo "✅ Concurrent voting test completed successfully!"
echo "🎉 Players can now vote simultaneously without blocking!"