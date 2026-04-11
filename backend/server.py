from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import hashlib
import hmac
import secrets
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import uuid
from datetime import datetime, timedelta
import json
import asyncio
from enum import Enum
import random
import threading
import time
from contextlib import asynccontextmanager

# Add session locks to prevent race conditions
session_locks = {}
session_lock_manager = threading.Lock()

@asynccontextmanager
async def session_lock(session_id: str):
    """Context manager for session-level locking"""
    with session_lock_manager:
        if session_id not in session_locks:
            session_locks[session_id] = asyncio.Lock()
        lock = session_locks[session_id]
    
    async with lock:
        yield

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# ── Player token authentication ─────────────────────────────────────────
# Maps (session_id, player_id) → token. Tokens are issued on create/join
# and required on all mutation endpoints to prevent player_id spoofing.
_player_tokens: Dict[str, str] = {}  # key = f"{session_id}:{player_id}"

def _issue_token(session_id: str, player_id: str) -> str:
    """Issue a random token for a player in a session."""
    token = secrets.token_urlsafe(32)
    _player_tokens[f"{session_id}:{player_id}"] = hashlib.sha256(token.encode()).hexdigest()
    return token

def _verify_token(session_id: str, player_id: str, token: str) -> bool:
    """Verify a player's token."""
    key = f"{session_id}:{player_id}"
    expected = _player_tokens.get(key)
    if not expected:
        return False
    return hmac.compare_digest(expected, hashlib.sha256(token.encode()).hexdigest())

def _require_auth(session_id: str, player_id: str, player_token: str):
    """Raise 403 if the token doesn't match the player."""
    if not player_token or not _verify_token(session_id, player_id, player_token):
        raise HTTPException(status_code=403, detail="Invalid player token")

# Create the main app without a prefix
app = FastAPI(title="Avalon Game API", version="1.0.0")

# Add CORS middleware first
# CORS origins: set CORS_ORIGINS env var to comma-separated list, or use defaults
_cors_origins = os.environ.get("CORS_ORIGINS", "").split(",") if os.environ.get("CORS_ORIGINS") else [
    "http://localhost:3000",
    "https://avalon.weikit.me",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        await db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Avalon Game API", "status": "running"}

@api_router.get("/")
async def api_root():
    """API root endpoint"""
    return {"message": "Avalon Game API is running", "status": "healthy"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}  # session_id -> player_id -> websocket
    
    async def connect(self, websocket: WebSocket, session_id: str, player_id: str = None):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = {}
        
        # Use a temporary ID if player_id is not provided
        connection_id = player_id or str(uuid.uuid4())
        self.active_connections[session_id][connection_id] = websocket
        print(f"WebSocket connected for session {session_id}, player {connection_id}")
    
    def disconnect(self, websocket: WebSocket, session_id: str, player_id: str = None):
        if session_id in self.active_connections:
            # Find and remove the websocket
            to_remove = None
            for pid, ws in self.active_connections[session_id].items():
                if ws == websocket:
                    to_remove = pid
                    break
            
            if to_remove:
                del self.active_connections[session_id][to_remove]
                print(f"WebSocket disconnected for session {session_id}, player {to_remove}")
                
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def send_to_player(self, message: str, session_id: str, player_id: str):
        if session_id in self.active_connections and player_id in self.active_connections[session_id]:
            try:
                await self.active_connections[session_id][player_id].send_text(message)
            except:
                pass
    
    async def broadcast_to_session(self, message: str, session_id: str):
        if session_id in self.active_connections:
            for player_id, connection in self.active_connections[session_id].items():
                try:
                    await connection.send_text(message)
                except:
                    pass

manager = ConnectionManager()

# Session cleanup background task
async def cleanup_old_sessions():
    """Clean up sessions older than 7 days"""
    while True:
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            # Find and delete old sessions
            result = await db.game_sessions.delete_many({
                "created_at": {"$lt": cutoff_date}
            })
            
            if result.deleted_count > 0:
                print(f"Cleaned up {result.deleted_count} old sessions")
            
        except Exception as e:
            print(f"Error during session cleanup: {e}")
        
        # Run cleanup every 6 hours
        await asyncio.sleep(6 * 3600)

# Start cleanup task
cleanup_task = None

def start_cleanup_task():
    global cleanup_task
    if cleanup_task is None:
        cleanup_task = asyncio.create_task(cleanup_old_sessions())

# Start cleanup on app startup
@app.on_event("startup")
async def startup_event():
    start_cleanup_task()

# Enums and Models
class GamePhase(str, Enum):
    LOBBY = "lobby"
    ROLE_ASSIGNMENT = "role_assignment"
    MISSION_TEAM_SELECTION = "mission_team_selection"
    MISSION_VOTING = "mission_voting"
    MISSION_EXECUTION = "mission_execution"
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
    players: List[Player] = []
    phase: GamePhase = GamePhase.LOBBY
    current_mission: int = 0
    missions: List[Mission] = []
    current_leader: int = 0
    vote_track: int = 0
    lady_of_the_lake_holder: Optional[str] = None
    lady_of_the_lake_enabled: bool = True
    lady_of_the_lake_results: Dict[str, Dict[str, str]] = {}  # user_id -> {target_id: allegiance}
    # Dynamic role balancing
    mordred_enabled: bool = True
    oberon_enabled: bool = True
    good_total_wins: int = 0  # Track across all games for balancing
    evil_total_wins: int = 0  # Track across all games for balancing
    game_result: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    good_wins: int = 0
    evil_wins: int = 0
    vote_history: List[Dict] = []
    game_log: List[str] = []

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

class RestartGameRequest(BaseModel):
    session_id: str

# Role configurations for different player counts
ROLE_CONFIGS = {
    5: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN],
    6: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN],
    7: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN, Role.OBERON],
    8: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN, Role.MINION],
    9: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN, Role.MORDRED],
    10: [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.OBERON]
}

# Mission configurations
MISSION_CONFIGS = {
    5: [(2, 1), (3, 1), (2, 1), (3, 1), (3, 1)],
    6: [(2, 1), (3, 1), (4, 1), (3, 1), (4, 1)],
    7: [(2, 1), (3, 1), (3, 1), (4, 2), (4, 1)],
    8: [(3, 1), (4, 1), (4, 1), (5, 2), (5, 1)],
    9: [(3, 1), (4, 1), (4, 1), (5, 2), (5, 1)],
    10: [(3, 1), (4, 1), (4, 1), (5, 2), (5, 1)]
}

def assign_roles(players: List[Player], game_session: GameSession = None) -> List[Player]:
    """Assign roles to players based on player count and dynamic balancing"""
    player_count = len(players)
    if player_count < 5:
        raise ValueError(f"Invalid player count: {player_count}")
    
    # Use static role configuration for reliability
    if player_count not in ROLE_CONFIGS:
        # Use closest configuration
        closest_config = min(ROLE_CONFIGS.keys(), key=lambda x: abs(x - player_count))
        base_roles = ROLE_CONFIGS[closest_config].copy()
        # Adjust for exact player count
        while len(base_roles) < player_count:
            base_roles.append(Role.LOYAL_SERVANT)
        while len(base_roles) > player_count:
            # Remove loyal servants first
            if Role.LOYAL_SERVANT in base_roles:
                base_roles.remove(Role.LOYAL_SERVANT)
            else:
                base_roles.pop()
        roles = base_roles
    else:
        roles = ROLE_CONFIGS[player_count].copy()
    
    # Optional dynamic balancing for 7+ players (if game_session provided)
    if player_count >= 7 and game_session:
        # Simple balancing: swap some roles based on win history
        total_games = game_session.good_total_wins + game_session.evil_total_wins
        if total_games >= 3:  # Only after several games
            good_win_rate = game_session.good_total_wins / total_games
            
            # If good wins too much (>70%), consider adding Mordred
            if good_win_rate > 0.7 and game_session.mordred_enabled:
                if Role.MINION in roles and Role.MORDRED not in roles:
                    roles[roles.index(Role.MINION)] = Role.MORDRED
            
            # If evil wins too much (>70%), consider adding Oberon  
            elif good_win_rate < 0.3 and game_session.oberon_enabled:
                if Role.MINION in roles and Role.OBERON not in roles:
                    roles[roles.index(Role.MINION)] = Role.OBERON
    
    # Ensure we have exactly the right number of roles
    roles = roles[:player_count]
    
    random.shuffle(roles)
    
    for i, player in enumerate(players):
        player.role = roles[i]
    
    return players

# Bot AI Functions
async def bot_select_team(game_session: GameSession, bot_player: Player) -> List[str]:
    """Bot logic for selecting team members"""
    current_mission = game_session.missions[game_session.current_mission]
    team_size = current_mission.team_size
    
    # Simple bot logic: include self and random others
    available_players = [p.id for p in game_session.players]
    team = [bot_player.id]
    
    # Add random other players
    other_players = [p.id for p in game_session.players if p.id != bot_player.id]
    random.shuffle(other_players)
    team.extend(other_players[:team_size - 1])
    
    return team

async def bot_vote_team(game_session: GameSession, bot_player: Player) -> bool:
    """Bot logic for voting on team proposals"""
    current_mission = game_session.missions[game_session.current_mission]
    
    # Evil bots are more likely to reject teams they're not on
    if bot_player.role in [Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.MINION, Role.OBERON]:
        if bot_player.id not in current_mission.team_members:
            return random.choice([True, False, False])  # 33% approve
        else:
            return random.choice([True, True, False])  # 66% approve
    else:
        # Good bots vote more randomly
        return random.choice([True, True, False])  # 66% approve

async def bot_vote_mission(game_session: GameSession, bot_player: Player) -> bool:
    """Bot logic for voting on mission success/failure"""
    # Evil bots sometimes fail missions
    if bot_player.role in [Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.MINION, Role.OBERON]:
        # Evil bots fail missions 40% of the time
        return random.choice([True, True, True, False, False])
    else:
        # Good bots always vote for success
        return True

async def process_bot_actions(session_id: str):
    """Process pending bot actions for the current game phase"""
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        return
    
    game_session = GameSession(**session)
    
    # Team selection phase - bot leader selects team
    if game_session.phase == GamePhase.MISSION_TEAM_SELECTION:
        current_leader = game_session.players[game_session.current_leader]
        if current_leader.is_bot and not current_leader.is_spectator:
            await asyncio.sleep(2)  # Simulate thinking time
            team = await bot_select_team(game_session, current_leader)
            
            # Update mission with bot's team selection
            current_mission = game_session.missions[game_session.current_mission]
            current_mission.team_members = team
            current_mission.votes = {}
            game_session.phase = GamePhase.MISSION_VOTING
            
            game_session.game_log.append(f"{current_leader.name} (bot) selected team: {[p.name for p in game_session.players if p.id in team]}")
            
            await db.game_sessions.replace_one({"id": session_id}, game_session.dict())
            await broadcast_game_state(session_id)
    
    # Team voting phase - bots vote on team (one at a time, re-reading DB each time)
    elif game_session.phase == GamePhase.MISSION_VOTING:
        for player in game_session.players:
            if player.is_bot and not player.is_spectator:
                await asyncio.sleep(1)  # Simulate thinking time
                # Re-read from DB each iteration to avoid overwriting human votes
                async with session_lock(session_id):
                    fresh_session = await db.game_sessions.find_one({"id": session_id})
                    if not fresh_session:
                        return
                    fresh_game = GameSession(**fresh_session)
                    if fresh_game.phase != GamePhase.MISSION_VOTING:
                        return  # Phase changed, stop
                    fresh_mission = fresh_game.missions[fresh_game.current_mission]
                    if player.id in fresh_mission.votes:
                        continue  # Already voted
                    vote = await bot_vote_team(fresh_game, player)
                    fresh_mission.votes[player.id] = vote
                    await db.game_sessions.replace_one({"id": session_id}, fresh_game.dict())

        # Re-read and check if all players have voted
        async with session_lock(session_id):
            fresh_session = await db.game_sessions.find_one({"id": session_id})
            if fresh_session:
                fresh_game = GameSession(**fresh_session)
                if fresh_game.phase == GamePhase.MISSION_VOTING:
                    fresh_mission = fresh_game.missions[fresh_game.current_mission]
                    active_players = [p for p in fresh_game.players if not p.is_spectator]
                    if len(fresh_mission.votes) == len(active_players):
                        await process_team_vote_result(session_id)

    # Mission execution phase - bots vote on mission (one at a time, re-reading DB each time)
    elif game_session.phase == GamePhase.MISSION_EXECUTION:
        for player in game_session.players:
            if player.is_bot and not player.is_spectator and player.id in game_session.missions[game_session.current_mission].team_members:
                await asyncio.sleep(1)  # Simulate thinking time
                # Re-read from DB each iteration to avoid overwriting human votes
                async with session_lock(session_id):
                    fresh_session = await db.game_sessions.find_one({"id": session_id})
                    if not fresh_session:
                        return
                    fresh_game = GameSession(**fresh_session)
                    if fresh_game.phase != GamePhase.MISSION_EXECUTION:
                        return  # Phase changed, stop
                    fresh_mission = fresh_game.missions[fresh_game.current_mission]
                    if player.id in fresh_mission.mission_votes:
                        continue  # Already voted
                    vote = await bot_vote_mission(fresh_game, player)
                    fresh_mission.mission_votes[player.id] = vote
                    await db.game_sessions.replace_one({"id": session_id}, fresh_game.dict())

        # Re-read and check if all team members have voted
        async with session_lock(session_id):
            fresh_session = await db.game_sessions.find_one({"id": session_id})
            if fresh_session:
                fresh_game = GameSession(**fresh_session)
                if fresh_game.phase == GamePhase.MISSION_EXECUTION:
                    fresh_mission = fresh_game.missions[fresh_game.current_mission]
                    if len(fresh_mission.mission_votes) == len(fresh_mission.team_members):
                        await process_mission_vote_result(session_id)
    
    # Assassination phase - bot assassin chooses target
    elif game_session.phase == GamePhase.ASSASSINATION:
        assassin = next((p for p in game_session.players if p.role == Role.ASSASSIN), None)
        if assassin and assassin.is_bot:
            await asyncio.sleep(3)  # Simulate thinking time
            
            # Bot assassin logic: target a random good player (excluding known evil)
            good_players = [p for p in game_session.players if p.role in [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT]]
            if good_players:
                target = random.choice(good_players)
                
                # Execute assassination
                if target.role == Role.MERLIN:
                    game_session.game_result = "evil"
                    game_session.evil_total_wins += 1  # Track for balancing
                    game_session.game_log.append(f"Assassination successful! {assassin.name} (bot) killed Merlin ({target.name}). Evil wins!")
                else:
                    game_session.game_result = "good"
                    game_session.good_total_wins += 1  # Track for balancing
                    game_session.game_log.append(f"Assassination failed! {assassin.name} (bot) killed {target.name} ({target.role}). Good wins!")
                
                game_session.phase = GamePhase.GAME_END
                
                await db.game_sessions.replace_one({"id": session_id}, game_session.dict())
                await broadcast_game_state(session_id)

async def process_team_vote_result(session_id: str):
    """Process the result of team voting"""
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        return
    
    game_session = GameSession(**session)
    current_mission = game_session.missions[game_session.current_mission]
    
    # Count votes from active players only
    active_players = [p for p in game_session.players if not p.is_spectator]
    approve_count = sum(1 for p in active_players if current_mission.votes.get(p.id, False))
    total_votes = len(active_players)
    
    # Record vote history
    vote_record = {
        "type": "team_vote",
        "mission": current_mission.number,
        "votes": {p.name: current_mission.votes.get(p.id, None) for p in active_players},
        "result": "approved" if approve_count > total_votes // 2 else "rejected",
        "approve_count": approve_count,
        "total_votes": total_votes
    }
    game_session.vote_history.append(vote_record)
    
    if approve_count > total_votes // 2:
        # Team approved
        current_mission.team_approved = True
        current_mission.mission_votes = {}
        game_session.phase = GamePhase.MISSION_EXECUTION
        game_session.game_log.append(f"Mission {current_mission.number} team approved ({approve_count}/{total_votes} votes)")
    else:
        # Team rejected
        game_session.vote_track += 1
        game_session.game_log.append(f"Mission {current_mission.number} team rejected ({approve_count}/{total_votes} votes) - Vote track: {game_session.vote_track}/5")
        
        if game_session.vote_track >= 5:
            # Evil wins on 5th rejection
            game_session.phase = GamePhase.GAME_END
            game_session.game_result = "evil"
            game_session.evil_total_wins += 1  # Track for balancing
            game_session.game_log.append("Evil wins! 5 teams rejected in a row.")
        else:
            # Move to next leader (only among active players)
            active_indices = [i for i, p in enumerate(game_session.players) if not p.is_spectator]
            current_leader_idx = active_indices.index(game_session.current_leader)
            next_leader_idx = (current_leader_idx + 1) % len(active_indices)
            game_session.current_leader = active_indices[next_leader_idx]
            
            for player in game_session.players:
                player.is_leader = False
            game_session.players[game_session.current_leader].is_leader = True
            game_session.phase = GamePhase.MISSION_TEAM_SELECTION
            current_mission.team_members = []
            current_mission.votes = {}
    
    await db.game_sessions.replace_one({"id": session_id}, game_session.dict())
    await broadcast_game_state(session_id)
    
    # Continue bot processing if needed
    asyncio.create_task(process_bot_actions(session_id))

async def process_mission_vote_result(session_id: str):
    """Process the result of mission voting"""
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        return
    
    game_session = GameSession(**session)
    current_mission = game_session.missions[game_session.current_mission]
    
    fail_count = sum(1 for vote in current_mission.mission_votes.values() if not vote)
    success_count = len(current_mission.mission_votes) - fail_count
    
    if fail_count >= current_mission.fails_required:
        current_mission.result = MissionResult.FAIL
        game_session.evil_wins += 1
        game_session.evil_total_wins += 1  # Track for balancing
        game_session.game_log.append(f"Mission {current_mission.number} failed! ({fail_count} fail, {success_count} success votes)")
    else:
        current_mission.result = MissionResult.SUCCESS
        game_session.good_wins += 1
        game_session.game_log.append(f"Mission {current_mission.number} succeeded! ({fail_count} fail, {success_count} success votes)")
    
    # Check win conditions
    if game_session.good_wins >= 3:
        # Good wins, move to assassination phase
        game_session.phase = GamePhase.ASSASSINATION
        game_session.game_log.append("Good has completed 3 missions! Assassination phase begins.")
    elif game_session.evil_wins >= 3:
        # Evil wins
        game_session.phase = GamePhase.GAME_END
        game_session.game_result = "evil"
        game_session.game_log.append("Evil wins! 3 missions failed.")
    else:
        # Continue to next mission
        game_session.current_mission += 1
        game_session.vote_track = 0
        
        # Check for Lady of the Lake phase
        if (game_session.lady_of_the_lake_enabled and 
            game_session.lady_of_the_lake_holder and 
            game_session.current_mission in [2, 3] and 
            len([p for p in game_session.players if not p.is_spectator]) >= 7):
            game_session.phase = GamePhase.LADY_OF_THE_LAKE
            game_session.game_log.append("Lady of the Lake phase begins!")
        else:
            game_session.phase = GamePhase.MISSION_TEAM_SELECTION
            
        # Move to next leader (only among active players)
        active_indices = [i for i, p in enumerate(game_session.players) if not p.is_spectator]
        current_leader_idx = active_indices.index(game_session.current_leader)
        next_leader_idx = (current_leader_idx + 1) % len(active_indices)
        game_session.current_leader = active_indices[next_leader_idx]
        
        for player in game_session.players:
            player.is_leader = False
        game_session.players[game_session.current_leader].is_leader = True
    
    # Save state and broadcast
    await db.game_sessions.replace_one({"id": session_id}, game_session.dict())
    await broadcast_game_state(session_id)
    
    # Continue bot processing if needed
    asyncio.create_task(process_bot_actions(session_id))

def initialize_missions(player_count: int) -> List[Mission]:
    """Initialize missions based on player count"""
    if player_count not in MISSION_CONFIGS:
        raise ValueError(f"Invalid player count: {player_count}")
    
    missions = []
    for i, (team_size, fails_required) in enumerate(MISSION_CONFIGS[player_count]):
        mission = Mission(
            number=i + 1,
            team_size=team_size,
            fails_required=fails_required
        )
        missions.append(mission)
    
    return missions

def get_role_info(player_role: Role, all_players: List[Player]) -> Dict[str, Any]:
    """Get role-specific information for a player - STABLE VERSION"""
    info = {
        "role": player_role,
        "team": "good" if player_role in [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT] else "evil",
        "description": "",
        "sees": []
    }
    
    if player_role == Role.MERLIN:
        info["description"] = "You can see all evil players except Mordred and Oberon"
        # Merlin sees Morgana, Assassin, and Minions, but NOT Mordred or Oberon
        evil_players = [p for p in all_players if p.role in [Role.MORGANA, Role.ASSASSIN, Role.MINION] and not p.is_spectator]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_players]
    
    elif player_role == Role.PERCIVAL:
        info["description"] = "You can see Merlin and Morgana, but don't know which is which"
        merlin_morgana = [p for p in all_players if p.role in [Role.MERLIN, Role.MORGANA] and not p.is_spectator]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "merlin_or_morgana"} for p in merlin_morgana]
    
    elif player_role == Role.MORGANA:
        info["description"] = "You are evil and can see other evil players (except Oberon)"
        # Morgana sees Assassin, Mordred, Minion but NOT Oberon
        evil_visible = [p for p in all_players if p.role in [Role.ASSASSIN, Role.MORDRED, Role.MINION] and not p.is_spectator]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_visible]

    elif player_role == Role.ASSASSIN:
        info["description"] = "You are evil and can see other evil players (except Oberon). You can assassinate Merlin if good wins"
        # Assassin sees Morgana, Mordred, Minion but NOT Oberon
        evil_visible = [p for p in all_players if p.role in [Role.MORGANA, Role.MORDRED, Role.MINION] and not p.is_spectator]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_visible]

    elif player_role == Role.MORDRED:
        info["description"] = "You are evil and can see other evil players (except Oberon). You are hidden from Merlin"
        # Mordred sees Morgana, Assassin, Minion but NOT Oberon
        evil_visible = [p for p in all_players if p.role in [Role.MORGANA, Role.ASSASSIN, Role.MINION] and not p.is_spectator]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_visible]

    elif player_role == Role.MINION:
        info["description"] = "You are evil and can see other evil players (except Oberon)"
        # Minion sees Morgana, Assassin, Mordred but NOT Oberon
        evil_visible = [p for p in all_players if p.role in [Role.MORGANA, Role.ASSASSIN, Role.MORDRED] and not p.is_spectator]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_visible]
    
    elif player_role == Role.OBERON:
        info["description"] = "You are evil but hidden from other evil players and Merlin"
        info["sees"] = []
    
    else:  # LOYAL_SERVANT
        info["description"] = "You are a loyal servant of Arthur. Trust in Merlin's guidance"
        info["sees"] = []
    
    return info

async def broadcast_game_state(session_id: str):
    """Broadcast current game state to all players in session"""
    try:
        session = await db.game_sessions.find_one({"id": session_id})
        if not session:
            print(f"Warning: Session {session_id} not found for broadcast")
            return
        
        game_session = GameSession(**session)
        player_count = len(game_session.players)
        
        # Debug logging for larger sessions
        if player_count >= 7:
            print(f"Broadcasting to {player_count} players in session {session_id}")
        
        # Send personalized state to each player
        for player in game_session.players:
            try:
                player_state = {
                    "type": "game_state",
                    "session": {
                        "id": game_session.id,
                        "name": game_session.name,
                        "phase": game_session.phase,
                        "current_mission": game_session.current_mission,
                        "current_leader": game_session.current_leader,
                        "vote_track": game_session.vote_track,
                        "good_wins": game_session.good_wins,
                        "evil_wins": game_session.evil_wins,
                        "game_result": game_session.game_result,
                        "lady_of_the_lake_enabled": game_session.lady_of_the_lake_enabled,
                        "players": [
                            {
                                "id": p.id,
                                "name": p.name,
                                "is_leader": p.is_leader,
                                "is_connected": p.is_connected,
                                "lady_of_the_lake": p.lady_of_the_lake,
                                "is_bot": p.is_bot,
                                "is_spectator": p.is_spectator,
                                # SECURITY: Only show player's own role, never others' roles
                                "role": p.role if (game_session.phase == GamePhase.GAME_END or p.id == player.id) else None
                            } for p in game_session.players
                        ],
                        "missions": [
                            {
                                "number": m.number,
                                "team_size": m.team_size,
                                "fails_required": m.fails_required,
                                "team_members": m.team_members,
                                "result": m.result,
                                "team_approved": m.team_approved,
                                "votes": m.votes if len(m.votes) == len([p for p in game_session.players if not p.is_spectator]) or game_session.phase == GamePhase.MISSION_EXECUTION else {},
                                # SECURITY: Never expose individual mission votes - only show if all voted and game ended
                                "mission_votes": {} if m.result == MissionResult.PENDING else {
                                    "total_votes": len(m.mission_votes),
                                    "fail_count": sum(1 for vote in m.mission_votes.values() if not vote),
                                    "success_count": sum(1 for vote in m.mission_votes.values() if vote)
                                }
                            } for m in game_session.missions
                        ],
                        "vote_history": game_session.vote_history,
                        "game_log": game_session.game_log
                    }
                }
                
                # Add role information if game has started - THIS IS PERSONALIZED PER PLAYER
                if game_session.phase != GamePhase.LOBBY and player.role:
                    player_state["role_info"] = get_role_info(player.role, game_session.players)
                
                # Add Lady of the Lake results for this player
                if player.id in game_session.lady_of_the_lake_results:
                    player_state["lady_of_lake_knowledge"] = []
                    for target_id, allegiance in game_session.lady_of_the_lake_results[player.id].items():
                        target_player = next((p for p in game_session.players if p.id == target_id), None)
                        if target_player:
                            player_state["lady_of_lake_knowledge"].append({
                                "target_id": target_id,
                                "target_name": target_player.name,
                                "allegiance": allegiance
                            })
                
                # Add current mission details if in mission phase
                if game_session.current_mission < len(game_session.missions):
                    current_mission = game_session.missions[game_session.current_mission]
                    player_state["current_mission_details"] = {
                        "number": current_mission.number,
                        "team_size": current_mission.team_size,
                        "fails_required": current_mission.fails_required,
                        "team_members": current_mission.team_members,
                        "votes": current_mission.votes,
                        # SECURITY: Only show vote counts after result; always show player_voted status
                        "mission_votes": {
                            "player_voted": player.id in current_mission.mission_votes,
                            "total_votes": len(current_mission.mission_votes),
                        } if current_mission.result == MissionResult.PENDING else {
                            "total_votes": len(current_mission.mission_votes),
                            "fail_count": sum(1 for vote in current_mission.mission_votes.values() if not vote),
                            "success_count": sum(1 for vote in current_mission.mission_votes.values() if vote),
                            "player_voted": player.id in current_mission.mission_votes
                        },
                        "result": current_mission.result,
                        "team_approved": current_mission.team_approved
                    }
                
                # Send personalized message to this specific player
                message = json.dumps(player_state)
                await manager.send_to_player(message, session_id, player.id)
                
            except Exception as e:
                print(f"Error sending state to player {player.name}: {str(e)}")
                continue
        
        # Also broadcast to any unidentified connections
        general_state = {
            "type": "game_state",
            "session": {
                "id": game_session.id,
                "name": game_session.name,
                "phase": game_session.phase,
                "current_mission": game_session.current_mission,
                "current_leader": game_session.current_leader,
                "vote_track": game_session.vote_track,
                "good_wins": game_session.good_wins,
                "evil_wins": game_session.evil_wins,
                "game_result": game_session.game_result,
                "players": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "is_leader": p.is_leader,
                        "is_connected": p.is_connected,
                        "lady_of_the_lake": p.lady_of_the_lake,
                        "is_bot": p.is_bot,
                        "is_spectator": p.is_spectator,
                        # SECURITY: Never show roles in general broadcast
                        "role": None
                    } for p in game_session.players
                ],
                "missions": [
                    {
                        "number": m.number,
                        "team_size": m.team_size,
                        "fails_required": m.fails_required,
                        "team_members": m.team_members,
                        "result": m.result,
                        "team_approved": m.team_approved
                    } for m in game_session.missions
                ],
                "lady_of_the_lake_holder": game_session.lady_of_the_lake_holder
            }
        }
        
        # Send to any connections that don't have a player_id
        if session_id in manager.active_connections:
            for connection_id, websocket in manager.active_connections[session_id].items():
                if not any(p.id == connection_id for p in game_session.players):
                    try:
                        await websocket.send_text(json.dumps(general_state))
                    except:
                        pass
                        
    except Exception as e:
        print(f"Error in broadcast_game_state for session {session_id}: {str(e)}")
        import traceback
        traceback.print_exc()

@app.websocket("/api/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, player_id: str = None):
    # Try to get player_id from query parameters
    query_params = dict(websocket.query_params)
    player_id = query_params.get('player_id', player_id)
    
    await manager.connect(websocket, session_id, player_id)
    try:
        # Send initial game state immediately
        await broadcast_game_state(session_id)
        
        while True:
            # Keep connection alive and handle any client messages
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle any WebSocket messages from client if needed
                message = json.loads(data)
                if message.get('type') == 'pong':
                    # Client responded to ping, connection is healthy
                    continue
                elif message.get('type') == 'identify' and message.get('player_id'):
                    # Update player identification - remap the connection
                    new_player_id = message.get('player_id')
                    if session_id in manager.active_connections:
                        # Remove old mapping and add new one
                        old_id = None
                        for pid, ws in manager.active_connections[session_id].items():
                            if ws == websocket:
                                old_id = pid
                                break
                        if old_id and old_id != new_player_id:
                            del manager.active_connections[session_id][old_id]
                        manager.active_connections[session_id][new_player_id] = websocket
                    player_id = new_player_id
                    print(f"Player identified as {player_id} in session {session_id}")
                    # Send fresh state to the newly identified player
                    await broadcast_game_state(session_id)
            except asyncio.TimeoutError:
                # Send periodic ping to keep connection alive
                await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket message error: {e}")
                break
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id, player_id)
        print(f"WebSocket disconnected from session {session_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, session_id, player_id)

@api_router.post("/create-session")
async def create_session(request: CreateSessionRequest):
    """Create a new game session"""
    session = GameSession(
        name=request.name,
        players=[Player(name=request.player_name)]
    )
    
    await db.game_sessions.insert_one(session.dict())
    await broadcast_game_state(session.id)

    token = _issue_token(session.id, session.players[0].id)
    return {"session_id": session.id, "player_id": session.players[0].id, "player_token": token}

@api_router.post("/join-session")
async def join_session(request: JoinSessionRequest):
    """Join an existing game session"""
    try:
        session = await db.game_sessions.find_one({"id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        game_session = GameSession(**session)
        
        # Check if player already exists (for reconnection)
        existing_player = next((p for p in game_session.players if p.name == request.player_name), None)
        if existing_player:
            existing_player.is_connected = True
            player_id = existing_player.id
        else:
            # Add new player
            if request.as_spectator:
                # Spectators can always join
                new_player = Player(name=request.player_name, is_spectator=True)
                game_session.players.append(new_player)
                player_id = new_player.id
            else:
                # Regular players limited to 10
                active_players = [p for p in game_session.players if not p.is_spectator]
                if len(active_players) >= 10:
                    raise HTTPException(status_code=400, detail="Session is full")
                
                new_player = Player(name=request.player_name)
                game_session.players.append(new_player)
                player_id = new_player.id
        
        # Debug logging for 7+ players
        active_count = len([p for p in game_session.players if not p.is_spectator])
        print(f"Join session: {active_count} active players, Lady of Lake enabled: {game_session.lady_of_the_lake_enabled}")
        
        await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
        await broadcast_game_state(request.session_id)
        
        token = _issue_token(request.session_id, player_id)
        return {"player_id": player_id, "is_spectator": request.as_spectator, "player_token": token}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in join_session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to join session: {str(e)}")

@api_router.post("/start-game")
async def start_game(request: StartGameRequest):
    """Start the game and assign roles"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    # Only count active players (not spectators)
    active_players = [p for p in game_session.players if not p.is_spectator]
    
    if len(active_players) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 players to start")
    
    # Check if game has already started (prevent role reassignment)
    if game_session.phase != GamePhase.LOBBY:
        raise HTTPException(status_code=400, detail="Game has already started")
    
    # Assign roles and initialize missions ONLY if not already assigned
    if not any(player.role for player in active_players):
        # Only assign roles to active players with dynamic balancing
        active_players = assign_roles(active_players, game_session)
        print(f"Assigned roles: {[(p.name, p.role) for p in active_players]}")
        
        # Update the active players in the game session
        for i, player in enumerate(game_session.players):
            if not player.is_spectator:
                # Find the corresponding active player with assigned role
                for active_player in active_players:
                    if active_player.id == player.id:
                        game_session.players[i] = active_player
                        break
    
    game_session.missions = initialize_missions(len(active_players))
    game_session.phase = GamePhase.MISSION_TEAM_SELECTION
    
    # ALWAYS randomize leader selection
    import random
    active_indices = [i for i, p in enumerate(game_session.players) if not p.is_spectator]
    random_leader_idx = random.choice(active_indices)
    
    # Clear all leader flags first
    for player in game_session.players:
        player.is_leader = False
    
    # Set random leader
    game_session.current_leader = random_leader_idx
    game_session.players[random_leader_idx].is_leader = True
    
    # Set initial Lady of the Lake holder (if using expansion)
    if len(active_players) >= 7 and game_session.lady_of_the_lake_enabled:
        game_session.lady_of_the_lake_holder = game_session.players[random_leader_idx].id
        game_session.players[random_leader_idx].lady_of_the_lake = True
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    # Start bot processing after a short delay
    asyncio.create_task(asyncio.sleep(1))
    asyncio.create_task(process_bot_actions(request.session_id))
    
    return {"message": "Game started successfully"}

# Add a test mode endpoint for easier testing
@api_router.post("/start-test-game")
async def start_test_game(request: StartGameRequest):
    """Start a test game with relaxed player requirements"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    # Check if game has already started (prevent role reassignment)
    if game_session.phase != GamePhase.LOBBY:
        raise HTTPException(status_code=400, detail="Game has already started")
    
    # Count active players (not spectators)
    active_players = [p for p in game_session.players if not p.is_spectator]
    
    # Add bot players if needed for testing
    while len(active_players) < 5:
        bot_name = f"Bot{len(game_session.players) + 1}"
        bot_player = Player(name=bot_name, is_bot=True)
        game_session.players.append(bot_player)
        active_players.append(bot_player)
    
    # Assign roles and initialize missions ONLY if not already assigned
    if not any(player.role for player in active_players):
        active_players = assign_roles(active_players, game_session)
        print(f"Assigned roles: {[(p.name, p.role) for p in active_players]}")
        
        # Update the active players in the game session
        for i, player in enumerate(game_session.players):
            if not player.is_spectator:
                # Find the corresponding active player with assigned role
                for active_player in active_players:
                    if active_player.id == player.id:
                        game_session.players[i] = active_player
                        break
    
    game_session.missions = initialize_missions(len(active_players))
    game_session.phase = GamePhase.MISSION_TEAM_SELECTION
    
    # ALWAYS randomize leader selection
    import random
    active_indices = [i for i, p in enumerate(game_session.players) if not p.is_spectator]
    random_leader_idx = random.choice(active_indices)
    
    # Clear all leader flags first
    for player in game_session.players:
        player.is_leader = False
    
    # Set random leader
    game_session.current_leader = random_leader_idx
    game_session.players[random_leader_idx].is_leader = True
    
    # Set initial Lady of the Lake holder (if using expansion)
    if len(active_players) >= 7 and game_session.lady_of_the_lake_enabled:
        game_session.lady_of_the_lake_holder = game_session.players[random_leader_idx].id
        game_session.players[random_leader_idx].lady_of_the_lake = True
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    # Start bot processing after a short delay
    asyncio.create_task(asyncio.sleep(1))
    asyncio.create_task(process_bot_actions(request.session_id))
    
    return {"message": "Test game started successfully"}

@api_router.post("/select-team")
async def select_team(request: TeamSelectionRequest):
    """Select team for current mission"""
    _require_auth(request.session_id, request.player_id, request.player_token)
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    # Verify it's the leader's turn
    current_leader = game_session.players[game_session.current_leader]
    if current_leader.id != request.player_id:
        raise HTTPException(status_code=400, detail="Not your turn to select team")
    
    current_mission = game_session.missions[game_session.current_mission]
    
    # Verify team size
    if len(request.team_members) != current_mission.team_size:
        raise HTTPException(status_code=400, detail=f"Team must have {current_mission.team_size} members")
    
    # Update mission with team selection
    current_mission.team_members = request.team_members
    current_mission.votes = {}
    game_session.phase = GamePhase.MISSION_VOTING
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    # Trigger bot actions after team selection
    asyncio.create_task(process_bot_actions(request.session_id))
    
    return {"message": "Team selected successfully"}

@api_router.post("/vote-team")
async def vote_team(request: VoteRequest):
    """Vote on team selection"""
    _require_auth(request.session_id, request.player_id, request.player_token)
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    # Verify phase
    if game_session.phase != GamePhase.MISSION_VOTING:
        raise HTTPException(status_code=400, detail="Not in voting phase")
    
    current_mission = game_session.missions[game_session.current_mission]
    
    # Check if player already voted
    if request.player_id in current_mission.votes:
        raise HTTPException(status_code=400, detail="You have already voted")
    
    # Record vote with optimistic update
    current_mission.votes[request.player_id] = request.vote
    
    # Save state immediately
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    
    # Check if all active players have voted
    active_players = [p for p in game_session.players if not p.is_spectator]
    if len(current_mission.votes) == len(active_players):
        # Only use locking when processing final result
        async with session_lock(request.session_id):
            # Re-fetch to ensure we have latest state
            updated_session = await db.game_sessions.find_one({"id": request.session_id})
            if updated_session:
                updated_game_session = GameSession(**updated_session)
                updated_mission = updated_game_session.missions[updated_game_session.current_mission]
                updated_active_players = [p for p in updated_game_session.players if not p.is_spectator]
                
                # Double-check all votes are in before processing
                if len(updated_mission.votes) == len(updated_active_players):
                    await process_team_vote_result(request.session_id)
    else:
        await broadcast_game_state(request.session_id)
        # Trigger bot voting if there are bots that haven't voted yet
        asyncio.create_task(process_bot_actions(request.session_id))

    return {"message": "Vote recorded successfully"}

@api_router.post("/vote-mission")
async def vote_mission(request: MissionVoteRequest):
    """Vote on mission success/failure"""
    _require_auth(request.session_id, request.player_id, request.player_token)
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    # Verify phase
    if game_session.phase != GamePhase.MISSION_EXECUTION:
        raise HTTPException(status_code=400, detail="Not in mission execution phase")
    
    current_mission = game_session.missions[game_session.current_mission]
    
    # Verify player is on the mission team
    if request.player_id not in current_mission.team_members:
        raise HTTPException(status_code=400, detail="You are not on this mission")
    
    # Check if player already voted (prevent double voting)
    if request.player_id in current_mission.mission_votes:
        raise HTTPException(status_code=400, detail="You have already voted")
    
    # Record mission vote with optimistic update
    current_mission.mission_votes[request.player_id] = request.vote
    
    # Save state immediately
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    
    # Check if all team members have voted
    if len(current_mission.mission_votes) == len(current_mission.team_members):
        # Only use locking when processing final result to prevent double processing
        async with session_lock(request.session_id):
            # Re-fetch to ensure we have latest state
            updated_session = await db.game_sessions.find_one({"id": request.session_id})
            if updated_session:
                updated_game_session = GameSession(**updated_session)
                updated_mission = updated_game_session.missions[updated_game_session.current_mission]
                
                # Double-check all votes are in before processing
                if len(updated_mission.mission_votes) == len(updated_mission.team_members):
                    await process_mission_vote_result(request.session_id)
    else:
        # Just broadcast the updated voting state
        await broadcast_game_state(request.session_id)
        # Trigger bot voting if there are bots that haven't voted yet
        asyncio.create_task(process_bot_actions(request.session_id))

    return {"message": "Vote recorded successfully"}

@api_router.post("/lady-of-lake")
async def lady_of_lake(request: LadyOfLakeRequest):
    """Use Lady of the Lake to reveal a player's allegiance"""
    _require_auth(request.session_id, request.player_id, request.player_token)
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    if game_session.phase != GamePhase.LADY_OF_THE_LAKE:
        raise HTTPException(status_code=400, detail="Not in Lady of the Lake phase")
    
    current_player = next((p for p in game_session.players if p.id == request.player_id), None)
    if not current_player or not current_player.lady_of_the_lake:
        raise HTTPException(status_code=400, detail="You don't have the Lady of the Lake")
    
    target_player = next((p for p in game_session.players if p.id == request.target_player_id), None)
    if not target_player:
        raise HTTPException(status_code=404, detail="Target player not found")
    
    # Determine allegiance
    allegiance = "good" if target_player.role in [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT] else "evil"
    
    # Save the result persistently
    if request.player_id not in game_session.lady_of_the_lake_results:
        game_session.lady_of_the_lake_results[request.player_id] = {}
    game_session.lady_of_the_lake_results[request.player_id][request.target_player_id] = allegiance
    
    # Transfer Lady of the Lake to target
    current_player.lady_of_the_lake = False
    target_player.lady_of_the_lake = True
    game_session.lady_of_the_lake_holder = target_player.id
    
    # Move to next mission (leader was already advanced in process_mission_vote_result)
    game_session.phase = GamePhase.MISSION_TEAM_SELECTION

    game_session.game_log.append(f"{current_player.name} used Lady of the Lake on {target_player.name}")
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {
        "target_name": target_player.name,
        "allegiance": allegiance
    }

@api_router.post("/assassinate")
async def assassinate(request: AssassinationRequest):
    """Assassin attempts to kill Merlin"""
    _require_auth(request.session_id, request.player_id, request.player_token)
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    # Verify player is the assassin
    assassin = next((p for p in game_session.players if p.role == Role.ASSASSIN), None)
    if not assassin or assassin.id != request.player_id:
        raise HTTPException(status_code=400, detail="Only the assassin can perform assassination")
    
    # Check if target is Merlin
    target_player = next((p for p in game_session.players if p.id == request.target_player_id), None)
    if not target_player:
        raise HTTPException(status_code=404, detail="Target player not found")
    
    if target_player.role == Role.MERLIN:
        game_session.game_result = "evil"
        game_session.evil_total_wins += 1  # Track for balancing
    else:
        game_session.game_result = "good"
        game_session.good_total_wins += 1  # Track for balancing
    
    game_session.phase = GamePhase.GAME_END
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"success": target_player.role == Role.MERLIN, "target_name": target_player.name}

@api_router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session details — roles are stripped to prevent information leakage"""
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = GameSession(**session)
    return {
        "id": game_session.id,
        "name": game_session.name,
        "phase": game_session.phase,
        "current_mission": game_session.current_mission,
        "current_leader": game_session.current_leader,
        "vote_track": game_session.vote_track,
        "good_wins": game_session.good_wins,
        "evil_wins": game_session.evil_wins,
        "game_result": game_session.game_result,
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "is_leader": p.is_leader,
                "is_connected": p.is_connected,
                "is_bot": p.is_bot,
                "is_spectator": p.is_spectator,
                # Only reveal roles after game ends
                "role": p.role if game_session.phase == GamePhase.GAME_END else None,
            } for p in game_session.players
        ],
    }
@api_router.post("/toggle-lady-of-lake")
async def toggle_lady_of_lake(request: ToggleLadyOfLakeRequest):
    """Toggle Lady of the Lake expansion"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    if game_session.phase != GamePhase.LOBBY:
        raise HTTPException(status_code=400, detail="Can only change settings in lobby")
    
    game_session.lady_of_the_lake_enabled = request.enabled
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"lady_of_the_lake_enabled": game_session.lady_of_the_lake_enabled}

@api_router.post("/toggle-mordred")
async def toggle_mordred(request: ToggleMordredRequest):
    """Toggle Mordred role availability"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    if game_session.phase != GamePhase.LOBBY:
        raise HTTPException(status_code=400, detail="Can only change settings in lobby")
    
    game_session.mordred_enabled = request.enabled
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"mordred_enabled": game_session.mordred_enabled}

@api_router.post("/toggle-oberon")
async def toggle_oberon(request: ToggleOberonRequest):
    """Toggle Oberon role availability"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    if game_session.phase != GamePhase.LOBBY:
        raise HTTPException(status_code=400, detail="Can only change settings in lobby")
    
    game_session.oberon_enabled = request.enabled
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"oberon_enabled": game_session.oberon_enabled}

@api_router.post("/restart-game")
async def restart_game(request: RestartGameRequest):
    """Restart the game with same players"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    # Reset game state but keep players
    for player in game_session.players:
        player.role = None
        player.is_leader = False
        player.lady_of_the_lake = False
    
    # ALWAYS randomize leader selection for restart
    active_players = [p for p in game_session.players if not p.is_spectator]
    if active_players:
        import random
        active_indices = [i for i, p in enumerate(game_session.players) if not p.is_spectator]
        random_leader_idx = random.choice(active_indices)
        game_session.current_leader = random_leader_idx
        game_session.players[random_leader_idx].is_leader = True
    
    game_session.phase = GamePhase.LOBBY
    game_session.current_mission = 0
    game_session.missions = []
    game_session.vote_track = 0
    game_session.lady_of_the_lake_holder = None
    game_session.lady_of_the_lake_results = {}  # Clear Lady of the Lake knowledge
    game_session.game_result = None
    game_session.good_wins = 0
    game_session.evil_wins = 0
    game_session.vote_history = []
    game_session.game_log = []
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"message": "Game restarted successfully"}

@api_router.post("/end-game")
async def end_game(request: RestartGameRequest):
    """End the current game and reveal all roles"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    # Set game to end state
    game_session.phase = GamePhase.GAME_END
    if not game_session.game_result:
        game_session.game_result = "ended"
    
    game_session.game_log.append("Game ended manually - all roles revealed!")
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"message": "Game ended successfully"}

# Include the router in the main app
app.include_router(api_router)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()