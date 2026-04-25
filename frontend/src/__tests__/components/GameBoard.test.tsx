import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GameBoard from "../../components/GameBoard";
import api from "../../api";
import { GameState, GamePhase, Session, Player, Mission, RoleInfo, MissionVotes } from "../../types";

jest.mock("../../api");
const mockedApi = api as jest.Mocked<typeof api>;

jest.mock("../../components/RuleBook", () => {
  return function MockRuleBook() {
    return <div data-testid="rulebook">RuleBook</div>;
  };
});

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
    id: "session-uuid-gameboard",
    name: "Game Board Test",
    code: "GAME01",
    phase: GamePhase.MISSION_TEAM_SELECTION,
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
      makePlayer({ id: "p1", name: "Alice", is_leader: true }),
      makePlayer({ id: "p2", name: "Bob" }),
      makePlayer({ id: "p3", name: "Carol" }),
      makePlayer({ id: "p4", name: "Dave" }),
      makePlayer({ id: "p5", name: "Eve" }),
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

function makeRoleInfo(overrides: Partial<RoleInfo> = {}): RoleInfo {
  return {
    role: "merlin",
    team: "good",
    description: "Knows all evil players",
    sees: [],
    ...overrides,
  };
}

function makeGameState(
  sessionOverrides: Partial<Session> = {},
  missionOverrides: Partial<Mission> = {},
  roleOverrides?: Partial<RoleInfo>
): GameState {
  return {
    type: "game_state",
    session: makeSession(sessionOverrides),
    role_info: roleOverrides !== undefined ? makeRoleInfo(roleOverrides) : makeRoleInfo(),
    current_mission_details: makeMission({ team_size: 2, ...missionOverrides }),
  };
}

describe("GameBoard", () => {
  const defaultProps = {
    playerId: "p1",
    playerToken: "token1",
    isConnected: true,
    onLeave: jest.fn(),
  };

  const mockWriteText = jest.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    jest.clearAllMocks();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: mockWriteText },
      writable: true,
      configurable: true,
    });
  });

  describe("rendering", () => {
    it("renders the session name", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Game Board Test")).toBeInTheDocument();
    });

    it("renders nothing when session/player/playerId/token is null", () => {
      const gameState = { type: "game_state", session: undefined } as any;
      const { container } = render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(container.firstChild).toBeNull();
    });

    it("renders nothing when playerId is null", () => {
      const { container } = render(<GameBoard gameState={makeGameState()} {...defaultProps} playerId={null} />);
      expect(container.firstChild).toBeNull();
    });

    it("shows LIVE when connected", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("LIVE")).toBeInTheDocument();
    });

    it("shows OFFLINE when disconnected", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} isConnected={false} />);
      expect(screen.getByText("OFFLINE")).toBeInTheDocument();
    });

    it("renders Leave button", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Leave")).toBeInTheDocument();
    });

    it("calls onLeave when Leave is clicked", async () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      const user = userEvent.setup();
      await user.click(screen.getByText("Leave"));
      expect(defaultProps.onLeave).toHaveBeenCalled();
    });
  });

  describe("room code display", () => {
    it("displays Session.code in the room button", () => {
      render(<GameBoard gameState={makeGameState({ code: "XYZ99" })} {...defaultProps} />);
      expect(screen.getByText("Room: XYZ99")).toBeInTheDocument();
    });

    it("falls back to session ID first 8 chars when no code", () => {
      render(<GameBoard gameState={makeGameState({ code: null })} {...defaultProps} />);
      expect(screen.getByText("Room: session-")).toBeInTheDocument();
    });

    it("renders the room code in a clickable button", () => {
      render(<GameBoard gameState={makeGameState({ code: "CLIP99" })} {...defaultProps} />);
      const btn = screen.getByText("Room: CLIP99");
      expect(btn.tagName).toBe("BUTTON");
    });
  });

  describe("score display", () => {
    it("shows good and evil win counts", () => {
      render(<GameBoard gameState={makeGameState({ good_wins: 3, evil_wins: 1 })} {...defaultProps} />);
      expect(screen.getAllByText("3").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(1);
    });

    it("shows vote track", () => {
      render(<GameBoard gameState={makeGameState({ vote_track: 3 })} {...defaultProps} />);
      expect(screen.getByText("3/5")).toBeInTheDocument();
    });
  });

  describe("role info display", () => {
    it("shows role name", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Your Role: MERLIN")).toBeInTheDocument();
    });

    it("shows team affiliation", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("GOOD")).toBeInTheDocument();
    });

    it("shows role description", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Knows all evil players")).toBeInTheDocument();
    });

    it("shows visible players when role sees others", () => {
      const gameState = makeGameState({}, {}, {
        role: "merlin",
        team: "good",
        description: "Sees evil",
        sees: [{ name: "Bob", role: "assassin" }, { name: "Carol", role: "morgana" }],
      });
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("You can see:")).toBeInTheDocument();
      expect(screen.getByText("Bob (assassin)")).toBeInTheDocument();
      expect(screen.getByText("Carol (morgana)")).toBeInTheDocument();
    });

    it("shows evil team styling for evil roles", () => {
      const gameState = makeGameState({}, {}, {
        role: "assassin",
        team: "evil",
        description: "Can assassinate Merlin",
        sees: [],
      });
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("EVIL")).toBeInTheDocument();
    });
  });

  describe("missions display", () => {
    it("renders all 5 missions", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Missions")).toBeInTheDocument();
      expect(screen.getByText("Quest 1")).toBeInTheDocument();
      expect(screen.getByText("Quest 2")).toBeInTheDocument();
      expect(screen.getByText("Quest 3")).toBeInTheDocument();
      expect(screen.getByText("Quest 4")).toBeInTheDocument();
      expect(screen.getByText("Quest 5")).toBeInTheDocument();
    });

    it("shows completed mission results", () => {
      const gameState = makeGameState({
        missions: [
          makeMission({ number: 1, result: "success" }),
          makeMission({ number: 2, result: "fail" }),
          makeMission({ number: 3 }),
          makeMission({ number: 4 }),
          makeMission({ number: 5 }),
        ],
      });
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("success")).toBeInTheDocument();
      expect(screen.getByText("fail")).toBeInTheDocument();
    });
  });

  describe("mission team selection phase (uses GamePhase.MISSION_TEAM_SELECTION)", () => {
    it("shows leader info and team size", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_TEAM_SELECTION },
        { team_size: 2 }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText(/must select 2 players/)).toBeInTheDocument();
    });

    it("shows player selection buttons for leader", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_TEAM_SELECTION },
        { team_size: 2 }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      // Leader (p1 = Alice) should see buttons for all non-spectator players
      expect(screen.getByText("Propose Team")).toBeInTheDocument();
    });

    it("Propose Team button is disabled until correct team size is selected", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_TEAM_SELECTION },
        { team_size: 2 }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Propose Team")).toBeDisabled();
    });

    it("does not show selection UI for non-leader", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_TEAM_SELECTION },
        { team_size: 2 }
      );
      // p2 is not the leader
      render(<GameBoard gameState={gameState} {...defaultProps} playerId="p2" />);
      expect(screen.queryByText("Propose Team")).not.toBeInTheDocument();
    });
  });

  describe("mission voting phase (uses GamePhase.MISSION_VOTING)", () => {
    it("shows proposed team and Approve/Reject buttons", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_VOTING },
        { team_members: ["p1", "p2"], votes: {} }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Approve")).toBeInTheDocument();
      expect(screen.getByText("Reject")).toBeInTheDocument();
    });

    it("hides vote buttons after player has voted", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_VOTING },
        { team_members: ["p1", "p2"], votes: { p1: true } }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.queryByText("Approve")).not.toBeInTheDocument();
      expect(screen.queryByText("Reject")).not.toBeInTheDocument();
    });

    it("calls voteTeam API when Approve is clicked", async () => {
      mockedApi.voteTeam.mockResolvedValueOnce({ data: undefined } as any);
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_VOTING },
        { team_members: ["p1", "p2"], votes: {} }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      const user = userEvent.setup();
      await user.click(screen.getByText("Approve"));

      await waitFor(() => {
        expect(mockedApi.voteTeam).toHaveBeenCalledWith("session-uuid-gameboard", "p1", "token1", true);
      });
    });
  });

  describe("vote reveal phase (uses GamePhase.VOTE_REVEAL)", () => {
    it("shows vote results and team approved/rejected", () => {
      const gameState = makeGameState(
        { phase: GamePhase.VOTE_REVEAL },
        { team_members: ["p1", "p2"], votes: { p1: true, p2: true, p3: false, p4: true, p5: false }, team_approved: true }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Team APPROVED")).toBeInTheDocument();
    });

    it("shows Team REJECTED when not approved", () => {
      const gameState = makeGameState(
        { phase: GamePhase.VOTE_REVEAL },
        { team_members: ["p1", "p2"], votes: { p1: false, p2: false, p3: false, p4: true, p5: true }, team_approved: false }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Team REJECTED")).toBeInTheDocument();
    });
  });

  describe("mission execution phase (uses GamePhase.MISSION_EXECUTION)", () => {
    it("shows mission action buttons for team members", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_EXECUTION },
        { team_members: ["p1", "p2"], mission_votes: null }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("You are on this mission! Choose your action:")).toBeInTheDocument();
      expect(screen.getByText("Success")).toBeInTheDocument();
    });

    it("shows Fail button for evil team members", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_EXECUTION },
        { team_members: ["p1", "p2"], mission_votes: null },
        { role: "assassin", team: "evil", description: "Evil", sees: [] }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Fail")).toBeInTheDocument();
    });

    it("does not show Fail button for good team members", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_EXECUTION },
        { team_members: ["p1", "p2"], mission_votes: null },
        { role: "merlin", team: "good", description: "Good", sees: [] }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.queryByText("Fail")).not.toBeInTheDocument();
    });

    it("calls voteMission API when Success is clicked", async () => {
      mockedApi.voteMission.mockResolvedValueOnce({ data: undefined } as any);
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_EXECUTION },
        { team_members: ["p1", "p2"], mission_votes: null }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      const user = userEvent.setup();
      await user.click(screen.getByText("Success"));

      await waitFor(() => {
        expect(mockedApi.voteMission).toHaveBeenCalledWith("session-uuid-gameboard", "p1", "token1", true);
      });
    });

    it("shows vote progress when some votes are in", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_EXECUTION },
        {
          team_members: ["p1", "p2"],
          mission_votes: { total_votes: 1, player_voted: true },
        }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("1 of 2 team members have voted")).toBeInTheDocument();
    });
  });

  describe("mission reveal phase (uses GamePhase.MISSION_REVEAL)", () => {
    it("shows Mission SUCCESS", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_REVEAL },
        {
          result: "success",
          team_members: ["p1", "p2"],
          mission_votes: { total_votes: 2, success_count: 2, fail_count: 0 },
        }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Mission SUCCESS")).toBeInTheDocument();
      expect(screen.getByText("2 success, 0 fail")).toBeInTheDocument();
    });

    it("shows Mission FAILED", () => {
      const gameState = makeGameState(
        { phase: GamePhase.MISSION_REVEAL },
        {
          result: "fail",
          team_members: ["p1", "p2"],
          mission_votes: { total_votes: 2, success_count: 1, fail_count: 1 },
        }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Mission FAILED")).toBeInTheDocument();
      expect(screen.getByText("1 success, 1 fail")).toBeInTheDocument();
    });
  });

  describe("lady of the lake phase (uses GamePhase.LADY_OF_THE_LAKE)", () => {
    it("shows Lady of the Lake UI for holder", () => {
      const gameState = makeGameState({
        phase: GamePhase.LADY_OF_THE_LAKE,
        players: [
          makePlayer({ id: "p1", name: "Alice", lady_of_the_lake: true }),
          makePlayer({ id: "p2", name: "Bob" }),
          makePlayer({ id: "p3", name: "Carol" }),
          makePlayer({ id: "p4", name: "Dave" }),
          makePlayer({ id: "p5", name: "Eve" }),
        ],
      });
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText(/Choose a player to reveal their allegiance/)).toBeInTheDocument();
    });
  });

  describe("assassination phase (uses GamePhase.ASSASSINATION)", () => {
    it("shows assassination UI for assassin", () => {
      const gameState = makeGameState(
        {
          phase: GamePhase.ASSASSINATION,
          players: [
            makePlayer({ id: "p1", name: "Alice" }),
            makePlayer({ id: "p2", name: "Bob" }),
            makePlayer({ id: "p3", name: "Carol" }),
            makePlayer({ id: "p4", name: "Dave" }),
            makePlayer({ id: "p5", name: "Eve" }),
          ],
        },
        {},
        { role: "assassin", team: "evil", description: "Assassin", sees: [] }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText(/you can assassinate Merlin/)).toBeInTheDocument();
    });

    it("shows waiting message for non-assassin", () => {
      const gameState = makeGameState(
        {
          phase: GamePhase.ASSASSINATION,
          players: [
            makePlayer({ id: "p1", name: "Alice" }),
            makePlayer({ id: "p2", name: "Bob" }),
            makePlayer({ id: "p3", name: "Carol" }),
            makePlayer({ id: "p4", name: "Dave" }),
            makePlayer({ id: "p5", name: "Eve" }),
          ],
        },
        {},
        { role: "merlin", team: "good", description: "Merlin", sees: [] }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("The Assassin is choosing their target...")).toBeInTheDocument();
    });
  });

  describe("game end phase (uses GamePhase.GAME_END)", () => {
    it("shows GOOD WINS when good wins", () => {
      const gameState = makeGameState(
        { phase: GamePhase.GAME_END, game_result: "good", game_log: ["Good wins"] },
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("GOOD WINS!")).toBeInTheDocument();
    });

    it("shows EVIL WINS when evil wins", () => {
      const gameState = makeGameState(
        { phase: GamePhase.GAME_END, game_result: "evil", game_log: ["Evil wins"] },
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("EVIL WINS!")).toBeInTheDocument();
    });

    it("shows GAME ENDED when no specific result", () => {
      const gameState = makeGameState(
        { phase: GamePhase.GAME_END, game_result: null, game_log: [] },
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("GAME ENDED")).toBeInTheDocument();
    });

    it("shows player roles", () => {
      const gameState = makeGameState({
        phase: GamePhase.GAME_END,
        game_result: "good",
        game_log: ["Done"],
        players: [
          makePlayer({ id: "p1", name: "Alice", role: "merlin" }),
          makePlayer({ id: "p2", name: "Bob", role: "assassin" }),
          makePlayer({ id: "p3", name: "Carol", role: "loyal_servant" }),
          makePlayer({ id: "p4", name: "Dave", role: "morgana" }),
          makePlayer({ id: "p5", name: "Eve", role: "percival" }),
        ],
      });
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Player Roles:")).toBeInTheDocument();
      expect(screen.getByText("(merlin)")).toBeInTheDocument();
      expect(screen.getByText("(assassin)")).toBeInTheDocument();
    });

    it("shows Restart Game button at game end", () => {
      const gameState = makeGameState({ phase: GamePhase.GAME_END, game_result: "good", game_log: [] });
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Restart Game")).toBeInTheDocument();
    });

    it("calls restartGame API when Restart Game is clicked", async () => {
      mockedApi.restartGame.mockResolvedValueOnce({ data: undefined } as any);
      const gameState = makeGameState({ phase: GamePhase.GAME_END, game_result: "good", game_log: [] });
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      const user = userEvent.setup();
      await user.click(screen.getByText("Restart Game"));

      expect(mockedApi.restartGame).toHaveBeenCalledWith("session-uuid-gameboard");
    });
  });

  describe("controls", () => {
    it("shows Show Vote History button", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Show Vote History")).toBeInTheDocument();
    });

    it("shows Show Game Log button", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Show Game Log")).toBeInTheDocument();
    });

    it("shows End Game button when not at game_end", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("End Game & Reveal Roles")).toBeInTheDocument();
    });

    it("does not show End Game button at game_end", () => {
      const gameState = makeGameState({ phase: GamePhase.GAME_END, game_result: "good", game_log: [] });
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.queryByText("End Game & Reveal Roles")).not.toBeInTheDocument();
    });
  });

  describe("phase display", () => {
    it("displays current phase in header", () => {
      render(<GameBoard gameState={makeGameState({ phase: GamePhase.MISSION_TEAM_SELECTION })} {...defaultProps} />);
      expect(screen.getByText("Phase: MISSION TEAM SELECTION")).toBeInTheDocument();
    });
  });

  describe("player list", () => {
    it("shows all non-spectator players", () => {
      render(<GameBoard gameState={makeGameState()} {...defaultProps} />);
      expect(screen.getByText("Players")).toBeInTheDocument();
      // All 5 players should be listed in the sidebar
      expect(screen.getAllByText("Alice")).toBeTruthy();
      expect(screen.getAllByText("Bob")).toBeTruthy();
    });

    it("shows spectator section if spectators exist", () => {
      const gameState = makeGameState({
        players: [
          makePlayer({ id: "p1", name: "Alice", is_leader: true }),
          makePlayer({ id: "p2", name: "Bob" }),
          makePlayer({ id: "p3", name: "Carol" }),
          makePlayer({ id: "p4", name: "Dave" }),
          makePlayer({ id: "p5", name: "Eve" }),
          makePlayer({ id: "s1", name: "Watcher", is_spectator: true }),
        ],
      });
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Spectators")).toBeInTheDocument();
      expect(screen.getByText("Watcher")).toBeInTheDocument();
    });
  });

  describe("lady of the lake knowledge display", () => {
    it("shows Lady of the Lake knowledge when available", () => {
      const gameState: GameState = {
        ...makeGameState(),
        lady_of_lake_knowledge: [
          { target_name: "Bob", allegiance: "good" },
          { target_name: "Carol", allegiance: "evil" },
        ],
      };
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      expect(screen.getByText("Lady of the Lake Knowledge:")).toBeInTheDocument();
      expect(screen.getByText("Bob: GOOD")).toBeInTheDocument();
      expect(screen.getByText("Carol: EVIL")).toBeInTheDocument();
    });
  });

  describe("error handling", () => {
    it("shows error when API call fails", async () => {
      mockedApi.voteTeam.mockRejectedValueOnce({
        response: { data: { detail: "Already voted" } },
        message: "Bad request",
      });

      const gameState = makeGameState(
        { phase: GamePhase.MISSION_VOTING },
        { team_members: ["p1", "p2"], votes: {} }
      );
      render(<GameBoard gameState={gameState} {...defaultProps} />);
      const user = userEvent.setup();
      await user.click(screen.getByText("Approve"));

      await waitFor(() => {
        expect(screen.getByText("Already voted")).toBeInTheDocument();
      });
    });
  });
});
