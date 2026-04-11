#!/bin/bash

# Test script to simulate 7 players joining a session
echo "🧪 Testing 7-player join scenario..."

BASE_URL="http://localhost:8001/api"

# Create session
echo "Creating session..."
RESPONSE=$(curl -s -X POST "$BASE_URL/create-session" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test7Players", "player_name": "Host"}')

SESSION_ID=$(echo $RESPONSE | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$SESSION_ID" ]; then
    echo "❌ Failed to create session"
    echo "Response: $RESPONSE"
    exit 1
fi

echo "✅ Created session: $SESSION_ID"

# Add 7 players
for i in {1..7}; do
    echo "Adding Player$i..."
    
    RESPONSE=$(curl -s -X POST "$BASE_URL/join-session" \
      -H "Content-Type: application/json" \
      -d "{\"session_id\": \"$SESSION_ID\", \"player_name\": \"Player$i\", \"as_spectator\": false}")
    
    if echo "$RESPONSE" | grep -q "player_id"; then
        echo "✅ Added Player$i"
    else
        echo "❌ Failed to add Player$i"
        echo "Response: $RESPONSE"
        exit 1
    fi
    
    sleep 0.5
done

echo "🎉 Successfully added 7 players!"

# Try to start the game
echo "Starting game..."
RESPONSE=$(curl -s -X POST "$BASE_URL/start-game" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\"}")

if echo "$RESPONSE" | grep -q "successfully"; then
    echo "✅ Game started successfully!"
else
    echo "❌ Failed to start game"
    echo "Response: $RESPONSE"
fi