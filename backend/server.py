from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
import time as _time
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import asyncio
import json
import logging
import os
import random

from models import (
    GameSession, GamePhase, Role, MissionResult, Player,
    CreateSessionRequest, JoinSessionRequest, StartGameRequest,
    TeamSelectionRequest, VoteRequest, MissionVoteRequest,
    LadyOfLakeRequest, AssassinationRequest,
    ToggleLadyOfLakeRequest, ToggleMordredRequest, ToggleOberonRequest,
    RestartGameRequest, LeaveSessionRequest,
    generate_code,
)
from game_logic import initialize_game, process_team_vote, process_mission_vote, advance_vote_reveal, advance_mission_reveal
from bots import process_bot_actions
from websocket import ConnectionManager, broadcast_game_state
from auth import issue_token, require_auth, verify_token, cleanup_session_tokens

# ── Rate limiter ────────────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-IP rate limiter: max requests per window."""

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = _time.monotonic()
        # Prune old entries
        self._hits[ip] = [t for t in self._hits[ip] if now - t < self.window]
        if len(self._hits[ip]) >= self.max_requests:
            from starlette.responses import JSONResponse
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        self._hits[ip].append(now)
        return await call_next(request)

# ── Setup ───────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# Per-session async locks (with cleanup)
_session_locks: dict[str, asyncio.Lock] = {}

@asynccontextmanager
async def session_lock(session_id: str):
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    async with _session_locks[session_id]:
        yield

def _cleanup_lock(session_id: str):
    _session_locks.pop(session_id, None)

manager = ConnectionManager()

# Convenience wrappers so modules don't need db/manager references
async def _broadcast(session_id: str):
    await broadcast_game_state(session_id, db, manager)

async def _delayed_bot_actions(session_id: str):
    await asyncio.sleep(1)
    await process_bot_actions(session_id, db, session_lock, _broadcast)

async def _advance_mission_reveal(session_id: str):
    """Wait, then advance from MISSION_REVEAL to the real next phase."""
    await asyncio.sleep(5)
    async with session_lock(session_id):
        session = await db.game_sessions.find_one({"id": session_id})
        if not session:
            return
        gs = GameSession(**session)
        if gs.phase != GamePhase.MISSION_REVEAL:
            return
        advance_mission_reveal(gs)
        await db.game_sessions.replace_one({"id": session_id}, gs.model_dump())
    await _broadcast(session_id)
    asyncio.create_task(_delayed_bot_actions(session_id))

async def _advance_vote_reveal(session_id: str):
    """Wait, then advance from VOTE_REVEAL to the real next phase."""
    await asyncio.sleep(5)
    async with session_lock(session_id):
        session = await db.game_sessions.find_one({"id": session_id})
        if not session:
            return
        gs = GameSession(**session)
        if gs.phase != GamePhase.VOTE_REVEAL:
            return
        advance_vote_reveal(gs)
        await db.game_sessions.replace_one({"id": session_id}, gs.model_dump())
    await _broadcast(session_id)
    asyncio.create_task(_delayed_bot_actions(session_id))

# ── Lifecycle ───────────────────────────────────────────────────────────

_cleanup_task = None

async def _cleanup_old_sessions():
    while True:
        try:
            cutoff = datetime.utcnow() - timedelta(days=7)
            old_sessions = await db.game_sessions.find(
                {"created_at": {"$lt": cutoff}}, {"id": 1}
            ).to_list(1000)
            if old_sessions:
                old_ids = [s["id"] for s in old_sessions]
                result = await db.game_sessions.delete_many({"created_at": {"$lt": cutoff}})
                for sid in old_ids:
                    cleanup_session_tokens(sid)
                    _cleanup_lock(sid)
                logger.info("Cleaned up %d old sessions", result.deleted_count)
        except Exception as e:
            logger.error("Session cleanup error: %s", e)
        await asyncio.sleep(6 * 3600)

@asynccontextmanager
async def _lifespan(app):
    global _cleanup_task
    await db.game_sessions.create_index("id", unique=True)
    await db.game_sessions.create_index("code", unique=True, sparse=True)
    await db.game_sessions.create_index("created_at")
    logger.info("MongoDB indexes ensured")
    _cleanup_task = asyncio.create_task(_cleanup_old_sessions())
    yield
    client.close()

# ── App & Router ────────────────────────────────────────────────────────

app = FastAPI(title="Avalon Game API", version="1.0.0", lifespan=_lifespan)
app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)

_cors_origins = (
    [o.strip() for o in os.environ["CORS_ORIGINS"].split(",") if o.strip()]
    if os.environ.get("CORS_ORIGINS")
    else ["http://localhost:3000"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")

# ── Health ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    try:
        await db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")

@app.get("/")
async def root():
    return {"message": "Avalon Game API", "status": "running"}

@api_router.get("/")
async def api_root():
    return {"message": "Avalon Game API is running", "status": "healthy"}

async def _resolve_session(identifier: str):
    """Find a session by UUID or short code. Returns the raw document or None."""
    doc = await db.game_sessions.find_one({"id": identifier})
    if doc:
        return doc
    return await db.game_sessions.find_one({"code": identifier.upper()})

# ── Session management ──────────────────────────────────────────────────

@api_router.post("/create-session")
async def create_session(request: CreateSessionRequest):
    session = GameSession(name=request.name, players=[Player(name=request.player_name)])
    for _ in range(10):
        code = generate_code()
        if not await db.game_sessions.find_one({"code": code}):
            session.code = code
            break
    await db.game_sessions.insert_one(session.model_dump())
    await _broadcast(session.id)
    token = issue_token(session.id, session.players[0].id)
    return {"session_id": session.id, "player_id": session.players[0].id, "player_token": token}

@api_router.post("/join-session")
async def join_session(request: JoinSessionRequest):
    session = await _resolve_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    gs = GameSession(**session)

    # Reconnection by name
    existing = next((p for p in gs.players if p.name == request.player_name), None)
    if existing:
        existing.is_connected = True
        player_id = existing.id
    elif request.as_spectator:
        new_player = Player(name=request.player_name, is_spectator=True)
        gs.players.append(new_player)
        player_id = new_player.id
    else:
        active = [p for p in gs.players if not p.is_spectator]
        if len(active) >= 10:
            raise HTTPException(status_code=400, detail="Session is full")
        new_player = Player(name=request.player_name)
        gs.players.append(new_player)
        player_id = new_player.id

    await db.game_sessions.replace_one({"id": gs.id}, gs.model_dump())
    await _broadcast(gs.id)
    token = issue_token(gs.id, player_id)
    return {"session_id": gs.id, "player_id": player_id, "is_spectator": request.as_spectator, "player_token": token}

@api_router.post("/leave-session")
async def leave_session(request: LeaveSessionRequest):
    require_auth(request.session_id, request.player_id, request.player_token)

    async with session_lock(request.session_id):
        session = await db.game_sessions.find_one({"id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        gs = GameSession(**session)
        player = next((p for p in gs.players if p.id == request.player_id), None)
        if not player:
            return {"message": "Already removed"}

        if gs.phase == GamePhase.LOBBY or player.is_spectator:
            gs.players = [p for p in gs.players if p.id != request.player_id]
        else:
            player.is_connected = False

        await db.game_sessions.replace_one({"id": request.session_id}, gs.model_dump())

    await _broadcast(request.session_id)
    return {"message": "Left session"}

# ── Game start ──────────────────────────────────────────────────────────

@api_router.post("/start-game")
async def start_game(request: StartGameRequest):
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    gs = GameSession(**session)

    active = [p for p in gs.players if not p.is_spectator]
    if len(active) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 players to start")
    if gs.phase != GamePhase.LOBBY:
        raise HTTPException(status_code=400, detail="Game has already started")

    initialize_game(gs, fill_bots=False)
    await db.game_sessions.replace_one({"id": request.session_id}, gs.model_dump())
    await _broadcast(request.session_id)
    asyncio.create_task(_delayed_bot_actions(request.session_id))
    return {"message": "Game started successfully"}

@api_router.post("/start-test-game")
async def start_test_game(request: StartGameRequest):
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    gs = GameSession(**session)

    if gs.phase != GamePhase.LOBBY:
        raise HTTPException(status_code=400, detail="Game has already started")

    initialize_game(gs, fill_bots=True)
    await db.game_sessions.replace_one({"id": request.session_id}, gs.model_dump())
    await _broadcast(request.session_id)
    asyncio.create_task(_delayed_bot_actions(request.session_id))
    return {"message": "Test game started successfully"}

# ── Team selection ──────────────────────────────────────────────────────

@api_router.post("/select-team")
async def select_team(request: TeamSelectionRequest):
    require_auth(request.session_id, request.player_id, request.player_token)

    async with session_lock(request.session_id):
        session = await db.game_sessions.find_one({"id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        gs = GameSession(**session)
        if gs.phase != GamePhase.MISSION_TEAM_SELECTION:
            raise HTTPException(status_code=400, detail="Not in team selection phase")

        leader = gs.players[gs.current_leader]
        if leader.id != request.player_id:
            raise HTTPException(status_code=400, detail="Not your turn to select team")

        cm = gs.missions[gs.current_mission]
        if len(request.team_members) != cm.team_size:
            raise HTTPException(status_code=400, detail=f"Team must have {cm.team_size} members")

        valid_ids = {p.id for p in gs.players if not p.is_spectator}
        if len(set(request.team_members)) != len(request.team_members):
            raise HTTPException(status_code=400, detail="Duplicate team members")
        invalid = set(request.team_members) - valid_ids
        if invalid:
            raise HTTPException(status_code=400, detail="Invalid player IDs in team")

        cm.team_members = request.team_members
        cm.votes = {}
        gs.phase = GamePhase.MISSION_VOTING

        await db.game_sessions.replace_one({"id": request.session_id}, gs.model_dump())

    await _broadcast(request.session_id)
    asyncio.create_task(process_bot_actions(request.session_id, db, session_lock, _broadcast))
    return {"message": "Team selected successfully"}

# ── Voting ──────────────────────────────────────────────────────────────

@api_router.post("/vote-team")
async def vote_team(request: VoteRequest):
    require_auth(request.session_id, request.player_id, request.player_token)

    async with session_lock(request.session_id):
        session = await db.game_sessions.find_one({"id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        gs = GameSession(**session)
        if gs.phase != GamePhase.MISSION_VOTING:
            raise HTTPException(status_code=400, detail="Not in voting phase")

        cm = gs.missions[gs.current_mission]
        if request.player_id in cm.votes:
            raise HTTPException(status_code=400, detail="You have already voted")

        cm.votes[request.player_id] = request.vote
        active = [p for p in gs.players if not p.is_spectator]

        all_voted = len(cm.votes) == len(active)
        if all_voted:
            process_team_vote(gs)

        await db.game_sessions.replace_one({"id": request.session_id}, gs.model_dump())

    await _broadcast(request.session_id)
    if all_voted:
        # Auto-advance after 5s reveal
        asyncio.create_task(_advance_vote_reveal(request.session_id))
    else:
        asyncio.create_task(process_bot_actions(request.session_id, db, session_lock, _broadcast))
    return {"message": "Vote recorded successfully"}

@api_router.post("/vote-mission")
async def vote_mission(request: MissionVoteRequest):
    require_auth(request.session_id, request.player_id, request.player_token)

    async with session_lock(request.session_id):
        session = await db.game_sessions.find_one({"id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        gs = GameSession(**session)
        if gs.phase != GamePhase.MISSION_EXECUTION:
            raise HTTPException(status_code=400, detail="Not in mission execution phase")

        cm = gs.missions[gs.current_mission]
        if request.player_id not in cm.team_members:
            raise HTTPException(status_code=400, detail="You are not on this mission")
        if request.player_id in cm.mission_votes:
            raise HTTPException(status_code=400, detail="You have already voted")

        # Good players cannot vote fail — enforce server-side
        if not request.vote:
            player = next((p for p in gs.players if p.id == request.player_id), None)
            if player and player.role in (Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT):
                raise HTTPException(status_code=400, detail="Good players must vote success")

        cm.mission_votes[request.player_id] = request.vote

        all_voted = len(cm.mission_votes) == len(cm.team_members)
        if all_voted:
            process_mission_vote(gs)

        await db.game_sessions.replace_one({"id": request.session_id}, gs.model_dump())

    await _broadcast(request.session_id)
    if all_voted:
        asyncio.create_task(_advance_mission_reveal(request.session_id))
    else:
        asyncio.create_task(process_bot_actions(request.session_id, db, session_lock, _broadcast))
    return {"message": "Vote recorded successfully"}

# ── Lady of the Lake ────────────────────────────────────────────────────

@api_router.post("/lady-of-lake")
async def lady_of_lake(request: LadyOfLakeRequest):
    require_auth(request.session_id, request.player_id, request.player_token)

    async with session_lock(request.session_id):
        session = await db.game_sessions.find_one({"id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        gs = GameSession(**session)
        if gs.phase != GamePhase.LADY_OF_THE_LAKE:
            raise HTTPException(status_code=400, detail="Not in Lady of the Lake phase")

        current_player = next((p for p in gs.players if p.id == request.player_id), None)
        if not current_player or not current_player.lady_of_the_lake:
            raise HTTPException(status_code=400, detail="You don't have the Lady of the Lake")

        target = next((p for p in gs.players if p.id == request.target_player_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Target player not found")
        if target.is_spectator:
            raise HTTPException(status_code=400, detail="Cannot target a spectator")
        if target.id == request.player_id:
            raise HTTPException(status_code=400, detail="Cannot target yourself")
        # Can't target anyone who has previously held the Lady of the Lake
        previous_holders = set(gs.lady_of_the_lake_results.keys())
        if target.id in previous_holders:
            raise HTTPException(status_code=400, detail="Cannot target a previous Lady of the Lake holder")

        allegiance = "good" if target.role in (Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT) else "evil"

        if request.player_id not in gs.lady_of_the_lake_results:
            gs.lady_of_the_lake_results[request.player_id] = {}
        gs.lady_of_the_lake_results[request.player_id][request.target_player_id] = allegiance

        current_player.lady_of_the_lake = False
        target.lady_of_the_lake = True
        gs.lady_of_the_lake_holder = target.id
        gs.phase = GamePhase.MISSION_TEAM_SELECTION
        gs.game_log.append(f"{current_player.name} used Lady of the Lake on {target.name}")

        await db.game_sessions.replace_one({"id": request.session_id}, gs.model_dump())

    await _broadcast(request.session_id)
    return {"target_name": target.name, "allegiance": allegiance}

# ── Assassination ───────────────────────────────────────────────────────

@api_router.post("/assassinate")
async def assassinate(request: AssassinationRequest):
    require_auth(request.session_id, request.player_id, request.player_token)

    async with session_lock(request.session_id):
        session = await db.game_sessions.find_one({"id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        gs = GameSession(**session)
        if gs.phase != GamePhase.ASSASSINATION:
            raise HTTPException(status_code=400, detail="Not in assassination phase")

        assassin = next((p for p in gs.players if p.role == Role.ASSASSIN), None)
        if not assassin or assassin.id != request.player_id:
            raise HTTPException(status_code=400, detail="Only the assassin can perform assassination")

        target = next((p for p in gs.players if p.id == request.target_player_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Target player not found")

        if target.role == Role.MERLIN:
            gs.game_result = "evil"
            gs.evil_total_wins += 1
            gs.game_log.append(f"Assassination successful! {assassin.name} killed Merlin ({target.name}). Evil wins!")
        else:
            gs.game_result = "good"
            gs.good_total_wins += 1
            gs.game_log.append(f"Assassination failed! {assassin.name} targeted {target.name} ({target.role}). Good wins!")

        gs.phase = GamePhase.GAME_END
        await db.game_sessions.replace_one({"id": request.session_id}, gs.model_dump())

    await _broadcast(request.session_id)
    return {"success": target.role == Role.MERLIN, "target_name": target.name}

# ── Session queries ─────────────────────────────────────────────────────

@api_router.get("/session/{session_id}")
async def get_session(session_id: str):
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    gs = GameSession(**session)
    return {
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
                "id": p.id, "name": p.name, "is_leader": p.is_leader,
                "is_connected": p.is_connected, "is_bot": p.is_bot,
                "is_spectator": p.is_spectator,
                "role": p.role if gs.phase == GamePhase.GAME_END else None,
            }
            for p in gs.players
        ],
    }

@api_router.get("/session/{session_id}/me")
async def get_session_personalized(session_id: str, player_id: str, player_token: str):
    """Authenticated endpoint returning personalized state (role info, Lady knowledge).
    Used by the polling fallback when WebSocket is down."""
    require_auth(session_id, player_id, player_token)
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    gs = GameSession(**session)
    player = next((p for p in gs.players if p.id == player_id), None)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found in session")

    from websocket import _build_player_state
    return _build_player_state(gs, player)

# ── Lobby settings ──────────────────────────────────────────────────────

_TOGGLE_FIELDS = {
    "lady-of-lake": "lady_of_the_lake_enabled",
    "mordred": "mordred_enabled",
    "oberon": "oberon_enabled",
}

async def _toggle_setting(session_id: str, field: str, enabled: bool):
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    gs = GameSession(**session)
    if gs.phase != GamePhase.LOBBY:
        raise HTTPException(status_code=400, detail="Can only change settings in lobby")
    setattr(gs, field, enabled)
    await db.game_sessions.replace_one({"id": session_id}, gs.model_dump())
    await _broadcast(session_id)
    return {field: enabled}

@api_router.post("/toggle-lady-of-lake")
async def toggle_lady_of_lake(request: ToggleLadyOfLakeRequest):
    return await _toggle_setting(request.session_id, "lady_of_the_lake_enabled", request.enabled)

@api_router.post("/toggle-mordred")
async def toggle_mordred(request: ToggleMordredRequest):
    return await _toggle_setting(request.session_id, "mordred_enabled", request.enabled)

@api_router.post("/toggle-oberon")
async def toggle_oberon(request: ToggleOberonRequest):
    return await _toggle_setting(request.session_id, "oberon_enabled", request.enabled)

# ── Game lifecycle ──────────────────────────────────────────────────────

@api_router.post("/restart-game")
async def restart_game(request: RestartGameRequest):
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    gs = GameSession(**session)

    for player in gs.players:
        player.role = None
        player.is_leader = False
        player.lady_of_the_lake = False

    active_indices = [i for i, p in enumerate(gs.players) if not p.is_spectator]
    if active_indices:
        leader_idx = random.choice(active_indices)
        gs.current_leader = leader_idx
        gs.players[leader_idx].is_leader = True

    gs.phase = GamePhase.LOBBY
    gs.current_mission = 0
    gs.missions = []
    gs.vote_track = 0
    gs.lady_of_the_lake_holder = None
    gs.lady_of_the_lake_results = {}
    gs.game_result = None
    gs.good_wins = 0
    gs.evil_wins = 0
    gs.vote_history = []
    gs.game_log = []

    await db.game_sessions.replace_one({"id": request.session_id}, gs.model_dump())
    await _broadcast(request.session_id)
    return {"message": "Game restarted successfully"}

@api_router.post("/end-game")
async def end_game(request: RestartGameRequest):
    session = await db.game_sessions.find_one({"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    gs = GameSession(**session)
    gs.phase = GamePhase.GAME_END
    if not gs.game_result:
        gs.game_result = "ended"
    gs.game_log.append("Game ended manually - all roles revealed!")
    await db.game_sessions.replace_one({"id": request.session_id}, gs.model_dump())
    await _broadcast(request.session_id)
    return {"message": "Game ended successfully"}

async def _set_player_connected(session_id: str, player_id: str, connected: bool):
    """Update a player's is_connected flag in the DB and broadcast."""
    if not connected:
        # On disconnect, check if the player still has an active connection
        # (handles page refresh where new WS connects before old one closes)
        if session_id in manager.active_connections:
            if player_id in manager.active_connections[session_id]:
                return  # Player reconnected already, don't mark offline
    await db.game_sessions.update_one(
        {"id": session_id, "players.id": player_id},
        {"$set": {"players.$.is_connected": connected}},
    )
    await _broadcast(session_id)

# ── WebSocket ───────────────────────────────────────────────────────────

@app.websocket("/api/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, player_id: str = None):
    query_params = dict(websocket.query_params)
    player_id = query_params.get("player_id", player_id)

    doc = await _resolve_session(session_id)
    if doc:
        session_id = doc["id"]

    await manager.connect(websocket, session_id, player_id)
    # Mark player as connected
    if player_id:
        await _set_player_connected(session_id, player_id, True)
    try:
        await _broadcast(session_id)
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                if message.get("type") == "pong":
                    continue
                elif message.get("type") == "identify" and message.get("player_id"):
                    new_player_id = message["player_id"]
                    # Verify token before allowing identify
                    msg_token = message.get("player_token", "")
                    if not verify_token(session_id, new_player_id, msg_token):
                        await websocket.send_text(json.dumps({"type": "error", "detail": "Invalid token"}))
                        await websocket.close(1008, "Invalid token")
                        return
                    # Remap connection
                    if session_id in manager.active_connections:
                        old_id = None
                        for pid, ws in manager.active_connections[session_id].items():
                            if ws == websocket:
                                old_id = pid
                                break
                        if old_id and old_id != new_player_id:
                            del manager.active_connections[session_id][old_id]
                        manager.active_connections[session_id][new_player_id] = websocket
                    player_id = new_player_id
                    await _set_player_connected(session_id, player_id, True)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning("WebSocket message error: %s", e)
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, session_id, player_id)
        if player_id:
            await _set_player_connected(session_id, player_id, False)

# ── Mount router ────────────────────────────────────────────────────────

app.include_router(api_router)
