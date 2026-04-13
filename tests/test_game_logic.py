"""
Comprehensive unit tests for backend/game_logic.py.

These are pure function tests -- no database, no network, no server required.
Run with: pytest tests/test_game_logic.py -v
"""

import sys
import os
from collections import Counter
from copy import deepcopy

import pytest

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models import (
    Player, Mission, GameSession, GamePhase, Role, MissionResult,
    ROLE_CONFIGS, MISSION_CONFIGS,
)
from game_logic import (
    assign_roles,
    initialize_missions,
    get_role_info,
    process_team_vote,
    advance_vote_reveal,
    process_mission_vote,
    advance_mission_reveal,
    advance_leader,
    initialize_game,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GOOD_ROLES = {Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT}
EVIL_ROLES = {Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.OBERON, Role.MINION}


def make_players(n: int, **overrides) -> list[Player]:
    """Create *n* basic players with sequential names."""
    return [Player(name=f"Player{i+1}", **overrides) for i in range(n)]


def make_session(
    n_players: int = 5,
    *,
    phase: GamePhase = GamePhase.LOBBY,
    current_mission: int = 0,
    vote_track: int = 0,
    good_wins: int = 0,
    evil_wins: int = 0,
    good_total_wins: int = 0,
    evil_total_wins: int = 0,
    lady_of_the_lake_enabled: bool = True,
    lady_of_the_lake_holder: str | None = None,
    mordred_enabled: bool = True,
    oberon_enabled: bool = True,
    extra_spectators: int = 0,
) -> GameSession:
    """Build a GameSession pre-populated with *n_players* active players."""
    players = make_players(n_players)
    for _ in range(extra_spectators):
        players.append(Player(name=f"Spectator{_+1}", is_spectator=True))
    gs = GameSession(
        name="TestSession",
        players=players,
        phase=phase,
        current_mission=current_mission,
        vote_track=vote_track,
        good_wins=good_wins,
        evil_wins=evil_wins,
        good_total_wins=good_total_wins,
        evil_total_wins=evil_total_wins,
        lady_of_the_lake_enabled=lady_of_the_lake_enabled,
        lady_of_the_lake_holder=lady_of_the_lake_holder,
        mordred_enabled=mordred_enabled,
        oberon_enabled=oberon_enabled,
    )
    return gs


def assign_specific_roles(players: list[Player], roles: list[Role]) -> None:
    """Manually assign roles to players for deterministic tests."""
    for p, r in zip(players, roles):
        p.role = r


def setup_mission_with_votes(
    gs: GameSession, mission_idx: int, team_ids: list[str], votes: dict[str, bool]
) -> None:
    """Set up a mission with team and votes ready for process_team_vote."""
    mission = gs.missions[mission_idx]
    mission.team_members = team_ids
    mission.votes = votes


# ===========================================================================
# 1. assign_roles
# ===========================================================================

class TestAssignRoles:
    """Tests for assign_roles()."""

    # -- correct counts for every supported player count ----

    @pytest.mark.parametrize(
        "count,expected_good,expected_evil",
        [
            (5, 3, 2),
            (6, 4, 2),
            (7, 4, 3),
            (8, 5, 3),
            (9, 6, 3),
            (10, 6, 4),
        ],
    )
    def test_good_evil_ratio(self, count, expected_good, expected_evil):
        players = make_players(count)
        assign_roles(players)
        good = sum(1 for p in players if p.role in GOOD_ROLES)
        evil = sum(1 for p in players if p.role in EVIL_ROLES)
        assert good == expected_good, f"Expected {expected_good} good, got {good}"
        assert evil == expected_evil, f"Expected {expected_evil} evil, got {evil}"

    @pytest.mark.parametrize("count", [5, 6, 7, 8, 9, 10])
    def test_every_player_gets_a_role(self, count):
        players = make_players(count)
        assign_roles(players)
        for p in players:
            assert p.role is not None

    def test_raises_for_fewer_than_five(self):
        with pytest.raises(ValueError, match="Invalid player count"):
            assign_roles(make_players(4))

    def test_raises_for_one_player(self):
        with pytest.raises(ValueError):
            assign_roles(make_players(1))

    def test_raises_for_zero_players(self):
        with pytest.raises(ValueError):
            assign_roles([])

    @pytest.mark.parametrize("count", [5, 6, 7, 8, 9, 10])
    def test_always_has_merlin_and_assassin(self, count):
        players = make_players(count)
        assign_roles(players)
        roles = [p.role for p in players]
        assert Role.MERLIN in roles
        assert Role.ASSASSIN in roles

    @pytest.mark.parametrize("count", [5, 6, 7, 8, 9, 10])
    def test_role_count_matches_player_count(self, count):
        players = make_players(count)
        assign_roles(players)
        assert all(p.role is not None for p in players)
        assert len(players) == count

    # -- specific compositions per player count ----

    def test_5p_composition(self):
        players = make_players(5)
        assign_roles(players)
        roles = Counter(p.role for p in players)
        assert roles[Role.MERLIN] == 1
        assert roles[Role.PERCIVAL] == 1
        assert roles[Role.LOYAL_SERVANT] == 1
        assert roles[Role.MORGANA] == 1
        assert roles[Role.ASSASSIN] == 1

    def test_7p_has_oberon(self):
        players = make_players(7)
        assign_roles(players)
        roles = [p.role for p in players]
        assert Role.OBERON in roles

    def test_9p_has_mordred(self):
        players = make_players(9)
        assign_roles(players)
        roles = [p.role for p in players]
        assert Role.MORDRED in roles

    def test_10p_has_mordred_and_oberon(self):
        players = make_players(10)
        assign_roles(players)
        roles = [p.role for p in players]
        assert Role.MORDRED in roles
        assert Role.OBERON in roles

    # -- dynamic balancing ----

    def test_dynamic_balancing_replaces_minion_with_mordred_when_good_dominant(self):
        """When good_win_rate > 0.7 and mordred_enabled, a Minion should become Mordred."""
        gs = make_session(
            8,
            good_total_wins=8,
            evil_total_wins=1,
            mordred_enabled=True,
        )
        # 8-player default has a MINION and no MORDRED
        players = [p for p in gs.players if not p.is_spectator]
        assign_roles(players, gs)
        roles = [p.role for p in players]
        assert Role.MORDRED in roles, "Mordred should replace Minion when good dominates"

    def test_dynamic_balancing_replaces_minion_with_oberon_when_evil_dominant(self):
        """When good_win_rate < 0.3 and oberon_enabled, a Minion should become Oberon."""
        gs = make_session(
            8,
            good_total_wins=1,
            evil_total_wins=8,
            oberon_enabled=True,
        )
        players = [p for p in gs.players if not p.is_spectator]
        assign_roles(players, gs)
        roles = [p.role for p in players]
        assert Role.OBERON in roles, "Oberon should replace Minion when evil dominates"

    def test_dynamic_balancing_not_triggered_under_3_games(self):
        """Balancing should not kick in when total games < 3."""
        gs = make_session(
            8,
            good_total_wins=2,
            evil_total_wins=0,  # 100% good win rate but only 2 games
            mordred_enabled=True,
        )
        players = [p for p in gs.players if not p.is_spectator]
        assign_roles(players, gs)
        roles = [p.role for p in players]
        # 8-player base config has MINION, not MORDRED
        assert Role.MINION in roles, "Balancing should not trigger with < 3 total games"

    def test_dynamic_balancing_skipped_under_7_players(self):
        """Balancing only kicks in at 7+ players."""
        gs = make_session(
            6,
            good_total_wins=8,
            evil_total_wins=1,
            mordred_enabled=True,
        )
        players = [p for p in gs.players if not p.is_spectator]
        assign_roles(players, gs)
        roles = [p.role for p in players]
        # 6-player config has no MINION and no MORDRED -- should stay unchanged
        assert Role.MORDRED not in roles

    def test_dynamic_balancing_no_session_object(self):
        """If game_session is None, no balancing happens (no crash)."""
        players = make_players(8)
        assign_roles(players, None)
        # Should work without error; no assertion on specific roles since it's random


# ===========================================================================
# 2. initialize_missions
# ===========================================================================

class TestInitializeMissions:

    @pytest.mark.parametrize("count", [5, 6, 7, 8, 9, 10])
    def test_returns_five_missions(self, count):
        missions = initialize_missions(count)
        assert len(missions) == 5

    @pytest.mark.parametrize("count", [5, 6, 7, 8, 9, 10])
    def test_mission_numbers_are_sequential(self, count):
        missions = initialize_missions(count)
        assert [m.number for m in missions] == [1, 2, 3, 4, 5]

    @pytest.mark.parametrize(
        "count,expected_team_sizes",
        [
            (5, [2, 3, 2, 3, 3]),
            (6, [2, 3, 4, 3, 4]),
            (7, [2, 3, 3, 4, 4]),
            (8, [3, 4, 4, 5, 5]),
            (9, [3, 4, 4, 5, 5]),
            (10, [3, 4, 4, 5, 5]),
        ],
    )
    def test_team_sizes(self, count, expected_team_sizes):
        missions = initialize_missions(count)
        actual = [m.team_size for m in missions]
        assert actual == expected_team_sizes

    @pytest.mark.parametrize("count", [7, 8, 9, 10])
    def test_mission_4_requires_2_fails_for_7_plus(self, count):
        missions = initialize_missions(count)
        assert missions[3].fails_required == 2, (
            f"Mission 4 for {count} players should require 2 fails"
        )

    @pytest.mark.parametrize("count", [5, 6])
    def test_mission_4_requires_1_fail_for_under_7(self, count):
        missions = initialize_missions(count)
        assert missions[3].fails_required == 1

    def test_all_missions_start_pending(self):
        for count in range(5, 11):
            for m in initialize_missions(count):
                assert m.result == MissionResult.PENDING

    def test_raises_for_invalid_count(self):
        with pytest.raises(ValueError, match="Invalid player count"):
            initialize_missions(4)

    def test_raises_for_11_players(self):
        with pytest.raises(ValueError):
            initialize_missions(11)


# ===========================================================================
# 3. get_role_info
# ===========================================================================

class TestGetRoleInfo:

    def _make_full_cast(self) -> list[Player]:
        """Create a deterministic 10-player game with all roles represented."""
        roles = [
            Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
            Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
            Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.OBERON,
        ]
        players = make_players(10)
        assign_specific_roles(players, roles)
        return players

    # -- Merlin ----

    def test_merlin_sees_morgana_assassin_minion(self):
        """Merlin sees Morgana, Assassin, and Minion as evil."""
        roles = [
            Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT,
            Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
            Role.MORGANA, Role.ASSASSIN, Role.MINION,
        ]
        players = make_players(8)
        assign_specific_roles(players, roles)

        info = get_role_info(Role.MERLIN, players)
        seen_names = {s["name"] for s in info["sees"]}

        # Morgana = Player6, Assassin = Player7, Minion = Player8
        assert "Player6" in seen_names  # Morgana
        assert "Player7" in seen_names  # Assassin
        assert "Player8" in seen_names  # Minion

    def test_merlin_does_not_see_mordred(self):
        players = self._make_full_cast()
        info = get_role_info(Role.MERLIN, players)
        seen_ids = {s["id"] for s in info["sees"]}
        mordred_player = next(p for p in players if p.role == Role.MORDRED)
        assert mordred_player.id not in seen_ids

    def test_merlin_does_not_see_oberon(self):
        players = self._make_full_cast()
        info = get_role_info(Role.MERLIN, players)
        seen_ids = {s["id"] for s in info["sees"]}
        oberon_player = next(p for p in players if p.role == Role.OBERON)
        assert oberon_player.id not in seen_ids

    def test_merlin_team_is_good(self):
        players = self._make_full_cast()
        info = get_role_info(Role.MERLIN, players)
        assert info["team"] == "good"

    def test_merlin_sees_entries_labeled_evil(self):
        players = self._make_full_cast()
        info = get_role_info(Role.MERLIN, players)
        for entry in info["sees"]:
            assert entry["role"] == "evil"

    # -- Percival ----

    def test_percival_sees_merlin_and_morgana(self):
        players = self._make_full_cast()
        info = get_role_info(Role.PERCIVAL, players)
        seen_ids = {s["id"] for s in info["sees"]}
        merlin_id = next(p.id for p in players if p.role == Role.MERLIN)
        morgana_id = next(p.id for p in players if p.role == Role.MORGANA)
        assert merlin_id in seen_ids
        assert morgana_id in seen_ids

    def test_percival_sees_both_as_merlin_or_morgana(self):
        players = self._make_full_cast()
        info = get_role_info(Role.PERCIVAL, players)
        for entry in info["sees"]:
            assert entry["role"] == "merlin_or_morgana"

    def test_percival_sees_exactly_two(self):
        players = self._make_full_cast()
        info = get_role_info(Role.PERCIVAL, players)
        assert len(info["sees"]) == 2

    def test_percival_team_is_good(self):
        players = self._make_full_cast()
        info = get_role_info(Role.PERCIVAL, players)
        assert info["team"] == "good"

    # -- Evil players see each other (except Oberon) ----

    def test_morgana_sees_other_evil_not_oberon(self):
        players = self._make_full_cast()
        info = get_role_info(Role.MORGANA, players)
        seen_ids = {s["id"] for s in info["sees"]}

        assassin_id = next(p.id for p in players if p.role == Role.ASSASSIN)
        mordred_id = next(p.id for p in players if p.role == Role.MORDRED)
        oberon_id = next(p.id for p in players if p.role == Role.OBERON)

        assert assassin_id in seen_ids
        assert mordred_id in seen_ids
        assert oberon_id not in seen_ids

    def test_assassin_sees_other_evil_not_oberon(self):
        players = self._make_full_cast()
        info = get_role_info(Role.ASSASSIN, players)
        seen_ids = {s["id"] for s in info["sees"]}

        morgana_id = next(p.id for p in players if p.role == Role.MORGANA)
        mordred_id = next(p.id for p in players if p.role == Role.MORDRED)
        oberon_id = next(p.id for p in players if p.role == Role.OBERON)

        assert morgana_id in seen_ids
        assert mordred_id in seen_ids
        assert oberon_id not in seen_ids

    def test_mordred_sees_other_evil_not_oberon(self):
        players = self._make_full_cast()
        info = get_role_info(Role.MORDRED, players)
        seen_ids = {s["id"] for s in info["sees"]}

        morgana_id = next(p.id for p in players if p.role == Role.MORGANA)
        assassin_id = next(p.id for p in players if p.role == Role.ASSASSIN)
        oberon_id = next(p.id for p in players if p.role == Role.OBERON)

        assert morgana_id in seen_ids
        assert assassin_id in seen_ids
        assert oberon_id not in seen_ids

    def test_evil_player_does_not_see_self(self):
        players = self._make_full_cast()
        info = get_role_info(Role.MORGANA, players)
        morgana_id = next(p.id for p in players if p.role == Role.MORGANA)
        seen_ids = {s["id"] for s in info["sees"]}
        assert morgana_id not in seen_ids

    def test_evil_team_label(self):
        for role in (Role.MORGANA, Role.ASSASSIN, Role.MORDRED, Role.OBERON, Role.MINION):
            players = self._make_full_cast()
            info = get_role_info(role, players)
            assert info["team"] == "evil"

    # -- Oberon ----

    def test_oberon_sees_nobody(self):
        players = self._make_full_cast()
        info = get_role_info(Role.OBERON, players)
        assert info["sees"] == []

    # -- Loyal Servant ----

    def test_loyal_servant_sees_nobody(self):
        players = self._make_full_cast()
        info = get_role_info(Role.LOYAL_SERVANT, players)
        assert info["sees"] == []

    def test_loyal_servant_team_is_good(self):
        players = self._make_full_cast()
        info = get_role_info(Role.LOYAL_SERVANT, players)
        assert info["team"] == "good"

    # -- Spectators are excluded from visibility ----

    def test_spectator_evil_not_visible_to_merlin(self):
        """A spectator who has an evil role should not appear in Merlin's vision."""
        players = make_players(6)
        assign_specific_roles(
            players,
            [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT,
             Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN],
        )
        # Make the Assassin (Player6) a spectator
        players[5].is_spectator = True
        info = get_role_info(Role.MERLIN, players)
        seen_ids = {s["id"] for s in info["sees"]}
        assert players[5].id not in seen_ids

    # -- Minion ----

    def test_minion_sees_other_evil(self):
        roles = [
            Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT,
            Role.LOYAL_SERVANT, Role.LOYAL_SERVANT,
            Role.MORGANA, Role.ASSASSIN, Role.MINION,
        ]
        players = make_players(8)
        assign_specific_roles(players, roles)
        info = get_role_info(Role.MINION, players)
        seen_ids = {s["id"] for s in info["sees"]}
        morgana_id = next(p.id for p in players if p.role == Role.MORGANA)
        assassin_id = next(p.id for p in players if p.role == Role.ASSASSIN)
        assert morgana_id in seen_ids
        assert assassin_id in seen_ids


# ===========================================================================
# 4. process_team_vote
# ===========================================================================

class TestProcessTeamVote:

    def _make_voting_session(
        self, n_players: int = 5, approve_ids: list[str] | None = None
    ) -> GameSession:
        """Build a session in MISSION_VOTING phase with missions initialized."""
        gs = make_session(n_players, phase=GamePhase.MISSION_VOTING)
        gs.missions = initialize_missions(n_players)
        gs.current_mission = 0
        active = [p for p in gs.players if not p.is_spectator]

        # Default: nobody votes approve unless specified
        votes = {}
        for p in active:
            votes[p.id] = p.id in (approve_ids or [])
        gs.missions[0].votes = votes
        gs.missions[0].team_members = [active[0].id, active[1].id]
        gs.current_leader = 0
        gs.players[0].is_leader = True
        return gs

    def test_majority_approve_enters_vote_reveal(self):
        gs = self._make_voting_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        approve_ids = [active[0].id, active[1].id, active[2].id]
        gs.missions[0].votes = {p.id: p.id in approve_ids for p in active}

        process_team_vote(gs)

        assert gs.phase == GamePhase.VOTE_REVEAL
        assert gs.missions[0].team_approved is True

    def test_approve_advance_reveal_moves_to_execution(self):
        gs = self._make_voting_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        approve_ids = [active[0].id, active[1].id, active[2].id]
        gs.missions[0].votes = {p.id: p.id in approve_ids for p in active}

        process_team_vote(gs)
        advance_vote_reveal(gs)

        assert gs.phase == GamePhase.MISSION_EXECUTION

    def test_majority_reject_enters_vote_reveal(self):
        gs = self._make_voting_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        approve_ids = [active[0].id, active[1].id]
        gs.missions[0].votes = {p.id: p.id in approve_ids for p in active}

        process_team_vote(gs)

        assert gs.phase == GamePhase.VOTE_REVEAL

    def test_reject_advance_reveal_increments_vote_track(self):
        gs = self._make_voting_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        approve_ids = [active[0].id, active[1].id]
        gs.missions[0].votes = {p.id: p.id in approve_ids for p in active}

        process_team_vote(gs)
        advance_vote_reveal(gs)

        assert gs.vote_track == 1
        assert gs.phase == GamePhase.MISSION_TEAM_SELECTION

    def test_tie_is_rejected(self):
        """A tie (e.g. 3 approve out of 6) should count as rejected."""
        gs = self._make_voting_session(6)
        active = [p for p in gs.players if not p.is_spectator]
        approve_ids = [active[0].id, active[1].id, active[2].id]
        gs.missions[0].votes = {p.id: p.id in approve_ids for p in active}

        process_team_vote(gs)
        advance_vote_reveal(gs)

        assert gs.vote_track == 1
        assert gs.phase == GamePhase.MISSION_TEAM_SELECTION

    def test_exact_majority_approves(self):
        """Just over half (4 of 6) should approve."""
        gs = self._make_voting_session(6)
        active = [p for p in gs.players if not p.is_spectator]
        approve_ids = [active[0].id, active[1].id, active[2].id, active[3].id]
        gs.missions[0].votes = {p.id: p.id in approve_ids for p in active}

        process_team_vote(gs)
        advance_vote_reveal(gs)

        assert gs.phase == GamePhase.MISSION_EXECUTION

    def test_5th_rejection_evil_wins(self):
        gs = self._make_voting_session(5)
        gs.vote_track = 4  # Already had 4 rejections
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].votes = {p.id: False for p in active}

        process_team_vote(gs)
        advance_vote_reveal(gs)

        assert gs.vote_track == 5
        assert gs.phase == GamePhase.GAME_END
        assert gs.game_result == "evil"
        assert gs.evil_total_wins == 1

    def test_vote_track_not_incremented_during_reveal(self):
        """process_team_vote sets VOTE_REVEAL; vote_track incremented in advance_vote_reveal."""
        gs = self._make_voting_session(5)
        gs.vote_track = 2
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].votes = {p.id: False for p in active}

        process_team_vote(gs)
        assert gs.vote_track == 2  # Not yet incremented
        advance_vote_reveal(gs)
        assert gs.vote_track == 3

    def test_rejection_advances_leader_after_reveal(self):
        gs = self._make_voting_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].votes = {p.id: False for p in active}
        original_leader = gs.current_leader

        process_team_vote(gs)
        advance_vote_reveal(gs)

        assert gs.current_leader != original_leader

    def test_rejection_clears_team_and_votes_after_reveal(self):
        gs = self._make_voting_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].votes = {p.id: False for p in active}

        process_team_vote(gs)
        # Votes still visible during reveal
        assert gs.missions[0].votes != {}
        advance_vote_reveal(gs)
        # Cleared after reveal
        assert gs.missions[0].team_members == []
        assert gs.missions[0].votes == {}

    def test_vote_history_recorded(self):
        gs = self._make_voting_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].votes = {p.id: True for p in active}

        process_team_vote(gs)

        assert len(gs.vote_history) == 1
        record = gs.vote_history[0]
        assert record["type"] == "team_vote"
        assert record["result"] == "approved"
        assert record["approve_count"] == 5

    def test_game_log_on_approval(self):
        gs = self._make_voting_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].votes = {p.id: True for p in active}

        process_team_vote(gs)

        assert any("approved" in entry for entry in gs.game_log)

    def test_game_log_on_rejection(self):
        gs = self._make_voting_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].votes = {p.id: False for p in active}

        process_team_vote(gs)

        assert any("rejected" in entry for entry in gs.game_log)


# ===========================================================================
# 5. process_mission_vote
# ===========================================================================

class TestProcessMissionVote:

    def _make_mission_session(
        self,
        n_players: int = 5,
        mission_votes: dict[str, bool] | None = None,
        current_mission: int = 0,
        good_wins: int = 0,
        evil_wins: int = 0,
        lady_of_the_lake_enabled: bool = False,
        lady_of_the_lake_holder: str | None = None,
    ) -> GameSession:
        gs = make_session(
            n_players,
            phase=GamePhase.MISSION_EXECUTION,
            current_mission=current_mission,
            good_wins=good_wins,
            evil_wins=evil_wins,
            lady_of_the_lake_enabled=lady_of_the_lake_enabled,
            lady_of_the_lake_holder=lady_of_the_lake_holder,
        )
        gs.missions = initialize_missions(n_players)
        if mission_votes is not None:
            gs.missions[current_mission].mission_votes = mission_votes
        return gs

    def test_all_success_mission_succeeds(self):
        gs = self._make_mission_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: True}

        process_mission_vote(gs)

        assert gs.missions[0].result == MissionResult.SUCCESS
        assert gs.good_wins == 1

    def test_one_fail_mission_fails(self):
        gs = self._make_mission_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: False}

        process_mission_vote(gs)

        assert gs.missions[0].result == MissionResult.FAIL
        assert gs.evil_wins == 1

    def test_mission_needing_2_fails_succeeds_with_1_fail(self):
        """For 7+ players, mission 4 needs 2 fails. One fail should still succeed."""
        gs = self._make_mission_session(7, current_mission=3)
        active = [p for p in gs.players if not p.is_spectator]
        # Mission 4 for 7p has team_size=4, fails_required=2
        gs.missions[3].mission_votes = {
            active[0].id: True,
            active[1].id: True,
            active[2].id: True,
            active[3].id: False,  # Only 1 fail
        }

        process_mission_vote(gs)

        assert gs.missions[3].result == MissionResult.SUCCESS

    def test_mission_needing_2_fails_fails_with_2(self):
        gs = self._make_mission_session(7, current_mission=3)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[3].mission_votes = {
            active[0].id: True,
            active[1].id: True,
            active[2].id: False,
            active[3].id: False,  # 2 fails
        }

        process_mission_vote(gs)

        assert gs.missions[3].result == MissionResult.FAIL

    def test_mission_vote_enters_mission_reveal(self):
        gs = self._make_mission_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: True}

        process_mission_vote(gs)

        assert gs.phase == GamePhase.MISSION_REVEAL

    def test_3_good_wins_triggers_assassination(self):
        gs = self._make_mission_session(5, good_wins=2)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.good_wins == 3
        assert gs.phase == GamePhase.ASSASSINATION

    def test_3_evil_wins_triggers_game_end(self):
        gs = self._make_mission_session(5, evil_wins=2)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: False}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.evil_wins == 3
        assert gs.phase == GamePhase.GAME_END
        assert gs.game_result == "evil"

    def test_mission_increments_current_mission_on_continue(self):
        gs = self._make_mission_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.current_mission == 1

    def test_vote_track_resets_after_mission(self):
        gs = self._make_mission_session(5)
        gs.vote_track = 3
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.vote_track == 0

    def test_evil_total_wins_incremented_on_fail(self):
        gs = self._make_mission_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: False}

        process_mission_vote(gs)

        assert gs.evil_total_wins == 1

    def test_leader_advances_after_mission(self):
        gs = self._make_mission_session(5)
        gs.current_leader = 0
        gs.players[0].is_leader = True
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.current_leader == 1

    # -- Lady of the Lake ----

    def test_lady_of_the_lake_triggers_after_mission_2(self):
        """LotL should trigger when current_mission becomes 2 (after completing mission index 1)."""
        gs = self._make_mission_session(
            7, current_mission=1, lady_of_the_lake_enabled=True, lady_of_the_lake_holder="some-player-id",
        )
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[1].mission_votes = {active[0].id: True, active[1].id: True, active[2].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.current_mission == 2
        assert gs.phase == GamePhase.LADY_OF_THE_LAKE

    def test_lady_of_the_lake_triggers_after_mission_3(self):
        gs = self._make_mission_session(
            7, current_mission=2, good_wins=1, lady_of_the_lake_enabled=True, lady_of_the_lake_holder="some-player-id",
        )
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[2].mission_votes = {active[0].id: True, active[1].id: True, active[2].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.current_mission == 3
        assert gs.phase == GamePhase.LADY_OF_THE_LAKE

    def test_lady_of_the_lake_triggers_after_mission_4(self):
        gs = self._make_mission_session(
            7, current_mission=3, good_wins=1, evil_wins=1, lady_of_the_lake_enabled=True, lady_of_the_lake_holder="some-player-id",
        )
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[3].mission_votes = {active[0].id: True, active[1].id: True, active[2].id: True, active[3].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.current_mission == 4
        assert gs.phase == GamePhase.LADY_OF_THE_LAKE

    def test_lady_of_the_lake_not_triggered_under_7_players(self):
        gs = self._make_mission_session(5, current_mission=1, lady_of_the_lake_enabled=True, lady_of_the_lake_holder="some-player-id")
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[1].mission_votes = {active[0].id: True, active[1].id: True, active[2].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.phase == GamePhase.MISSION_TEAM_SELECTION

    def test_lady_of_the_lake_not_triggered_when_disabled(self):
        gs = self._make_mission_session(7, current_mission=1, lady_of_the_lake_enabled=False)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[1].mission_votes = {active[0].id: True, active[1].id: True, active[2].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.phase == GamePhase.MISSION_TEAM_SELECTION

    def test_lady_of_the_lake_not_triggered_without_holder(self):
        gs = self._make_mission_session(7, current_mission=1, lady_of_the_lake_enabled=True, lady_of_the_lake_holder=None)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[1].mission_votes = {active[0].id: True, active[1].id: True, active[2].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.phase == GamePhase.MISSION_TEAM_SELECTION

    def test_lady_of_the_lake_not_triggered_on_mission_1_or_5(self):
        gs = self._make_mission_session(7, current_mission=0, lady_of_the_lake_enabled=True, lady_of_the_lake_holder="some-player-id")
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: True}

        process_mission_vote(gs)
        advance_mission_reveal(gs)

        assert gs.phase == GamePhase.MISSION_TEAM_SELECTION

    def test_game_log_on_success(self):
        gs = self._make_mission_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: True}

        process_mission_vote(gs)

        assert any("succeeded" in entry for entry in gs.game_log)

    def test_game_log_on_fail(self):
        gs = self._make_mission_session(5)
        active = [p for p in gs.players if not p.is_spectator]
        gs.missions[0].mission_votes = {active[0].id: True, active[1].id: False}

        process_mission_vote(gs)

        assert any("failed" in entry for entry in gs.game_log)


# ===========================================================================
# 6. advance_leader
# ===========================================================================

class TestAdvanceLeader:

    def test_basic_advance(self):
        gs = make_session(5)
        gs.current_leader = 0
        gs.players[0].is_leader = True

        advance_leader(gs)

        assert gs.current_leader == 1
        assert gs.players[1].is_leader is True
        assert gs.players[0].is_leader is False

    def test_wraps_around(self):
        gs = make_session(5)
        gs.current_leader = 4
        gs.players[4].is_leader = True

        advance_leader(gs)

        assert gs.current_leader == 0
        assert gs.players[0].is_leader is True

    def test_skips_spectators(self):
        gs = make_session(5, extra_spectators=0)
        # Make Player2 (index 1) a spectator
        gs.players[1].is_spectator = True
        gs.current_leader = 0
        gs.players[0].is_leader = True

        advance_leader(gs)

        # Should skip index 1 (spectator) and go to index 2
        assert gs.current_leader == 2

    def test_skips_multiple_spectators(self):
        gs = make_session(5)
        gs.players[1].is_spectator = True
        gs.players[2].is_spectator = True
        gs.current_leader = 0
        gs.players[0].is_leader = True

        advance_leader(gs)

        assert gs.current_leader == 3

    def test_wraps_around_skipping_spectators(self):
        gs = make_session(5)
        gs.players[0].is_spectator = True  # spectator
        gs.current_leader = 4
        gs.players[4].is_leader = True

        advance_leader(gs)

        # Should skip 0 (spectator) and land on 1
        assert gs.current_leader == 1

    def test_current_leader_out_of_range_defaults_to_first_active(self):
        """If current_leader index is not in active_indices, falls back gracefully."""
        gs = make_session(5)
        gs.players[2].is_spectator = True
        gs.current_leader = 2  # This is now a spectator, so not in active_indices

        advance_leader(gs)

        # ValueError caught internally, current_pos becomes 0, next_pos becomes 1
        # active_indices = [0, 1, 3, 4], pos 0 is index 0, next is index 1
        assert gs.current_leader == 1

    def test_no_active_players_noop(self):
        """If all players are spectators, advance_leader returns without change."""
        gs = make_session(3)
        for p in gs.players:
            p.is_spectator = True
        gs.current_leader = 0

        advance_leader(gs)

        # Should not crash; leader stays at 0
        assert gs.current_leader == 0

    def test_only_one_active_player(self):
        gs = make_session(3)
        gs.players[0].is_spectator = True
        gs.players[2].is_spectator = True
        gs.current_leader = 1
        gs.players[1].is_leader = True

        advance_leader(gs)

        # Only one active player, wraps back to self
        assert gs.current_leader == 1

    def test_leader_flag_set_correctly(self):
        gs = make_session(5)
        gs.current_leader = 2
        gs.players[2].is_leader = True

        advance_leader(gs)

        # Only the new leader should have is_leader=True
        leader_count = sum(1 for p in gs.players if p.is_leader)
        assert leader_count == 1
        assert gs.players[gs.current_leader].is_leader is True


# ===========================================================================
# 7. initialize_game
# ===========================================================================

class TestInitializeGame:

    def test_fill_bots_reaches_5_players(self):
        gs = GameSession(name="TestSession", players=[Player(name="Human1")])

        initialize_game(gs, fill_bots=True)

        active = [p for p in gs.players if not p.is_spectator]
        assert len(active) == 5

    def test_fill_bots_adds_bot_players(self):
        gs = GameSession(name="TestSession", players=[Player(name="Human1")])

        initialize_game(gs, fill_bots=True)

        bots = [p for p in gs.players if p.is_bot]
        assert len(bots) == 4

    def test_fill_bots_false_does_not_add(self):
        gs = GameSession(
            name="TestSession",
            players=make_players(5),
        )
        original_count = len(gs.players)

        initialize_game(gs, fill_bots=False)

        assert len(gs.players) == original_count

    def test_sets_random_leader(self):
        gs = GameSession(name="TestSession", players=make_players(5))

        initialize_game(gs)

        assert any(p.is_leader for p in gs.players)
        leaders = [p for p in gs.players if p.is_leader]
        assert len(leaders) == 1

    def test_leader_is_active_player(self):
        gs = GameSession(name="TestSession", players=make_players(5))
        gs.players.append(Player(name="Spectator", is_spectator=True))

        initialize_game(gs)

        leader = next(p for p in gs.players if p.is_leader)
        assert not leader.is_spectator

    def test_phase_set_to_team_selection(self):
        gs = GameSession(name="TestSession", players=make_players(5))

        initialize_game(gs)

        assert gs.phase == GamePhase.MISSION_TEAM_SELECTION

    def test_missions_initialized(self):
        gs = GameSession(name="TestSession", players=make_players(5))

        initialize_game(gs)

        assert len(gs.missions) == 5

    def test_roles_assigned(self):
        gs = GameSession(name="TestSession", players=make_players(5))

        initialize_game(gs)

        active = [p for p in gs.players if not p.is_spectator]
        for p in active:
            assert p.role is not None

    def test_does_not_reassign_roles_if_already_set(self):
        players = make_players(5)
        roles = [Role.MERLIN, Role.PERCIVAL, Role.LOYAL_SERVANT, Role.MORGANA, Role.ASSASSIN]
        assign_specific_roles(players, roles)
        gs = GameSession(name="TestSession", players=players)

        initialize_game(gs)

        # Roles should remain exactly as assigned
        for p, r in zip(gs.players, roles):
            assert p.role == r

    def test_lady_of_the_lake_set_for_7_plus_players(self):
        gs = GameSession(
            name="TestSession",
            players=make_players(7),
            lady_of_the_lake_enabled=True,
        )

        initialize_game(gs)

        assert gs.lady_of_the_lake_holder is not None
        holder = next(
            (p for p in gs.players if p.id == gs.lady_of_the_lake_holder), None
        )
        assert holder is not None
        assert holder.lady_of_the_lake is True

    def test_lady_of_the_lake_not_set_for_under_7(self):
        gs = GameSession(
            name="TestSession",
            players=make_players(5),
            lady_of_the_lake_enabled=True,
        )

        initialize_game(gs)

        assert gs.lady_of_the_lake_holder is None

    def test_lady_of_the_lake_not_set_when_disabled(self):
        gs = GameSession(
            name="TestSession",
            players=make_players(7),
            lady_of_the_lake_enabled=False,
        )

        initialize_game(gs)

        assert gs.lady_of_the_lake_holder is None

    def test_lady_of_the_lake_holder_is_leader(self):
        """The LotL holder should be the randomly chosen leader."""
        gs = GameSession(
            name="TestSession",
            players=make_players(7),
            lady_of_the_lake_enabled=True,
        )

        initialize_game(gs)

        leader = next(p for p in gs.players if p.is_leader)
        assert gs.lady_of_the_lake_holder == leader.id

    def test_fill_bots_names_are_unique(self):
        gs = GameSession(name="TestSession", players=[Player(name="Human1")])

        initialize_game(gs, fill_bots=True)

        names = [p.name for p in gs.players]
        assert len(names) == len(set(names))

    def test_fill_bots_not_needed_when_enough_players(self):
        gs = GameSession(name="TestSession", players=make_players(7))

        initialize_game(gs, fill_bots=True)

        # Should still be 7, not padded to anything
        active = [p for p in gs.players if not p.is_spectator]
        assert len(active) == 7
        bots = [p for p in gs.players if p.is_bot]
        assert len(bots) == 0
