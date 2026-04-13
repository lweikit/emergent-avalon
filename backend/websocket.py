import json
import logging
from typing import Dict

from fastapi import WebSocket

from models import GameSession, GamePhase, MissionResult
from game_logic import get_role_info

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str, player_id: str = None):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = {}
        import uuid
        connection_id = player_id or str(uuid.uuid4())
        self.active_connections[session_id][connection_id] = websocket

    def disconnect(self, websocket: WebSocket, session_id: str, player_id: str = None):
        if session_id in self.active_connections:
            to_remove = None
            for pid, ws in self.active_connections[session_id].items():
                if ws == websocket:
                    to_remove = pid
                    break
            if to_remove:
                del self.active_connections[session_id][to_remove]
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_to_player(self, message: str, session_id: str, player_id: str):
        if session_id in self.active_connections and player_id in self.active_connections[session_id]:
            try:
                await self.active_connections[session_id][player_id].send_text(message)
            except Exception:
                # Remove dead connection
                self.active_connections[session_id].pop(player_id, None)

    async def broadcast_to_session(self, message: str, session_id: str):
        if session_id not in self.active_connections:
            return
        dead = []
        for player_id, connection in self.active_connections[session_id].items():
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(player_id)
        for pid in dead:
            self.active_connections[session_id].pop(pid, None)


async def broadcast_game_state(session_id: str, db, manager: ConnectionManager):
    """Broadcast personalized game state to all players in a session."""
    try:
        session = await db.game_sessions.find_one({"id": session_id})
        if not session:
            return

        game_session = GameSession(**session)

        for player in game_session.players:
            try:
                player_state = _build_player_state(game_session, player)
                await manager.send_to_player(json.dumps(player_state), session_id, player.id)
            except Exception as e:
                logger.warning("Error sending state to player %s: %s", player.name, e)

        # Send generic state to unidentified connections
        if session_id in manager.active_connections:
            player_ids = {p.id for p in game_session.players}
            general = _build_general_state(game_session)
            for cid, websocket in list(manager.active_connections[session_id].items()):
                if cid not in player_ids:
                    try:
                        await websocket.send_text(json.dumps(general))
                    except Exception:
                        manager.active_connections[session_id].pop(cid, None)

    except Exception as e:
        logger.error("Error in broadcast_game_state for session %s: %s", session_id, e)


def _build_player_state(gs: GameSession, player) -> dict:
    """Build a personalized state payload for one player."""
    active_count = len([p for p in gs.players if not p.is_spectator])
    state = {
        "type": "game_state",
        "session": {
            "id": gs.id,
            "name": gs.name,
            "phase": gs.phase,
            "current_mission": gs.current_mission,
            "current_leader": gs.current_leader,
            "vote_track": gs.vote_track,
            "good_wins": gs.good_wins,
            "evil_wins": gs.evil_wins,
            "game_result": gs.game_result,
            "lady_of_the_lake_enabled": gs.lady_of_the_lake_enabled,
            "lady_of_the_lake_previous_holders": list(gs.lady_of_the_lake_results.keys()),
            "mordred_enabled": gs.mordred_enabled,
            "oberon_enabled": gs.oberon_enabled,
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "is_leader": p.is_leader,
                    "is_connected": p.is_connected,
                    "lady_of_the_lake": p.lady_of_the_lake,
                    "is_bot": p.is_bot,
                    "is_spectator": p.is_spectator,
                    "role": p.role if (gs.phase == GamePhase.GAME_END or p.id == player.id) else None,
                }
                for p in gs.players
            ],
            "missions": [
                {
                    "number": m.number,
                    "team_size": m.team_size,
                    "fails_required": m.fails_required,
                    "team_members": m.team_members,
                    "result": m.result,
                    "team_approved": m.team_approved,
                    "votes": m.votes if len(m.votes) == active_count or gs.phase in (GamePhase.VOTE_REVEAL, GamePhase.MISSION_EXECUTION) else {},
                    "mission_votes": {} if m.result == MissionResult.PENDING else {
                        "total_votes": len(m.mission_votes),
                        "fail_count": sum(1 for v in m.mission_votes.values() if not v),
                        "success_count": sum(1 for v in m.mission_votes.values() if v),
                    },
                }
                for m in gs.missions
            ],
            "vote_history": gs.vote_history,
            "game_log": gs.game_log,
        },
    }

    if gs.phase != GamePhase.LOBBY and player.role:
        state["role_info"] = get_role_info(player.role, gs.players)

    if player.id in gs.lady_of_the_lake_results:
        knowledge = []
        for target_id, allegiance in gs.lady_of_the_lake_results[player.id].items():
            target = next((p for p in gs.players if p.id == target_id), None)
            if target:
                knowledge.append({"target_id": target_id, "target_name": target.name, "allegiance": allegiance})
        state["lady_of_lake_knowledge"] = knowledge

    if gs.current_mission < len(gs.missions):
        cm = gs.missions[gs.current_mission]
        state["current_mission_details"] = {
            "number": cm.number,
            "team_size": cm.team_size,
            "fails_required": cm.fails_required,
            "team_members": cm.team_members,
            "votes": cm.votes,
            "mission_votes": (
                {"player_voted": player.id in cm.mission_votes, "total_votes": len(cm.mission_votes)}
                if cm.result == MissionResult.PENDING
                else {
                    "total_votes": len(cm.mission_votes),
                    "fail_count": sum(1 for v in cm.mission_votes.values() if not v),
                    "success_count": sum(1 for v in cm.mission_votes.values() if v),
                    "player_voted": player.id in cm.mission_votes,
                }
            ),
            "result": cm.result,
            "team_approved": cm.team_approved,
        }

    return state


def _build_general_state(gs: GameSession) -> dict:
    """Build a non-personalized state for unidentified connections."""
    return {
        "type": "game_state",
        "session": {
            "id": gs.id,
            "name": gs.name,
            "phase": gs.phase,
            "current_mission": gs.current_mission,
            "current_leader": gs.current_leader,
            "vote_track": gs.vote_track,
            "good_wins": gs.good_wins,
            "evil_wins": gs.evil_wins,
            "game_result": gs.game_result,
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "is_leader": p.is_leader,
                    "is_connected": p.is_connected,
                    "lady_of_the_lake": p.lady_of_the_lake,
                    "is_bot": p.is_bot,
                    "is_spectator": p.is_spectator,
                    "role": None,
                }
                for p in gs.players
            ],
            "missions": [
                {
                    "number": m.number,
                    "team_size": m.team_size,
                    "fails_required": m.fails_required,
                    "team_members": m.team_members,
                    "result": m.result,
                    "team_approved": m.team_approved,
                }
                for m in gs.missions
            ],
            "lady_of_the_lake_holder": gs.lady_of_the_lake_holder,
        },
    }
