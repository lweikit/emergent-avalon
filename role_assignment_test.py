import requests
import json
import sys
import time
import random
import string
from datetime import datetime

class AvalonRoleAssignmentTester:
    def __init__(self, base_url="https://6dea0238-f0e0-412c-a0be-b01fdaec96fe.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.session_id = None
        self.player_ids = {}
        self.role_distribution = {}

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

    def start_test_game(self):
        """Start a test game with bots if needed"""
        if not self.session_id:
            print("❌ No active session to start")
            return False
        
        success, _ = self.run_test(
            "Start Test Game",
            "POST",
            "start-test-game",
            200,
            data={"session_id": self.session_id}
        )
        return success

    def get_debug_session(self):
        """Get debug session details with role information"""
        if not self.session_id:
            print("❌ No active session")
            return False, None
        
        success, response = self.run_test(
            "Get Debug Session",
            "GET",
            f"debug/session/{self.session_id}",
            200
        )
        
        if success:
            # Store role distribution for analysis
            self.role_distribution = response.get('role_distribution', {})
            
            # Print role distribution
            print("\n📊 Role Distribution:")
            print(f"Total Players: {self.role_distribution.get('total_players', 0)}")
            print(f"Expected Roles: {self.role_distribution.get('expected_roles', [])}")
            print(f"Actual Roles: {self.role_distribution.get('actual_roles', [])}")
            
            # Print player roles
            print("\n👥 Player Roles:")
            for player in response.get('players', []):
                print(f"{player.get('name')}: {player.get('role')}")
        
        return success, response

    def select_team(self, leader_id, team_member_ids):
        """Select team for a mission"""
        if not self.session_id:
            print("❌ Invalid session")
            return False
        
        success, _ = self.run_test(
            f"Select Team",
            "POST",
            "select-team",
            200,
            data={
                "session_id": self.session_id,
                "player_id": leader_id,
                "team_members": team_member_ids
            }
        )
        return success

    def vote_team(self, player_id, vote):
        """Vote on the proposed team"""
        if not self.session_id:
            print("❌ Invalid session")
            return False
        
        success, _ = self.run_test(
            f"Vote Team ({player_id}: {'Approve' if vote else 'Reject'})",
            "POST",
            "vote-team",
            200,
            data={
                "session_id": self.session_id,
                "player_id": player_id,
                "vote": vote
            }
        )
        return success

    def vote_mission(self, player_id, vote):
        """Vote on mission success/failure"""
        if not self.session_id:
            print("❌ Invalid session")
            return False
        
        success, _ = self.run_test(
            f"Vote Mission ({player_id}: {'Success' if vote else 'Fail'})",
            "POST",
            "vote-mission",
            200,
            data={
                "session_id": self.session_id,
                "player_id": player_id,
                "vote": vote
            }
        )
        return success

    def verify_role_distribution(self, expected_roles):
        """Verify that roles are distributed correctly"""
        if not self.role_distribution:
            print("❌ No role distribution data available")
            return False
        
        actual_roles = self.role_distribution.get('actual_roles', [])
        
        # Check if we have the right number of roles
        if len(actual_roles) != len(expected_roles):
            print(f"❌ Wrong number of roles: expected {len(expected_roles)}, got {len(actual_roles)}")
            return False
        
        # Check if we have the expected roles (ignoring order)
        expected_role_counts = {}
        for role in expected_roles:
            expected_role_counts[role] = expected_role_counts.get(role, 0) + 1
        
        actual_role_counts = {}
        for role in actual_roles:
            actual_role_counts[role] = actual_role_counts.get(role, 0) + 1
        
        if expected_role_counts != actual_role_counts:
            print(f"❌ Role distribution mismatch:")
            print(f"Expected: {expected_role_counts}")
            print(f"Actual: {actual_role_counts}")
            return False
        
        print("✅ Role distribution is correct")
        return True

    def verify_role_persistence(self, initial_roles, final_roles):
        """Verify that roles persist throughout the game"""
        if not initial_roles or not final_roles:
            print("❌ Missing role data for persistence check")
            return False
        
        # Check if each player's role remains the same
        for player_id, initial_role in initial_roles.items():
            if player_id not in final_roles:
                print(f"❌ Player {player_id} missing from final roles")
                return False
            
            if initial_role != final_roles[player_id]:
                print(f"❌ Role changed for player {player_id}: {initial_role} -> {final_roles[player_id]}")
                return False
        
        print("✅ Roles persisted correctly throughout the game")
        return True

def test_role_assignment():
    """Test role assignment for 5 players"""
    tester = AvalonRoleAssignmentTester()
    timestamp = datetime.now().strftime("%H%M%S")
    session_name = f"Role Test {timestamp}"
    player_name = f"Tester_{timestamp}"
    
    # Create session with 1 player
    if not tester.create_session(session_name, player_name):
        return 1
    
    # Start test game (adds bots to reach 5 players)
    if not tester.start_test_game():
        return 1
    
    # Get debug info to check role distribution
    success, debug_data = tester.get_debug_session()
    if not success:
        return 1
    
    # Store initial roles for persistence check
    initial_roles = {}
    for player in debug_data.get('players', []):
        initial_roles[player.get('id')] = player.get('role')
    
    # Verify correct role distribution for 5 players
    expected_roles = ['merlin', 'percival', 'loyal_servant', 'morgana', 'assassin']
    if not tester.verify_role_distribution(expected_roles):
        return 1
    
    # Find the leader
    leader_id = None
    team_members = []
    for player in debug_data.get('players', []):
        if player.get('is_leader', False):
            leader_id = player.get('id')
        team_members.append(player.get('id'))
    
    if not leader_id:
        print("❌ No leader found")
        return 1
    
    # Select first 2 players for the mission
    if not tester.select_team(leader_id, team_members[:2]):
        return 1
    
    # All players vote on the team
    for player_id in team_members:
        if not tester.vote_team(player_id, True):  # All approve
            return 1
    
    # Wait for votes to process
    time.sleep(1)
    
    # Get updated session state
    success, debug_data = tester.get_debug_session()
    if not success:
        return 1
    
    # Store final roles for persistence check
    final_roles = {}
    for player in debug_data.get('players', []):
        final_roles[player.get('id')] = player.get('role')
    
    # Verify roles persisted
    if not tester.verify_role_persistence(initial_roles, final_roles):
        return 1
    
    # Print test results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

def test_multiple_game_starts():
    """Test that game cannot be started multiple times"""
    tester = AvalonRoleAssignmentTester()
    timestamp = datetime.now().strftime("%H%M%S")
    session_name = f"Multi-Start Test {timestamp}"
    player_name = f"Tester_{timestamp}"
    
    # Create session with 1 player
    if not tester.create_session(session_name, player_name):
        return 1
    
    # Start test game first time
    if not tester.start_test_game():
        return 1
    
    # Get debug info after first start
    success, debug_data = tester.get_debug_session()
    if not success:
        return 1
    
    # Store initial roles
    initial_roles = {}
    for player in debug_data.get('players', []):
        initial_roles[player.get('id')] = player.get('role')
    
    # Try to start the game again (should fail or not reassign roles)
    print("\n🔍 Testing multiple game starts protection...")
    second_start_success, _ = tester.run_test(
        "Start Game Again",
        "POST",
        "start-test-game",
        400,  # Expecting failure with 400 Bad Request
        data={"session_id": tester.session_id}
    )
    
    # If second start succeeded (which it shouldn't), verify roles didn't change
    if second_start_success:
        print("⚠️ Second game start succeeded, checking if roles were preserved...")
        
        # Get debug info after second start
        success, debug_data = tester.get_debug_session()
        if not success:
            return 1
        
        # Store final roles
        final_roles = {}
        for player in debug_data.get('players', []):
            final_roles[player.get('id')] = player.get('role')
        
        # Verify roles didn't change
        if not tester.verify_role_persistence(initial_roles, final_roles):
            return 1
    else:
        print("✅ Second game start correctly rejected")
    
    # Print test results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

def main():
    # Run the tests
    print("🧪 Running Avalon Role Assignment Tests")
    
    try:
        # Test role assignment
        print("\n🔍 Testing Role Assignment")
        role_result = test_role_assignment()
        
        # Test multiple game starts
        print("\n🔍 Testing Multiple Game Starts Protection")
        multi_start_result = test_multiple_game_starts()
        
        # Overall result
        overall_result = role_result == 0 and multi_start_result == 0
        
        print("\n📋 Test Summary:")
        print(f"Role Assignment Test: {'✅ PASS' if role_result == 0 else '❌ FAIL'}")
        print(f"Multiple Game Starts Test: {'✅ PASS' if multi_start_result == 0 else '❌ FAIL'}")
        print(f"Overall Result: {'✅ PASS' if overall_result else '❌ FAIL'}")
        
        return 0 if overall_result else 1
    except Exception as e:
        print(f"❌ Test execution failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())