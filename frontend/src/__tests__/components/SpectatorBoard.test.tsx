import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SpectatorBoard from "../../components/SpectatorBoard";
import { GameState, GamePhase, Session, Player, Mission } from "../../types";

function makePlayer(overrides: Partial<Player> = {}): Player {
  return {
    id: "p1",
    name: "Alice",
    role: null,
    is_leader: false,
    is_connected: true,
    lady_of_the_lake: false,
    is_bot: false,
    is_spectator: false,
    ...overrides,
  };
}

function makeMission(overrides: Partial<Mission> = {}): Mission {
  return {
    number: 1,
    team_size: 2,
    fails_required: 1,
    team_members: [],
    votes: {},
    mission_votes: null,
    result: "pending",
    team_approved: null,
    ...overrides,
  };
}

function makeSession(overrides: Partial<Session> = {}): Session {
  return {
    id: "sess-12345678-full-uuid",
    name: "Spectator Game",
    code: "SPEC01",
    phase: GamePhase.LOBBY,
    current_mission: 0,
    current_leader: 0,
    vote_track: 0,
    good_wins: 0,
    evil_wins: 0,
    game_result: null,
    lady_of_the_lake_enabled: false,
    lady_of_the_lake_previous_holders: [],
    mordred_enabled: false,
    oberon_enabled: false,
    players: [
      makePlayer({ id: "p1", name: "Alice" }),
      makePlayer({ id: "p2", name: "Bob" }),
      makePlayer({ id: "p3", name: "Carol" }),
    ],
    missions: [
      makeMission({ number: 1, team_size: 2 }),
      makeMission({ number: 2, team_size: 3 }),
      makeMission({ number: 3, team_size: 2 }),
      makeMission({ number: 4, team_size: 3 }),
      makeMission({ number: 5, team_size: 3 }),
    ],
    vote_history: [],
    game_log: [],
    ...overrides,
  };
}

function makeGameState(sessionOverrides: Partial<Session> = {}, stateOverrides: Partial<GameState> = {}): GameState {
  return {
    type: "game_state",
    session: makeSession(sessionOverrides),
    ...stateOverrides,
  };
}

describe("SpectatorBoard", () => {
  const defaultProps = {
    isConnected: true,
    onLeave: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("rendering", () => {
    it("renders the session name", () => {
      render(<SpectatorBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Spectator Game")).toBeInTheDocument();
    });

    it("renders nothing when session is null/undefined", () => {
      const gameState = { type: "game_state", session: undefined } as any;
      const { container } = render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(container.firstChild).toBeNull();
    });

    it("shows LIVE when connected", () => {
      render(<SpectatorBoard gameState={makeGameState()} {...defaultProps} isConnected={true} />);
      expect(screen.getByText("LIVE")).toBeInTheDocument();
    });

    it("shows OFFLINE when disconnected", () => {
      render(<SpectatorBoard gameState={makeGameState()} {...defaultProps} isConnected={false} />);
      expect(screen.getByText("OFFLINE")).toBeInTheDocument();
    });

    it("renders EXIT button", () => {
      render(<SpectatorBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("EXIT")).toBeInTheDocument();
    });

    it("calls onLeave when EXIT is clicked", async () => {
      render(<SpectatorBoard gameState={makeGameState()} {...defaultProps} />);
      const user = userEvent.setup();
      await user.click(screen.getByText("EXIT"));
      expect(defaultProps.onLeave).toHaveBeenCalled();
    });
  });

  describe("room code display", () => {
    it("displays Session.code when available", () => {
      render(<SpectatorBoard gameState={makeGameState({ code: "ROOM42" })} {...defaultProps} />);
      expect(screen.getByText("ROOM42")).toBeInTheDocument();
    });

    it("does not display code element when code is null/undefined", () => {
      render(<SpectatorBoard gameState={makeGameState({ code: null })} {...defaultProps} />);
      expect(screen.queryByText("SPEC01")).not.toBeInTheDocument();
    });
  });

  describe("player list", () => {
    it("displays all active players", () => {
      render(<SpectatorBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Alice")).toBeInTheDocument();
      expect(screen.getByText("Bob")).toBeInTheDocument();
      expect(screen.getByText("Carol")).toBeInTheDocument();
    });

    it("shows player count", () => {
      render(<SpectatorBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Players (3)")).toBeInTheDocument();
    });

    it("shows BOT label for bot players", () => {
      const gameState = makeGameState({
        players: [
          makePlayer({ id: "p1", name: "Alice" }),
          makePlayer({ id: "b1", name: "BotPlayer", is_bot: true }),
        ],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("BOT")).toBeInTheDocument();
    });

    it("shows spectators section when spectators exist", () => {
      const gameState = makeGameState({
        players: [
          makePlayer({ id: "p1", name: "Alice" }),
          makePlayer({ id: "s1", name: "Watcher", is_spectator: true }),
        ],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Spectators")).toBeInTheDocument();
      expect(screen.getByText("Watcher")).toBeInTheDocument();
    });
  });

  describe("score display", () => {
    it("shows good and evil win counts", () => {
      render(<SpectatorBoard gameState={makeGameState({ good_wins: 2, evil_wins: 1 })} {...defaultProps} />);
      expect(screen.getAllByText("2").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("phase labels", () => {
    it("shows LOBBY phase label", () => {
      render(<SpectatorBoard gameState={makeGameState({ phase: GamePhase.LOBBY })} {...defaultProps} />);
      expect(screen.getByText("LOBBY")).toBeInTheDocument();
    });

    it("shows TEAM SELECTION phase label", () => {
      const gameState = makeGameState({
        phase: GamePhase.MISSION_TEAM_SELECTION,
        players: [
          makePlayer({ id: "p1", name: "Alice", is_leader: true }),
          makePlayer({ id: "p2", name: "Bob" }),
        ],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("TEAM SELECTION")).toBeInTheDocument();
    });

    it("shows TEAM VOTE phase label", () => {
      const gameState = makeGameState({
        phase: GamePhase.MISSION_VOTING,
        missions: [makeMission({ team_members: ["p1", "p2"] })],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("TEAM VOTE")).toBeInTheDocument();
    });

    it("shows GAME OVER phase label", () => {
      const gameState = makeGameState({
        phase: GamePhase.GAME_END,
        game_result: "good",
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("GAME OVER")).toBeInTheDocument();
    });
  });

  describe("lobby phase display", () => {
    it("shows waiting message and player count", () => {
      render(<SpectatorBoard gameState={makeGameState({ phase: GamePhase.LOBBY })} {...defaultProps} />);
      expect(screen.getByText("Waiting for players...")).toBeInTheDocument();
      expect(screen.getByText("3 players in lobby")).toBeInTheDocument();
    });
  });

  describe("team selection phase", () => {
    it("shows leader name and team size", () => {
      const gameState = makeGameState({
        phase: GamePhase.MISSION_TEAM_SELECTION,
        current_mission: 0,
        players: [
          makePlayer({ id: "p1", name: "Alice", is_leader: true }),
          makePlayer({ id: "p2", name: "Bob" }),
        ],
        missions: [makeMission({ number: 1, team_size: 2 })],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getAllByText("Alice").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("2").length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("mission voting phase", () => {
    it("shows voting message with team names", () => {
      const gameState = makeGameState({
        phase: GamePhase.MISSION_VOTING,
        current_mission: 0,
        players: [
          makePlayer({ id: "p1", name: "Alice" }),
          makePlayer({ id: "p2", name: "Bob" }),
        ],
        missions: [makeMission({ team_members: ["p1", "p2"] })],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText(/Waiting for all players to vote/)).toBeInTheDocument();
    });
  });

  describe("vote reveal phase", () => {
    it("shows vote results for each player", () => {
      const gameState = makeGameState({
        phase: GamePhase.VOTE_REVEAL,
        current_mission: 0,
        players: [
          makePlayer({ id: "p1", name: "Alice" }),
          makePlayer({ id: "p2", name: "Bob" }),
        ],
        missions: [
          makeMission({
            team_members: ["p1", "p2"],
            votes: { p1: true, p2: false },
            team_approved: false,
          }),
        ],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Alice: APPROVE")).toBeInTheDocument();
      expect(screen.getByText("Bob: REJECT")).toBeInTheDocument();
      expect(screen.getByText("Team REJECTED")).toBeInTheDocument();
    });
  });

  describe("mission execution phase", () => {
    it("shows mission team and vote progress", () => {
      const gameState = makeGameState({
        phase: GamePhase.MISSION_EXECUTION,
        current_mission: 0,
        players: [
          makePlayer({ id: "p1", name: "Alice" }),
          makePlayer({ id: "p2", name: "Bob" }),
        ],
        missions: [
          makeMission({
            team_members: ["p1", "p2"],
            mission_votes: { total_votes: 1 },
          }),
        ],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("1/2 votes submitted")).toBeInTheDocument();
    });
  });

  describe("mission reveal phase", () => {
    it("shows SUCCESS result", () => {
      const gameState = makeGameState({
        phase: GamePhase.MISSION_REVEAL,
        current_mission: 0,
        missions: [
          makeMission({
            result: "success",
            mission_votes: { total_votes: 2, success_count: 2, fail_count: 0 },
          }),
        ],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("MISSION SUCCESS")).toBeInTheDocument();
    });

    it("shows FAILED result", () => {
      const gameState = makeGameState({
        phase: GamePhase.MISSION_REVEAL,
        current_mission: 0,
        missions: [
          makeMission({
            result: "fail",
            mission_votes: { total_votes: 3, success_count: 2, fail_count: 1 },
          }),
        ],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("MISSION FAILED")).toBeInTheDocument();
    });
  });

  describe("assassination phase", () => {
    it("shows assassination message", () => {
      const gameState = makeGameState({ phase: GamePhase.ASSASSINATION });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("The Assassin is choosing a target...")).toBeInTheDocument();
      expect(screen.getByText("Good completed 3 missions. Can evil find Merlin?")).toBeInTheDocument();
    });
  });

  describe("lady of the lake phase", () => {
    it("shows Lady of the Lake holder", () => {
      const gameState = makeGameState({
        phase: GamePhase.LADY_OF_THE_LAKE,
        players: [
          makePlayer({ id: "p1", name: "Alice", lady_of_the_lake: true }),
          makePlayer({ id: "p2", name: "Bob" }),
        ],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText(/using the Lady of the Lake/)).toBeInTheDocument();
    });
  });

  describe("game end phase", () => {
    it("shows GOOD WINS when good wins", () => {
      const gameState = makeGameState({
        phase: GamePhase.GAME_END,
        game_result: "good",
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("GOOD WINS!")).toBeInTheDocument();
    });

    it("shows EVIL WINS when evil wins", () => {
      const gameState = makeGameState({
        phase: GamePhase.GAME_END,
        game_result: "evil",
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("EVIL WINS!")).toBeInTheDocument();
    });

    it("shows GAME ENDED when no result", () => {
      const gameState = makeGameState({
        phase: GamePhase.GAME_END,
        game_result: null,
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("GAME ENDED")).toBeInTheDocument();
    });

    it("shows player roles at game end", () => {
      const gameState = makeGameState({
        phase: GamePhase.GAME_END,
        game_result: "good",
        players: [
          makePlayer({ id: "p1", name: "Alice", role: "merlin" }),
          makePlayer({ id: "p2", name: "Bob", role: "assassin" }),
        ],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("MERLIN")).toBeInTheDocument();
      expect(screen.getByText("ASSASSIN")).toBeInTheDocument();
    });

    it("shows game log final entry", () => {
      const gameState = makeGameState({
        phase: GamePhase.GAME_END,
        game_result: "good",
        game_log: ["Mission 1 succeeded", "Mission 2 failed", "Good team wins!"],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getAllByText("Good team wins!").length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("mission cards", () => {
    it("renders all 5 mission cards", () => {
      render(<SpectatorBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("1")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByText("4")).toBeInTheDocument();
      expect(screen.getByText("5")).toBeInTheDocument();
    });

    it("shows SUCCESS/FAIL labels on completed missions", () => {
      const gameState = makeGameState({
        missions: [
          makeMission({ number: 1, result: "success" }),
          makeMission({ number: 2, result: "fail" }),
          makeMission({ number: 3 }),
          makeMission({ number: 4 }),
          makeMission({ number: 5 }),
        ],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("SUCCESS")).toBeInTheDocument();
      expect(screen.getByText("FAIL")).toBeInTheDocument();
    });
  });

  describe("vote track", () => {
    it("shows vote track section", () => {
      render(<SpectatorBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Vote Track")).toBeInTheDocument();
      expect(screen.getByText("5 rejections = Evil wins")).toBeInTheDocument();
    });

    it("shows DANGER label when vote track is >= 4", () => {
      render(<SpectatorBoard gameState={makeGameState({ vote_track: 4 })} {...defaultProps} />);
      expect(screen.getByText("DANGER")).toBeInTheDocument();
    });
  });

  describe("game log", () => {
    it("shows no events message when log is empty", () => {
      render(<SpectatorBoard gameState={makeGameState({ game_log: [] })} {...defaultProps} />);
      expect(screen.getByText("No events yet")).toBeInTheDocument();
    });

    it("shows game log entries when present", () => {
      const gameState = makeGameState({
        game_log: ["Game started", "Mission 1 team proposed"],
      });
      render(<SpectatorBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Game started")).toBeInTheDocument();
      expect(screen.getByText("Mission 1 team proposed")).toBeInTheDocument();
    });
  });
});
