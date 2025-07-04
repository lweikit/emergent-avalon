import requests
import asyncio
import websockets
import json
import sys
import time
import random
import string
from datetime import datetime

class AvalonAPITester:
    def __init__(self, base_url="https://6dea0238-f0e0-412c-a0be-b01fdaec96fe.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.ws_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        self.tests_run = 0
        self.tests_passed = 0
        self.session_id = None
        self.player_ids = {}
        self.ws_connections = {}
        self.game_states = {}
        self.bot_players = []
        self.bot_players = []

    def run_test(self, name, method, endpoint, expected_status, data=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                return success, response.json()
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"Response: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    async def connect_websocket(self, session_id, player_name):
        """Connect to WebSocket for real-time updates"""
        ws_endpoint = f"{self.ws_url}/api/ws/{session_id}"
        try:
            websocket = await websockets.connect(ws_endpoint)
            self.ws_connections[player_name] = websocket
            print(f"✅ WebSocket connected for {player_name}")
            return True
        except Exception as e:
            print(f"❌ WebSocket connection failed for {player_name}: {str(e)}")
            return False

    async def listen_for_updates(self, player_name, timeout=5):
        """Listen for WebSocket updates for a specific player"""
        if player_name not in self.ws_connections:
            print(f"❌ No WebSocket connection for {player_name}")
            return None
        
        websocket = self.ws_connections[player_name]
        try:
            websocket.sock.settimeout(timeout)
            message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
            data = json.loads(message)
            self.game_states[player_name] = data
            print(f"✅ Received game state update for {player_name}")
            return data
        except asyncio.TimeoutError:
            print(f"⚠️ No WebSocket updates received for {player_name} within {timeout} seconds")
            return None
        except Exception as e:
            print(f"❌ Error receiving WebSocket updates for {player_name}: {str(e)}")
            return None

    async def close_websockets(self):
        """Close all WebSocket connections"""
        for player_name, websocket in self.ws_connections.items():
            try:
                await websocket.close()
                print(f"✅ WebSocket closed for {player_name}")
            except Exception as e:
                print(f"⚠️ Error closing WebSocket for {player_name}: {str(e)}")

    def create_session(self, session_name, player_name):
        """Create a new game session"""
        success, response = self.run_test(
            "Create Session",
            "POST",
            "create-session",
            200,
            data={"name": session_name, "player_name": player_name}
        )
        if success:
            self.session_id = response.get('session_id')
            self.player_ids[player_name] = response.get('player_id')
            print(f"📝 Session created: {self.session_id}")
            print(f"👤 Player {player_name} joined with ID: {self.player_ids[player_name]}")
        return success

    def join_session(self, player_name):
        """Join an existing game session"""
        if not self.session_id:
            print("❌ No active session to join")
            return False
        
        success, response = self.run_test(
            f"Join Session ({player_name})",
            "POST",
            "join-session",
            200,
            data={"session_id": self.session_id, "player_name": player_name}
        )
        if success:
            self.player_ids[player_name] = response.get('player_id')
            print(f"👤 Player {player_name} joined with ID: {self.player_ids[player_name]}")
        return success

    def start_game(self):
        """Start the game"""
        if not self.session_id:
            print("❌ No active session to start")
            return False
        
        success, _ = self.run_test(
            "Start Game",
            "POST",
            "start-game",
            200,
            data={"session_id": self.session_id}
        )
        return success

    def select_team(self, leader_name, team_members):
        """Select team for a mission"""
        if not self.session_id or leader_name not in self.player_ids:
            print("❌ Invalid session or leader")
            return False
        
        team_member_ids = [self.player_ids[name] for name in team_members if name in self.player_ids]
        
        success, _ = self.run_test(
            f"Select Team ({leader_name})",
            "POST",
            "select-team",
            200,
            data={
                "session_id": self.session_id,
                "player_id": self.player_ids[leader_name],
                "team_members": team_member_ids
            }
        )
        return success

    def vote_team(self, player_name, vote):
        """Vote on the proposed team"""
        if not self.session_id or player_name not in self.player_ids:
            print("❌ Invalid session or player")
            return False
        
        success, _ = self.run_test(
            f"Vote Team ({player_name}: {'Approve' if vote else 'Reject'})",
            "POST",
            "vote-team",
            200,
            data={
                "session_id": self.session_id,
                "player_id": self.player_ids[player_name],
                "vote": vote
            }
        )
        return success

    def vote_mission(self, player_name, vote):
        """Vote on mission success/failure"""
        if not self.session_id or player_name not in self.player_ids:
            print("❌ Invalid session or player")
            return False
        
        success, _ = self.run_test(
            f"Vote Mission ({player_name}: {'Success' if vote else 'Fail'})",
            "POST",
            "vote-mission",
            200,
            data={
                "session_id": self.session_id,
                "player_id": self.player_ids[player_name],
                "vote": vote
            }
        )
        return success

    def use_lady_of_lake(self, player_name, target_name):
        """Use Lady of the Lake to reveal a player's allegiance"""
        if not self.session_id or player_name not in self.player_ids or target_name not in self.player_ids:
            print("❌ Invalid session, player, or target")
            return False
        
        success, response = self.run_test(
            f"Lady of Lake ({player_name} -> {target_name})",
            "POST",
            "lady-of-lake",
            200,
            data={
                "session_id": self.session_id,
                "player_id": self.player_ids[player_name],
                "target_player_id": self.player_ids[target_name]
            }
        )
        if success:
            print(f"🌟 {target_name}'s allegiance: {response.get('allegiance', 'unknown')}")
        return success

    def assassinate(self, assassin_name, target_name):
        """Assassin attempts to kill Merlin"""
        if not self.session_id or assassin_name not in self.player_ids or target_name not in self.player_ids:
            print("❌ Invalid session, assassin, or target")
            return False
        
        success, response = self.run_test(
            f"Assassinate ({assassin_name} -> {target_name})",
            "POST",
            "assassinate",
            200,
            data={
                "session_id": self.session_id,
                "player_id": self.player_ids[assassin_name],
                "target_player_id": self.player_ids[target_name]
            }
        )
        if success:
            result = "successful" if response.get('success', False) else "failed"
            print(f"🗡️ Assassination {result}")
        return success

    def toggle_lady_of_lake(self, enabled):
        """Toggle Lady of the Lake expansion on/off"""
        if not self.session_id:
            print("❌ No active session")
            return False
        
        success, _ = self.run_test(
            f"Toggle Lady of the Lake ({enabled})",
            "POST",
            "toggle-lady-of-lake",
            200,
            data={
                "session_id": self.session_id,
                "enabled": enabled
            }
        )
        return success
        
    def restart_game(self):
        """Restart the game with the same players"""
        if not self.session_id:
            print("❌ No active session")
            return False
        
        success, _ = self.run_test(
            "Restart Game",
            "POST",
            "restart-game",
            200,
            data={"session_id": self.session_id}
        )
        return success
        
    def start_test_game(self):
        """Start a test game with bot players"""
        if not self.session_id:
            print("❌ No active session")
            return False
        
        success, _ = self.run_test(
            "Start Test Game",
            "POST",
            "start-test-game",
            200,
            data={"session_id": self.session_id}
        )
        return success

async def test_basic_game_flow():
    """Test a basic game flow with 5 players"""
    tester = AvalonAPITester()
    timestamp = datetime.now().strftime("%H%M%S")
    session_name = f"Test Session {timestamp}"
    
    # Create players with unique names
    players = [f"Player{i}_{timestamp}" for i in range(1, 6)]
    
    # Create session and join players
    if not tester.create_session(session_name, players[0]):
        return 1
    
    # Connect first player to WebSocket
    await tester.connect_websocket(tester.session_id, players[0])
    
    # Join other players
    for player in players[1:]:
        if not tester.join_session(player):
            return 1
        # Connect each player to WebSocket
        await tester.connect_websocket(tester.session_id, player)
    
    # Listen for updates for the first player
    game_state = await tester.listen_for_updates(players[0])
    if game_state:
        print(f"Initial game state phase: {game_state.get('session', {}).get('phase', 'unknown')}")
    
    # Start the game
    if not tester.start_game():
        return 1
    
    # Listen for updates after game start
    game_state = await tester.listen_for_updates(players[0])
    if game_state:
        print(f"Game state after start: {game_state.get('session', {}).get('phase', 'unknown')}")
        
        # Check if roles were assigned
        if 'role_info' in game_state:
            print(f"Player role: {game_state['role_info'].get('role', 'unknown')}")
            print(f"Team: {game_state['role_info'].get('team', 'unknown')}")
    
    # Get the current leader
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    # Find the leader
    leader_index = None
    for i, player in enumerate(session_data.get('players', [])):
        if player.get('is_leader', False):
            leader_index = i
            break
    
    if leader_index is None:
        print("❌ No leader found")
        return 1
    
    leader_name = players[leader_index]
    print(f"Current leader: {leader_name}")
    
    # Select team for first mission (2 players for 5-player game)
    team_members = [players[0], players[1]]
    if not tester.select_team(leader_name, team_members):
        return 1
    
    # All players vote on the team
    for player in players:
        # Randomly approve or reject
        vote = random.choice([True, False])
        if not tester.vote_team(player, vote):
            return 1
    
    # Wait for a moment to let the votes process
    time.sleep(2)
    
    # Get updated session state
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    # Check the current phase
    current_phase = session_data.get('phase', '')
    print(f"Current game phase: {current_phase}")
    
    # If the team was approved, vote on the mission
    if current_phase == 'mission_execution':
        for team_member in team_members:
            # Good players always vote success, evil might vote fail
            vote = True  # For simplicity, always vote success in this test
            if not tester.vote_mission(team_member, vote):
                return 1
    
    # Close all WebSocket connections
    await tester.close_websockets()
    
    # Print test results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

async def test_full_game_flow():
    """Test a complete game flow with 7 players including Lady of the Lake"""
    tester = AvalonAPITester()
    timestamp = datetime.now().strftime("%H%M%S")
    session_name = f"Full Test {timestamp}"
    
    # Create players with unique names
    players = [f"Player{i}_{timestamp}" for i in range(1, 8)]
    
    # Create session and join players
    if not tester.create_session(session_name, players[0]):
        return 1
    
    # Join other players
    for player in players[1:]:
        if not tester.join_session(player):
            return 1
    
    # Start the game
    if not tester.start_game():
        return 1
    
    # Get the current leader and session state
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    # Run through multiple missions
    for mission_num in range(1, 4):  # Test first 3 missions
        print(f"\n🎯 Testing Mission {mission_num}")
        
        # Get updated session state
        success, session_data = tester.get_session()
        if not success:
            return 1
        
        # Find the leader
        leader_index = None
        for i, player in enumerate(session_data.get('players', [])):
            if player.get('is_leader', False):
                leader_index = i
                break
        
        if leader_index is None:
            print("❌ No leader found")
            return 1
        
        leader_name = players[leader_index % len(players)]
        print(f"Current leader: {leader_name}")
        
        # Get mission details
        current_mission = session_data.get('missions', [])[mission_num - 1]
        team_size = current_mission.get('team_size', 2)
        
        # Select team for the mission
        team_members = players[:team_size]
        if not tester.select_team(leader_name, team_members):
            return 1
        
        # All players vote on the team
        for player in players:
            # For testing, have everyone approve
            if not tester.vote_team(player, True):
                return 1
        
        # Wait for a moment to let the votes process
        time.sleep(1)
        
        # Get updated session state
        success, session_data = tester.get_session()
        if not success:
            return 1
        
        # Check the current phase
        current_phase = session_data.get('phase', '')
        print(f"Current game phase: {current_phase}")
        
        # If the team was approved, vote on the mission
        if current_phase == 'mission_execution':
            for team_member in team_members:
                # For testing, have all missions succeed
                if not tester.vote_mission(team_member, True):
                    return 1
        
        # Wait for mission to complete
        time.sleep(1)
        
        # Check for Lady of the Lake phase after missions 2 & 3
        if mission_num in [2, 3]:
            success, session_data = tester.get_session()
            if not success:
                return 1
            
            current_phase = session_data.get('phase', '')
            if current_phase == 'lady_of_the_lake':
                # Find who has Lady of the Lake
                lady_holder = None
                for player_data in session_data.get('players', []):
                    if player_data.get('lady_of_the_lake', False):
                        lady_holder = next((p for p in players if tester.player_ids.get(p) == player_data.get('id')), None)
                        break
                
                if lady_holder:
                    # Choose a target that isn't the holder
                    target = next((p for p in players if p != lady_holder), None)
                    if target:
                        tester.use_lady_of_lake(lady_holder, target)
    
    # Check if we reached assassination phase
    success, session_data = tester.get_session()
    if success:
        current_phase = session_data.get('phase', '')
        if current_phase == 'assassination':
            # Find the assassin
            assassin = None
            for player_data in session_data.get('players', []):
                if player_data.get('role') == 'assassin':
                    assassin = next((p for p in players if tester.player_ids.get(p) == player_data.get('id')), None)
                    break
            
            if assassin:
                # Choose a random target that isn't the assassin
                target = next((p for p in players if p != assassin), None)
                if target:
                    tester.assassinate(assassin, target)
    
    # Print test results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

async def test_websocket_vs_fallback():
    """Test both WebSocket and fallback polling mechanisms"""
    tester = AvalonAPITester()
    timestamp = datetime.now().strftime("%H%M%S")
    session_name = f"WebSocket Test {timestamp}"
    
    # Create players with unique names
    players = [f"Player{i}_{timestamp}" for i in range(1, 6)]
    
    # Create session and join players
    if not tester.create_session(session_name, players[0]):
        return 1
    
    # Try to connect first player to WebSocket
    ws_connected = await tester.connect_websocket(tester.session_id, players[0])
    
    # Join other players
    for player in players[1:]:
        if not tester.join_session(player):
            return 1
    
    # If WebSocket connected, try to listen for updates
    if ws_connected:
        print("\n🔍 Testing WebSocket real-time updates")
        game_state = await tester.listen_for_updates(players[0])
        if game_state:
            print(f"✅ Received real-time update via WebSocket: {game_state.get('type', 'unknown')}")
        else:
            print("⚠️ No WebSocket updates received, falling back to polling")
            # Test polling as fallback
            success, _ = tester.get_session()
            if success:
                print("✅ Fallback polling mechanism is working")
    else:
        print("\n🔍 WebSocket connection failed, testing fallback polling")
        # Test polling as primary method
        success, _ = tester.get_session()
        if success:
            print("✅ Fallback polling mechanism is working")
    
    # Start the game
    if not tester.start_game():
        return 1
    
    # Get the current leader
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    # Find the leader
    leader_index = None
    for i, player in enumerate(session_data.get('players', [])):
        if player.get('is_leader', False):
            leader_index = i
            break
    
    if leader_index is None:
        print("❌ No leader found")
        return 1
    
    leader_name = players[leader_index % len(players)]
    print(f"Current leader: {leader_name}")
    
    # Select team for first mission
    team_members = players[:2]  # First 2 players
    if not tester.select_team(leader_name, team_members):
        return 1
    
    # All players vote on the team
    for player in players:
        if not tester.vote_team(player, True):  # All approve
            return 1
    
    # Wait for a moment to let the votes process
    time.sleep(1)
    
    # Get updated session state
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    # Check the current phase
    current_phase = session_data.get('phase', '')
    print(f"Current game phase: {current_phase}")
    
    # If the team was approved, vote on the mission
    if current_phase == 'mission_execution':
        for team_member in team_members:
            if not tester.vote_mission(team_member, True):  # All vote success
                return 1
    
    # Close WebSocket connections
    await tester.close_websockets()
    
    # Print test results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

async def test_bot_ai_system():
    """Test the bot AI system"""
    tester = AvalonAPITester()
    timestamp = datetime.now().strftime("%H%M%S")
    session_name = f"Bot Test {timestamp}"
    player_name = f"Human_{timestamp}"
    
    print("\n🤖 Testing Bot AI System")
    
    # Create session with one human player
    if not tester.create_session(session_name, player_name):
        return 1
    
    # Start a test game with bots
    if not tester.start_test_game():
        return 1
    
    # Get session to check if bots were added
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    # Check if bots were added
    players = session_data.get('players', [])
    bot_count = sum(1 for p in players if p.get('is_bot', False))
    print(f"✅ {bot_count} bot players added to the game")
    
    # Connect to WebSocket to monitor bot actions
    await tester.connect_websocket(tester.session_id, player_name)
    
    # Wait for bots to take actions
    print("⏳ Waiting for bot actions...")
    
    # Monitor game state changes for 30 seconds
    start_time = time.time()
    phase_changes = []
    last_phase = session_data.get('phase', '')
    phase_changes.append(last_phase)
    
    while time.time() - start_time < 30:
        # Get current game state
        success, session_data = tester.get_session()
        if success:
            current_phase = session_data.get('phase', '')
            if current_phase != last_phase:
                print(f"🔄 Game phase changed: {last_phase} -> {current_phase}")
                phase_changes.append(current_phase)
                last_phase = current_phase
                
                # Check for mission results
                if current_phase in ['mission_team_selection', 'game_end']:
                    missions = session_data.get('missions', [])
                    completed_missions = [m for m in missions if m.get('result') != 'pending']
                    for mission in completed_missions:
                        print(f"🎯 Mission {mission.get('number')}: {mission.get('result')}")
        
        # Wait a bit before checking again
        await asyncio.sleep(2)
    
    # Check if game progressed automatically
    if len(phase_changes) > 1:
        print(f"✅ Game progressed automatically through phases: {' -> '.join(phase_changes)}")
        
        # Check vote history for bot votes
        success, session_data = tester.get_session()
        if success:
            vote_history = session_data.get('vote_history', [])
            if vote_history:
                print(f"✅ Vote history recorded {len(vote_history)} voting rounds")
                for i, vote_record in enumerate(vote_history):
                    print(f"  Round {i+1}: {vote_record.get('approve_count')}/{vote_record.get('total_votes')} approved")
            else:
                print("❌ No vote history recorded")
    else:
        print("❌ Game did not progress automatically")
    
    # Close WebSocket connection
    await tester.close_websockets()
    
    # Print test results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run and len(phase_changes) > 1 else 1

async def test_vote_transparency():
    """Test vote transparency features"""
    tester = AvalonAPITester()
    timestamp = datetime.now().strftime("%H%M%S")
    session_name = f"Vote Test {timestamp}"
    
    # Create players with unique names
    players = [f"Player{i}_{timestamp}" for i in range(1, 6)]
    
    print("\n📊 Testing Vote Transparency")
    
    # Create session and join players
    if not tester.create_session(session_name, players[0]):
        return 1
    
    # Join other players
    for player in players[1:]:
        if not tester.join_session(player):
            return 1
    
    # Start the game
    if not tester.start_game():
        return 1
    
    # Get the current leader
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    # Find the leader
    leader_index = None
    for i, player in enumerate(session_data.get('players', [])):
        if player.get('is_leader', False):
            leader_index = i
            break
    
    if leader_index is None:
        print("❌ No leader found")
        return 1
    
    leader_name = players[leader_index % len(players)]
    print(f"Current leader: {leader_name}")
    
    # Select team for first mission
    team_size = session_data.get('missions', [])[0].get('team_size', 2)
    team_members = players[:team_size]
    if not tester.select_team(leader_name, team_members):
        return 1
    
    # Have players vote with different choices
    for i, player in enumerate(players):
        # Alternate approve/reject votes
        vote = i % 2 == 0
        if not tester.vote_team(player, vote):
            return 1
    
    # Wait for votes to process
    time.sleep(2)
    
    # Check vote history
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    vote_history = session_data.get('vote_history', [])
    if not vote_history:
        print("❌ No vote history recorded")
        return 1
    
    # Verify vote details are recorded
    latest_vote = vote_history[-1]
    if 'votes' not in latest_vote:
        print("❌ Individual votes not recorded in vote history")
        return 1
    
    print("✅ Vote history recorded individual votes:")
    for player_name, vote in latest_vote.get('votes', {}).items():
        print(f"  {player_name}: {'Approve' if vote else 'Reject'}")
    
    # Check game log
    game_log = session_data.get('game_log', [])
    if not game_log:
        print("❌ No game log entries recorded")
        return 1
    
    print("✅ Game log entries:")
    for log_entry in game_log:
        print(f"  {log_entry}")
    
    # Print test results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run and vote_history and game_log else 1

async def test_lady_of_lake_toggle():
    """Test Lady of the Lake toggle feature"""
    tester = AvalonAPITester()
    timestamp = datetime.now().strftime("%H%M%S")
    session_name = f"Lady Test {timestamp}"
    
    # Create players with unique names (7 players to trigger Lady of the Lake)
    players = [f"Player{i}_{timestamp}" for i in range(1, 8)]
    
    print("\n🌟 Testing Lady of the Lake Toggle")
    
    # Create session and join players
    if not tester.create_session(session_name, players[0]):
        return 1
    
    # Join other players
    for player in players[1:]:
        if not tester.join_session(player):
            return 1
    
    # Check default Lady of the Lake setting
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    default_setting = session_data.get('lady_of_the_lake_enabled', None)
    print(f"Default Lady of the Lake setting: {default_setting}")
    
    # Toggle Lady of the Lake off
    if not tester.toggle_lady_of_lake(False):
        return 1
    
    # Verify setting was changed
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    if session_data.get('lady_of_the_lake_enabled', True) != False:
        print("❌ Failed to disable Lady of the Lake")
        return 1
    
    print("✅ Successfully disabled Lady of the Lake")
    
    # Toggle Lady of the Lake back on
    if not tester.toggle_lady_of_lake(True):
        return 1
    
    # Verify setting was changed back
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    if session_data.get('lady_of_the_lake_enabled', False) != True:
        print("❌ Failed to enable Lady of the Lake")
        return 1
    
    print("✅ Successfully enabled Lady of the Lake")
    
    # Start game with Lady of the Lake enabled
    if not tester.start_game():
        return 1
    
    # Verify Lady of the Lake holder is set
    success, session_data = tester.get_session()
    if not success:
        return 1
    
    lady_holder = session_data.get('lady_of_the_lake_holder', None)
    if not lady_holder:
        print("❌ Lady of the Lake holder not set")
        return 1
    
    print(f"✅ Lady of the Lake holder set: {lady_holder}")
    
    # Print test results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

async def test_game_restart():
    """Test game restart feature"""
    tester = AvalonAPITester()
    timestamp = datetime.now().strftime("%H%M%S")
    session_name = f"Restart Test {timestamp}"
    
    # Create players with unique names
    players = [f"Player{i}_{timestamp}" for i in range(1, 6)]
    
    print("\n🔄 Testing Game Restart")
    
    # Create session and join players
    if not tester.create_session(session_name, players[0]):
        return 1
    
    # Join other players
    for player in players[1:]:
        if not tester.join_session(player):
            return 1
    
    # Record initial player IDs
    success, initial_session = tester.get_session()
    if not success:
        return 1
    
    initial_player_ids = [p.get('id') for p in initial_session.get('players', [])]
    print(f"Initial players: {len(initial_player_ids)}")
    
    # Start the game
    if not tester.start_game():
        return 1
    
    # Verify game started
    success, started_session = tester.get_session()
    if not success:
        return 1
    
    if started_session.get('phase') == 'lobby':
        print("❌ Game failed to start")
        return 1
    
    print(f"✅ Game started, phase: {started_session.get('phase')}")
    
    # Restart the game
    if not tester.restart_game():
        return 1
    
    # Verify game was reset
    success, restarted_session = tester.get_session()
    if not success:
        return 1
    
    # Check phase is back to lobby
    if restarted_session.get('phase') != 'lobby':
        print(f"❌ Game not reset to lobby phase: {restarted_session.get('phase')}")
        return 1
    
    print("✅ Game reset to lobby phase")
    
    # Check players are the same
    restarted_player_ids = [p.get('id') for p in restarted_session.get('players', [])]
    if set(initial_player_ids) != set(restarted_player_ids):
        print("❌ Player list changed after restart")
        return 1
    
    print(f"✅ Same {len(restarted_player_ids)} players preserved after restart")
    
    # Check roles were reset
    if any(p.get('role') for p in restarted_session.get('players', [])):
        print("❌ Roles not reset after restart")
        return 1
    
    print("✅ Player roles reset successfully")
    
    # Print test results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

def main():
    # Run the tests
    print("🧪 Running Avalon API Tests")
    
    try:
        # Test basic game flow
        print("\n🔍 Testing Basic Game Flow")
        basic_result = asyncio.run(test_basic_game_flow())
        
        # Test full game flow with Lady of the Lake
        print("\n🔍 Testing Full Game Flow with Lady of the Lake")
        full_result = asyncio.run(test_full_game_flow())
        
        # Test WebSocket vs. fallback
        print("\n🔍 Testing WebSocket vs. Fallback Mechanism")
        websocket_result = asyncio.run(test_websocket_vs_fallback())
        
        # Test new features
        print("\n🔍 Testing Bot AI System")
        bot_result = asyncio.run(test_bot_ai_system())
        
        print("\n🔍 Testing Vote Transparency")
        vote_result = asyncio.run(test_vote_transparency())
        
        print("\n🔍 Testing Lady of the Lake Toggle")
        lady_result = asyncio.run(test_lady_of_lake_toggle())
        
        print("\n🔍 Testing Game Restart")
        restart_result = asyncio.run(test_game_restart())
        
        # Overall result
        overall_result = (basic_result == 0 and full_result == 0 and 
                          websocket_result == 0 and bot_result == 0 and 
                          vote_result == 0 and lady_result == 0 and 
                          restart_result == 0)
        
        print("\n📋 Test Summary:")
        print(f"Basic Game Flow Test: {'✅ PASS' if basic_result == 0 else '❌ FAIL'}")
        print(f"Full Game Flow Test: {'✅ PASS' if full_result == 0 else '❌ FAIL'}")
        print(f"WebSocket/Fallback Test: {'✅ PASS' if websocket_result == 0 else '❌ FAIL'}")
        print(f"Bot AI System Test: {'✅ PASS' if bot_result == 0 else '❌ FAIL'}")
        print(f"Vote Transparency Test: {'✅ PASS' if vote_result == 0 else '❌ FAIL'}")
        print(f"Lady of the Lake Toggle Test: {'✅ PASS' if lady_result == 0 else '❌ FAIL'}")
        print(f"Game Restart Test: {'✅ PASS' if restart_result == 0 else '❌ FAIL'}")
        print(f"Overall Result: {'✅ PASS' if overall_result else '❌ FAIL'}")
        
        return 0 if overall_result else 1
    except Exception as e:
        print(f"❌ Test execution failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())