"""
Comprehensive tests for server endpoints, auth cleanup, websocket ConnectionManager,
and bot AI pure functions.

Covers:
  - auth.py: cleanup_session_tokens
  - websocket.py: ConnectionManager (connect, disconnect, send_to_player, broadcast_to_session)
  - bots.py: bot_select_team, bot_vote_team, bot_vote_mission
  - server.py: all remaining endpoints (start-game, start-test-game, select-team,
    vote-team, vote-mission, lady-of-lake, assassinate, toggles, restart, end-game,
    session queries, health, WS endpoint)

Run with: pytest tests/test_server_endpoints.py -v
"""

import sys
import os
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models import (
    Player, Mission, GameSession, GamePhase, Role, MissionResult,
    MISSION_CONFIGS,
)
from game_logic import initialize_missions

# Set env vars BEFORE importing server (it reads them at module level)
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "avalon_test")

import server as _srv
from auth import issue_token, cleanup_session_tokens, verify_token, _player_tokens
from websocket import ConnectionManager
from bots import bot_select_team, bot_vote_team, bot_vote_mission


# ===========================================================================
# Helpers
# ===========================================================================

def _make_players(n, roles=None):
    """Create n players with optional role assignments."""
    default_roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT,
                     Role.MORGANA, Role.ASSASSIN, Role.LOYAL_SERVANT,
                     Role.OBERON, Role.MINION, Role.MORDRED, Role.LOYAL_SERVANT]
    players = []
    for i in range(n):
        p = Player(name=f"Player{i+1}")
        if roles:
            p.role = roles[i]
        elif i < len(default_roles):
            p.role = default_roles[i]
        players.append(p)
    return players


def _make_game_session(n_players=5, phase=GamePhase.LOBBY, roles=None, **kwargs):
    """Create a GameSession with n active players."""
    players = _make_players(n_players, roles=roles)
    gs = GameSession(
        name="TestGame",
        players=players,
        phase=phase,
        **kwargs,
    )
    return gs


def _make_started_game(n_players=5, phase=GamePhase.MISSION_TEAM_SELECTION, roles=None):
    """Create a game session that has been started with missions initialized."""
    default_roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT,
                     Role.MORGANA, Role.ASSASSIN][:n_players]
    if n_players > 5:
        default_roles.extend([Role.LOYAL_SERVANT] * (n_players - 5))
    r = roles or default_roles
    players = _make_players(n_players, roles=r)
    missions = initialize_missions(n_players)
    gs = GameSession(
        name="TestGame",
        players=players,
        phase=phase,
        missions=missions,
        current_leader=0,
    )
    gs.players[0].is_leader = True
    return gs


# ===========================================================================
# 1. auth.py — cleanup_session_tokens
# ===========================================================================

class TestCleanupSessionTokens:

    def test_cleanup_removes_all_tokens_for_session(self):
        session_id = "cleanup-test-session"
        t1 = issue_token(session_id, "player1")
        t2 = issue_token(session_id, "player2")
        # Tokens should exist
        assert verify_token(session_id, "player1", t1)
        assert verify_token(session_id, "player2", t2)

        cleanup_session_tokens(session_id)

        # Tokens should be gone
        assert not verify_token(session_id, "player1", t1)
        assert not verify_token(session_id, "player2", t2)

    def test_cleanup_does_not_affect_other_sessions(self):
        session_a = "cleanup-session-a"
        session_b = "cleanup-session-b"
        token_a = issue_token(session_a, "player1")
        token_b = issue_token(session_b, "player1")

        cleanup_session_tokens(session_a)

        assert not verify_token(session_a, "player1", token_a)
        assert verify_token(session_b, "player1", token_b)

        # Cleanup
        cleanup_session_tokens(session_b)

    def test_cleanup_nonexistent_session_is_noop(self):
        # Should not raise
        cleanup_session_tokens("nonexistent-session-xyz")

    def test_cleanup_empty_session_after_no_tokens(self):
        session_id = "empty-session"
        cleanup_session_tokens(session_id)
        # Double cleanup should not raise
        cleanup_session_tokens(session_id)


# ===========================================================================
# 2. websocket.py — ConnectionManager
# ===========================================================================

class TestConnectionManager:

    @pytest.fixture
    def manager(self):
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_accepts_and_stores(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, "session1", "player1")

        ws.accept.assert_awaited_once()
        assert "session1" in manager.active_connections
        assert "player1" in manager.active_connections["session1"]
        assert manager.active_connections["session1"]["player1"] == ws

    @pytest.mark.asyncio
    async def test_connect_without_player_id_uses_uuid(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, "session1", None)

        ws.accept.assert_awaited_once()
        assert "session1" in manager.active_connections
        # Should have one connection with a UUID key
        assert len(manager.active_connections["session1"]) == 1

    @pytest.mark.asyncio
    async def test_connect_multiple_players_same_session(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(ws1, "session1", "player1")
        await manager.connect(ws2, "session1", "player2")

        assert len(manager.active_connections["session1"]) == 2

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, "session1", "player1")
        manager.disconnect(ws, "session1", "player1")

        # Session should be cleaned up since it's empty
        assert "session1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_keeps_other_connections(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(ws1, "session1", "player1")
        await manager.connect(ws2, "session1", "player2")

        manager.disconnect(ws1, "session1", "player1")

        assert "session1" in manager.active_connections
        assert "player1" not in manager.active_connections["session1"]
        assert "player2" in manager.active_connections["session1"]

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_empty_sessions(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, "session1", "player1")
        manager.disconnect(ws, "session1", "player1")

        assert "session1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_session_is_noop(self, manager):
        ws = AsyncMock()
        # Should not raise
        manager.disconnect(ws, "nonexistent", "player1")

    @pytest.mark.asyncio
    async def test_disconnect_finds_by_websocket_reference(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, "session1", "player1")
        # Disconnect without specifying player_id, but should match by ws reference
        manager.disconnect(ws, "session1", None)
        assert "session1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_send_to_player_sends_message(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, "session1", "player1")

        await manager.send_to_player("hello", "session1", "player1")
        ws.send_text.assert_awaited_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_to_player_nonexistent_session(self, manager):
        # Should not raise
        await manager.send_to_player("hello", "nonexistent", "player1")

    @pytest.mark.asyncio
    async def test_send_to_player_nonexistent_player(self, manager):
        ws = AsyncMock()
        await manager.connect(ws, "session1", "player1")

        # Should not raise or send
        await manager.send_to_player("hello", "session1", "nonexistent")
        ws.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_to_player_removes_dead_connection(self, manager):
        ws = AsyncMock()
        ws.send_text.side_effect = Exception("Connection closed")
        await manager.connect(ws, "session1", "player1")

        await manager.send_to_player("hello", "session1", "player1")

        # Dead connection should be removed
        assert "player1" not in manager.active_connections.get("session1", {})

    @pytest.mark.asyncio
    async def test_broadcast_to_session_sends_to_all(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(ws1, "session1", "player1")
        await manager.connect(ws2, "session1", "player2")

        await manager.broadcast_to_session("broadcast_msg", "session1")

        ws1.send_text.assert_awaited_once_with("broadcast_msg")
        ws2.send_text.assert_awaited_once_with("broadcast_msg")

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_session(self, manager):
        # Should not raise
        await manager.broadcast_to_session("msg", "nonexistent")

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.send_text.side_effect = Exception("Dead")
        await manager.connect(ws1, "session1", "player1")
        await manager.connect(ws2, "session1", "player2")

        await manager.broadcast_to_session("msg", "session1")

        # Dead connection should be removed, live one stays
        assert "player1" not in manager.active_connections["session1"]
        assert "player2" in manager.active_connections["session1"]


# ===========================================================================
# 3. bots.py — Pure functions
# ===========================================================================

class TestBotSelectTeam:

    @pytest.mark.asyncio
    async def test_returns_correct_team_size(self):
        gs = _make_started_game(5)
        bot = gs.players[0]
        bot.is_bot = True
        team = await bot_select_team(gs, bot)
        expected_size = gs.missions[0].team_size
        assert len(team) == expected_size

    @pytest.mark.asyncio
    async def test_includes_bot_itself(self):
        gs = _make_started_game(5)
        bot = gs.players[0]
        bot.is_bot = True
        team = await bot_select_team(gs, bot)
        assert bot.id in team

    @pytest.mark.asyncio
    async def test_excludes_spectators(self):
        gs = _make_started_game(5)
        spectator = Player(name="Spectator", is_spectator=True)
        gs.players.append(spectator)
        bot = gs.players[0]
        bot.is_bot = True

        team = await bot_select_team(gs, bot)
        assert spectator.id not in team

    @pytest.mark.asyncio
    async def test_no_duplicates(self):
        gs = _make_started_game(5)
        bot = gs.players[0]
        bot.is_bot = True
        team = await bot_select_team(gs, bot)
        assert len(team) == len(set(team))

    @pytest.mark.asyncio
    async def test_all_members_are_valid_players(self):
        gs = _make_started_game(5)
        bot = gs.players[0]
        bot.is_bot = True
        valid_ids = {p.id for p in gs.players if not p.is_spectator}
        team = await bot_select_team(gs, bot)
        for member in team:
            assert member in valid_ids


class TestBotVoteTeam:

    @pytest.mark.asyncio
    async def test_returns_bool(self):
        gs = _make_started_game(5)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[1].id]
        for player in gs.players:
            result = await bot_vote_team(gs, player)
            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_good_player_votes(self):
        gs = _make_started_game(5)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[1].id]
        good_player = gs.players[0]  # MERLIN
        # Run multiple times to check it always returns bool
        for _ in range(20):
            result = await bot_vote_team(gs, good_player)
            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_evil_player_votes(self):
        gs = _make_started_game(5)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[1].id]
        evil_player = gs.players[3]  # MORGANA
        for _ in range(20):
            result = await bot_vote_team(gs, evil_player)
            assert isinstance(result, bool)


class TestBotVoteMission:

    @pytest.mark.asyncio
    async def test_good_player_always_votes_success(self):
        gs = _make_started_game(5)
        merlin = gs.players[0]  # Role.MERLIN
        percival = gs.players[1]  # Role.PERCIVAL
        loyal = gs.players[2]  # Role.LOYAL_SERVANT

        for good_player in [merlin, percival, loyal]:
            for _ in range(50):
                result = await bot_vote_mission(gs, good_player)
                assert result is True, f"{good_player.role} should always vote True"

    @pytest.mark.asyncio
    async def test_evil_player_may_vote_fail(self):
        gs = _make_started_game(5)
        morgana = gs.players[3]  # Role.MORGANA
        assassin = gs.players[4]  # Role.ASSASSIN

        # Run enough times to see at least one fail vote
        for evil_player in [morgana, assassin]:
            results = set()
            for _ in range(100):
                results.add(await bot_vote_mission(gs, evil_player))
            assert False in results, f"{evil_player.role} should sometimes vote False"

    @pytest.mark.asyncio
    async def test_evil_player_returns_bool(self):
        gs = _make_started_game(5)
        evil_player = gs.players[3]  # MORGANA
        result = await bot_vote_mission(gs, evil_player)
        assert isinstance(result, bool)


# ===========================================================================
# 4. server.py — All remaining endpoints
# ===========================================================================

class TestServerEndpoints:
    """Test all server endpoints using FastAPI's TestClient with mocked DB."""

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

    def _mock_update_one(self):
        self.db_mock.game_sessions.update_one = AsyncMock()

    # ── Health check ──────────────────────────────────────────────────

    def test_health_check_healthy(self):
        self.db_mock.command = AsyncMock(return_value={"ok": 1})
        res = self.client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

    def test_health_check_unhealthy(self):
        self.db_mock.command = AsyncMock(side_effect=Exception("DB down"))
        res = self.client.get("/health")
        assert res.status_code == 503

    def test_root_endpoint(self):
        res = self.client.get("/")
        assert res.status_code == 200
        assert res.json()["status"] == "running"

    def test_api_root_endpoint(self):
        res = self.client.get("/api/")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

    # ── Start game ────────────────────────────────────────────────────

    def test_start_game_success(self):
        gs = _make_game_session(5, phase=GamePhase.LOBBY)
        # Remove roles so initialize_game can assign them
        for p in gs.players:
            p.role = None
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/start-game", json={"session_id": gs.id})
        assert res.status_code == 200
        assert "started" in res.json()["message"].lower()

    def test_start_game_not_enough_players(self):
        gs = _make_game_session(3, phase=GamePhase.LOBBY)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/start-game", json={"session_id": gs.id})
        assert res.status_code == 400
        assert "5 players" in res.json()["detail"]

    def test_start_game_already_started(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/start-game", json={"session_id": gs.id})
        assert res.status_code == 400
        assert "already started" in res.json()["detail"].lower()

    def test_start_game_session_not_found(self):
        self._mock_find_one(returns=None)

        res = self.client.post("/api/start-game", json={"session_id": "nonexistent"})
        assert res.status_code == 404

    def test_start_game_spectators_not_counted(self):
        gs = _make_game_session(4, phase=GamePhase.LOBBY)
        spectator = Player(name="Spectator", is_spectator=True)
        gs.players.append(spectator)
        # Remove roles
        for p in gs.players:
            p.role = None
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/start-game", json={"session_id": gs.id})
        assert res.status_code == 400
        assert "5 players" in res.json()["detail"]

    # ── Start test game ───────────────────────────────────────────────

    def test_start_test_game_success(self):
        gs = _make_game_session(1, phase=GamePhase.LOBBY)
        for p in gs.players:
            p.role = None
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/start-test-game", json={"session_id": gs.id})
        assert res.status_code == 200
        assert "test game started" in res.json()["message"].lower()

    def test_start_test_game_already_started(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/start-test-game", json={"session_id": gs.id})
        assert res.status_code == 400

    def test_start_test_game_not_found(self):
        self._mock_find_one(returns=None)

        res = self.client.post("/api/start-test-game", json={"session_id": "nonexistent"})
        assert res.status_code == 404

    # ── Select team ───────────────────────────────────────────────────

    def test_select_team_success(self):
        gs = _make_started_game(5)
        leader = gs.players[0]
        token = issue_token(gs.id, leader.id)
        team = [gs.players[0].id, gs.players[1].id]  # team_size for 5 players, mission 1 = 2

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/select-team", json={
            "session_id": gs.id,
            "player_id": leader.id,
            "player_token": token,
            "team_members": team,
        })
        assert res.status_code == 200
        assert "selected" in res.json()["message"].lower()

    def test_select_team_wrong_phase(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_VOTING)
        leader = gs.players[0]
        token = issue_token(gs.id, leader.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/select-team", json={
            "session_id": gs.id,
            "player_id": leader.id,
            "player_token": token,
            "team_members": [gs.players[0].id, gs.players[1].id],
        })
        assert res.status_code == 400
        assert "team selection" in res.json()["detail"].lower()

    def test_select_team_not_leader(self):
        gs = _make_started_game(5)
        non_leader = gs.players[1]
        token = issue_token(gs.id, non_leader.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/select-team", json={
            "session_id": gs.id,
            "player_id": non_leader.id,
            "player_token": token,
            "team_members": [gs.players[0].id, gs.players[1].id],
        })
        assert res.status_code == 400
        assert "not your turn" in res.json()["detail"].lower()

    def test_select_team_wrong_size(self):
        gs = _make_started_game(5)
        leader = gs.players[0]
        token = issue_token(gs.id, leader.id)

        self._mock_find_one(returns=gs.model_dump())

        # Mission 1 for 5 players requires 2 members, provide 3
        res = self.client.post("/api/select-team", json={
            "session_id": gs.id,
            "player_id": leader.id,
            "player_token": token,
            "team_members": [gs.players[0].id, gs.players[1].id, gs.players[2].id],
        })
        assert res.status_code == 400
        assert "members" in res.json()["detail"].lower()

    def test_select_team_duplicate_members(self):
        gs = _make_started_game(5)
        leader = gs.players[0]
        token = issue_token(gs.id, leader.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/select-team", json={
            "session_id": gs.id,
            "player_id": leader.id,
            "player_token": token,
            "team_members": [gs.players[0].id, gs.players[0].id],
        })
        assert res.status_code == 400
        assert "duplicate" in res.json()["detail"].lower()

    def test_select_team_invalid_player_ids(self):
        gs = _make_started_game(5)
        leader = gs.players[0]
        token = issue_token(gs.id, leader.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/select-team", json={
            "session_id": gs.id,
            "player_id": leader.id,
            "player_token": token,
            "team_members": [gs.players[0].id, "nonexistent-id"],
        })
        assert res.status_code == 400
        assert "invalid" in res.json()["detail"].lower()

    def test_select_team_no_auth(self):
        gs = _make_started_game(5)
        leader = gs.players[0]

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/select-team", json={
            "session_id": gs.id,
            "player_id": leader.id,
            "player_token": "bad-token",
            "team_members": [gs.players[0].id, gs.players[1].id],
        })
        assert res.status_code == 403

    def test_select_team_session_not_found(self):
        token = issue_token("fake-session", "fake-player")
        self._mock_find_one(returns=None)

        res = self.client.post("/api/select-team", json={
            "session_id": "fake-session",
            "player_id": "fake-player",
            "player_token": token,
            "team_members": ["a", "b"],
        })
        assert res.status_code == 404

    # ── Vote team ─────────────────────────────────────────────────────

    def test_vote_team_success(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_VOTING)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[1].id]
        voter = gs.players[0]
        token = issue_token(gs.id, voter.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/vote-team", json={
            "session_id": gs.id,
            "player_id": voter.id,
            "player_token": token,
            "vote": True,
        })
        assert res.status_code == 200
        assert "recorded" in res.json()["message"].lower()

    def test_vote_team_wrong_phase(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        voter = gs.players[0]
        token = issue_token(gs.id, voter.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/vote-team", json={
            "session_id": gs.id,
            "player_id": voter.id,
            "player_token": token,
            "vote": True,
        })
        assert res.status_code == 400

    def test_vote_team_already_voted(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_VOTING)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[1].id]
        voter = gs.players[0]
        gs.missions[0].votes[voter.id] = True
        token = issue_token(gs.id, voter.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/vote-team", json={
            "session_id": gs.id,
            "player_id": voter.id,
            "player_token": token,
            "vote": True,
        })
        assert res.status_code == 400
        assert "already voted" in res.json()["detail"].lower()

    def test_vote_team_all_voted_triggers_processing(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_VOTING)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[1].id]
        # 4 players already voted
        for i in range(1, 5):
            gs.missions[0].votes[gs.players[i].id] = True

        last_voter = gs.players[0]
        token = issue_token(gs.id, last_voter.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/vote-team", json={
            "session_id": gs.id,
            "player_id": last_voter.id,
            "player_token": token,
            "vote": True,
        })
        assert res.status_code == 200

        # Verify replace_one was called (state was saved)
        assert self.db_mock.game_sessions.replace_one.await_count >= 1

    def test_vote_team_no_auth(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_VOTING)
        res = self.client.post("/api/vote-team", json={
            "session_id": gs.id,
            "player_id": gs.players[0].id,
            "player_token": "bad-token",
            "vote": True,
        })
        assert res.status_code == 403

    def test_vote_team_session_not_found(self):
        token = issue_token("fake", "fake")
        self._mock_find_one(returns=None)

        res = self.client.post("/api/vote-team", json={
            "session_id": "fake",
            "player_id": "fake",
            "player_token": token,
            "vote": True,
        })
        assert res.status_code == 404

    # ── Vote mission ──────────────────────────────────────────────────

    def test_vote_mission_success(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_EXECUTION)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[1].id]
        voter = gs.players[0]  # MERLIN (good)
        token = issue_token(gs.id, voter.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/vote-mission", json={
            "session_id": gs.id,
            "player_id": voter.id,
            "player_token": token,
            "vote": True,
        })
        assert res.status_code == 200

    def test_vote_mission_wrong_phase(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_VOTING)
        voter = gs.players[0]
        token = issue_token(gs.id, voter.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/vote-mission", json={
            "session_id": gs.id,
            "player_id": voter.id,
            "player_token": token,
            "vote": True,
        })
        assert res.status_code == 400

    def test_vote_mission_not_on_team(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_EXECUTION)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[1].id]
        non_team_member = gs.players[2]
        token = issue_token(gs.id, non_team_member.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/vote-mission", json={
            "session_id": gs.id,
            "player_id": non_team_member.id,
            "player_token": token,
            "vote": True,
        })
        assert res.status_code == 400
        assert "not on this mission" in res.json()["detail"].lower()

    def test_vote_mission_already_voted(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_EXECUTION)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[1].id]
        voter = gs.players[0]
        gs.missions[0].mission_votes[voter.id] = True
        token = issue_token(gs.id, voter.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/vote-mission", json={
            "session_id": gs.id,
            "player_id": voter.id,
            "player_token": token,
            "vote": True,
        })
        assert res.status_code == 400
        assert "already voted" in res.json()["detail"].lower()

    def test_vote_mission_good_cannot_vote_fail(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_EXECUTION)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[1].id]
        merlin = gs.players[0]  # MERLIN (good)
        token = issue_token(gs.id, merlin.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/vote-mission", json={
            "session_id": gs.id,
            "player_id": merlin.id,
            "player_token": token,
            "vote": False,
        })
        assert res.status_code == 400
        assert "good players" in res.json()["detail"].lower()

    def test_vote_mission_percival_cannot_vote_fail(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_EXECUTION)
        percival = gs.players[1]  # PERCIVAL
        gs.missions[0].team_members = [percival.id, gs.players[3].id]
        token = issue_token(gs.id, percival.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/vote-mission", json={
            "session_id": gs.id,
            "player_id": percival.id,
            "player_token": token,
            "vote": False,
        })
        assert res.status_code == 400

    def test_vote_mission_loyal_servant_cannot_vote_fail(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_EXECUTION)
        loyal = gs.players[2]  # LOYAL_SERVANT
        gs.missions[0].team_members = [loyal.id, gs.players[3].id]
        token = issue_token(gs.id, loyal.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/vote-mission", json={
            "session_id": gs.id,
            "player_id": loyal.id,
            "player_token": token,
            "vote": False,
        })
        assert res.status_code == 400

    def test_vote_mission_evil_can_vote_fail(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_EXECUTION)
        morgana = gs.players[3]  # MORGANA (evil)
        gs.missions[0].team_members = [morgana.id, gs.players[0].id]
        token = issue_token(gs.id, morgana.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/vote-mission", json={
            "session_id": gs.id,
            "player_id": morgana.id,
            "player_token": token,
            "vote": False,
        })
        assert res.status_code == 200

    def test_vote_mission_all_voted_triggers_processing(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_EXECUTION)
        gs.missions[0].team_members = [gs.players[0].id, gs.players[3].id]
        # First member already voted
        gs.missions[0].mission_votes[gs.players[0].id] = True
        # Evil player votes last
        morgana = gs.players[3]
        token = issue_token(gs.id, morgana.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/vote-mission", json={
            "session_id": gs.id,
            "player_id": morgana.id,
            "player_token": token,
            "vote": False,
        })
        assert res.status_code == 200
        assert self.db_mock.game_sessions.replace_one.await_count >= 1

    def test_vote_mission_session_not_found(self):
        token = issue_token("fake", "fake")
        self._mock_find_one(returns=None)

        res = self.client.post("/api/vote-mission", json={
            "session_id": "fake",
            "player_id": "fake",
            "player_token": token,
            "vote": True,
        })
        assert res.status_code == 404

    # ── Lady of the Lake ──────────────────────────────────────────────

    def test_lady_of_lake_success(self):
        gs = _make_started_game(7, phase=GamePhase.LADY_OF_THE_LAKE)
        # Extend roles for 7 players
        extra_roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
                       Role.MORGANA, Role.ASSASSIN, Role.OBERON]
        for i, r in enumerate(extra_roles):
            gs.players[i].role = r

        holder = gs.players[0]
        holder.lady_of_the_lake = True
        gs.lady_of_the_lake_holder = holder.id
        target = gs.players[4]  # MORGANA (evil)

        token = issue_token(gs.id, holder.id)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/lady-of-lake", json={
            "session_id": gs.id,
            "player_id": holder.id,
            "player_token": token,
            "target_player_id": target.id,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["allegiance"] == "evil"
        assert data["target_name"] == target.name

    def test_lady_of_lake_good_target(self):
        gs = _make_started_game(7, phase=GamePhase.LADY_OF_THE_LAKE)
        extra_roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
                       Role.MORGANA, Role.ASSASSIN, Role.OBERON]
        for i, r in enumerate(extra_roles):
            gs.players[i].role = r

        holder = gs.players[4]  # MORGANA has lady
        holder.lady_of_the_lake = True
        gs.lady_of_the_lake_holder = holder.id
        target = gs.players[0]  # MERLIN (good)

        token = issue_token(gs.id, holder.id)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/lady-of-lake", json={
            "session_id": gs.id,
            "player_id": holder.id,
            "player_token": token,
            "target_player_id": target.id,
        })
        assert res.status_code == 200
        assert res.json()["allegiance"] == "good"

    def test_lady_of_lake_wrong_phase(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        token = issue_token(gs.id, gs.players[0].id)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/lady-of-lake", json={
            "session_id": gs.id,
            "player_id": gs.players[0].id,
            "player_token": token,
            "target_player_id": gs.players[1].id,
        })
        assert res.status_code == 400

    def test_lady_of_lake_not_holder(self):
        gs = _make_started_game(7, phase=GamePhase.LADY_OF_THE_LAKE)
        extra_roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
                       Role.MORGANA, Role.ASSASSIN, Role.OBERON]
        for i, r in enumerate(extra_roles):
            gs.players[i].role = r
        # Player 0 has lady, but player 1 tries to use it
        gs.players[0].lady_of_the_lake = True
        non_holder = gs.players[1]
        token = issue_token(gs.id, non_holder.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/lady-of-lake", json={
            "session_id": gs.id,
            "player_id": non_holder.id,
            "player_token": token,
            "target_player_id": gs.players[2].id,
        })
        assert res.status_code == 400
        assert "lady of the lake" in res.json()["detail"].lower()

    def test_lady_of_lake_target_self(self):
        gs = _make_started_game(7, phase=GamePhase.LADY_OF_THE_LAKE)
        extra_roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
                       Role.MORGANA, Role.ASSASSIN, Role.OBERON]
        for i, r in enumerate(extra_roles):
            gs.players[i].role = r
        holder = gs.players[0]
        holder.lady_of_the_lake = True
        token = issue_token(gs.id, holder.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/lady-of-lake", json={
            "session_id": gs.id,
            "player_id": holder.id,
            "player_token": token,
            "target_player_id": holder.id,
        })
        assert res.status_code == 400
        assert "yourself" in res.json()["detail"].lower()

    def test_lady_of_lake_target_spectator(self):
        gs = _make_started_game(7, phase=GamePhase.LADY_OF_THE_LAKE)
        extra_roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
                       Role.MORGANA, Role.ASSASSIN, Role.OBERON]
        for i, r in enumerate(extra_roles):
            gs.players[i].role = r
        spectator = Player(name="Spectator", is_spectator=True)
        gs.players.append(spectator)
        holder = gs.players[0]
        holder.lady_of_the_lake = True
        token = issue_token(gs.id, holder.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/lady-of-lake", json={
            "session_id": gs.id,
            "player_id": holder.id,
            "player_token": token,
            "target_player_id": spectator.id,
        })
        assert res.status_code == 400
        assert "spectator" in res.json()["detail"].lower()

    def test_lady_of_lake_target_not_found(self):
        gs = _make_started_game(7, phase=GamePhase.LADY_OF_THE_LAKE)
        extra_roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
                       Role.MORGANA, Role.ASSASSIN, Role.OBERON]
        for i, r in enumerate(extra_roles):
            gs.players[i].role = r
        holder = gs.players[0]
        holder.lady_of_the_lake = True
        token = issue_token(gs.id, holder.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/lady-of-lake", json={
            "session_id": gs.id,
            "player_id": holder.id,
            "player_token": token,
            "target_player_id": "nonexistent",
        })
        assert res.status_code == 404

    def test_lady_of_lake_target_previous_holder(self):
        gs = _make_started_game(7, phase=GamePhase.LADY_OF_THE_LAKE)
        extra_roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
                       Role.MORGANA, Role.ASSASSIN, Role.OBERON]
        for i, r in enumerate(extra_roles):
            gs.players[i].role = r
        holder = gs.players[1]
        holder.lady_of_the_lake = True
        gs.lady_of_the_lake_holder = holder.id
        # Player 0 was a previous holder
        gs.lady_of_the_lake_results = {gs.players[0].id: {gs.players[2].id: "good"}}
        token = issue_token(gs.id, holder.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/lady-of-lake", json={
            "session_id": gs.id,
            "player_id": holder.id,
            "player_token": token,
            "target_player_id": gs.players[0].id,
        })
        assert res.status_code == 400
        assert "previous" in res.json()["detail"].lower()

    def test_lady_of_lake_session_not_found(self):
        token = issue_token("fake", "fake")
        self._mock_find_one(returns=None)

        res = self.client.post("/api/lady-of-lake", json={
            "session_id": "fake",
            "player_id": "fake",
            "player_token": token,
            "target_player_id": "someone",
        })
        assert res.status_code == 404

    # ── Assassination ─────────────────────────────────────────────────

    def test_assassinate_success_kills_merlin(self):
        gs = _make_started_game(5, phase=GamePhase.ASSASSINATION)
        assassin = gs.players[4]  # ASSASSIN
        merlin = gs.players[0]  # MERLIN
        token = issue_token(gs.id, assassin.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/assassinate", json={
            "session_id": gs.id,
            "player_id": assassin.id,
            "player_token": token,
            "target_player_id": merlin.id,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["target_name"] == merlin.name

    def test_assassinate_fails_wrong_target(self):
        gs = _make_started_game(5, phase=GamePhase.ASSASSINATION)
        assassin = gs.players[4]  # ASSASSIN
        percival = gs.players[1]  # PERCIVAL (not Merlin)
        token = issue_token(gs.id, assassin.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/assassinate", json={
            "session_id": gs.id,
            "player_id": assassin.id,
            "player_token": token,
            "target_player_id": percival.id,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False

    def test_assassinate_wrong_phase(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        assassin = gs.players[4]
        token = issue_token(gs.id, assassin.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/assassinate", json={
            "session_id": gs.id,
            "player_id": assassin.id,
            "player_token": token,
            "target_player_id": gs.players[0].id,
        })
        assert res.status_code == 400

    def test_assassinate_not_assassin(self):
        gs = _make_started_game(5, phase=GamePhase.ASSASSINATION)
        non_assassin = gs.players[0]  # MERLIN, not ASSASSIN
        token = issue_token(gs.id, non_assassin.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/assassinate", json={
            "session_id": gs.id,
            "player_id": non_assassin.id,
            "player_token": token,
            "target_player_id": gs.players[1].id,
        })
        assert res.status_code == 400
        assert "assassin" in res.json()["detail"].lower()

    def test_assassinate_target_not_found(self):
        gs = _make_started_game(5, phase=GamePhase.ASSASSINATION)
        assassin = gs.players[4]
        token = issue_token(gs.id, assassin.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/assassinate", json={
            "session_id": gs.id,
            "player_id": assassin.id,
            "player_token": token,
            "target_player_id": "nonexistent",
        })
        assert res.status_code == 404

    def test_assassinate_session_not_found(self):
        token = issue_token("fake", "fake")
        self._mock_find_one(returns=None)

        res = self.client.post("/api/assassinate", json={
            "session_id": "fake",
            "player_id": "fake",
            "player_token": token,
            "target_player_id": "someone",
        })
        assert res.status_code == 404

    # ── Toggle Lady of the Lake ───────────────────────────────────────

    def test_toggle_lady_of_lake_enable(self):
        gs = _make_game_session(5, phase=GamePhase.LOBBY)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/toggle-lady-of-lake", json={
            "session_id": gs.id,
            "enabled": True,
        })
        assert res.status_code == 200
        assert res.json()["lady_of_the_lake_enabled"] is True

    def test_toggle_lady_of_lake_disable(self):
        gs = _make_game_session(5, phase=GamePhase.LOBBY, lady_of_the_lake_enabled=True)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/toggle-lady-of-lake", json={
            "session_id": gs.id,
            "enabled": False,
        })
        assert res.status_code == 200
        assert res.json()["lady_of_the_lake_enabled"] is False

    def test_toggle_lady_of_lake_not_in_lobby(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/toggle-lady-of-lake", json={
            "session_id": gs.id,
            "enabled": True,
        })
        assert res.status_code == 400
        assert "lobby" in res.json()["detail"].lower()

    def test_toggle_lady_of_lake_not_found(self):
        self._mock_find_one(returns=None)

        res = self.client.post("/api/toggle-lady-of-lake", json={
            "session_id": "nonexistent",
            "enabled": True,
        })
        assert res.status_code == 404

    # ── Toggle Mordred ────────────────────────────────────────────────

    def test_toggle_mordred_enable(self):
        gs = _make_game_session(5, phase=GamePhase.LOBBY)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/toggle-mordred", json={
            "session_id": gs.id,
            "enabled": True,
        })
        assert res.status_code == 200
        assert res.json()["mordred_enabled"] is True

    def test_toggle_mordred_disable(self):
        gs = _make_game_session(5, phase=GamePhase.LOBBY, mordred_enabled=True)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/toggle-mordred", json={
            "session_id": gs.id,
            "enabled": False,
        })
        assert res.status_code == 200
        assert res.json()["mordred_enabled"] is False

    def test_toggle_mordred_not_in_lobby(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/toggle-mordred", json={
            "session_id": gs.id,
            "enabled": True,
        })
        assert res.status_code == 400

    def test_toggle_mordred_not_found(self):
        self._mock_find_one(returns=None)

        res = self.client.post("/api/toggle-mordred", json={
            "session_id": "nonexistent",
            "enabled": True,
        })
        assert res.status_code == 404

    # ── Toggle Oberon ─────────────────────────────────────────────────

    def test_toggle_oberon_enable(self):
        gs = _make_game_session(5, phase=GamePhase.LOBBY)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/toggle-oberon", json={
            "session_id": gs.id,
            "enabled": True,
        })
        assert res.status_code == 200
        assert res.json()["oberon_enabled"] is True

    def test_toggle_oberon_disable(self):
        gs = _make_game_session(5, phase=GamePhase.LOBBY, oberon_enabled=True)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/toggle-oberon", json={
            "session_id": gs.id,
            "enabled": False,
        })
        assert res.status_code == 200
        assert res.json()["oberon_enabled"] is False

    def test_toggle_oberon_not_in_lobby(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.post("/api/toggle-oberon", json={
            "session_id": gs.id,
            "enabled": True,
        })
        assert res.status_code == 400

    def test_toggle_oberon_not_found(self):
        self._mock_find_one(returns=None)

        res = self.client.post("/api/toggle-oberon", json={
            "session_id": "nonexistent",
            "enabled": True,
        })
        assert res.status_code == 404

    # ── Restart game ──────────────────────────────────────────────────

    def test_restart_game_success(self):
        gs = _make_started_game(5, phase=GamePhase.GAME_END)
        gs.game_result = "good"
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/restart-game", json={"session_id": gs.id})
        assert res.status_code == 200
        assert "restarted" in res.json()["message"].lower()

        # Verify the state was reset
        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        assert updated["phase"] == GamePhase.LOBBY
        assert updated["current_mission"] == 0
        assert updated["vote_track"] == 0
        assert updated["game_result"] is None
        assert updated["missions"] == []

    def test_restart_game_resets_player_roles(self):
        gs = _make_started_game(5, phase=GamePhase.GAME_END)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        self.client.post("/api/restart-game", json={"session_id": gs.id})

        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        for p in updated["players"]:
            assert p["role"] is None
            assert p["lady_of_the_lake"] is False

    def test_restart_game_not_found(self):
        self._mock_find_one(returns=None)

        res = self.client.post("/api/restart-game", json={"session_id": "nonexistent"})
        assert res.status_code == 404

    # ── End game ──────────────────────────────────────────────────────

    def test_end_game_success(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        res = self.client.post("/api/end-game", json={"session_id": gs.id})
        assert res.status_code == 200
        assert "ended" in res.json()["message"].lower()

        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        assert updated["phase"] == GamePhase.GAME_END

    def test_end_game_preserves_existing_result(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        gs.game_result = "evil"
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        self.client.post("/api/end-game", json={"session_id": gs.id})

        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        assert updated["game_result"] == "evil"

    def test_end_game_sets_ended_when_no_result(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        gs.game_result = None
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        self.client.post("/api/end-game", json={"session_id": gs.id})

        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        assert updated["game_result"] == "ended"

    def test_end_game_adds_log_entry(self):
        gs = _make_started_game(5, phase=GamePhase.MISSION_TEAM_SELECTION)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        self.client.post("/api/end-game", json={"session_id": gs.id})

        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        assert any("ended manually" in entry.lower() for entry in updated["game_log"])

    def test_end_game_not_found(self):
        self._mock_find_one(returns=None)

        res = self.client.post("/api/end-game", json={"session_id": "nonexistent"})
        assert res.status_code == 404

    # ── Get session (public) ──────────────────────────────────────────

    def test_get_session_success(self):
        gs = _make_started_game(5)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.get(f"/api/session/{gs.id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == gs.id
        assert data["name"] == gs.name
        assert data["phase"] == gs.phase
        assert len(data["players"]) == 5

    def test_get_session_hides_roles_during_game(self):
        gs = _make_started_game(5)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.get(f"/api/session/{gs.id}")
        data = res.json()
        for p in data["players"]:
            assert p["role"] is None

    def test_get_session_reveals_roles_at_game_end(self):
        gs = _make_started_game(5, phase=GamePhase.GAME_END)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.get(f"/api/session/{gs.id}")
        data = res.json()
        for p in data["players"]:
            assert p["role"] is not None

    def test_get_session_not_found(self):
        self._mock_find_one(returns=None)

        res = self.client.get("/api/session/nonexistent")
        assert res.status_code == 404

    def test_get_session_includes_game_state_fields(self):
        gs = _make_started_game(5)
        gs.good_wins = 2
        gs.evil_wins = 1
        gs.vote_track = 3
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.get(f"/api/session/{gs.id}")
        data = res.json()
        assert data["good_wins"] == 2
        assert data["evil_wins"] == 1
        assert data["vote_track"] == 3
        assert data["current_mission"] == 0
        assert data["current_leader"] == 0

    # ── Get session personalized (/me) ────────────────────────────────

    def test_get_session_personalized_success(self):
        gs = _make_started_game(5)
        player = gs.players[0]
        token = issue_token(gs.id, player.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.get(
            f"/api/session/{gs.id}/me",
            params={"player_id": player.id, "player_token": token},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "game_state"
        assert data["session"]["id"] == gs.id

    def test_get_session_personalized_includes_own_role(self):
        gs = _make_started_game(5)
        player = gs.players[0]  # MERLIN
        token = issue_token(gs.id, player.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.get(
            f"/api/session/{gs.id}/me",
            params={"player_id": player.id, "player_token": token},
        )
        data = res.json()
        own_player = next(p for p in data["session"]["players"] if p["id"] == player.id)
        assert own_player["role"] is not None

    def test_get_session_personalized_hides_other_roles(self):
        gs = _make_started_game(5)
        player = gs.players[0]
        token = issue_token(gs.id, player.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.get(
            f"/api/session/{gs.id}/me",
            params={"player_id": player.id, "player_token": token},
        )
        data = res.json()
        others = [p for p in data["session"]["players"] if p["id"] != player.id]
        assert all(p["role"] is None for p in others)

    def test_get_session_personalized_includes_role_info(self):
        gs = _make_started_game(5)
        player = gs.players[0]  # MERLIN
        token = issue_token(gs.id, player.id)

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.get(
            f"/api/session/{gs.id}/me",
            params={"player_id": player.id, "player_token": token},
        )
        data = res.json()
        assert "role_info" in data

    def test_get_session_personalized_no_auth(self):
        gs = _make_started_game(5)
        self._mock_find_one(returns=gs.model_dump())

        res = self.client.get(
            f"/api/session/{gs.id}/me",
            params={"player_id": gs.players[0].id, "player_token": "bad-token"},
        )
        assert res.status_code == 403

    def test_get_session_personalized_session_not_found(self):
        token = issue_token("fake", "fake")
        self._mock_find_one(returns=None)

        res = self.client.get(
            "/api/session/fake/me",
            params={"player_id": "fake", "player_token": token},
        )
        assert res.status_code == 404

    def test_get_session_personalized_player_not_found(self):
        gs = _make_started_game(5)
        token = issue_token(gs.id, "nonexistent-player")

        self._mock_find_one(returns=gs.model_dump())

        res = self.client.get(
            f"/api/session/{gs.id}/me",
            params={"player_id": "nonexistent-player", "player_token": token},
        )
        assert res.status_code == 404

    # ── WebSocket endpoint ────────────────────────────────────────────

    def test_websocket_connect_and_receive(self):
        gs = _make_started_game(5)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()
        self._mock_update_one()

        with self.client.websocket_connect(
            f"/api/ws/{gs.id}?player_id={gs.players[0].id}"
        ) as ws:
            # Should receive initial broadcast
            data = ws.receive_json()
            assert data["type"] == "game_state"

    def test_websocket_connect_without_player_id(self):
        gs = _make_started_game(5)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()
        self._mock_update_one()

        with self.client.websocket_connect(f"/api/ws/{gs.id}") as ws:
            data = ws.receive_json()
            assert data["type"] == "game_state"

    def test_websocket_pong_ignored(self):
        gs = _make_started_game(5)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()
        self._mock_update_one()

        with self.client.websocket_connect(
            f"/api/ws/{gs.id}?player_id={gs.players[0].id}"
        ) as ws:
            # Receive initial broadcast
            ws.receive_json()
            # Send pong (should be silently ignored)
            ws.send_json({"type": "pong"})

    def test_websocket_identify_with_valid_token(self):
        gs = _make_started_game(5)
        player = gs.players[0]
        token = issue_token(gs.id, player.id)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()
        self._mock_update_one()

        with self.client.websocket_connect(f"/api/ws/{gs.id}") as ws:
            # Receive initial broadcast
            ws.receive_json()
            # Identify
            ws.send_json({
                "type": "identify",
                "player_id": player.id,
                "player_token": token,
            })

    def test_websocket_identify_with_invalid_token(self):
        gs = _make_started_game(5)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()
        self._mock_update_one()

        with pytest.raises(Exception):
            with self.client.websocket_connect(f"/api/ws/{gs.id}") as ws:
                ws.receive_json()
                ws.send_json({
                    "type": "identify",
                    "player_id": gs.players[0].id,
                    "player_token": "bad-token",
                })
                # Should receive error and close
                data = ws.receive_json()
                if data.get("type") == "error":
                    # Try to receive again - should fail since WS is closed
                    ws.receive_json()

    # ── Rate limiter ──────────────────────────────────────────────────

    def test_rate_limiter_allows_normal_traffic(self):
        self.db_mock.command = AsyncMock(return_value={"ok": 1})
        # Make a few requests - should be fine
        for _ in range(5):
            res = self.client.get("/health")
            assert res.status_code == 200


# ===========================================================================
# 5. Additional integration-like tests for complex flows
# ===========================================================================

class TestGameFlows:
    """Test multi-step game flows through the API."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
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

    def _mock_replace_one(self):
        self.db_mock.game_sessions.replace_one = AsyncMock()

    def test_assassination_sets_evil_win_on_merlin_kill(self):
        gs = _make_started_game(5, phase=GamePhase.ASSASSINATION)
        assassin = gs.players[4]  # ASSASSIN
        merlin = gs.players[0]  # MERLIN
        token = issue_token(gs.id, assassin.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        self.client.post("/api/assassinate", json={
            "session_id": gs.id,
            "player_id": assassin.id,
            "player_token": token,
            "target_player_id": merlin.id,
        })

        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        assert updated["game_result"] == "evil"
        assert updated["phase"] == GamePhase.GAME_END

    def test_assassination_sets_good_win_on_wrong_target(self):
        gs = _make_started_game(5, phase=GamePhase.ASSASSINATION)
        assassin = gs.players[4]  # ASSASSIN
        percival = gs.players[1]  # PERCIVAL
        token = issue_token(gs.id, assassin.id)

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        self.client.post("/api/assassinate", json={
            "session_id": gs.id,
            "player_id": assassin.id,
            "player_token": token,
            "target_player_id": percival.id,
        })

        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        assert updated["game_result"] == "good"
        assert updated["phase"] == GamePhase.GAME_END

    def test_select_team_transitions_to_voting(self):
        gs = _make_started_game(5)
        leader = gs.players[0]
        token = issue_token(gs.id, leader.id)
        team = [gs.players[0].id, gs.players[1].id]

        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        self.client.post("/api/select-team", json={
            "session_id": gs.id,
            "player_id": leader.id,
            "player_token": token,
            "team_members": team,
        })

        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        assert updated["phase"] == GamePhase.MISSION_VOTING

    def test_lady_of_lake_transfers_to_target(self):
        gs = _make_started_game(7, phase=GamePhase.LADY_OF_THE_LAKE)
        extra_roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
                       Role.MORGANA, Role.ASSASSIN, Role.OBERON]
        for i, r in enumerate(extra_roles):
            gs.players[i].role = r

        holder = gs.players[0]
        holder.lady_of_the_lake = True
        gs.lady_of_the_lake_holder = holder.id
        target = gs.players[2]

        token = issue_token(gs.id, holder.id)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        self.client.post("/api/lady-of-lake", json={
            "session_id": gs.id,
            "player_id": holder.id,
            "player_token": token,
            "target_player_id": target.id,
        })

        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        # Holder should lose lady
        holder_updated = next(p for p in updated["players"] if p["id"] == holder.id)
        assert holder_updated["lady_of_the_lake"] is False
        # Target should gain lady
        target_updated = next(p for p in updated["players"] if p["id"] == target.id)
        assert target_updated["lady_of_the_lake"] is True
        # Phase should transition
        assert updated["phase"] == GamePhase.MISSION_TEAM_SELECTION

    def test_restart_sets_new_leader(self):
        gs = _make_started_game(5, phase=GamePhase.GAME_END)
        self._mock_find_one(returns=gs.model_dump())
        self._mock_replace_one()

        self.client.post("/api/restart-game", json={"session_id": gs.id})

        call_args = self.db_mock.game_sessions.replace_one.call_args
        updated = call_args[0][1]
        # One player should be leader
        leaders = [p for p in updated["players"] if p["is_leader"]]
        assert len(leaders) == 1
