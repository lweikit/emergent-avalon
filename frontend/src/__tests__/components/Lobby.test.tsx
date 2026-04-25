import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Lobby from "../../components/Lobby";
import api from "../../api";
import { Session, GamePhase } from "../../types";

jest.mock("../../api");
const mockedApi = api as jest.Mocked<typeof api>;

jest.mock("../../components/RuleBook", () => {
  return function MockRuleBook() {
    return <div data-testid="rulebook">RuleBook</div>;
  };
});

function makeSession(overrides: Partial<Session> = {}): Session {
  return {
    id: "session-uuid-full-length",
    name: "Test Game",
    code: "ABC123",
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
      { id: "p1", name: "Alice", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: false },
      { id: "p2", name: "Bob", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: false },
    ],
    missions: [],
    vote_history: [],
    game_log: [],
    ...overrides,
  };
}

describe("Lobby", () => {
  const defaultProps = {
    playerId: "p1",
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
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText("Test Game")).toBeInTheDocument();
    });

    it("renders waiting message", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText("Waiting for players to join...")).toBeInTheDocument();
    });

    it("renders connection status as LIVE", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText("LIVE")).toBeInTheDocument();
    });

    it("renders connection status as OFFLINE when disconnected", () => {
      render(<Lobby session={makeSession()} {...defaultProps} isConnected={false} />);
      expect(screen.getByText("OFFLINE")).toBeInTheDocument();
    });

    it("renders the Leave button", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText("Leave")).toBeInTheDocument();
    });
  });

  describe("room code display", () => {
    it("displays Session.code when available", () => {
      render(<Lobby session={makeSession({ code: "XYZ789" })} {...defaultProps} />);
      expect(screen.getByText("Room: XYZ789")).toBeInTheDocument();
    });

    it("falls back to first 8 chars of session ID when code is null", () => {
      render(<Lobby session={makeSession({ code: null })} {...defaultProps} />);
      expect(screen.getByText("Room: session-")).toBeInTheDocument();
    });

    it("falls back to first 8 chars of session ID when code is undefined", () => {
      const session = makeSession();
      delete (session as any).code;
      render(<Lobby session={session} {...defaultProps} />);
      expect(screen.getByText("Room: session-")).toBeInTheDocument();
    });

    it("renders the room code in a clickable button", () => {
      render(<Lobby session={makeSession({ code: "COPY123" })} {...defaultProps} />);
      const btn = screen.getByText("Room: COPY123");
      expect(btn.tagName).toBe("BUTTON");
    });
  });

  describe("player list", () => {
    it("displays all active players", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText("Alice")).toBeInTheDocument();
      expect(screen.getByText("Bob")).toBeInTheDocument();
    });

    it("shows active player count", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText("Active Players (2/10)")).toBeInTheDocument();
    });

    it("marks the current player with You badge", () => {
      render(<Lobby session={makeSession()} {...defaultProps} playerId="p1" />);
      expect(screen.getByText("You")).toBeInTheDocument();
    });

    it("shows player online/offline status via dot indicators", () => {
      const session = makeSession({
        players: [
          { id: "p1", name: "Alice", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: false },
          { id: "p2", name: "Bob", role: null, is_leader: false, is_connected: false, lady_of_the_lake: false, is_bot: false, is_spectator: false },
        ],
      });
      const { container } = render(<Lobby session={session} {...defaultProps} />);
      expect(container.querySelector(".bg-green-500")).toBeInTheDocument();
      expect(container.querySelector(".bg-red-500")).toBeInTheDocument();
    });

    it("shows Bot label for bot players", () => {
      const session = makeSession({
        players: [
          { id: "p1", name: "Alice", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: false },
          { id: "p2", name: "BotPlayer", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: true, is_spectator: false },
        ],
      });
      render(<Lobby session={session} {...defaultProps} />);
      expect(screen.getByText("Bot")).toBeInTheDocument();
    });

    it("shows spectators section when spectators exist", () => {
      const session = makeSession({
        players: [
          { id: "p1", name: "Alice", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: false },
          { id: "s1", name: "Viewer", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: true },
        ],
      });
      render(<Lobby session={session} {...defaultProps} />);
      expect(screen.getByText("Spectators (1)")).toBeInTheDocument();
      expect(screen.getByText("Viewer")).toBeInTheDocument();
    });

    it("does not show spectators section when no spectators", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.queryByText(/Spectators/)).not.toBeInTheDocument();
    });
  });

  describe("game settings toggles", () => {
    it("renders Mordred toggle", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText("Mordred")).toBeInTheDocument();
    });

    it("renders Oberon toggle", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText("Oberon")).toBeInTheDocument();
    });

    it("renders Lady of the Lake toggle", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText("Lady of the Lake")).toBeInTheDocument();
    });

    it("shows Mordred as Off when disabled", () => {
      render(<Lobby session={makeSession({ mordred_enabled: false })} {...defaultProps} />);
      // Find the Mordred toggle button specifically
      const mordredSection = screen.getByText("Mordred").closest("div")!.parentElement!;
      expect(mordredSection.querySelector("button")).toHaveTextContent("Off");
    });

    it("shows Mordred as On when enabled", () => {
      render(<Lobby session={makeSession({ mordred_enabled: true })} {...defaultProps} />);
      const mordredSection = screen.getByText("Mordred").closest("div")!.parentElement!;
      expect(mordredSection.querySelector("button")).toHaveTextContent("On");
    });

    it("calls toggleMordred API when clicked", async () => {
      mockedApi.toggleMordred.mockResolvedValueOnce({ data: undefined } as any);
      render(<Lobby session={makeSession({ mordred_enabled: false })} {...defaultProps} />);
      const user = userEvent.setup();

      const mordredSection = screen.getByText("Mordred").closest("div")!.parentElement!;
      const toggleBtn = mordredSection.querySelector("button")!;
      await user.click(toggleBtn);

      await waitFor(() => {
        expect(mockedApi.toggleMordred).toHaveBeenCalledWith("session-uuid-full-length", true);
      });
    });

    it("calls toggleOberon API when clicked", async () => {
      mockedApi.toggleOberon.mockResolvedValueOnce({ data: undefined } as any);
      render(<Lobby session={makeSession({ oberon_enabled: true })} {...defaultProps} />);
      const user = userEvent.setup();

      const oberonSection = screen.getByText("Oberon").closest("div")!.parentElement!;
      const toggleBtn = oberonSection.querySelector("button")!;
      await user.click(toggleBtn);

      await waitFor(() => {
        expect(mockedApi.toggleOberon).toHaveBeenCalledWith("session-uuid-full-length", false);
      });
    });

    it("calls toggleLadyOfLake API when clicked", async () => {
      mockedApi.toggleLadyOfLake.mockResolvedValueOnce({ data: undefined } as any);
      render(<Lobby session={makeSession({ lady_of_the_lake_enabled: false })} {...defaultProps} />);
      const user = userEvent.setup();

      const ladySection = screen.getByText("Lady of the Lake").closest("div")!.parentElement!;
      const toggleBtn = ladySection.querySelector("button")!;
      await user.click(toggleBtn);

      await waitFor(() => {
        expect(mockedApi.toggleLadyOfLake).toHaveBeenCalledWith("session-uuid-full-length", true);
      });
    });
  });

  describe("error banner", () => {
    it("shows error when API call fails", async () => {
      mockedApi.startGame.mockRejectedValueOnce({
        response: { data: { detail: "Not enough players" } },
        message: "Bad request",
      });

      const session = makeSession({
        players: [
          { id: "p1", name: "Alice", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: false },
          { id: "p2", name: "Bob", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: false },
          { id: "p3", name: "Carol", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: false },
          { id: "p4", name: "Dave", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: false },
          { id: "p5", name: "Eve", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: false },
        ],
      });

      render(<Lobby session={session} {...defaultProps} />);
      const user = userEvent.setup();

      await user.click(screen.getByText("Start Game"));

      await waitFor(() => {
        expect(screen.getByText("Not enough players")).toBeInTheDocument();
      });
    });

    it("shows generic error when API response has no detail", async () => {
      mockedApi.toggleMordred.mockRejectedValueOnce({
        message: "Network Error",
      });

      render(<Lobby session={makeSession()} {...defaultProps} />);
      const user = userEvent.setup();

      const mordredSection = screen.getByText("Mordred").closest("div")!.parentElement!;
      await user.click(mordredSection.querySelector("button")!);

      await waitFor(() => {
        expect(screen.getByText("Action failed")).toBeInTheDocument();
      });
    });
  });

  describe("start game buttons", () => {
    it("shows need more players message when < 5 active players", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText(/Need at least 5 players/)).toBeInTheDocument();
    });

    it("shows Start Test Game button when < 5 players", () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      expect(screen.getByText("Start Test Game (adds bots)")).toBeInTheDocument();
    });

    it("shows Start Game button when >= 5 active players", () => {
      const session = makeSession({
        players: Array.from({ length: 5 }, (_, i) => ({
          id: `p${i + 1}`,
          name: `Player${i + 1}`,
          role: null,
          is_leader: false,
          is_connected: true,
          lady_of_the_lake: false,
          is_bot: false,
          is_spectator: false,
        })),
      });
      render(<Lobby session={session} {...defaultProps} />);
      expect(screen.getByText("Start Game")).toBeInTheDocument();
    });

    it("shows spectating message for spectator players", () => {
      const session = makeSession({
        players: [
          { id: "s1", name: "Viewer", role: null, is_leader: false, is_connected: true, lady_of_the_lake: false, is_bot: false, is_spectator: true },
        ],
      });
      render(<Lobby session={session} {...defaultProps} playerId="s1" />);
      expect(screen.getByText("You are spectating. Waiting for players to start...")).toBeInTheDocument();
    });

    it("calls startGame API when Start Game is clicked", async () => {
      mockedApi.startGame.mockResolvedValueOnce({ data: undefined } as any);
      const session = makeSession({
        players: Array.from({ length: 5 }, (_, i) => ({
          id: `p${i + 1}`,
          name: `Player${i + 1}`,
          role: null,
          is_leader: false,
          is_connected: true,
          lady_of_the_lake: false,
          is_bot: false,
          is_spectator: false,
        })),
      });

      render(<Lobby session={session} {...defaultProps} playerId="p1" />);
      const user = userEvent.setup();
      await user.click(screen.getByText("Start Game"));

      await waitFor(() => {
        expect(mockedApi.startGame).toHaveBeenCalledWith("session-uuid-full-length");
      });
    });

    it("calls startTestGame API when Start Test Game is clicked", async () => {
      mockedApi.startTestGame.mockResolvedValueOnce({ data: undefined } as any);

      render(<Lobby session={makeSession()} {...defaultProps} />);
      const user = userEvent.setup();
      await user.click(screen.getByText("Start Test Game (adds bots)"));

      await waitFor(() => {
        expect(mockedApi.startTestGame).toHaveBeenCalledWith("session-uuid-full-length");
      });
    });
  });

  describe("leave button", () => {
    it("calls onLeave when Leave button is clicked", async () => {
      render(<Lobby session={makeSession()} {...defaultProps} />);
      const user = userEvent.setup();
      await user.click(screen.getByText("Leave"));
      expect(defaultProps.onLeave).toHaveBeenCalled();
    });
  });
});
