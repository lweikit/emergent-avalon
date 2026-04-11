#!/usr/bin/env python3

import asyncio
import aiohttp
import json

# Test script to simulate 7 players joining a session
async def test_seven_players():
    base_url = "http://localhost:8001/api"
    
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing 7-player join scenario...")
        
        # Create session
        create_data = {"session_name": "Test7Players"}
        async with session.post(f"{base_url}/create-session", json=create_data) as resp:
            if resp.status != 200:
                print(f"❌ Failed to create session: {resp.status}")
                return
            result = await resp.json()
            session_id = result["session_id"]
            print(f"✅ Created session: {session_id}")
        
        # Add 7 players
        for i in range(1, 8):
            player_data = {
                "session_id": session_id,
                "player_name": f"Player{i}",
                "as_spectator": False
            }
            
            print(f"Adding Player{i}...")
            async with session.post(f"{base_url}/join-session", json=player_data) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"❌ Failed to add Player{i}: {resp.status} - {text}")
                    return
                result = await resp.json()
                print(f"✅ Added Player{i} with ID: {result['player_id']}")
                
                # Small delay to simulate real users
                await asyncio.sleep(0.5)
        
        print("🎉 Successfully added 7 players!")
        
        # Try to start the game
        start_data = {"session_id": session_id}
        async with session.post(f"{base_url}/start-game", json=start_data) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"❌ Failed to start game: {resp.status} - {text}")
                return
            print("✅ Game started successfully!")

if __name__ == "__main__":
    asyncio.run(test_seven_players())