import asyncio
import random
import logging
from typing import List

from models import GameSession, GamePhase, Role, MissionResult, Player
from game_logic import process_team_vote, process_mission_vote, advance_vote_reveal, advance_mission_reveal

logger = logging.getLogger(__name__)


async def bot_select_team(game_session: GameSession, bot_player: Player) -> List[str]:
    """Bot logic for selecting team members."""
    current_mission = game_session.missions[game_session.current_mission]
    team = [bot_player.id]
    others = [p.id for p in game_session.players if p.id != bot_player.id and not p.is_spectator]
    random.shuffle(others)
    team.extend(others[: current_mission.team_size - 1])
    return team


async def bot_vote_team(game_session: GameSession, bot_player: Player) -> bool:
    """Bot logic for voting on team proposals."""
    current_mission = game_session.missions[game_session.current_mission]
    is_evil = bot_player.role in (Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.MINION, Role.OBERON)
    if is_evil:
        weight = [True, False, False] if bot_player.id not in current_mission.team_members else [True, True, False]
    else:
        weight = [True, True, False]
    return random.choice(weight)


async def bot_vote_mission(game_session: GameSession, bot_player: Player) -> bool:
    """Bot logic for mission success/failure votes."""
    is_evil = bot_player.role in (Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.MINION, Role.OBERON)
    if is_evil:
        return random.choice([True, True, True, False, False])
    return True


async def process_bot_actions(session_id: str, db, session_lock, broadcast_fn):
    """Process pending bot actions for the current game phase.

    Parameters:
        session_id: The game session ID.
        db: The motor database instance.
        session_lock: An async context manager factory for per-session locking.
        broadcast_fn: An async callable to broadcast game state.
    """
    session = await db.game_sessions.find_one({"id": session_id})
    if not session:
        return

    game_session = GameSession(**session)

    # Guard against out-of-bounds mission index
    if game_session.current_mission >= len(game_session.missions):
        return

    # ── Team selection ──────────────────────────────────────────────
    if game_session.phase == GamePhase.MISSION_TEAM_SELECTION:
        if game_session.current_leader >= len(game_session.players):
            return
        current_leader = game_session.players[game_session.current_leader]
        if current_leader.is_bot and not current_leader.is_spectator:
            await asyncio.sleep(2)
            team = await bot_select_team(game_session, current_leader)
            current_mission = game_session.missions[game_session.current_mission]
            current_mission.team_members = team
            current_mission.votes = {}
            game_session.phase = GamePhase.MISSION_VOTING
            game_session.game_log.append(
                f"{current_leader.name} (bot) selected team: {[p.name for p in game_session.players if p.id in team]}"
            )
            await db.game_sessions.replace_one({"id": session_id}, game_session.dict())
            await broadcast_fn(session_id)

    # ── Team voting ─────────────────────────────────────────────────
    elif game_session.phase == GamePhase.MISSION_VOTING:
        for player in game_session.players:
            if player.is_bot and not player.is_spectator:
                await asyncio.sleep(1)
                async with session_lock(session_id):
                    fresh = await db.game_sessions.find_one({"id": session_id})
                    if not fresh:
                        return
                    fg = GameSession(**fresh)
                    if fg.phase != GamePhase.MISSION_VOTING:
                        return
                    fm = fg.missions[fg.current_mission]
                    if player.id in fm.votes:
                        continue
                    fm.votes[player.id] = await bot_vote_team(fg, player)
                    await db.game_sessions.replace_one({"id": session_id}, fg.dict())

        # Check if all voted
        async with session_lock(session_id):
            fresh = await db.game_sessions.find_one({"id": session_id})
            if fresh:
                fg = GameSession(**fresh)
                if fg.phase == GamePhase.MISSION_VOTING:
                    fm = fg.missions[fg.current_mission]
                    active = [p for p in fg.players if not p.is_spectator]
                    if len(fm.votes) == len(active):
                        process_team_vote(fg)
                        await db.game_sessions.replace_one({"id": session_id}, fg.dict())
                        await broadcast_fn(session_id)
                        # Auto-advance after vote reveal
                        async def _bot_advance_reveal():
                            await asyncio.sleep(5)
                            async with session_lock(session_id):
                                s = await db.game_sessions.find_one({"id": session_id})
                                if not s:
                                    return
                                g = GameSession(**s)
                                if g.phase != GamePhase.VOTE_REVEAL:
                                    return
                                advance_vote_reveal(g)
                                await db.game_sessions.replace_one({"id": session_id}, g.dict())
                            await broadcast_fn(session_id)
                            asyncio.create_task(process_bot_actions(session_id, db, session_lock, broadcast_fn))
                        asyncio.create_task(_bot_advance_reveal())

    # ── Mission execution ───────────────────────────────────────────
    elif game_session.phase == GamePhase.MISSION_EXECUTION:
        team_members = game_session.missions[game_session.current_mission].team_members
        for player in game_session.players:
            if player.is_bot and not player.is_spectator and player.id in team_members:
                await asyncio.sleep(1)
                async with session_lock(session_id):
                    fresh = await db.game_sessions.find_one({"id": session_id})
                    if not fresh:
                        return
                    fg = GameSession(**fresh)
                    if fg.phase != GamePhase.MISSION_EXECUTION:
                        return
                    fm = fg.missions[fg.current_mission]
                    if player.id in fm.mission_votes:
                        continue
                    fm.mission_votes[player.id] = await bot_vote_mission(fg, player)
                    await db.game_sessions.replace_one({"id": session_id}, fg.dict())

        async with session_lock(session_id):
            fresh = await db.game_sessions.find_one({"id": session_id})
            if fresh:
                fg = GameSession(**fresh)
                if fg.phase == GamePhase.MISSION_EXECUTION:
                    fm = fg.missions[fg.current_mission]
                    if len(fm.mission_votes) == len(fm.team_members):
                        process_mission_vote(fg)
                        await db.game_sessions.replace_one({"id": session_id}, fg.dict())
                        await broadcast_fn(session_id)
                        async def _bot_advance_mission():
                            await asyncio.sleep(5)
                            async with session_lock(session_id):
                                s = await db.game_sessions.find_one({"id": session_id})
                                if not s:
                                    return
                                g = GameSession(**s)
                                if g.phase != GamePhase.MISSION_REVEAL:
                                    return
                                advance_mission_reveal(g)
                                await db.game_sessions.replace_one({"id": session_id}, g.dict())
                            await broadcast_fn(session_id)
                            asyncio.create_task(process_bot_actions(session_id, db, session_lock, broadcast_fn))
                        asyncio.create_task(_bot_advance_mission())

    # ── Assassination ───────────────────────────────────────────────
    elif game_session.phase == GamePhase.ASSASSINATION:
        assassin = next((p for p in game_session.players if p.role == Role.ASSASSIN), None)
        if assassin and assassin.is_bot:
            await asyncio.sleep(3)
            good_players = [p for p in game_session.players if p.role in (Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT)]
            if good_players:
                target = random.choice(good_players)
                if target.role == Role.MERLIN:
                    game_session.game_result = "evil"
                    game_session.evil_total_wins += 1
                    game_session.game_log.append(
                        f"Assassination successful! {assassin.name} (bot) killed Merlin ({target.name}). Evil wins!"
                    )
                else:
                    game_session.game_result = "good"
                    game_session.good_total_wins += 1
                    game_session.game_log.append(
                        f"Assassination failed! {assassin.name} (bot) killed {target.name} ({target.role}). Good wins!"
                    )
                game_session.phase = GamePhase.GAME_END
                await db.game_sessions.replace_one({"id": session_id}, game_session.dict())
                await broadcast_fn(session_id)

    # ── Lady of the Lake (bot holder) ───────────────────────────────
    elif game_session.phase == GamePhase.LADY_OF_THE_LAKE:
        holder = next((p for p in game_session.players if p.lady_of_the_lake), None)
        if holder and holder.is_bot:
            await asyncio.sleep(2)
            targets = [p for p in game_session.players if p.id != holder.id and not p.is_spectator]
            if targets:
                target = random.choice(targets)
                allegiance = "good" if target.role in (Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT) else "evil"
                if holder.id not in game_session.lady_of_the_lake_results:
                    game_session.lady_of_the_lake_results[holder.id] = {}
                game_session.lady_of_the_lake_results[holder.id][target.id] = allegiance
                holder.lady_of_the_lake = False
                target.lady_of_the_lake = True
                game_session.lady_of_the_lake_holder = target.id
                game_session.phase = GamePhase.MISSION_TEAM_SELECTION
                game_session.game_log.append(f"{holder.name} (bot) used Lady of the Lake on {target.name}")
                await db.game_sessions.replace_one({"id": session_id}, game_session.dict())
                await broadcast_fn(session_id)
                asyncio.create_task(process_bot_actions(session_id, db, session_lock, broadcast_fn))
