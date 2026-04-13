import random
from typing import List, Dict, Any

from models import (
    Player, Mission, GameSession, GamePhase, Role, MissionResult,
    ROLE_CONFIGS, MISSION_CONFIGS,
)


def assign_roles(players: List[Player], game_session: GameSession = None) -> List[Player]:
    """Assign roles to players based on player count and dynamic balancing."""
    player_count = len(players)
    if player_count < 5:
        raise ValueError(f"Invalid player count: {player_count}")

    if player_count not in ROLE_CONFIGS:
        closest_config = min(ROLE_CONFIGS.keys(), key=lambda x: abs(x - player_count))
        base_roles = ROLE_CONFIGS[closest_config].copy()
        while len(base_roles) < player_count:
            base_roles.append(Role.LOYAL_SERVANT)
        while len(base_roles) > player_count:
            if Role.LOYAL_SERVANT in base_roles:
                base_roles.remove(Role.LOYAL_SERVANT)
            else:
                base_roles.pop()
        roles = base_roles
    else:
        roles = ROLE_CONFIGS[player_count].copy()

    # Optional dynamic balancing for 7+ players
    if player_count >= 7 and game_session:
        total_games = game_session.good_total_wins + game_session.evil_total_wins
        if total_games >= 3:
            good_win_rate = game_session.good_total_wins / total_games
            if good_win_rate > 0.7 and game_session.mordred_enabled:
                if Role.MINION in roles and Role.MORDRED not in roles:
                    roles[roles.index(Role.MINION)] = Role.MORDRED
            elif good_win_rate < 0.3 and game_session.oberon_enabled:
                if Role.MINION in roles and Role.OBERON not in roles:
                    roles[roles.index(Role.MINION)] = Role.OBERON

    roles = roles[:player_count]
    random.shuffle(roles)

    for i, player in enumerate(players):
        player.role = roles[i]

    return players


def initialize_missions(player_count: int) -> List[Mission]:
    """Initialize missions based on player count."""
    if player_count not in MISSION_CONFIGS:
        raise ValueError(f"Invalid player count: {player_count}")

    return [
        Mission(number=i + 1, team_size=team_size, fails_required=fails_required)
        for i, (team_size, fails_required) in enumerate(MISSION_CONFIGS[player_count])
    ]


def get_role_info(player_role: Role, all_players: List[Player]) -> Dict[str, Any]:
    """Get role-specific information for a player."""
    is_good = player_role in (Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT)
    info: Dict[str, Any] = {
        "role": player_role,
        "team": "good" if is_good else "evil",
        "description": "",
        "sees": [],
    }

    active = [p for p in all_players if not p.is_spectator]

    if player_role == Role.MERLIN:
        info["description"] = "You can see all evil players except Mordred and Oberon"
        evil_visible = [p for p in active if p.role in (Role.MORGANA, Role.ASSASSIN, Role.MINION)]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_visible]

    elif player_role == Role.PERCIVAL:
        info["description"] = "You can see Merlin and Morgana, but don't know which is which"
        targets = [p for p in active if p.role in (Role.MERLIN, Role.MORGANA)]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "merlin_or_morgana"} for p in targets]

    elif player_role in (Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.MINION):
        descs = {
            Role.MORGANA: "You are evil and can see other evil players (except Oberon)",
            Role.ASSASSIN: "You are evil and can see other evil players (except Oberon). You can assassinate Merlin if good wins",
            Role.MORDRED: "You are evil and can see other evil players (except Oberon). You are hidden from Merlin",
            Role.MINION: "You are evil and can see other evil players (except Oberon)",
        }
        info["description"] = descs[player_role]
        evil_roles = {Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.MINION} - {player_role}
        evil_visible = [p for p in active if p.role in evil_roles]
        info["sees"] = [{"id": p.id, "name": p.name, "role": "evil"} for p in evil_visible]

    elif player_role == Role.OBERON:
        info["description"] = "You are evil but hidden from other evil players and Merlin"

    else:  # LOYAL_SERVANT
        info["description"] = "You are a loyal servant of Arthur. Trust in Merlin's guidance"

    return info


def advance_leader(game_session: GameSession) -> None:
    """Advance to the next leader among active players."""
    active_indices = [i for i, p in enumerate(game_session.players) if not p.is_spectator]
    if not active_indices:
        return

    # Safely find current leader's position
    try:
        current_pos = active_indices.index(game_session.current_leader)
    except ValueError:
        current_pos = 0

    next_pos = (current_pos + 1) % len(active_indices)
    game_session.current_leader = active_indices[next_pos]

    for player in game_session.players:
        player.is_leader = False
    game_session.players[game_session.current_leader].is_leader = True


def process_team_vote(game_session: GameSession) -> None:
    """Process the result of team voting. Mutates game_session in place."""
    current_mission = game_session.missions[game_session.current_mission]
    active_players = [p for p in game_session.players if not p.is_spectator]

    approve_count = sum(1 for p in active_players if current_mission.votes.get(p.id, False))
    total_votes = len(active_players)

    vote_record = {
        "type": "team_vote",
        "mission": current_mission.number,
        "votes": {p.name: current_mission.votes.get(p.id, None) for p in active_players},
        "result": "approved" if approve_count > total_votes // 2 else "rejected",
        "approve_count": approve_count,
        "total_votes": total_votes,
    }
    game_session.vote_history.append(vote_record)

    # Enter vote reveal phase — votes stay on mission for frontend to display.
    # advance_vote_reveal() is called after a delay to move to the real next phase.
    game_session.phase = GamePhase.VOTE_REVEAL
    if approve_count > total_votes // 2:
        current_mission.team_approved = True
        game_session.game_log.append(
            f"Mission {current_mission.number} team approved ({approve_count}/{total_votes} votes)"
        )
    else:
        game_session.game_log.append(
            f"Mission {current_mission.number} team rejected ({approve_count}/{total_votes} votes) - Vote track: {game_session.vote_track + 1}/5"
        )


def advance_vote_reveal(game_session: GameSession) -> None:
    """Advance from VOTE_REVEAL to the actual next phase. Called after reveal delay."""
    if game_session.phase != GamePhase.VOTE_REVEAL:
        return

    current_mission = game_session.missions[game_session.current_mission]

    if current_mission.team_approved:
        current_mission.mission_votes = {}
        game_session.phase = GamePhase.MISSION_EXECUTION
    else:
        game_session.vote_track += 1
        if game_session.vote_track >= 5:
            game_session.phase = GamePhase.GAME_END
            game_session.game_result = "evil"
            game_session.evil_total_wins += 1
            game_session.game_log.append("Evil wins! 5 teams rejected in a row.")
        else:
            advance_leader(game_session)
            game_session.phase = GamePhase.MISSION_TEAM_SELECTION
            current_mission.team_members = []
            current_mission.votes = {}


def process_mission_vote(game_session: GameSession) -> None:
    """Process the result of mission voting. Mutates game_session in place."""
    current_mission = game_session.missions[game_session.current_mission]

    fail_count = sum(1 for vote in current_mission.mission_votes.values() if not vote)
    success_count = len(current_mission.mission_votes) - fail_count

    if fail_count >= current_mission.fails_required:
        current_mission.result = MissionResult.FAIL
        game_session.evil_wins += 1
        game_session.evil_total_wins += 1
        game_session.game_log.append(
            f"Mission {current_mission.number} failed! ({fail_count} fail, {success_count} success votes)"
        )
    else:
        current_mission.result = MissionResult.SUCCESS
        game_session.good_wins += 1
        game_session.game_log.append(
            f"Mission {current_mission.number} succeeded! ({fail_count} fail, {success_count} success votes)"
        )

    # Pause to show result before advancing
    game_session.phase = GamePhase.MISSION_REVEAL


def advance_mission_reveal(game_session: GameSession) -> None:
    """Advance from MISSION_REVEAL to the actual next phase. Called after reveal delay."""
    if game_session.phase != GamePhase.MISSION_REVEAL:
        return

    if game_session.good_wins >= 3:
        game_session.phase = GamePhase.ASSASSINATION
        game_session.game_log.append("Good has completed 3 missions! Assassination phase begins.")
    elif game_session.evil_wins >= 3:
        game_session.phase = GamePhase.GAME_END
        game_session.game_result = "evil"
        game_session.game_log.append("Evil wins! 3 missions failed.")
    else:
        game_session.current_mission += 1
        game_session.vote_track = 0

        if (
            game_session.lady_of_the_lake_enabled
            and game_session.lady_of_the_lake_holder
            and game_session.current_mission in (2, 3, 4)
            and len([p for p in game_session.players if not p.is_spectator]) >= 7
        ):
            game_session.phase = GamePhase.LADY_OF_THE_LAKE
            game_session.game_log.append("Lady of the Lake phase begins!")
        else:
            game_session.phase = GamePhase.MISSION_TEAM_SELECTION

        advance_leader(game_session)


def initialize_game(game_session: GameSession, fill_bots: bool = False) -> None:
    """Shared initialization for start-game and start-test-game. Mutates in place."""
    active_players = [p for p in game_session.players if not p.is_spectator]

    if fill_bots:
        while len(active_players) < 5:
            bot = Player(name=f"Bot{len(game_session.players) + 1}", is_bot=True)
            game_session.players.append(bot)
            active_players.append(bot)

    # Assign roles only if not already assigned
    if not any(p.role for p in active_players):
        active_players = assign_roles(active_players, game_session)
        for i, player in enumerate(game_session.players):
            if not player.is_spectator:
                for ap in active_players:
                    if ap.id == player.id:
                        game_session.players[i] = ap
                        break

    game_session.missions = initialize_missions(len(active_players))
    game_session.phase = GamePhase.MISSION_TEAM_SELECTION

    # Random leader selection
    active_indices = [i for i, p in enumerate(game_session.players) if not p.is_spectator]
    leader_idx = random.choice(active_indices)
    for player in game_session.players:
        player.is_leader = False
    game_session.current_leader = leader_idx
    game_session.players[leader_idx].is_leader = True

    # Lady of the Lake
    if len(active_players) >= 7 and game_session.lady_of_the_lake_enabled:
        game_session.lady_of_the_lake_holder = game_session.players[leader_idx].id
        game_session.players[leader_idx].lady_of_the_lake = True
