from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum
from datetime import datetime
import secrets
import uuid

_CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(_CODE_CHARS) for _ in range(length))


class GamePhase(str, Enum):
    LOBBY = "lobby"
    ROLE_ASSIGNMENT = "role_assignment"
    MISSION_TEAM_SELECTION = "mission_team_selection"
    MISSION_VOTING = "mission_voting"
    VOTE_REVEAL = "vote_reveal"
    MISSION_EXECUTION = "mission_execution"
    MISSION_REVEAL = "mission_reveal"
    LADY_OF_THE_LAKE = "lady_of_the_lake"
    ASSASSINATION = "assassination"
    GAME_END = "game_end"


class Role(str, Enum):
    MERLIN = "merlin"
    PERCIVAL = "percival"
    LOYAL_SERVANT = "loyal_servant"
    MORGANA = "morgana"
    MORDRED = "mordred"
    ASSASSIN = "assassin"
    OBERON = "oberon"
    MINION = "minion"


class MissionResult(str, Enum):
    SUCCESS = "success"
    FAIL = "fail"
    PENDING = "pending"


class Player(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    role: Optional[Role] = None
    is_leader: bool = False
    is_connected: bool = True
    lady_of_the_lake: bool = False
    is_bot: bool = False
    is_spectator: bool = False


class Mission(BaseModel):
    number: int
    team_size: int
    fails_required: int = 1
    team_members: List[str] = []
    votes: Dict[str, bool] = {}
    mission_votes: Dict[str, bool] = {}
    result: MissionResult = MissionResult.PENDING
    team_approved: bool = False


class GameSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    code: Optional[str] = None
    players: List[Player] = []
    phase: GamePhase = GamePhase.LOBBY
    current_mission: int = 0
    missions: List[Mission] = []
    current_leader: int = 0
    vote_track: int = 0
    lady_of_the_lake_holder: Optional[str] = None
    lady_of_the_lake_enabled: bool = False
    lady_of_the_lake_results: Dict[str, Dict[str, str]] = {}
    mordred_enabled: bool = False
    oberon_enabled: bool = False
    good_total_wins: int = 0
    evil_total_wins: int = 0
    game_result: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    good_wins: int = 0
    evil_wins: int = 0
    vote_history: List[Dict] = []
    game_log: List[str] = []


# ── Request models ──────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    name: str
    player_name: str


class JoinSessionRequest(BaseModel):
    session_id: str
    player_name: str
    as_spectator: bool = False


class StartGameRequest(BaseModel):
    session_id: str


class TeamSelectionRequest(BaseModel):
    session_id: str
    player_id: str
    player_token: str
    team_members: List[str]


class VoteRequest(BaseModel):
    session_id: str
    player_id: str
    player_token: str
    vote: bool


class MissionVoteRequest(BaseModel):
    session_id: str
    player_id: str
    player_token: str
    vote: bool


class LadyOfLakeRequest(BaseModel):
    session_id: str
    player_id: str
    player_token: str
    target_player_id: str


class AssassinationRequest(BaseModel):
    session_id: str
    player_id: str
    player_token: str
    target_player_id: str


class ToggleMordredRequest(BaseModel):
    session_id: str
    enabled: bool


class ToggleOberonRequest(BaseModel):
    session_id: str
    enabled: bool


class ToggleLadyOfLakeRequest(BaseModel):
    session_id: str
    enabled: bool


class LeaveSessionRequest(BaseModel):
    session_id: str
    player_id: str
    player_token: str


class RestartGameRequest(BaseModel):
    session_id: str


# ── Game configuration tables ───────────────────────────────────────────

ROLE_CONFIGS = {
    5: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN],
    6: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN],
    7: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN, Role.OBERON],
    8: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN, Role.MINION],
    9: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN, Role.MORDRED],
    10: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.OBERON],
}

MISSION_CONFIGS = {
    5: [(2, 1), (3, 1), (2, 1), (3, 1), (3, 1)],
    6: [(2, 1), (3, 1), (4, 1), (3, 1), (4, 1)],
    7: [(2, 1), (3, 1), (3, 1), (4, 2), (4, 1)],
    8: [(3, 1), (4, 1), (4, 1), (5, 2), (5, 1)],
    9: [(3, 1), (4, 1), (4, 1), (5, 2), (5, 1)],
    10: [(3, 1), (4, 1), (4, 1), (5, 2), (5, 1)],
}
