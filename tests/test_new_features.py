"""
Tests for the latest changes:
  - Short room codes (generate_code, GameSession.code field)
  - LeaveSessionRequest model
  - Broadcast state includes code
  - _resolve_session helper
  - Leave session endpoint
  - Join via short code
  - Join response includes session_id

Run with: pytest tests/test_new_features.py -v
"""

import sys
import os
import re
from collections import Counter
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models import (
    Player, Mission, GameSession, GamePhase, Role, MissionResult,
    LeaveSessionRequest, generate_code,
)
from websocket import _build_player_state, _build_general_state


# ===========================================================================
# 1. generate_code
# ===========================================================================

class TestGenerateCode:

    VALID_CHARS = set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")

    def test_default_length_is_6(self):
        code = generate_code()
        assert len(code) == 6

    def test_custom_length(self):
        for length in [4, 8, 10]:
            code = generate_code(length)
            assert len(code) == length

    def test_only_valid_characters(self):
        for _ in range(100):
            code = generate_code()
            for ch in code:
                assert ch in self.VALID_CHARS, f"Invalid char '{ch}' in code '{code}'"

    def test_excludes_confusing_characters(self):
        codes = "".join(generate_code() for _ in range(500))
        for bad in "01OIL":
            assert bad not in codes, f"Found confusing char '{bad}' in generated codes"

    def test_codes_are_not_all_identical(self):
        codes = {generate_code() for _ in range(50)}
        assert len(codes) > 1, "50 generated codes should not all be the same"

    def test_distribution_is_reasonable(self):
        chars = "".join(generate_code() for _ in range(1000))
        counts = Counter(chars)
        assert len(counts) > 10, "Should use a reasonable variety of characters"


# ===========================================================================
# 2. GameSession.code field
# ===========================================================================

class TestGameSessionCode:

    def test_code_defaults_to_none(self):
        gs = GameSession(name="Test")
        assert gs.code is None

    def test_code_can_be_set(self):
        gs = GameSession(name="Test", code="ABC123")
        assert gs.code == "ABC123"

    def test_code_in_dict(self):
        gs = GameSession(name="Test", code="XYZ789")
        d = gs.model_dump()
        assert d["code"] == "XYZ789"

    def test_code_none_in_dict(self):
        gs = GameSession(name="Test")
        d = gs.model_dump()
        assert d["code"] is None

    def test_code_survives_round_trip(self):
        gs = GameSession(name="Test", code="ROUND1")
        d = gs.model_dump()
        gs2 = GameSession(**d)
        assert gs2.code == "ROUND1"


# ===========================================================================
# 3. LeaveSessionRequest model
# ===========================================================================

class TestLeaveSessionRequest:

    def test_valid_request(self):
        req = LeaveSessionRequest(
            session_id="abc-123",
            player_id="player-1",
            player_token="token-xyz",
        )
        assert req.session_id == "abc-123"
        assert req.player_id == "player-1"
        assert req.player_token == "token-xyz"

    def test_missing_session_id_raises(self):
        with pytest.raises(Exception):
            LeaveSessionRequest(player_id="p1", player_token="t1")

    def test_missing_player_id_raises(self):
        with pytest.raises(Exception):
            LeaveSessionRequest(session_id="s1", player_token="t1")

    def test_missing_player_token_raises(self):
        with pytest.raises(Exception):
            LeaveSessionRequest(session_id="s1", player_id="p1")


# ===========================================================================
# 4. Broadcast state includes code
# ===========================================================================

def _make_gs_with_code(code="TEST42", n_players=5, phase=GamePhase.MISSION_TEAM_SELECTION):
    roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
    players = [Player(name=f"P{i+1}") for i in range(n_players)]
    for p, r in zip(players, roles[:n_players]):
        p.role = r
    from game_logic import initialize_missions
    missions = initialize_missions(n_players)
    gs = GameSession(
        name="CodeTest",
        code=code,
        players=players,
        phase=phase,
        missions=missions,
    )
    return gs


class TestBroadcastStateIncludesCode:

    def test_player_state_has_code(self):
        gs = _make_gs_with_code(code="HELLO1")
        state = _build_player_state(gs, gs.players[0])
        assert state["session"]["code"] == "HELLO1"

    def test_player_state_code_none_for_old_session(self):
        gs = _make_gs_with_code(code=None)
        state = _build_player_state(gs, gs.players[0])
        assert state["session"]["code"] is None

    def test_general_state_has_code(self):
        gs = _make_gs_with_code(code="WORLD2")
        state = _build_general_state(gs)
        assert state["session"]["code"] == "WORLD2"

    def test_general_state_code_none_for_old_session(self):
        gs = _make_gs_with_code(code=None)
        state = _build_general_state(gs)
        assert state["session"]["code"] is None

    def test_player_state_code_matches_session(self):
        code = generate_code()
        gs = _make_gs_with_code(code=code)
        state = _build_player_state(gs, gs.players[0])
        assert state["session"]["code"] == code

    def test_general_state_code_matches_session(self):
        code = generate_code()
        gs = _make_gs_with_code(code=code)
        state = _build_general_state(gs)
        assert state["session"]["code"] == code


# ===========================================================================
# 5. Broadcast state structure integrity
# ===========================================================================

class TestBroadcastStateStructure:
    """Verify that _build_player_state and _build_general_state return
    all expected fields — regression tests for the broadcast payloads."""

    def test_player_state_session_fields(self):
        gs = _make_gs_with_code()
        state = _build_player_state(gs, gs.players[0])
        session = state["session"]
        required = [
            "id", "name", "code", "phase", "current_mission", "current_leader",
            "vote_track", "good_wins", "evil_wins", "game_result",
            "lady_of_the_lake_enabled", "lady_of_the_lake_previous_holders",
            "mordred_enabled", "oberon_enabled", "players", "missions",
            "vote_history", "game_log",
        ]
        for field in required:
            assert field in session, f"Missing field '{field}' in player state"

    def test_general_state_session_fields(self):
        gs = _make_gs_with_code()
        state = _build_general_state(gs)
        session = state["session"]
        required = [
            "id", "name", "code", "phase", "current_mission", "current_leader",
            "vote_track", "good_wins", "evil_wins", "game_result",
            "lady_of_the_lake_enabled", "lady_of_the_lake_previous_holders",
            "mordred_enabled", "oberon_enabled", "players", "missions",
            "vote_history", "game_log",
        ]
        for field in required:
            assert field in session, f"Missing field '{field}' in general state"

    def test_player_state_has_type(self):
        gs = _make_gs_with_code()
        state = _build_player_state(gs, gs.players[0])
        assert state["type"] == "game_state"

    def test_general_state_has_type(self):
        gs = _make_gs_with_code()
        state = _build_general_state(gs)
        assert state["type"] == "game_state"

    def test_player_state_includes_role_info(self):
        gs = _make_gs_with_code()
        state = _build_player_state(gs, gs.players[0])
        assert "role_info" in state

    def test_general_state_no_role_info(self):
        gs = _make_gs_with_code()
        state = _build_general_state(gs)
        assert "role_info" not in state

    def test_player_sees_own_role(self):
        gs = _make_gs_with_code()
        state = _build_player_state(gs, gs.players[0])
        players = state["session"]["players"]
        own = next(p for p in players if p["id"] == gs.players[0].id)
        assert own["role"] is not None

    def test_player_does_not_see_others_roles_during_game(self):
        gs = _make_gs_with_code()
        state = _build_player_state(gs, gs.players[0])
        players = state["session"]["players"]
        others = [p for p in players if p["id"] != gs.players[0].id]
        assert all(p["role"] is None for p in others)

    def test_general_state_hides_all_roles_during_game(self):
        gs = _make_gs_with_code()
        state = _build_general_state(gs)
        players = state["session"]["players"]
        assert all(p["role"] is None for p in players)

    def test_general_state_reveals_roles_at_game_end(self):
        gs = _make_gs_with_code(phase=GamePhase.GAME_END)
        state = _build_general_state(gs)
        players = state["session"]["players"]
        assert all(p["role"] is not None for p in players)

    def test_player_state_reveals_all_roles_at_game_end(self):
        gs = _make_gs_with_code(phase=GamePhase.GAME_END)
        state = _build_player_state(gs, gs.players[0])
        players = state["session"]["players"]
        assert all(p["role"] is not None for p in players)


# ===========================================================================
# 6. Server endpoint tests (using FastAPI TestClient)
# ===========================================================================

# Set env vars BEFORE importing server (it reads them at module level)
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "avalon_test")

import server as _srv  # noqa: E402

class TestServerEndpoints:
    """Test the new/modified server endpoints using FastAPI's TestClient.

    These tests use unittest.mock to patch the MongoDB database operations,
    so no actual database is needed.
    """

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """Create a fresh TestClient with mocked DB for each test."""
        self.db_mock = MagicMock()
        self.original_db = _srv.db
        _srv.db = self.db_mock

        from fastapi.testclient import TestClient
        self.client = TestClient(_srv.app)

        yield

        _srv.db = self.original_db

    def _mock_find_one(self, returns=None, side_effect=None):
        if side_effect:
            self.db_mock.game_sessions.find_one = AsyncMock(side_effect=side_effect)
        else:
            self.db_mock.game_sessions.find_one = AsyncMock(return_value=returns)

    def _mock_insert_one(self):
        self.db_mock.game_sessions.insert_one = AsyncMock()

    def _mock_replace_one(self):
        self.db_mock.game_sessions.replace_one = AsyncMock()

    # -- create-session generates code --

    def test_create_session_returns_session_id(self):
        self._mock_find_one(returns=None)
        self._mock_insert_one()

        res = self.client.post("/api/create-session", json={"name": "Test", "player_name": "Alice"})
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert "player_id" in data
        assert "player_token" in data

    def test_create_session_inserts_with_code(self):
        self._mock_find_one(returns=None)
        self._mock_insert_one()

        self.client.post("/api/create-session", json={"name": "Test", "player_name": "Alice"})

        call_args = self.db_mock.game_sessions.insert_one.call_args
        inserted = call_args[0][0]
        assert inserted["code"] is not None
        assert len(inserted["code"]) == 6

    def test_create_session_code_uses_valid_chars(self):
        valid = set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")
        self._mock_find_one(returns=None)
        self._mock_insert_one()

        self.client.post("/api/create-session", json={"name": "Test", "player_name": "Alice"})

        call_args = self.db_mock.game_sessions.insert_one.call_args
        code = call_args[0][0]["code"]
        for ch in code:
            assert ch in valid

    # -- join-session returns session_id --

    def test_join_session_returns_session_id(self):
        gs = GameSession(name="Test", code="JOINME", players=[Player(name="Alice")])
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/join-session", json={
            "session_id": gs.id, "player_name": "Bob",
        })
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert data["session_id"] == gs.id

    # -- join via short code --

    def test_join_session_resolves_short_code(self):
        gs = GameSession(name="Test", code="XCODE1", players=[Player(name="Alice")])
        gs_dict = gs.model_dump()

        async def mock_find_one(query):
            if "id" in query:
                return None
            if "code" in query and query["code"] == "XCODE1":
                return gs_dict
            return None

        self.db_mock.game_sessions.find_one = AsyncMock(side_effect=mock_find_one)
        self._mock_replace_one()

        res = self.client.post("/api/join-session", json={
            "session_id": "xcode1", "player_name": "Bob",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == gs.id

    def test_join_session_code_case_insensitive(self):
        gs = GameSession(name="Test", code="ABCD23", players=[Player(name="Alice")])
        gs_dict = gs.model_dump()

        async def mock_find_one(query):
            if "id" in query:
                return None
            if "code" in query and query["code"] == "ABCD23":
                return gs_dict
            return None

        self.db_mock.game_sessions.find_one = AsyncMock(side_effect=mock_find_one)
        self._mock_replace_one()

        res = self.client.post("/api/join-session", json={
            "session_id": "abcd23", "player_name": "Bob",
        })
        assert res.status_code == 200
        assert res.json()["session_id"] == gs.id

    def test_join_session_not_found(self):
        self._mock_find_one(returns=None)

        res = self.client.post("/api/join-session", json={
            "session_id": "nonexistent", "player_name": "Bob",
        })
        assert res.status_code == 404

    # -- join as spectator --

    def test_join_as_spectator_returns_session_id(self):
        gs = GameSession(name="Test", code="SPEC11", players=[Player(name="Alice")])
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/join-session", json={
            "session_id": gs.id, "player_name": "Watcher", "as_spectator": True,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == gs.id
        assert data["is_spectator"] is True

    # -- leave session --

    def test_leave_session_removes_player_in_lobby(self):
        alice = Player(name="Alice")
        bob = Player(name="Bob")
        gs = GameSession(name="Test", code="LEAVE1", players=[alice, bob], phase=GamePhase.LOBBY)

        from auth import issue_token
        token = issue_token(gs.id, bob.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/leave-session", json={
            "session_id": gs.id, "player_id": bob.id, "player_token": token,
        })
        assert res.status_code == 200

        replace_call = self.db_mock.game_sessions.replace_one.call_args
        updated_doc = replace_call[0][1]
        player_ids = [p["id"] for p in updated_doc["players"]]
        assert bob.id not in player_ids
        assert alice.id in player_ids

    def test_leave_session_removes_spectator_mid_game(self):
        alice = Player(name="Alice")
        spectator = Player(name="Watcher", is_spectator=True)
        gs = GameSession(
            name="Test", code="LEAVE2",
            players=[alice, spectator],
            phase=GamePhase.MISSION_TEAM_SELECTION,
        )

        from auth import issue_token
        token = issue_token(gs.id, spectator.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/leave-session", json={
            "session_id": gs.id, "player_id": spectator.id, "player_token": token,
        })
        assert res.status_code == 200

        replace_call = self.db_mock.game_sessions.replace_one.call_args
        updated_doc = replace_call[0][1]
        player_ids = [p["id"] for p in updated_doc["players"]]
        assert spectator.id not in player_ids

    def test_leave_session_disconnects_active_player_mid_game(self):
        alice = Player(name="Alice", role=Role.MERLIN)
        bob = Player(name="Bob", role=Role.ASSASSIN)
        gs = GameSession(
            name="Test", code="LEAVE3",
            players=[alice, bob],
            phase=GamePhase.MISSION_TEAM_SELECTION,
        )

        from auth import issue_token
        token = issue_token(gs.id, bob.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/leave-session", json={
            "session_id": gs.id, "player_id": bob.id, "player_token": token,
        })
        assert res.status_code == 200

        replace_call = self.db_mock.game_sessions.replace_one.call_args
        updated_doc = replace_call[0][1]
        bob_doc = next(p for p in updated_doc["players"] if p["id"] == bob.id)
        assert bob_doc["is_connected"] is False

    def test_leave_session_wrong_token_rejected(self):
        alice = Player(name="Alice")
        gs = GameSession(name="Test", code="LEAVE4", players=[alice], phase=GamePhase.LOBBY)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/leave-session", json={
            "session_id": gs.id, "player_id": alice.id, "player_token": "wrong-token",
        })
        assert res.status_code == 403

    def test_leave_session_not_found(self):
        from auth import issue_token
        token = issue_token("fake-session", "fake-player")

        self._mock_find_one(returns=None)

        res = self.client.post("/api/leave-session", json={
            "session_id": "fake-session", "player_id": "fake-player", "player_token": token,
        })
        assert res.status_code == 404

    def test_leave_session_already_removed(self):
        alice = Player(name="Alice")
        gs = GameSession(name="Test", code="LEAVE5", players=[alice], phase=GamePhase.LOBBY)

        from auth import issue_token
        token = issue_token(gs.id, "nonexistent-player")

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/leave-session", json={
            "session_id": gs.id, "player_id": "nonexistent-player", "player_token": token,
        })
        assert res.status_code == 200
        assert res.json()["message"] == "Already removed"

    # -- reconnection by name still returns session_id --

    def test_reconnect_by_name_returns_session_id(self):
        alice = Player(name="Alice", is_connected=False)
        gs = GameSession(name="Test", code="RECON1", players=[alice])
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/join-session", json={
            "session_id": gs.id, "player_name": "Alice",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == gs.id
        assert data["player_id"] == alice.id

    # -- session full --

    def test_join_full_session_rejected(self):
        players = [Player(name=f"P{i}") for i in range(10)]
        gs = GameSession(name="Full", code="FULL10", players=players)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/join-session", json={
            "session_id": gs.id, "player_name": "Overflow",
        })
        assert res.status_code == 400
        assert "full" in res.json()["detail"].lower()

    # -- spectators don't count toward full --

    def test_join_full_with_spectators_still_allows_player(self):
        active = [Player(name=f"P{i}") for i in range(9)]
        spectators = [Player(name="Spec1", is_spectator=True)]
        gs = GameSession(name="Almost", code="ALM001", players=active + spectators)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/join-session", json={
            "session_id": gs.id, "player_name": "NewPlayer",
        })
        assert res.status_code == 200

    # -- code collision retry on create --

    def test_create_session_retries_on_code_collision(self):
        call_count = 0

        async def mock_find_one(query):
            nonlocal call_count
            if "code" in query:
                call_count += 1
                if call_count <= 3:
                    return {"id": "existing"}
                return None
            return None

        self.db_mock.game_sessions.find_one = AsyncMock(side_effect=mock_find_one)
        self._mock_insert_one()

        res = self.client.post("/api/create-session", json={"name": "Retry", "player_name": "Alice"})
        assert res.status_code == 200
        assert call_count > 1

    # -- leave preserves other players --

    def test_leave_lobby_preserves_other_players(self):
        alice = Player(name="Alice")
        bob = Player(name="Bob")
        charlie = Player(name="Charlie")
        gs = GameSession(name="Test", code="PRSRV1", players=[alice, bob, charlie], phase=GamePhase.LOBBY)

        from auth import issue_token
        token = issue_token(gs.id, bob.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/leave-session", json={
            "session_id": gs.id, "player_id": bob.id, "player_token": token,
        })
        assert res.status_code == 200

        updated = self.db_mock.game_sessions.replace_one.call_args[0][1]
        names = [p["name"] for p in updated["players"]]
        assert "Alice" in names
        assert "Charlie" in names
        assert "Bob" not in names


# ===========================================================================
# 7. Additional edge case tests for broadcast state
# ===========================================================================

class TestBroadcastEdgeCases:
    """Edge cases for _build_player_state and _build_general_state."""

    def test_spectators_excluded_from_active_count(self):
        """Active count used for vote visibility should exclude spectators."""
        players = [Player(name=f"P{i}") for i in range(5)]
        players.append(Player(name="Spec", is_spectator=True))
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
        for p, r in zip(players[:5], roles):
            p.role = r

        from game_logic import initialize_missions
        missions = initialize_missions(5)
        missions[0].votes = {players[i].id: True for i in range(5)}
        missions[0].team_members = [players[0].id, players[1].id]

        gs = GameSession(
            name="Test", code="EDGE01", players=players,
            phase=GamePhase.VOTE_REVEAL, missions=missions,
        )
        state = _build_player_state(gs, players[0])
        mission_votes = state["session"]["missions"][0]["votes"]
        assert len(mission_votes) == 5

    def test_general_state_hides_pending_mission_votes(self):
        """Mission votes should be empty dict for pending missions in general state."""
        players = [Player(name=f"P{i}") for i in range(5)]
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
        for p, r in zip(players, roles):
            p.role = r

        from game_logic import initialize_missions
        missions = initialize_missions(5)

        gs = GameSession(
            name="Test", code="EDGE02", players=players,
            phase=GamePhase.MISSION_TEAM_SELECTION, missions=missions,
        )
        state = _build_general_state(gs)
        for m in state["session"]["missions"]:
            assert m["mission_votes"] == {}

    def test_completed_mission_shows_vote_counts(self):
        """Completed missions show aggregated vote counts, not individual votes."""
        players = [Player(name=f"P{i}") for i in range(5)]
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
        for p, r in zip(players, roles):
            p.role = r

        from game_logic import initialize_missions
        missions = initialize_missions(5)
        missions[0].result = MissionResult.SUCCESS
        missions[0].mission_votes = {players[0].id: True, players[1].id: True}
        missions[0].team_members = [players[0].id, players[1].id]

        gs = GameSession(
            name="Test", code="EDGE03", players=players,
            phase=GamePhase.MISSION_TEAM_SELECTION, missions=missions,
            current_mission=1,
        )
        state = _build_general_state(gs)
        mv = state["session"]["missions"][0]["mission_votes"]
        assert mv["total_votes"] == 2
        assert mv["success_count"] == 2
        assert mv["fail_count"] == 0

    def test_general_state_includes_vote_history(self):
        players = [Player(name=f"P{i}") for i in range(5)]
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
        for p, r in zip(players, roles):
            p.role = r

        from game_logic import initialize_missions
        gs = GameSession(
            name="Test", code="EDGE04", players=players,
            phase=GamePhase.MISSION_TEAM_SELECTION, missions=initialize_missions(5),
            vote_history=[{"type": "team_vote", "mission": 1, "result": "approved", "approve_count": 3, "total_votes": 5, "votes": {}}],
        )
        state = _build_general_state(gs)
        assert len(state["session"]["vote_history"]) == 1

    def test_general_state_includes_game_log(self):
        players = [Player(name=f"P{i}") for i in range(5)]
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
        for p, r in zip(players, roles):
            p.role = r

        from game_logic import initialize_missions
        gs = GameSession(
            name="Test", code="EDGE05", players=players,
            phase=GamePhase.MISSION_TEAM_SELECTION, missions=initialize_missions(5),
            game_log=["Game started", "Team selected"],
        )
        state = _build_general_state(gs)
        assert state["session"]["game_log"] == ["Game started", "Team selected"]

    def test_player_state_lady_of_lake_knowledge(self):
        players = [Player(name=f"P{i}") for i in range(7)]
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
                 Role.MORGANA, Role.ASSASSIN, Role.OBERON]
        for p, r in zip(players, roles):
            p.role = r

        from game_logic import initialize_missions
        gs = GameSession(
            name="Test", code="EDGE06", players=players,
            phase=GamePhase.MISSION_TEAM_SELECTION, missions=initialize_missions(7),
            lady_of_the_lake_results={
                players[0].id: {players[4].id: "evil"},
            },
        )
        state = _build_player_state(gs, players[0])
        assert "lady_of_lake_knowledge" in state
        assert len(state["lady_of_lake_knowledge"]) == 1
        assert state["lady_of_lake_knowledge"][0]["allegiance"] == "evil"

    def test_player_state_no_lady_knowledge_for_non_holder(self):
        players = [Player(name=f"P{i}") for i in range(7)]
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
                 Role.MORGANA, Role.ASSASSIN, Role.OBERON]
        for p, r in zip(players, roles):
            p.role = r

        from game_logic import initialize_missions
        gs = GameSession(
            name="Test", code="EDGE07", players=players,
            phase=GamePhase.MISSION_TEAM_SELECTION, missions=initialize_missions(7),
            lady_of_the_lake_results={
                players[0].id: {players[4].id: "evil"},
            },
        )
        state = _build_player_state(gs, players[1])
        assert "lady_of_lake_knowledge" not in state or len(state.get("lady_of_lake_knowledge", [])) == 0

    def test_player_state_current_mission_details(self):
        players = [Player(name=f"P{i}") for i in range(5)]
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
        for p, r in zip(players, roles):
            p.role = r

        from game_logic import initialize_missions
        missions = initialize_missions(5)
        missions[0].team_members = [players[0].id, players[1].id]

        gs = GameSession(
            name="Test", code="EDGE08", players=players,
            phase=GamePhase.MISSION_TEAM_SELECTION, missions=missions,
        )
        state = _build_player_state(gs, players[0])
        assert "current_mission_details" in state
        assert state["current_mission_details"]["number"] == 1
        assert state["current_mission_details"]["team_size"] == 2

    def test_general_state_settings_flags(self):
        players = [Player(name=f"P{i}") for i in range(5)]
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
        for p, r in zip(players, roles):
            p.role = r

        from game_logic import initialize_missions
        gs = GameSession(
            name="Test", code="EDGE09", players=players,
            phase=GamePhase.MISSION_TEAM_SELECTION, missions=initialize_missions(5),
            lady_of_the_lake_enabled=True,
            mordred_enabled=True,
            oberon_enabled=False,
        )
        state = _build_general_state(gs)
        assert state["session"]["lady_of_the_lake_enabled"] is True
        assert state["session"]["mordred_enabled"] is True
        assert state["session"]["oberon_enabled"] is False

    def test_votes_hidden_during_voting_phase(self):
        """During mission_voting phase, votes should not be sent to general state
        until all players have voted."""
        players = [Player(name=f"P{i}") for i in range(5)]
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
        for p, r in zip(players, roles):
            p.role = r

        from game_logic import initialize_missions
        missions = initialize_missions(5)
        missions[0].votes = {players[0].id: True, players[1].id: False}
        missions[0].team_members = [players[0].id, players[1].id]

        gs = GameSession(
            name="Test", code="EDGE10", players=players,
            phase=GamePhase.MISSION_VOTING, missions=missions,
        )
        state = _build_general_state(gs)
        assert state["session"]["missions"][0]["votes"] == {}

    def test_votes_shown_when_all_voted(self):
        """When all active players have voted, votes should be visible."""
        players = [Player(name=f"P{i}") for i in range(5)]
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
        for p, r in zip(players, roles):
            p.role = r

        from game_logic import initialize_missions
        missions = initialize_missions(5)
        missions[0].votes = {p.id: True for p in players}
        missions[0].team_members = [players[0].id, players[1].id]

        gs = GameSession(
            name="Test", code="EDGE11", players=players,
            phase=GamePhase.MISSION_VOTING, missions=missions,
        )
        state = _build_general_state(gs)
        assert len(state["session"]["missions"][0]["votes"]) == 5


# ===========================================================================
# 8. _resolve_session unit tests
# ===========================================================================

class TestResolveSession:
    """Test the _resolve_session helper directly."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.original_db = _srv.db
        self.db_mock = MagicMock()
        _srv.db = self.db_mock
        yield
        _srv.db = self.original_db

    @pytest.mark.asyncio
    async def test_resolves_by_uuid(self):
        doc = {"id": "uuid-123", "code": "ABC123"}
        self.db_mock.game_sessions.find_one = AsyncMock(return_value=doc)

        result = await _srv._resolve_session("uuid-123")
        assert result == doc

    @pytest.mark.asyncio
    async def test_resolves_by_code_when_uuid_not_found(self):
        doc = {"id": "uuid-456", "code": "XYZ789"}

        async def mock_find(query):
            if "id" in query:
                return None
            if "code" in query and query["code"] == "XYZ789":
                return doc
            return None

        self.db_mock.game_sessions.find_one = AsyncMock(side_effect=mock_find)

        result = await _srv._resolve_session("xyz789")
        assert result == doc

    @pytest.mark.asyncio
    async def test_uppercases_code_for_lookup(self):
        async def mock_find(query):
            if "id" in query:
                return None
            if "code" in query:
                assert query["code"] == "LOWER1"
                return {"id": "found", "code": "LOWER1"}
            return None

        self.db_mock.game_sessions.find_one = AsyncMock(side_effect=mock_find)

        result = await _srv._resolve_session("lower1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        self.db_mock.game_sessions.find_one = AsyncMock(return_value=None)

        result = await _srv._resolve_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_uuid_takes_priority_over_code(self):
        uuid_doc = {"id": "uuid-match", "code": "CODE01"}

        async def mock_find(query):
            if "id" in query and query["id"] == "uuid-match":
                return uuid_doc
            return {"id": "code-match", "code": "UUID-MATCH"}

        self.db_mock.game_sessions.find_one = AsyncMock(side_effect=mock_find)

        result = await _srv._resolve_session("uuid-match")
        assert result["id"] == "uuid-match"
