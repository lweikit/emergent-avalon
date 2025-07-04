from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import uuid
from datetime import datetime
import json
import asyncio
from enum import Enum
import random
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Avalon Game API", version="1.0.0")

# Add CORS middleware first
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

@api_router.get("/")
async def root():
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

class StartGameRequest(BaseModel):
    session_id: str

class TeamSelectionRequest(BaseModel):
    session_id: str
    player_id: str
    team_members: List[str]

class VoteRequest(BaseModel):
    session_id: str
    player_id: str
    vote: bool

class MissionVoteRequest(BaseModel):
    session_id: str
    player_id: str
    vote: bool

class LadyOfLakeRequest(BaseModel):
    session_id: str
    player_id: str
    target_player_id: str

class AssassinationRequest(BaseModel):
    session_id: str
    player_id: str
    target_player_id: str

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

def assign_roles(players: List[Player]) -> List[Player]:
    """Assign roles to players based on player count"""
    player_count = len(players)
    if player_count not in ROLE_CONFIGS:
        raise ValueError(f"Invalid player count: {player_count}")
    
    roles = ROLE_CONFIGS[player_count].copy()
    random.shuffle(roles)
    
    for i, player in enumerate(players):
        player.role = roles[i]
    
    return players

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
    """Get role-specific information for a player"""
    info = {
        "role": player_role,
        "team": "good" if player_role in [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT] else "evil",
        "description": "",
        "sees": []
    }
    
    if player_role == Role.MERLIN:
        info["description"] = "You can see all evil players except Mordred"
        evil_players = [p for p in all_players if p.role in [Role.MORGANA, Role.ASSASSIN, Role.OBERON, Role.MINION]]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_players]
    
    elif player_role == Role.PERCIVAL:
        info["description"] = "You can see Merlin and Morgana, but don't know which is which"
        merlin_morgana = [p for p in all_players if p.role in [Role.MERLIN, Role.MORGANA]]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "merlin_or_morgana"} for p in merlin_morgana]
    
    elif player_role == Role.MORGANA:
        info["description"] = "You are evil and can see other evil players (except Oberon)"
        evil_players = [p for p in all_players if p.role in [Role.ASSASSIN, Role.MORDRED, Role.MINION]]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_players]
    
    elif player_role == Role.ASSASSIN:
        info["description"] = "You are evil and can see other evil players (except Oberon). You can assassinate Merlin if good wins"
        evil_players = [p for p in all_players if p.role in [Role.MORGANA, Role.MORDRED, Role.MINION]]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_players]
    
    elif player_role == Role.MORDRED:
        info["description"] = "You are evil and can see other evil players (except Oberon). You are hidden from Merlin"
        evil_players = [p for p in all_players if p.role in [Role.MORGANA, Role.ASSASSIN, Role.MINION]]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_players]
    
    elif player_role == Role.MINION:
        info["description"] = "You are evil and can see other evil players (except Oberon)"
        evil_players = [p for p in all_players if p.role in [Role.MORGANA, Role.ASSASSIN, Role.MORDRED]]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_players]
    
    elif player_role == Role.OBERON:
        info["description"] = "You are evil but hidden from other evil players and Merlin"
        info["sees"] = []
    
    else:  # LOYAL_SERVANT
        info["description"] = "You are a loyal servant of Arthur. Trust in Merlin's guidance"
        info["sees"] = []
    
    return info

async def broadcast_game_state(session_id: str):
    """Broadcast current game state to all players in session"""
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        return
    
    game_session = GameSession(**session)
    
    # Send personalized state to each player
    for player in game_session.players:
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
                "players": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "is_leader": p.is_leader,
                        "is_connected": p.is_connected,
                        "lady_of_the_lake": p.lady_of_the_lake,
                        "role": p.role if game_session.phase != GamePhase.LOBBY else None
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
                        "votes": m.votes if len(m.votes) == len(game_session.players) or game_session.phase == GamePhase.MISSION_EXECUTION else {},
                        "mission_votes": m.mission_votes if len(m.mission_votes) == len(m.team_members) else {}
                    } for m in game_session.missions
                ],
                "lady_of_the_lake_holder": game_session.lady_of_the_lake_holder
            },
            "player_id": player.id
        }
        
        # Add role information if game has started - THIS IS PERSONALIZED PER PLAYER
        if game_session.phase != GamePhase.LOBBY and player.role:
            player_state["role_info"] = get_role_info(player.role, game_session.players)
        
        # Add current mission details if in mission phase
        if game_session.current_mission < len(game_session.missions):
            current_mission = game_session.missions[game_session.current_mission]
            player_state["current_mission_details"] = {
                "number": current_mission.number,
                "team_size": current_mission.team_size,
                "fails_required": current_mission.fails_required,
                "team_members": current_mission.team_members,
                "votes": current_mission.votes,
                "mission_votes": current_mission.mission_votes,
                "result": current_mission.result,
                "team_approved": current_mission.team_approved
            }
        
        # Send personalized message to this specific player
        message = json.dumps(player_state)
        await manager.send_to_player(message, session_id, player.id)
    
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
                    "lady_of_the_lake": p.lady_of_the_lake
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
                    # Update player identification
                    player_id = message.get('player_id')
                    print(f"Player identified as {player_id} in session {session_id}")
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
    
    return {"session_id": session.id, "player_id": session.players[0].id}

@api_router.post("/join-session")
async def join_session(request: JoinSessionRequest):
    """Join an existing game session"""
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
        if len(game_session.players) >= 10:
            raise HTTPException(status_code=400, detail="Session is full")
        
        new_player = Player(name=request.player_name)
        game_session.players.append(new_player)
        player_id = new_player.id
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"player_id": player_id}

@api_router.post("/start-game")
async def start_game(request: StartGameRequest):
    """Start the game and assign roles"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    if len(game_session.players) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 players to start")
    
    # Check if game has already started (prevent role reassignment)
    if game_session.phase != GamePhase.LOBBY:
        raise HTTPException(status_code=400, detail="Game has already started")
    
    # Assign roles and initialize missions ONLY if not already assigned
    if not any(player.role for player in game_session.players):
        game_session.players = assign_roles(game_session.players)
        print(f"Assigned roles: {[(p.name, p.role) for p in game_session.players]}")
    
    game_session.missions = initialize_missions(len(game_session.players))
    game_session.phase = GamePhase.MISSION_TEAM_SELECTION
    game_session.players[0].is_leader = True
    
    # Set initial Lady of the Lake holder (if using expansion)
    if len(game_session.players) >= 7:
        game_session.lady_of_the_lake_holder = game_session.players[0].id
        game_session.players[0].lady_of_the_lake = True
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
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
    
    # Add bot players if needed for testing
    while len(game_session.players) < 5:
        bot_name = f"Bot{len(game_session.players)}"
        bot_player = Player(name=bot_name, is_connected=False)
        game_session.players.append(bot_player)
    
    # Assign roles and initialize missions ONLY if not already assigned
    if not any(player.role for player in game_session.players):
        game_session.players = assign_roles(game_session.players)
        print(f"Assigned roles: {[(p.name, p.role) for p in game_session.players]}")
    
    game_session.missions = initialize_missions(len(game_session.players))
    game_session.phase = GamePhase.MISSION_TEAM_SELECTION
    game_session.players[0].is_leader = True
    
    # Set initial Lady of the Lake holder (if using expansion)
    if len(game_session.players) >= 7:
        game_session.lady_of_the_lake_holder = game_session.players[0].id
        game_session.players[0].lady_of_the_lake = True
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"message": "Test game started successfully with bot players"}

@api_router.post("/select-team")
async def select_team(request: TeamSelectionRequest):
    """Select team for current mission"""
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
    
    return {"message": "Team selected successfully"}

@api_router.post("/vote-team")
async def vote_team(request: VoteRequest):
    """Vote on the proposed team"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    current_mission = game_session.missions[game_session.current_mission]
    
    # Record vote
    current_mission.votes[request.player_id] = request.vote
    
    # Check if all players have voted
    if len(current_mission.votes) == len(game_session.players):
        approve_count = sum(1 for vote in current_mission.votes.values() if vote)
        
        if approve_count > len(game_session.players) // 2:
            # Team approved
            current_mission.team_approved = True
            current_mission.mission_votes = {}
            game_session.phase = GamePhase.MISSION_EXECUTION
        else:
            # Team rejected
            game_session.vote_track += 1
            
            if game_session.vote_track >= 5:
                # Evil wins on 5th rejection
                game_session.phase = GamePhase.GAME_END
                game_session.game_result = "evil"
            else:
                # Move to next leader
                game_session.current_leader = (game_session.current_leader + 1) % len(game_session.players)
                for player in game_session.players:
                    player.is_leader = False
                game_session.players[game_session.current_leader].is_leader = True
                game_session.phase = GamePhase.MISSION_TEAM_SELECTION
                current_mission.team_members = []
                current_mission.votes = {}
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"message": "Vote recorded successfully"}

@api_router.post("/vote-mission")
async def vote_mission(request: MissionVoteRequest):
    """Vote on mission success/failure"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    current_mission = game_session.missions[game_session.current_mission]
    
    # Verify player is on the mission team
    if request.player_id not in current_mission.team_members:
        raise HTTPException(status_code=400, detail="You are not on this mission")
    
    # Record mission vote
    current_mission.mission_votes[request.player_id] = request.vote
    
    # Check if all team members have voted
    if len(current_mission.mission_votes) == len(current_mission.team_members):
        fail_count = sum(1 for vote in current_mission.mission_votes.values() if not vote)
        
        if fail_count >= current_mission.fails_required:
            current_mission.result = MissionResult.FAIL
            game_session.evil_wins += 1
        else:
            current_mission.result = MissionResult.SUCCESS
            game_session.good_wins += 1
        
        # Check win conditions
        if game_session.good_wins >= 3:
            # Good wins, move to assassination phase
            game_session.phase = GamePhase.ASSASSINATION
        elif game_session.evil_wins >= 3:
            # Evil wins
            game_session.phase = GamePhase.GAME_END
            game_session.game_result = "evil"
        else:
            # Continue to next mission
            game_session.current_mission += 1
            game_session.vote_track = 0
            
            # Check for Lady of the Lake phase
            if (game_session.lady_of_the_lake_holder and 
                game_session.current_mission in [2, 3] and 
                len(game_session.players) >= 7):
                game_session.phase = GamePhase.LADY_OF_THE_LAKE
            else:
                game_session.phase = GamePhase.MISSION_TEAM_SELECTION
                
            # Move to next leader
            game_session.current_leader = (game_session.current_leader + 1) % len(game_session.players)
            for player in game_session.players:
                player.is_leader = False
            game_session.players[game_session.current_leader].is_leader = True
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"message": "Mission vote recorded successfully"}

@api_router.post("/lady-of-lake")
async def lady_of_lake(request: LadyOfLakeRequest):
    """Use Lady of the Lake to reveal a player's allegiance"""
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    # Verify player has Lady of the Lake
    if game_session.lady_of_the_lake_holder != request.player_id:
        raise HTTPException(status_code=400, detail="You don't have the Lady of the Lake")
    
    # Get target player's allegiance
    target_player = next((p for p in game_session.players if p.id == request.target_player_id), None)
    if not target_player:
        raise HTTPException(status_code=404, detail="Target player not found")
    
    allegiance = "good" if target_player.role in [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT] else "evil"
    
    # Pass Lady of the Lake to target player
    for player in game_session.players:
        player.lady_of_the_lake = False
    target_player.lady_of_the_lake = True
    game_session.lady_of_the_lake_holder = target_player.id
    
    # Move to next mission
    game_session.phase = GamePhase.MISSION_TEAM_SELECTION
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"allegiance": allegiance, "target_name": target_player.name}

@api_router.post("/assassinate")
async def assassinate(request: AssassinationRequest):
    """Assassin attempts to kill Merlin"""
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
    else:
        game_session.game_result = "good"
    
    game_session.phase = GamePhase.GAME_END
    
    await db.game_sessions.replace_one({"id": request.session_id}, game_session.dict())
    await broadcast_game_state(request.session_id)
    
    return {"success": target_player.role == Role.MERLIN, "target_name": target_player.name}

@api_router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session details"""
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return GameSession(**session)

@api_router.get("/debug/session/{session_id}")
async def debug_session(session_id: str):
    """Debug session details with role information"""
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    game_session = GameSession(**session)
    
    debug_info = {
        "session_id": session_id,
        "phase": game_session.phase,
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "role": p.role,
                "is_leader": p.is_leader,
                "is_connected": p.is_connected
            } for p in game_session.players
        ],
        "role_distribution": {
            "total_players": len(game_session.players),
            "expected_roles": ROLE_CONFIGS.get(len(game_session.players), []),
            "actual_roles": [p.role for p in game_session.players if p.role]
        }
    }
    
    return debug_info

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